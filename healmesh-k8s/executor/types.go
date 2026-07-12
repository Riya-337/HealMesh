package executor

// ScaleParams represents the strictly typed parameters required for a SCALE action.
// It is impossible to pass an arbitrary dict or unvalidated string.
type ScaleParams struct {
	Namespace string `json:"namespace"`
	Name      string `json:"name"`
	Replicas  int32  `json:"replicas"`
}

// ExecutionRequest represents the strict JSON structure the HTTP handler expects.
type ExecutionRequest struct {
	ActionType string      `json:"action_type"`
	Params     ScaleParams `json:"params"`
	ApprovalID string      `json:"approval_id"` // Used as the idempotency key
}

// ExecutionResponse represents the response back to healmesh-core.
type ExecutionResponse struct {
	Status  string `json:"status"`
	Message string `json:"message"`
}
