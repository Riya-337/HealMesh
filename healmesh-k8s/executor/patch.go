package executor

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/kubernetes"
)

var patchAllowlistValidator = ValidatePatchAllowlist

// ExecutePatch takes a snapshot, constructs the patch from typed params, validates it against the allowlist, applies it, and runs the health check.
func ExecutePatch(client kubernetes.Interface, namespace, name string, params *PatchParams) error {
	// 1. Pre-action Snapshot
	snapshot, err := TakeSnapshot(client, namespace, name)
	if err != nil {
		return fmt.Errorf("failed to take snapshot: %w", err)
	}

	log.Printf("Snapshot taken for %s/%s", namespace, name)

	// Fetch current deployment to know the container name if we want to patch it.
	// For simplicity, we patch the first container if there are multiple.
	deploy, err := client.AppsV1().Deployments(namespace).Get(context.TODO(), name, metav1.GetOptions{})
	if err != nil {
		return fmt.Errorf("failed to get deployment to find container name: %w", err)
	}

	if len(deploy.Spec.Template.Spec.Containers) == 0 {
		return fmt.Errorf("deployment has no containers")
	}

	containerName := deploy.Spec.Template.Spec.Containers[0].Name

	// 2. Construct the patch body
	if params.Image == nil && len(params.Env) == 0 && len(params.Resources) == 0 {
		return fmt.Errorf("patch is empty or out-of-scope fields were dropped")
	}

	containerPatch := map[string]interface{}{
		"name": containerName,
	}

	if params.Image != nil {
		containerPatch["image"] = *params.Image
	}

	if params.Env != nil && len(params.Env) > 0 {
		envList := []interface{}{}
		for k, v := range params.Env {
			envList = append(envList, map[string]interface{}{
				"name":  k,
				"value": v,
			})
		}
		containerPatch["env"] = envList
	}

	if params.Resources != nil && len(params.Resources) > 0 {
		containerPatch["resources"] = params.Resources
	}

	patchBody := map[string]interface{}{
		"spec": map[string]interface{}{
			"template": map[string]interface{}{
				"spec": map[string]interface{}{
					"containers": []interface{}{
						containerPatch,
					},
				},
			},
		},
	}

	// 3. Defense-in-depth: Validate against the Go allowlist
	if err := patchAllowlistValidator(patchBody); err != nil {
		return fmt.Errorf("patch rejected by allowlist validator: %w", err)
	}

	patchBytes, err := json.Marshal(patchBody)
	if err != nil {
		return fmt.Errorf("failed to marshal patch body: %w", err)
	}

	// 4. Perform the PATCH action
	_, err = client.AppsV1().Deployments(namespace).Patch(context.TODO(), name, types.StrategicMergePatchType, patchBytes, metav1.PatchOptions{})
	if err != nil {
		return fmt.Errorf("failed to patch deployment %s/%s: %w", namespace, name, err)
	}

	log.Printf("Patched deployment %s/%s", namespace, name)

	// 5. Post-action Health Check (async or sync).
	err = WaitForHealthCheck(client, namespace, name, snapshot.Replicas, RolloutTimeout) // Reusing replicas since it doesn't change
	if err != nil {
		log.Printf("Health check failed for %s/%s: %v. Initiating rollback...", namespace, name, err)
		rollbackErr := RollbackPatch(client, namespace, name, snapshot)
		if rollbackErr != nil {
			return fmt.Errorf("health check failed AND rollback failed: %v (rollback err: %v)", err, rollbackErr)
		}
		return fmt.Errorf("health check failed, successfully rolled back. Error was: %v", err)
	}

	log.Printf("Health check passed for %s/%s", namespace, name)
	return nil
}

// RollbackPatch restores the previous state using the snapshot.
func RollbackPatch(client kubernetes.Interface, namespace, name string, snapshot *Snapshot) error {
	// In Phase 3 we use StrategicMergePatch with the old pod template spec
	// The Snapshot type only stores Replicas currently. We need to expand Snapshot to include PodTemplateSpec.
	// We will implement that update next.
	
	// For now, assume snapshot holds the full deployment bytes or the pod template.
	patchBytes, err := json.Marshal(map[string]interface{}{
		"spec": map[string]interface{}{
			"template": snapshot.PodTemplate,
		},
	})
	if err != nil {
		return fmt.Errorf("failed to marshal rollback patch: %w", err)
	}
	
	_, err = client.AppsV1().Deployments(namespace).Patch(context.TODO(), name, types.StrategicMergePatchType, patchBytes, metav1.PatchOptions{})
	if err != nil {
		return fmt.Errorf("failed to rollback patch for deployment %s/%s: %w", namespace, name, err)
	}
	return nil
}
