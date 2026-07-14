package executor

import (
	"context"
	"fmt"
	"log"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/client-go/kubernetes"
)

// ExecuteRedeploy executes a REDEPLOY action by injecting a restart annotation.
func ExecuteRedeploy(client kubernetes.Interface, namespace, deploymentName string) error {
	log.Printf("Executing REDEPLOY for deployment %s in namespace %s", deploymentName, namespace)

	deploy, err := client.AppsV1().Deployments(namespace).Get(context.TODO(), deploymentName, metav1.GetOptions{})
	if err != nil {
		return fmt.Errorf("failed to get deployment: %w", err)
	}

	// ADR-006: We do not capture a snapshot because REDEPLOY does not meaningfully modify the spec
	// and will not attempt a rollback on failure.

	patchBytes := []byte(fmt.Sprintf(
		`{"spec":{"template":{"metadata":{"annotations":{"kubectl.kubernetes.io/restartedAt":"%s"}}}}}`,
		time.Now().Format(time.RFC3339),
	))

	log.Printf("Applying REDEPLOY restart annotation to deployment %s", deploymentName)
	_, err = client.AppsV1().Deployments(namespace).Patch(context.TODO(), deploymentName, types.StrategicMergePatchType, patchBytes, metav1.PatchOptions{})
	if err != nil {
		return fmt.Errorf("failed to patch deployment for restart: %w", err)
	}

	// We pass the expected replicas and 0 for the default timeout duration.
	// Note: We use *deploy.Spec.Replicas for expected replicas since redeploy doesn't change it.
	expectedReplicas := int32(1)
	if deploy.Spec.Replicas != nil {
		expectedReplicas = *deploy.Spec.Replicas
	}

	if err := WaitForHealthCheck(client, namespace, deploymentName, expectedReplicas, 0); err != nil {
		// ADR-006: No rollback. Cleanly report failure.
		return fmt.Errorf("health check failed after redeploy, did not resolve the issue: %w", err)
	}

	log.Printf("REDEPLOY completed successfully for %s", deploymentName)
	return nil
}
