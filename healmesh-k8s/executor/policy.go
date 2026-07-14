package executor

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"k8s.io/client-go/rest"
)

// IsActionAllowedByPolicy checks if the given action is allowed in the namespace
// according to the HealPolicy CRDs. It defaults to fail-closed (false).
func IsActionAllowedByPolicy(restClient rest.Interface, namespace, actionType string) bool {
	// Query all HealPolicies in the namespace
	result := restClient.Get().
		AbsPath(fmt.Sprintf("/apis/healmesh.io/v1alpha1/namespaces/%s/healpolicies", namespace)).
		Do(context.TODO())

	if result.Error() != nil {
		log.Printf("Failed to get HealPolicy in namespace %s: %v. Defaulting to deny.", namespace, result.Error())
		return false
	}

	rawBytes, err := result.Raw()
	if err != nil {
		log.Printf("Failed to read HealPolicy raw bytes in namespace %s: %v. Defaulting to deny.", namespace, err)
		return false
	}

	var policyList HealPolicyList
	if err := json.Unmarshal(rawBytes, &policyList); err != nil {
		log.Printf("Failed to unmarshal HealPolicy in namespace %s: %v. Defaulting to deny.", namespace, err)
		return false
	}

	// If no policies exist, fail closed
	if len(policyList.Items) == 0 {
		log.Printf("No HealPolicy found in namespace %s. Defaulting to deny.", namespace)
		return false
	}

	// For simplicity, we merge allowed actions if multiple policies exist,
	// though typically there should be one or we can just check any of them.
	for _, policy := range policyList.Items {
		for _, allowed := range policy.Spec.AllowedActions {
			if allowed == actionType {
				return true
			}
		}
	}

	log.Printf("Action %s not allowed by HealPolicy in namespace %s. Defaulting to deny.", actionType, namespace)
	return false
}
