package watcher

import (
	"strings"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
)

// CrashLoopBackOffThreshold is the restart count threshold for detecting crash loops.
const CrashLoopBackOffThreshold = 3

// DetectCrashLoopBackOff checks if a pod's status indicates CrashLoopBackOff.
func DetectCrashLoopBackOff(pod *corev1.Pod) (bool, string) {
	for _, cs := range pod.Status.ContainerStatuses {
		if cs.State.Waiting != nil {
			if cs.State.Waiting.Reason == "CrashLoopBackOff" {
				return true, cs.State.Waiting.Reason
			}
		}
		if cs.RestartCount >= CrashLoopBackOffThreshold {
			return true, "HighRestartCount"
		}
	}
	return false, ""
}

// DetectOOMKilled checks if any container was killed due to OOM.
func DetectOOMKilled(pod *corev1.Pod) (bool, string) {
	for _, cs := range pod.Status.ContainerStatuses {
		if cs.LastTerminationState.Terminated != nil {
			if cs.LastTerminationState.Terminated.Reason == "OOMKilled" {
				return true, "OOMKilled"
			}
		}
		if cs.State.Terminated != nil {
			if cs.State.Terminated.Reason == "OOMKilled" {
				return true, "OOMKilled"
			}
		}
	}
	return false, ""
}

// DetectImagePullBackOff checks if a pod is failing to pull its image.
func DetectImagePullBackOff(pod *corev1.Pod) (bool, string) {
	for _, cs := range pod.Status.ContainerStatuses {
		if cs.State.Waiting != nil {
			reason := cs.State.Waiting.Reason
			if reason == "ImagePullBackOff" || reason == "ErrImagePull" {
				return true, reason
			}
		}
	}
	for _, cs := range pod.Status.InitContainerStatuses {
		if cs.State.Waiting != nil {
			reason := cs.State.Waiting.Reason
			if reason == "ImagePullBackOff" || reason == "ErrImagePull" {
				return true, reason
			}
		}
	}
	return false, ""
}

// DetectFailedRollout checks if a Deployment is in a failed rollout state.
func DetectFailedRollout(deployment *appsv1.Deployment) (bool, string) {
	for _, cond := range deployment.Status.Conditions {
		if cond.Type == appsv1.DeploymentProgressing {
			if cond.Reason == "ProgressDeadlineExceeded" {
				return true, "ProgressDeadlineExceeded"
			}
		}
		if cond.Type == appsv1.DeploymentAvailable && cond.Status == "False" {
			desired := deployment.Spec.Replicas
			if desired != nil && deployment.Status.ReadyReplicas < *desired {
				return true, "ReplicaMismatch"
			}
		}
	}
	return false, ""
}

// DetectResourceQuotaExceeded checks if a Kubernetes Event indicates quota exhaustion.
func DetectResourceQuotaExceeded(event *corev1.Event) (bool, string) {
	if event.Reason == "FailedCreate" || event.Reason == "FailedScheduling" {
		msg := strings.ToLower(event.Message)
		if strings.Contains(msg, "exceeded quota") || strings.Contains(msg, "quota exceeded") ||
			strings.Contains(msg, "resource quota") || strings.Contains(msg, "insufficient") {
			return true, event.Reason
		}
	}
	return false, ""
}

// ExtractContainerStatuses converts K8s container statuses to IncidentPayload format.
func ExtractContainerStatuses(pod *corev1.Pod) []ContainerStatus {
	statuses := make([]ContainerStatus, 0, len(pod.Status.ContainerStatuses))
	for _, cs := range pod.Status.ContainerStatuses {
		cs2 := ContainerStatus{
			Name:         cs.Name,
			Image:        cs.Image,
			RestartCount: cs.RestartCount,
			Ready:        cs.Ready,
		}
		if cs.LastTerminationState.Terminated != nil {
			exitCode := cs.LastTerminationState.Terminated.ExitCode
			reason := cs.LastTerminationState.Terminated.Reason
			cs2.LastExitCode = &exitCode
			cs2.LastTerminationReason = &reason
		}
		statuses = append(statuses, cs2)
	}
	return statuses
}

// ExtractResourceLimits extracts resource limits from the first container.
func ExtractResourceLimits(pod *corev1.Pod) *ResourceLimits {
	if len(pod.Spec.Containers) == 0 {
		return nil
	}
	c := pod.Spec.Containers[0]
	limits := &ResourceLimits{}
	if c.Resources.Requests != nil {
		if cpu, ok := c.Resources.Requests[corev1.ResourceCPU]; ok {
			s := cpu.String()
			limits.CPURequest = &s
		}
		if mem, ok := c.Resources.Requests[corev1.ResourceMemory]; ok {
			s := mem.String()
			limits.MemoryRequest = &s
		}
	}
	if c.Resources.Limits != nil {
		if cpu, ok := c.Resources.Limits[corev1.ResourceCPU]; ok {
			s := cpu.String()
			limits.CPULimit = &s
		}
		if mem, ok := c.Resources.Limits[corev1.ResourceMemory]; ok {
			s := mem.String()
			limits.MemoryLimit = &s
		}
	}
	return limits
}
