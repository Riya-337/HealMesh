package executor

import (
	"context"
	"fmt"
	
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

// Snapshot represents the state of a deployment prior to action.
type Snapshot struct {
	Replicas    int32                `json:"replicas"`
	PodTemplate corev1.PodTemplateSpec `json:"podTemplate"`
}

// TakeSnapshot captures the current replica count of the target deployment.
func TakeSnapshot(client kubernetes.Interface, namespace, name string) (*Snapshot, error) {
	deploy, err := client.AppsV1().Deployments(namespace).Get(context.TODO(), name, metav1.GetOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to get deployment %s/%s for snapshot: %w", namespace, name, err)
	}

	replicas := int32(1)
	if deploy.Spec.Replicas != nil {
		replicas = *deploy.Spec.Replicas
	}

	return &Snapshot{
		Replicas:    replicas,
		PodTemplate: deploy.Spec.Template,
	}, nil
}
