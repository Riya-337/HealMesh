package executor

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"k8s.io/client-go/kubernetes"
)

type ExecutionHandler struct {
	configAllowlist   []string
	k8sClient         kubernetes.Interface
	processedRequests map[string]bool
	mu                sync.Mutex
	executeActionFn   func(req *ExecutionRequest) error
	db                ExecutionDB
}

func NewExecutionHandler(configAllowlist []string, k8sClient kubernetes.Interface, db ExecutionDB) *ExecutionHandler {
	h := &ExecutionHandler{
		configAllowlist:   configAllowlist,
		k8sClient:         k8sClient,
		processedRequests: make(map[string]bool),
		db:                db,
	}
	h.executeActionFn = h.executeAction
	return h
}

func (h *ExecutionHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req ExecutionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// 1. Validate action type is supported
	if req.ActionType != "SCALE" {
		http.Error(w, "Unsupported action_type: only SCALE is permitted", http.StatusBadRequest)
		return
	}

	// 2. Validate namespace against denylist and allowlist
	if !IsNamespaceAllowed(req.Params.Namespace, h.configAllowlist) {
		http.Error(w, fmt.Sprintf("Namespace %s is not allowed", req.Params.Namespace), http.StatusForbidden)
		return
	}

	// 3. Idempotency Check using In-Memory Fast Path
	h.mu.Lock()
	if h.processedRequests[req.ApprovalID] {
		h.mu.Unlock()
		log.Printf("Idempotency hit (memory): action for approval_id %s already processed", req.ApprovalID)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(ExecutionResponse{Status: "ok", Message: "Already processed"})
		return
	}
	h.mu.Unlock()

	// 4. Idempotency Check using DB constraint
	if h.db != nil {
		if err := h.db.LockExecution(req.ApprovalID); err != nil {
			if err.Error() == "already executed" {
				log.Printf("Idempotency hit (DB): action for approval_id %s already processed", req.ApprovalID)
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusOK)
				json.NewEncoder(w).Encode(ExecutionResponse{Status: "ok", Message: "Already processed"})
				return
			}
			log.Printf("Failed to lock execution in DB: %v", err)
			http.Error(w, "Failed to lock execution", http.StatusInternalServerError)
			return
		}
	}

	h.mu.Lock()
	h.processedRequests[req.ApprovalID] = true
	h.mu.Unlock()

	// 4. Execute the action
	if err := h.executeActionFn(&req); err != nil {
		// In a real system, we might remove the idempotency key if it was a transient error,
		// but since we want to prevent double-execution even on failures, we leave it.
		log.Printf("Execution failed for %s: %v", req.ApprovalID, err)
		http.Error(w, fmt.Sprintf("Execution failed: %v", err), http.StatusInternalServerError)
		return
	}

	// 5. Respond success
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(ExecutionResponse{Status: "ok", Message: "Execution succeeded"})
}

func (h *ExecutionHandler) executeAction(req *ExecutionRequest) error {
	// Will be implemented in scale.go and snapshot.go
	return ExecuteScale(h.k8sClient, req.Params.Namespace, req.Params.Name, req.Params.Replicas)
}
