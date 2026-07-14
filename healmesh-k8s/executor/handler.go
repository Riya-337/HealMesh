package executor

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"
	"k8s.io/client-go/kubernetes"
)

type ExecutionHandler struct {
	configAllowlist   []string
	k8sClient         kubernetes.Interface
	processedRequests map[string]bool
	mu                sync.Mutex
	
	rateLimitGlobalMax    int
	rateLimitNamespaceMax int
	rateLimitWindow       time.Duration
	globalExecutions      []time.Time
	namespaceExecutions   map[string][]time.Time
	rateLimitMu           sync.Mutex

	executeActionFn   func(req *ExecutionRequest) error
	db                ExecutionDB
}

func NewExecutionHandler(configAllowlist []string, k8sClient kubernetes.Interface, db ExecutionDB) *ExecutionHandler {
	h := &ExecutionHandler{
		configAllowlist:       configAllowlist,
		k8sClient:             k8sClient,
		processedRequests:     make(map[string]bool),
		db:                    db,
		rateLimitGlobalMax:    10,
		rateLimitNamespaceMax: 5,
		rateLimitWindow:       60 * time.Second,
		globalExecutions:      make([]time.Time, 0),
		namespaceExecutions:   make(map[string][]time.Time),
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

	// 1. Validate action type is supported and extract namespace
	var namespace string
	switch req.ActionType {
	case "SCALE":
		var p ScaleParams
		if err := json.Unmarshal(req.Params, &p); err != nil {
			http.Error(w, "Invalid SCALE params", http.StatusBadRequest)
			return
		}
		namespace = p.Namespace
	case "PATCH":
		var p PatchParams
		if err := json.Unmarshal(req.Params, &p); err != nil {
			http.Error(w, "Invalid PATCH params", http.StatusBadRequest)
			return
		}
		namespace = p.Namespace
	case "REDEPLOY":
		var p RedeployParams
		if err := json.Unmarshal(req.Params, &p); err != nil {
			http.Error(w, "Invalid REDEPLOY params", http.StatusBadRequest)
			return
		}
		namespace = p.Namespace
	case "HELM_UPGRADE":
		var p HelmUpgradeParams
		if err := json.Unmarshal(req.Params, &p); err != nil {
			http.Error(w, "Invalid HELM_UPGRADE params", http.StatusBadRequest)
			return
		}
		namespace = p.Namespace
	default:
		http.Error(w, "Unsupported action_type", http.StatusBadRequest)
		return
	}

	// 2. Validate namespace against denylist and allowlist
	if !IsNamespaceAllowed(namespace, h.configAllowlist) {
		http.Error(w, fmt.Sprintf("Namespace %s is not allowed", namespace), http.StatusForbidden)
		return
	}

	// 2.1. Validate action is allowed by HealPolicy in the namespace
	if !IsActionAllowedByPolicy(h.k8sClient.CoreV1().RESTClient(), namespace, req.ActionType) {
		if h.db != nil {
			h.db.RecordResult(req.ApprovalID, "failed", "action denied by HealPolicy")
		}
		http.Error(w, fmt.Sprintf("Action %s is denied by HealPolicy in namespace %s", req.ActionType, namespace), http.StatusForbidden)
		return
	}

	// 2.5. Rate Limiting Check
	now := time.Now()
	cutoff := now.Add(-h.rateLimitWindow)

	h.rateLimitMu.Lock()
	// Cleanup global executions
	var validGlobal []time.Time
	for _, t := range h.globalExecutions {
		if t.After(cutoff) {
			validGlobal = append(validGlobal, t)
		}
	}
	h.globalExecutions = validGlobal

	// Cleanup namespace executions
	var validNs []time.Time
	for _, t := range h.namespaceExecutions[namespace] {
		if t.After(cutoff) {
			validNs = append(validNs, t)
		}
	}
	h.namespaceExecutions[namespace] = validNs

	// Check thresholds
	if len(h.globalExecutions) >= h.rateLimitGlobalMax {
		h.rateLimitMu.Unlock()
		if h.db != nil {
			h.db.RecordResult(req.ApprovalID, "failed", "rate limit exceeded")
		}
		http.Error(w, "Rate limit exceeded (global)", http.StatusTooManyRequests)
		return
	}
	if len(h.namespaceExecutions[namespace]) >= h.rateLimitNamespaceMax {
		h.rateLimitMu.Unlock()
		if h.db != nil {
			h.db.RecordResult(req.ApprovalID, "failed", "rate limit exceeded")
		}
		http.Error(w, "Rate limit exceeded (namespace)", http.StatusTooManyRequests)
		return
	}

	// Record execution
	h.globalExecutions = append(h.globalExecutions, now)
	h.namespaceExecutions[namespace] = append(h.namespaceExecutions[namespace], now)
	h.rateLimitMu.Unlock()

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
	switch req.ActionType {
	case "SCALE":
		var p ScaleParams
		json.Unmarshal(req.Params, &p)
		return ExecuteScale(h.k8sClient, p.Namespace, p.Name, p.Replicas)
	case "PATCH":
		var p PatchParams
		json.Unmarshal(req.Params, &p)
		return ExecutePatch(h.k8sClient, p.Namespace, p.DeploymentName, &p)
	case "REDEPLOY":
		var p RedeployParams
		json.Unmarshal(req.Params, &p)
		return ExecuteRedeploy(h.k8sClient, p.Namespace, p.DeploymentName)
	case "HELM_UPGRADE":
		var p HelmUpgradeParams
		json.Unmarshal(req.Params, &p)
		// We pass h.k8sClient so that ExecuteHelmUpgrade can build the SafeSecretClient
		return ExecuteHelmUpgrade(h.k8sClient, p.Namespace, p.ReleaseName, p.TargetRevision)
	default:
		return fmt.Errorf("unsupported action_type: %s", req.ActionType)
	}
}
