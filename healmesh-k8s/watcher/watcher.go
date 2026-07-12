// Package watcher implements the HealMesh Kubernetes Event Watcher.
//
// INVARIANT: This package is read-only.
// RBAC: get, list, watch on pods, deployments, events ONLY.
// No patch, update, delete, create, or exec permissions used.
package watcher

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/watch"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"

	"go.uber.org/zap"
)

// Watcher watches a Kubernetes namespace for the 5 canonical failure types.
type Watcher struct {
	clientset  kubernetes.Interface
	coreClient *CoreClient
	namespaces []string
	logger     *zap.Logger
}

// NewWatcher creates a Watcher. Uses in-cluster config if KUBECONFIG_PATH is not set.
func NewWatcher(logger *zap.Logger) (*Watcher, error) {
	var config *rest.Config
	var err error

	kubeconfigPath := os.Getenv("KUBECONFIG_PATH")
	if kubeconfigPath != "" {
		config, err = clientcmd.BuildConfigFromFlags("", kubeconfigPath)
	} else {
		config, err = rest.InClusterConfig()
	}
	if err != nil {
		return nil, fmt.Errorf("failed to build kubernetes config: %w", err)
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create kubernetes clientset: %w", err)
	}

	nsEnv := os.Getenv("WATCH_NAMESPACES")
	namespaces := []string{"default"}
	if nsEnv != "" {
		namespaces = strings.Split(nsEnv, ",")
	}

	return &Watcher{
		clientset:  clientset,
		coreClient: NewCoreClient(logger),
		namespaces: namespaces,
		logger:     logger,
	}, nil
}

// Run starts watching all configured namespaces. Blocks until context is cancelled.
func (w *Watcher) Run(ctx context.Context) error {
	w.logger.Info("Starting HealMesh watcher", zap.Strings("namespaces", w.namespaces))
	for _, ns := range w.namespaces {
		ns := ns
		go w.watchPods(ctx, ns)
		go w.watchDeployments(ctx, ns)
		go w.watchEvents(ctx, ns)
	}
	<-ctx.Done()
	w.logger.Info("Watcher shutting down")
	return nil
}

func (w *Watcher) watchPods(ctx context.Context, namespace string) {
	w.logger.Info("Watching pods", zap.String("namespace", namespace))
	for {
		if ctx.Err() != nil {
			return
		}
		watcher, err := w.clientset.CoreV1().Pods(namespace).Watch(ctx, metav1.ListOptions{})
		if err != nil {
			w.logger.Error("Failed to watch pods", zap.String("namespace", namespace), zap.Error(err))
			time.Sleep(5 * time.Second)
			continue
		}
		w.processPodEvents(ctx, watcher, namespace)
	}
}

func (w *Watcher) processPodEvents(ctx context.Context, watcher watch.Interface, namespace string) {
	defer watcher.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case event, ok := <-watcher.ResultChan():
			if !ok {
				w.logger.Warn("Pod watch channel closed, restarting", zap.String("namespace", namespace))
				return
			}
			if event.Type != watch.Modified && event.Type != watch.Added {
				continue
			}
			pod, ok := event.Object.(*corev1.Pod)
			if !ok {
				continue
			}
			w.checkPodFailures(ctx, pod)
		}
	}
}

func (w *Watcher) checkPodFailures(ctx context.Context, pod *corev1.Pod) {
	if detected, _ := DetectCrashLoopBackOff(pod); detected {
		w.sendPodIncident(ctx, pod, CrashLoopBackOff)
		return
	}
	if detected, _ := DetectOOMKilled(pod); detected {
		w.sendPodIncident(ctx, pod, OOMKilled)
		return
	}
	if detected, _ := DetectImagePullBackOff(pod); detected {
		w.sendPodIncident(ctx, pod, ImagePullBackOff)
		return
	}
}

func (w *Watcher) sendPodIncident(ctx context.Context, pod *corev1.Pod, ft FailureType) {
	logLines := w.fetchPodLogs(ctx, pod)
	payload := &IncidentPayload{
		IncidentID:        NewIncidentID(),
		PodName:           pod.Name,
		Namespace:         pod.Namespace,
		FailureType:       ft,
		DetectedAt:        time.Now().UTC(),
		ContainerStatuses: ExtractContainerStatuses(pod),
		LogLines:          logLines,
		ResourceLimits:    ExtractResourceLimits(pod),
	}
	if len(pod.Spec.Containers) > 0 {
		image := pod.Spec.Containers[0].Image
		pullPolicy := string(pod.Spec.Containers[0].ImagePullPolicy)
		payload.Image = &image
		payload.ImagePullPolicy = &pullPolicy
	}
	if err := w.coreClient.SendIncident(ctx, payload); err != nil {
		w.logger.Error("Failed to send incident",
			zap.String("pod", pod.Name),
			zap.String("namespace", pod.Namespace),
			zap.String("failure_type", string(ft)),
			zap.Error(err),
		)
	}
}

