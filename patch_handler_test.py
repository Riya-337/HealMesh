import re

with open("healmesh-k8s/executor/handler_test.go", "r") as f:
    content = f.read()

# Replace NewExecutionHandler(allowlist, client) with NewExecutionHandler(allowlist, client, nil) for other tests
content = re.sub(r'NewExecutionHandler\(([^,]+), ([^)]+)\)', r'NewExecutionHandler(\1, \2, nil)', content)

# But for TestIdempotency, we want a mock DB. We will rewrite it.
# Let's write the mock DB at the top.
mock_db = """
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
"""

content = content.replace("import (", "import (\n\t\"fmt\"\n\t\"k8s.io/client-go/testing\"\n\t\"k8s.io/client-go/kubernetes/fake\"\n\t\"k8s.io/apimachinery/pkg/runtime\"\n\tautoscalingv1 \"k8s.io/api/autoscaling/v1\"\n\tappsv1 \"k8s.io/api/apps/v1\"\n\tmetav1 \"k8s.io/apimachinery/pkg/apis/meta/v1\"\n")
content = content.replace("func TestIsNamespaceAllowed", mock_db + "\nfunc TestIsNamespaceAllowed")

with open("healmesh-k8s/executor/handler_test.go", "w") as f:
    f.write(content)
