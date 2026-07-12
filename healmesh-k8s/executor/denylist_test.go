package executor

import (
	"testing"
)

func TestIsNamespaceAllowed(t *testing.T) {
	// Setup our config-based allowlist
	configAllowlist := []string{"default", "prod", "staging"}

	tests := []struct {
		name      string
		namespace string
		allowlist []string
		expected  bool
	}{
		// Explicit Denylist Checks (must be rejected regardless of allowlist)
		{"Reject kube-system", "kube-system", configAllowlist, false},
		{"Reject kube-public", "kube-public", configAllowlist, false},
		{"Reject healmesh", "healmesh", configAllowlist, false},
		
		// Allowlist Checks
		{"Allow default", "default", configAllowlist, true},
		{"Allow prod", "prod", configAllowlist, true},
		{"Reject unknown namespace", "unknown", configAllowlist, false},
		
		// Edge case: Denylist namespace in allowlist config (must still reject)
		{"Reject denylisted even if in allowlist", "kube-system", []string{"kube-system", "default"}, false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := IsNamespaceAllowed(tt.namespace, tt.allowlist)
			if result != tt.expected {
				t.Errorf("IsNamespaceAllowed(%s, %v) = %v; want %v", tt.namespace, tt.allowlist, result, tt.expected)
			}
		})
	}
}
