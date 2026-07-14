package executor

import (
	"fmt"
	"testing"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	autoscalingv1 "k8s.io/api/autoscaling/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	k8stesting "k8s.io/client-go/testing"
	"k8s.io/client-go/kubernetes/fake"
)

func TestErrorPaths(t *testing.T) {
	// Snapshot error
	client1 := fake.NewSimpleClientset()
	client1.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		return true, nil, fmt.Errorf("forced error")
	})
	_, err := TakeSnapshot(client1, "default", "missing")
	if err == nil {
		t.Errorf("Expected error in TakeSnapshot")
	}

	// ExecuteScale errors
	client2 := fake.NewSimpleClientset()
	client2.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		return true, nil, fmt.Errorf("forced get error")
	})
	err = ExecuteScale(client2, "default", "missing", 5)
	if err == nil {
		t.Errorf("Expected error in ExecuteScale get")
	}

	dummyDeploy := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{Name: "missing", Namespace: "default"},
		Spec: appsv1.DeploymentSpec{Replicas: int32Ptr(1)},
		Status: appsv1.DeploymentStatus{Replicas: 1, ReadyReplicas: 1, UpdatedReplicas: 1},
	}

	client3 := fake.NewSimpleClientset(dummyDeploy)
	client3.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			return true, &autoscalingv1.Scale{
				ObjectMeta: metav1.ObjectMeta{Name: "missing", Namespace: "default"},
				Spec:       autoscalingv1.ScaleSpec{Replicas: 1},
			}, nil
		}
		return false, nil, nil
	})
	client3.PrependReactor("update", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			return true, nil, fmt.Errorf("forced update error")
		}
		return false, nil, nil
	})
	err = ExecuteScale(client3, "default", "missing", 5)
	if err == nil {
		t.Errorf("Expected error in ExecuteScale update")
	}

	// ExecuteScale rollback error
	clientRollback := fake.NewSimpleClientset(dummyDeploy)
	clientRollback.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			return true, &autoscalingv1.Scale{
				ObjectMeta: metav1.ObjectMeta{Name: "missing", Namespace: "default"},
				Spec:       autoscalingv1.ScaleSpec{Replicas: 1},
			}, nil
		}
		if action.GetSubresource() == "" {
			return true, nil, fmt.Errorf("forced health check error")
		}
		return false, nil, nil
	})
	clientRollback.PrependReactor("update", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			// fail the rollback update
			return true, nil, fmt.Errorf("forced rollback update error")
		}
		return false, nil, nil
	})
	err = ExecuteScale(clientRollback, "default", "missing", 5)
	if err == nil {
		t.Errorf("Expected error in ExecuteScale with failed rollback")
	}

	// RollbackScale error directly
	client4 := fake.NewSimpleClientset()
	client4.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		return true, nil, fmt.Errorf("forced rollback error")
	})
	err = RollbackScale(client4, "default", "missing", &Snapshot{Replicas: 1})
	if err == nil {
		t.Errorf("Expected error in RollbackScale")
	}

	// HealthCheck progressing error
	client5 := fake.NewSimpleClientset()
	err = WaitForHealthCheck(client5, "default", "missing", 2, 2*time.Second)
	if err == nil {
		t.Errorf("Expected timeout or progressing error in health check")
	}
}
