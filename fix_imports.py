import re

with open("healmesh-k8s/executor/handler_test.go", "r") as f:
    content = f.read()

# First, strip out the duplicate imports
import_block = """import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	autoscalingv1 "k8s.io/api/autoscaling/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
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
"""

# find first func and replace everything before it with package + imports
idx = content.find("func TestIsNamespaceAllowed")
if idx == -1:
    idx = content.find("func TestIdempotency")

new_content = "package executor\n\n" + import_block + "\n" + content[idx:]

# also fix other tests
new_content = re.sub(r'NewExecutionHandler\(([^,]+), ([^,)]+)\)', r'NewExecutionHandler(\1, \2, nil)', new_content)

with open("healmesh-k8s/executor/handler_test.go", "w") as f:
    f.write(new_content)

with open("healmesh-k8s/executor/error_paths_test.go", "r") as f:
    content = f.read()
content = re.sub(r'NewExecutionHandler\(([^,]+), ([^,)]+)\)', r'NewExecutionHandler(\1, \2, nil)', content)
with open("healmesh-k8s/executor/error_paths_test.go", "w") as f:
    f.write(content)
