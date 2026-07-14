package executor

import (
	"context"
	"testing"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	autoscalingv1 "k8s.io/api/autoscaling/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	k8stesting "k8s.io/client-go/testing"
	"k8s.io/client-go/kubernetes/fake"
)

func TestTakeSnapshot(t *testing.T) {
	fakeClient := fake.NewSimpleClientset(&appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "test-deploy",
			Namespace: "default",
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(3),
		},
	})
	
	// Add reactor for scale subresource
	fakeClient.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			getAct := action.(k8stesting.GetAction)
			return true, &autoscalingv1.Scale{
				ObjectMeta: metav1.ObjectMeta{Name: getAct.GetName(), Namespace: getAct.GetNamespace()},
				Spec:       autoscalingv1.ScaleSpec{Replicas: 3},
			}, nil
		}
		return false, nil, nil
	})

	snap, err := TakeSnapshot(fakeClient, "default", "test-deploy")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if snap.Replicas != 3 {
		t.Errorf("expected 3 replicas, got %d", snap.Replicas)
	}
}

func init() {
	RolloutTimeout = 1 * time.Second
}

func TestExecuteScaleAndRollback(t *testing.T) {
	fakeClient := fake.NewSimpleClientset(&appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "test-deploy",
			Namespace: "default",
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(2),
		},
		Status: appsv1.DeploymentStatus{
			Replicas:        2,
			ReadyReplicas:   2,
			UpdatedReplicas: 2,
			Conditions: []appsv1.DeploymentCondition{
				{Type: appsv1.DeploymentAvailable, Status: corev1.ConditionTrue},
			},
		},
	})

	var currentReplicas int32 = 2
	fakeClient.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			getAct := action.(k8stesting.GetAction)
			return true, &autoscalingv1.Scale{
				ObjectMeta: metav1.ObjectMeta{Name: getAct.GetName(), Namespace: getAct.GetNamespace()},
				Spec:       autoscalingv1.ScaleSpec{Replicas: currentReplicas},
			}, nil
		}
		return false, nil, nil
	})
	fakeClient.PrependReactor("update", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			updateAct := action.(k8stesting.UpdateAction)
			scale := updateAct.GetObject().(*autoscalingv1.Scale)
			currentReplicas = scale.Spec.Replicas
			return true, scale, nil
		}
		return false, nil, nil
	})

	// To test successful execution, we simulate a fast wait by overriding or running it against a state that's already correct.
	// But `ExecuteScale` expects the new replica count to be satisfied, which our fake client won't automatically do
	// unless we update it in a goroutine.
	go func() {
		time.Sleep(100 * time.Millisecond)
		deploy, _ := fakeClient.AppsV1().Deployments("default").Get(context.TODO(), "test-deploy", metav1.GetOptions{})
		deploy.Status.Replicas = 5
		deploy.Status.ReadyReplicas = 5
		deploy.Status.UpdatedReplicas = 5
		fakeClient.AppsV1().Deployments("default").UpdateStatus(context.TODO(), deploy, metav1.UpdateOptions{})
	}()

	err := ExecuteScale(fakeClient, "default", "test-deploy", 5)
	if err != nil {
		t.Fatalf("expected success, got %v", err)
	}

	scale, _ := fakeClient.AppsV1().Deployments("default").GetScale(context.TODO(), "test-deploy", metav1.GetOptions{})
	if scale.Spec.Replicas != 5 {
		t.Errorf("expected 5 replicas, got %d", scale.Spec.Replicas)
	}

	// Now test rollback manually
	snap := &Snapshot{Replicas: 2}
	err = RollbackScale(fakeClient, "default", "test-deploy", snap)
	if err != nil {
		t.Fatalf("expected success on rollback, got %v", err)
	}

	scale, _ = fakeClient.AppsV1().Deployments("default").GetScale(context.TODO(), "test-deploy", metav1.GetOptions{})
	if scale.Spec.Replicas != 2 {
		t.Errorf("expected 2 replicas after rollback, got %d", scale.Spec.Replicas)
	}
}

func TestExecuteScale_FailureRollback(t *testing.T) {
	oldTimeout := RolloutTimeout
	defer func() { RolloutTimeout = oldTimeout }()
	RolloutTimeout = 500 * time.Millisecond
	fakeClient := fake.NewSimpleClientset(&appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "test-deploy",
			Namespace: "default",
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: int32Ptr(2),
		},
		Status: appsv1.DeploymentStatus{
			Replicas:        2,
			ReadyReplicas:   2,
			UpdatedReplicas: 2,
		},
	})
	
	var currentReplicas int32 = 2
	fakeClient.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			getAct := action.(k8stesting.GetAction)
			return true, &autoscalingv1.Scale{
				ObjectMeta: metav1.ObjectMeta{Name: getAct.GetName(), Namespace: getAct.GetNamespace()},
				Spec:       autoscalingv1.ScaleSpec{Replicas: currentReplicas},
			}, nil
		}
		return false, nil, nil
	})
	fakeClient.PrependReactor("update", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			updateAct := action.(k8stesting.UpdateAction)
			scale := updateAct.GetObject().(*autoscalingv1.Scale)
			currentReplicas = scale.Spec.Replicas
			return true, scale, nil
		}
		return false, nil, nil
	})

	// Do NOT update the status to 5 replicas.
	// We'll simulate a failure to progress immediately.
	go func() {
		time.Sleep(100 * time.Millisecond)
		deploy, _ := fakeClient.AppsV1().Deployments("default").Get(context.TODO(), "test-deploy", metav1.GetOptions{})
		deploy.Status.Conditions = []appsv1.DeploymentCondition{
			{Type: appsv1.DeploymentProgressing, Status: corev1.ConditionFalse, Message: "timeout"},
		}
		fakeClient.AppsV1().Deployments("default").UpdateStatus(context.TODO(), deploy, metav1.UpdateOptions{})
	}()

	err := ExecuteScale(fakeClient, "default", "test-deploy", 5)
	if err == nil {
		t.Fatalf("expected error due to health check failure, got none")
	}

	// Verify it rolled back
	scale, _ := fakeClient.AppsV1().Deployments("default").GetScale(context.TODO(), "test-deploy", metav1.GetOptions{})
	if scale.Spec.Replicas != 2 {
		t.Errorf("expected 2 replicas after automated rollback, got %d", scale.Spec.Replicas)
	}
}

func int32Ptr(i int32) *int32 { return &i }
