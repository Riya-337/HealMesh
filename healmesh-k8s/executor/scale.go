package executor

import (
	"context"
	"fmt"
	"log"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	autoscalingv1 "k8s.io/api/autoscaling/v1"
	"k8s.io/client-go/kubernetes"
)

// ExecuteScale takes a snapshot, applies the scale, and runs the health check.
func ExecuteScale(client kubernetes.Interface, namespace, name string, replicas int32) error {
	// 1. Pre-action Snapshot
	snapshot, err := TakeSnapshot(client, namespace, name)
	if err != nil {
		return fmt.Errorf("failed to take snapshot: %w", err)
	}

	log.Printf("Snapshot taken for %s/%s: %d replicas", namespace, name, snapshot.Replicas)

	// 2. Perform the SCALE action via the scale subresource
	scale := &autoscalingv1.Scale{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
		Spec: autoscalingv1.ScaleSpec{
			Replicas: replicas,
		},
	}

	_, err = client.AppsV1().Deployments(namespace).UpdateScale(context.TODO(), name, scale, metav1.UpdateOptions{})
	if err != nil {
		return fmt.Errorf("failed to scale deployment %s/%s to %d: %w", namespace, name, replicas, err)
	}

	log.Printf("Scaled deployment %s/%s to %d replicas", namespace, name, replicas)

	// 3. Post-action Health Check (async or sync). 
	// For simplicity in this demo, we do it synchronously to return final status,
	// but production might prefer async with a status callback.
	err = WaitForHealthCheck(client, namespace, name, replicas)
	if err != nil {
		log.Printf("Health check failed for %s/%s: %v. Initiating rollback...", namespace, name, err)
		rollbackErr := RollbackScale(client, namespace, name, snapshot)
		if rollbackErr != nil {
			return fmt.Errorf("health check failed AND rollback failed: %v (rollback err: %v)", err, rollbackErr)
		}
		return fmt.Errorf("health check failed, successfully rolled back to %d replicas. Error was: %v", snapshot.Replicas, err)
	}

	log.Printf("Health check passed for %s/%s", namespace, name)
	return nil
}

// RollbackScale restores the previous replica count.
func RollbackScale(client kubernetes.Interface, namespace, name string, snapshot *Snapshot) error {
	scale := &autoscalingv1.Scale{
		ObjectMeta: metav1.ObjectMeta{
			Name:      name,
			Namespace: namespace,
		},
		Spec: autoscalingv1.ScaleSpec{
			Replicas: snapshot.Replicas,
		},
	}

	_, err := client.AppsV1().Deployments(namespace).UpdateScale(context.TODO(), name, scale, metav1.UpdateOptions{})
	if err != nil {
		return fmt.Errorf("failed to rollback scale for deployment %s/%s: %w", namespace, name, err)
	}
	return nil
}
