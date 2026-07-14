package executor

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	admissionv1 "k8s.io/api/admission/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// ValidateHealPolicy handles the ValidatingAdmissionWebhook for HealPolicy.
func ValidateHealPolicy(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "could not read body", http.StatusBadRequest)
		return
	}

	var admissionReview admissionv1.AdmissionReview
	if err := json.Unmarshal(body, &admissionReview); err != nil {
		http.Error(w, fmt.Sprintf("could not decode body: %v", err), http.StatusBadRequest)
		return
	}

	req := admissionReview.Request
	if req == nil {
		http.Error(w, "malformed admission review", http.StatusBadRequest)
		return
	}

	admissionResponse := &admissionv1.AdmissionResponse{
		UID:     req.UID,
		Allowed: true,
	}

	namespace := req.Namespace
	// Deny creating HealPolicy in denylisted namespaces
	if namespace == "kube-system" || namespace == "kube-public" || namespace == "healmesh" || strings.HasPrefix(namespace, "kube-") {
		admissionResponse.Allowed = false
		admissionResponse.Result = &metav1.Status{
			Message: fmt.Sprintf("Creation of HealPolicy in denylisted namespace %s is structurally forbidden", namespace),
		}
	}

	admissionReview.Response = admissionResponse

	resp, err := json.Marshal(admissionReview)
	if err != nil {
		http.Error(w, fmt.Sprintf("could not marshal response: %v", err), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Write(resp)
}
