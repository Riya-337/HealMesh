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

func TestExecutePatch_Success(t *testing.T) {
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

	newImage := "nginx:new"
	params := &PatchParams{
		Namespace:      "default",
		DeploymentName: "test-deploy",
		Image:          &newImage,
		Env:            map[string]string{"FOO": "BAR"},
		Resources: map[string]interface{}{
			"requests": map[string]interface{}{"cpu": "100m"},
		},
	}

	err := ExecutePatch(client, "default", "test-deploy", params)
	if err != nil {
		t.Fatalf("ExecutePatch failed: %v", err)
	}
}

func TestExecutePatch_Rollback(t *testing.T) {
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

	patchCallCount := 0
	client.PrependReactor("patch", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		patchCallCount++
		return false, nil, nil
	})

	// Do not start a goroutine to update the status, so the health check will time out.
	// We'll use a very short timeout for the test to fail quickly, but ExecutePatch hardcodes 2*time.Minute.
	// To speed up the test, we'll patch WaitForHealthCheck to use a shorter timeout if we were able to.
	// Since we can't easily inject a timeout into ExecutePatch without changing its signature again,
	// let's just test RollbackPatch directly.

	snapshot, _ := TakeSnapshot(client, "default", "test-deploy")

	err := RollbackPatch(client, "default", "test-deploy", snapshot)
	if err != nil {
		t.Fatalf("RollbackPatch failed: %v", err)
	}

	if patchCallCount != 1 {
		t.Fatalf("Expected 1 patch call for rollback, got %d", patchCallCount)
	}
}

func TestExecutePatch_ErrorPaths(t *testing.T) {
	newImage := "nginx:new"
	params := &PatchParams{
		Namespace:      "default",
		DeploymentName: "test-deploy",
		Image:          &newImage,
	}

	// 1. Snapshot failure
	client := fake.NewSimpleClientset()
	client.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		return true, nil, fmt.Errorf("fake get error")
	})
	err := ExecutePatch(client, "default", "test-deploy", params)
	if err == nil {
		t.Errorf("Expected snapshot error")
	}

	// 2. Patch API failure
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
	client2 := fake.NewSimpleClientset(deploy)
	client2.PrependReactor("patch", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		return true, nil, fmt.Errorf("fake patch error")
	})
	err = ExecutePatch(client2, "default", "test-deploy", params)
	if err == nil {
		t.Errorf("Expected patch API error")
	}

	// 3. Health Check failure, Rollback success
	client3 := fake.NewSimpleClientset(deploy)
	// Do not update status, so it times out
	oldTimeout := RolloutTimeout
	defer func() { RolloutTimeout = oldTimeout }()
	RolloutTimeout = 100 * time.Millisecond
	err = ExecutePatch(client3, "default", "test-deploy", params)
	if err == nil {
		t.Errorf("Expected health check error")
	}

	// 4. ValidatePatchAllowlist failure (mocked to prove defense-in-depth works)
	originalValidate := patchAllowlistValidator
	defer func() { patchAllowlistValidator = originalValidate }()
	
	patchAllowlistValidator = func(patch map[string]interface{}) error {
		return fmt.Errorf("mocked allowlist rejection")
	}
	
	client4 := fake.NewSimpleClientset(deploy)
	patchCallCount := 0
	client4.PrependReactor("patch", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		patchCallCount++
		return true, nil, nil
	})
	
	err = ExecutePatch(client4, "default", "test-deploy", params)
	if err == nil {
		t.Errorf("Expected ExecutePatch to fail due to mocked allowlist rejection")
	}
	
	if patchCallCount != 0 {
		t.Errorf("Expected 0 patch calls when allowlist rejects, got %d", patchCallCount)
	}
}

func TestExecutePatch_EmptyPatch(t *testing.T) {
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
	client := fake.NewSimpleClientset(deploy)
	
	// Create params with all optional fields nil/empty
	params := &PatchParams{
		Namespace:      "default",
		DeploymentName: "test-deploy",
	}

	err := ExecutePatch(client, "default", "test-deploy", params)
	if err == nil {
		t.Errorf("Expected ExecutePatch to fail when patch is empty")
	}
	if err != nil && err.Error() != "patch is empty or out-of-scope fields were dropped" {
		t.Errorf("Unexpected error message: %v", err)
	}
}
