package executor

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	autoscalingv1 "k8s.io/api/autoscaling/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"context"
	"time"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/client-go/kubernetes/fake"
	k8stesting "k8s.io/client-go/testing"
)

type MockDB struct {
	locked map[string]bool
}

func (m *MockDB) LockExecution(approvalID string) error {
	if m.locked[approvalID] {
		return fmt.Errorf("already executed")
	}
	m.locked[approvalID] = true
	return nil
}

func (m *MockDB) RecordResult(approvalID string, status string, errMessage string) error {
	return nil
}

func TestIdempotency(t *testing.T) {
	// 1. Setup mock DB and fake client
	mockDB := &MockDB{locked: make(map[string]bool)}
	
	dummyDeploy := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{Name: "test-deploy", Namespace: "default"},
		Spec:       appsv1.DeploymentSpec{Replicas: int32Ptr(1)},
		Status:     appsv1.DeploymentStatus{Replicas: 1, ReadyReplicas: 1},
	}
	client := fake.NewSimpleClientset(dummyDeploy)
	
	patchCallCount := 0
	client.PrependReactor("update", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			patchCallCount++
			scaleAction := action.(k8stesting.UpdateAction)
			return true, scaleAction.GetObject(), nil
		}
		return false, nil, nil
	})
	
	go func() {
		time.Sleep(100 * time.Millisecond)
		deploy, _ := client.AppsV1().Deployments("default").Get(context.TODO(), "test-deploy", metav1.GetOptions{})
		if deploy != nil {
			deploy.Status.Replicas = 3
			deploy.Status.ReadyReplicas = 3
			deploy.Status.UpdatedReplicas = 3
			deploy.Status.Conditions = []appsv1.DeploymentCondition{
				{Type: appsv1.DeploymentAvailable, Status: corev1.ConditionTrue},
			}
			client.AppsV1().Deployments("default").UpdateStatus(context.TODO(), deploy, metav1.UpdateOptions{})
		}
	}()
	client.PrependReactor("get", "deployments", func(action k8stesting.Action) (handled bool, ret runtime.Object, err error) {
		if action.GetSubresource() == "scale" {
			return true, &autoscalingv1.Scale{
				ObjectMeta: metav1.ObjectMeta{Name: "test-deploy", Namespace: "default"},
				Spec:       autoscalingv1.ScaleSpec{Replicas: 1},
			}, nil
		}
		return false, nil, nil
	})

	h := NewExecutionHandler([]string{"default"}, client, mockDB)

	reqBody := ExecutionRequest{
		ActionType: "SCALE",
		Params: ScaleParams{
			Namespace: "default",
			Name:      "test-deploy",
			Replicas:  3,
		},
		ApprovalID: "123e4567-e89b-12d3-a456-426614174000",
	}

	bodyBytes, _ := json.Marshal(reqBody)

	// 2. First call should be processed
	req, _ := http.NewRequest("POST", "/api/v1/execute", bytes.NewBuffer(bodyBytes))
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("First call expected 200 OK, got %d", rr.Code)
	}
	if patchCallCount != 1 {
		t.Errorf("Expected patchCallCount=1, got %d", patchCallCount)
	}

	// 3. Second call with same ApprovalID should return 200 OK without executing again
	req2, _ := http.NewRequest("POST", "/api/v1/execute", bytes.NewBuffer(bodyBytes))
	rr2 := httptest.NewRecorder()
	
	// Temporarily clear the in-memory map to force it to use the DB constraint!
	h.mu.Lock()
	h.processedRequests = make(map[string]bool)
	h.mu.Unlock()

	h.ServeHTTP(rr2, req2)

	if rr2.Code != http.StatusOK {
		t.Errorf("Second call expected 200 OK, got %d", rr2.Code)
	}
	
	// Assert patch was NOT called a second time
	if patchCallCount != 1 {
		t.Errorf("Expected patchCallCount=1 across both requests, got %d", patchCallCount)
	}

	// 5. Test Invalid Namespace
	reqBody.ActionType = "SCALE"
	reqBody.Params.Namespace = "kube-system"
	bodyBytes, _ = json.Marshal(reqBody)
	req4, _ := http.NewRequest("POST", "/api/v1/execute", bytes.NewBuffer(bodyBytes))
	rr4 := httptest.NewRecorder()
	h.ServeHTTP(rr4, req4)
	if rr4.Code != http.StatusForbidden {
		t.Errorf("Forbidden namespace expected 403, got %d", rr4.Code)
	}

	// 6. Test Execution Failure
	reqBody.Params.Namespace = "default"
	reqBody.ApprovalID = "new-approval"
	bodyBytes, _ = json.Marshal(reqBody)
	req5, _ := http.NewRequest("POST", "/api/v1/execute", bytes.NewBuffer(bodyBytes))
	rr5 := httptest.NewRecorder()
	h.executeActionFn = func(req *ExecutionRequest) error {
		return fmt.Errorf("fake error")
	}
	h.ServeHTTP(rr5, req5)
	if rr5.Code != http.StatusInternalServerError {
		t.Errorf("Execution failure expected 500, got %d", rr5.Code)
	}

	// 7. Invalid body
	req6, _ := http.NewRequest("POST", "/api/v1/execute", bytes.NewBuffer([]byte("{bad json")))
	rr6 := httptest.NewRecorder()
	h.ServeHTTP(rr6, req6)
	if rr6.Code != http.StatusBadRequest {
		t.Errorf("Bad JSON expected 400, got %d", rr6.Code)
	}

	// 8. Invalid Method
	req7, _ := http.NewRequest("GET", "/api/v1/execute", nil)
	rr7 := httptest.NewRecorder()
	h.ServeHTTP(rr7, req7)
	if rr7.Code != http.StatusMethodNotAllowed {
		t.Errorf("GET method expected 405, got %d", rr7.Code)
	}
}
