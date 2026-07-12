package executor

import (
	"context"
	"fmt"
	
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
)

// Snapshot represents the state of a deployment prior to action.
type Snapshot struct {
	Replicas int32 `json:"replicas"`
}

// TakeSnapshot captures the current replica count of the target deployment.
func TakeSnapshot(client kubernetes.Interface, namespace, name string) (*Snapshot, error) {
	scale, err := client.AppsV1().Deployments(namespace).GetScale(context.TODO(), name, metav1.GetOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to get scale for deployment %s/%s: %w", namespace, name, err)
	}

	return &Snapshot{
		Replicas: scale.Spec.Replicas,
	}, nil
}
