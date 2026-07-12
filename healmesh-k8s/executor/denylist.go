package executor

// Hardcoded denylist for critical namespaces
var hardcodedDenylist = map[string]bool{
	"kube-system": true,
	"kube-public": true,
	"healmesh":    true,
}

// IsNamespaceAllowed checks if the target namespace is allowed to be modified.
// It enforces a hardcoded denylist as a backstop, and requires the namespace 
// to be explicitly listed in the configAllowlist.
func IsNamespaceAllowed(namespace string, configAllowlist []string) bool {
	// 1. Hardcoded denylist enforcement (cannot be overridden by config)
	if hardcodedDenylist[namespace] {
		return false
	}

	// 2. Explicit config allowlist enforcement
	for _, allowed := range configAllowlist {
		if allowed == namespace {
			return true
		}
	}

	return false
}
