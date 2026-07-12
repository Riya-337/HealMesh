package watcher_test

import (
	"strings"
	"testing"

	corev1 "k8s.io/api/core/v1"
	appsv1 "k8s.io/api/apps/v1"

	"github.com/healmesh/healmesh-k8s/watcher"
)

func TestDetectCrashLoopBackOff(t *testing.T) {
	tests := []struct {
		name string
		pod  *corev1.Pod
		want bool
	}{
		{
			name: "detects CrashLoopBackOff reason",
			pod: &corev1.Pod{
				Status: corev1.PodStatus{
					ContainerStatuses: []corev1.ContainerStatus{
						{State: corev1.ContainerState{
							Waiting: &corev1.ContainerStateWaiting{Reason: "CrashLoopBackOff"},
						}},
					},
				},
			},
			want: true,
		},
		{
			name: "detects high restart count",
			pod: &corev1.Pod{
				Status: corev1.PodStatus{
					ContainerStatuses: []corev1.ContainerStatus{
						{RestartCount: watcher.CrashLoopBackOffThreshold},
					},
				},
			},
			want: true,
		},
		{
			name: "does not detect healthy pod",
			pod:  &corev1.Pod{Status: corev1.PodStatus{}},
			want: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, _ := watcher.DetectCrashLoopBackOff(tt.pod)
			if got != tt.want {
				t.Errorf("DetectCrashLoopBackOff() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestDetectOOMKilled(t *testing.T) {
	pod := &corev1.Pod{
		Status: corev1.PodStatus{
			ContainerStatuses: []corev1.ContainerStatus{
				{
					LastTerminationState: corev1.ContainerState{
						Terminated: &corev1.ContainerStateTerminated{Reason: "OOMKilled"},
					},
				},
			},
		},
	}
	if detected, _ := watcher.DetectOOMKilled(pod); !detected {
		t.Error("Expected OOMKilled to be detected")
	}
}

func TestDetectImagePullBackOff(t *testing.T) {
	pod := &corev1.Pod{
		Status: corev1.PodStatus{
			ContainerStatuses: []corev1.ContainerStatus{
				{State: corev1.ContainerState{
					Waiting: &corev1.ContainerStateWaiting{Reason: "ImagePullBackOff"},
				}},
			},
		},
	}
	if detected, _ := watcher.DetectImagePullBackOff(pod); !detected {
		t.Error("Expected ImagePullBackOff to be detected")
	}
}

func TestDetectResourceQuotaExceeded(t *testing.T) {
	event := &corev1.Event{
		Reason:  "FailedCreate",
		Message: "exceeded quota: default, requested: pods=1, used: pods=5, limited: pods=5",
	}
	if detected, _ := watcher.DetectResourceQuotaExceeded(event); !detected {
		t.Error("Expected ResourceQuotaExceeded to be detected")
	}

	// Should NOT detect non-quota event
	other := &corev1.Event{Reason: "Scheduled", Message: "Successfully assigned pod"}
	if detected, _ := watcher.DetectResourceQuotaExceeded(other); detected {
		t.Error("Should not detect non-quota event")
	}
}

func TestSanitizeLogLine(t *testing.T) {
	tests := []struct {
		input        string
		wantRedacted bool
	}{
		{"normal log line", false},
		{"api_key=abc123defghijklmnop", true},
		{"password: mysecretpassword123", true},
		{"postgres://user:pass@host:5432/db", true},
		{"AKIAIOSFODNN7EXAMPLE", true},
	}
	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			result := watcher.SanitizeLogLine(tt.input)
			hasRedacted := strings.Contains(result, "[REDACTED]")
			if hasRedacted != tt.wantRedacted {
				t.Errorf("SanitizeLogLine(%q): wantRedacted=%v, got=%q", tt.input, tt.wantRedacted, result)
			}
		})
	}
}

func TestSanitizeLogLines_Cap(t *testing.T) {
	lines := make([]string, 100)
	for i := range lines {
		lines[i] = "log line"
	}
	result := watcher.SanitizeLogLines(lines)
	if len(result) != watcher.MaxLogLines {
		t.Errorf("Expected %d lines, got %d", watcher.MaxLogLines, len(result))
	}
}

func TestDetectFailedRollout(t *testing.T) {
	desired := int32(3)
	deployment := &appsv1.Deployment{
		Spec: appsv1.DeploymentSpec{Replicas: &desired},
		Status: appsv1.DeploymentStatus{
			ReadyReplicas: 0,
			Conditions: []appsv1.DeploymentCondition{
				{
					Type:   appsv1.DeploymentProgressing,
					Reason: "ProgressDeadlineExceeded",
				},
			},
		},
	}
	if detected, _ := watcher.DetectFailedRollout(deployment); !detected {
		t.Error("Expected FailedRollout to be detected")
	}
}
