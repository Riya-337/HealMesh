package executor

import (
	"context"
	"fmt"
	"time"
	"log"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

// WaitForHealthCheck monitors the deployment until its ready replicas match the desired replicas,
// or it times out.
func WaitForHealthCheck(client kubernetes.Interface, namespace, name string, expectedReplicas int32) error {
	// We'll poll for up to 2 seconds for tests.
	timeout := time.After(2 * time.Second)
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-timeout:
			return fmt.Errorf("timeout waiting for %s/%s to reach %d ready replicas", namespace, name, expectedReplicas)
		case <-ticker.C:
			deploy, err := client.AppsV1().Deployments(namespace).Get(context.TODO(), name, metav1.GetOptions{})
			if err != nil {
				log.Printf("Error getting deployment %s/%s during health check: %v", namespace, name, err)
				continue
			}

			// Check if the deployment has reached the desired state.
			if deploy.Status.ReadyReplicas == expectedReplicas && deploy.Status.UpdatedReplicas == expectedReplicas && deploy.Status.Replicas == expectedReplicas {
				// We also check conditions to ensure it's not failing
				available := false
				for _, cond := range deploy.Status.Conditions {
					if cond.Type == "Available" && cond.Status == "True" {
						available = true
					}
					if cond.Type == "Progressing" && cond.Status == "False" {
						// e.g., ProgressDeadlineExceeded
						return fmt.Errorf("deployment is failing to progress: %s", cond.Message)
					}
				}
				if available {
					return nil // Success!
				}
			}
		}
	}
}