func (w *Watcher) fetchPodLogs(ctx context.Context, pod *corev1.Pod) []string {
	if len(pod.Spec.Containers) == 0 {
		return nil
	}
	tailLines := int64(MaxLogLines)
	logs, err := w.clientset.CoreV1().Pods(pod.Namespace).GetLogs(pod.Name, &corev1.PodLogOptions{
		Container: pod.Spec.Containers[0].Name,
		TailLines: &tailLines,
	}).DoRaw(ctx)
	if err != nil {
		w.logger.Warn("Failed to fetch pod logs", zap.String("pod", pod.Name), zap.Error(err))
		return nil
	}
	rawLines := strings.Split(string(logs), "\n")
	return SanitizeLogLines(rawLines)
}

func (w *Watcher) watchDeployments(ctx context.Context, namespace string) {
	w.logger.Info("Watching deployments", zap.String("namespace", namespace))
	for {
		if ctx.Err() != nil {
			return
		}
		watcher, err := w.clientset.AppsV1().Deployments(namespace).Watch(ctx, metav1.ListOptions{})
		if err != nil {
			w.logger.Error("Failed to watch deployments", zap.Error(err))
			time.Sleep(5 * time.Second)
			continue
		}
		w.processDeploymentEvents(ctx, watcher)
	}
}

func (w *Watcher) processDeploymentEvents(ctx context.Context, watcher watch.Interface) {
	defer watcher.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case event, ok := <-watcher.ResultChan():
			if !ok {
				return
			}
			if event.Type != watch.Modified {
				continue
			}
			deployment, ok := event.Object.(*appsv1.Deployment)
			if !ok {
				continue
			}
			if detected, _ := DetectFailedRollout(deployment); detected {
				w.sendDeploymentIncident(ctx, deployment)
			}
		}
	}
}

func (w *Watcher) sendDeploymentIncident(ctx context.Context, deployment *appsv1.Deployment) {
	name := deployment.Name
	ready := deployment.Status.ReadyReplicas
	payload := &IncidentPayload{
		IncidentID:     NewIncidentID(),
		PodName:        fmt.Sprintf("%s (deployment)", name),
		Namespace:      deployment.Namespace,
		FailureType:    FailedRollout,
		DetectedAt:     time.Now().UTC(),
		DeploymentName: &name,
		ReadyReplicas:  &ready,
	}
	if deployment.Spec.Replicas != nil {
		payload.DesiredReplicas = deployment.Spec.Replicas
	}
	if err := w.coreClient.SendIncident(ctx, payload); err != nil {
		w.logger.Error("Failed to send deployment incident", zap.String("deployment", name), zap.Error(err))
	}
}

func (w *Watcher) watchEvents(ctx context.Context, namespace string) {
	w.logger.Info("Watching events", zap.String("namespace", namespace))
	for {
		if ctx.Err() != nil {
			return
		}
		watcher, err := w.clientset.CoreV1().Events(namespace).Watch(ctx, metav1.ListOptions{})
		if err != nil {
			w.logger.Error("Failed to watch events", zap.Error(err))
			time.Sleep(5 * time.Second)
			continue
		}
		w.processEventWatch(ctx, watcher)
	}
}

func (w *Watcher) processEventWatch(ctx context.Context, watcher watch.Interface) {
	defer watcher.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case event, ok := <-watcher.ResultChan():
			if !ok {
				return
			}
			if event.Type != watch.Added {
				continue
			}
			k8sEvent, ok := event.Object.(*corev1.Event)
			if !ok {
				continue
			}
			if detected, _ := DetectResourceQuotaExceeded(k8sEvent); detected {
				w.sendQuotaIncident(ctx, k8sEvent)
			}
		}
	}
}

func (w *Watcher) sendQuotaIncident(ctx context.Context, event *corev1.Event) {
	resource, limit, used := ParseQuotaMessage(event.Message)
	payload := &IncidentPayload{
		IncidentID:    NewIncidentID(),
		PodName:       event.InvolvedObject.Name,
		Namespace:     event.Namespace,
		FailureType:   ResourceQuotaExceeded,
		DetectedAt:    time.Now().UTC(),
		QuotaResource: &resource,
		QuotaLimit:    &limit,
		QuotaUsed:     &used,
	}
	if err := w.coreClient.SendIncident(ctx, payload); err != nil {
		w.logger.Error("Failed to send quota incident", zap.Error(err))
	}
}
