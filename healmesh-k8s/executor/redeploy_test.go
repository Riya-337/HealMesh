package executor

import (
	"context"
	"fmt"
	"testing"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/client-go/kubernetes/fake"
	k8stesting "k8s.io/client-go/testing"
)

func TestExecuteRedeploy_Success(t *testing.T) {
	deploy := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{Name: "test-deploy", Namespace: "default", Generation: 1},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(1),
			Template: corev1.PodTemplateSpec{
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{
						{Name: "my-container", Image: "nginx:old"},
					},
				},
			},
		},
		Status: appsv1.DeploymentStatus{
			Replicas:           1,
			ReadyReplicas:      1,
			UpdatedReplicas:    1,
			ObservedGeneration: 1,
			Conditions: []appsv1.DeploymentCondition{
				{Type: appsv1.DeploymentAvailable, Status: corev1.ConditionTrue},
			},
		},
	}

	client := fake.NewSimpleClientset(deploy)

	// Simulate the deployment controller updating status after a patch
	go func() {
		time.Sleep(100 * time.Millisecond)
		d, _ := client.AppsV1().Deployments("default").Get(context.TODO(), "test-deploy", metav1.GetOptions{})
		if d != nil {
			d.Generation = 2
			d.Status.ObservedGeneration = 2
			d.Status.Replicas = 1
			d.Status.ReadyReplicas = 1
			d.Status.UpdatedReplicas = 1
			client.AppsV1().Deployments("default").Update(context.TODO(), d, metav1.UpdateOptions{})
		}
	}()

	err := ExecuteRedeploy(client, "default", "test-deploy")
	if err != nil {
		t.Fatalf("ExecuteRedeploy failed: %v", err)
	}

	// Verify that a patch actually happened
	actions := client.Actions()
	foundPatch := false
	for _, action := range actions {
		if action.GetVerb() == "patch" && action.GetResource().Resource == "deployments" {
			foundPatch = true
			break
		}
	}
	if !foundPatch {
		t.Fatalf("Expected a patch action for redeploy but found none")
	}
}

func TestExecuteRedeploy_ErrorPaths(t *testing.T) {
	deploy := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{Name: "test-deploy", Namespace: "default", Generation: 1},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(1),
			Template: corev1.PodTemplateSpec{
				Spec: corev1.PodSpec{
					Containers: []corev1.Container{{Name: "my-container"}},
				},
			},
		},
		Status: appsv1.DeploymentStatus{Replicas: 1, ReadyReplicas: 1, ObservedGeneration: 1},
	}

	// 1. Get failure
	client1 := fake.NewSimpleClientset()
	client1.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		return true, nil, fmt.Errorf("fake get error")
	})
	err := ExecuteRedeploy(client1, "default", "test-deploy")
	if err == nil {
		t.Errorf("Expected Get error")
	}

	// 2. Patch API failure
	client2 := fake.NewSimpleClientset(deploy)
	client2.PrependReactor("patch", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		return true, nil, fmt.Errorf("fake patch error")
	})
	err = ExecuteRedeploy(client2, "default", "test-deploy")
	if err == nil {
		t.Errorf("Expected patch API error")
	}

	// 3. Health Check failure (no rollback)
	client3 := fake.NewSimpleClientset(deploy)
	// Do not update status, so it times out
	oldTimeout := RolloutTimeout
	defer func() { RolloutTimeout = oldTimeout }()
	RolloutTimeout = 100 * time.Millisecond
	
	err = ExecuteRedeploy(client3, "default", "test-deploy")
	if err == nil {
		t.Errorf("Expected health check error")
	}
	if err != nil && err.Error() == "fake patch error" {
		t.Errorf("Wrong error received")
	}
}
