package executor

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	admissionv1 "k8s.io/api/admission/v1"
)

func TestValidateHealPolicy(t *testing.T) {
	tests := []struct {
		name        string
		namespace   string
		wantAllowed bool
	}{
		{"allowed in default namespace", "default", true},
		{"allowed in application namespace", "my-app", true},
		{"denied in kube-system", "kube-system", false},
		{"denied in kube-public", "kube-public", false},
		{"denied in kube-node-lease", "kube-node-lease", false},
		{"denied in healmesh", "healmesh", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := admissionv1.AdmissionReview{
				Request: &admissionv1.AdmissionRequest{
					UID:       "test-uid",
					Namespace: tt.namespace,
					Operation: admissionv1.Create,
				},
			}
			reqBody, _ := json.Marshal(req)

			httpReq := httptest.NewRequest(http.MethodPost, "/validate-healpolicy", bytes.NewReader(reqBody))
			httpReq.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()

			ValidateHealPolicy(w, httpReq)

			if w.Code != http.StatusOK {
				t.Fatalf("expected status 200, got %d", w.Code)
			}

			var resp admissionv1.AdmissionReview
			if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
				t.Fatalf("failed to unmarshal response: %v", err)
			}

			if resp.Response == nil {
				t.Fatalf("expected response in admission review, got nil")
			}

			if resp.Response.Allowed != tt.wantAllowed {
				t.Errorf("expected allowed=%v, got %v", tt.wantAllowed, resp.Response.Allowed)
			}
		})
	}
}
