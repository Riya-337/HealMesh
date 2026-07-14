package executor

import (
	"encoding/json"
)

// ScaleParams represents the strictly typed parameters required for a SCALE action.
// It is impossible to pass an arbitrary dict or unvalidated string.
type ScaleParams struct {
	Namespace string `json:"namespace"`
	Name      string `json:"name"`
	Replicas  int32  `json:"replicas"`
}

// PatchParams represents the strictly typed parameters required for a PATCH action.
type PatchParams struct {
	Namespace      string                 `json:"namespace"`
	DeploymentName string                 `json:"deployment_name"`
	Image          *string                `json:"image,omitempty"`
	Env            map[string]string      `json:"env,omitempty"`
	Resources      map[string]interface{} `json:"resources,omitempty"`
}

// RedeployParams represents the strictly typed parameters required for a REDEPLOY action.
type RedeployParams struct {
	Namespace      string `json:"namespace"`
	DeploymentName string `json:"deployment_name"`
}

// HelmUpgradeParams represents the strictly typed parameters required for a HELM_UPGRADE action.
type HelmUpgradeParams struct {
	Namespace      string `json:"namespace"`
	ReleaseName    string `json:"release_name"`
	TargetRevision int    `json:"target_revision"`
}

// ExecutionRequest represents the strict JSON structure the HTTP handler expects.
type ExecutionRequest struct {
	ActionType string          `json:"action_type"`
	Params     json.RawMessage `json:"params"`
	ApprovalID string          `json:"approval_id"` // Used as the idempotency key
}

// ExecutionResponse represents the response back to healmesh-core.
type ExecutionResponse struct {
	Status  string `json:"status"`
	Message string `json:"message"`
}

// HealPolicy represents the healpolicies.healmesh.io CRD.
type HealPolicy struct {
	Spec HealPolicySpec `json:"spec"`
}

type HealPolicySpec struct {
	AllowedActions []string `json:"allowedActions"`
}

// HealPolicyList represents a list of HealPolicy resources.
type HealPolicyList struct {
	Items []HealPolicy `json:"items"`
}

