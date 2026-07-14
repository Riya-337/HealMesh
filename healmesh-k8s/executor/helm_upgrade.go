package executor

import (
	"context"
	"fmt"
	"log"
	"strings"

	"helm.sh/helm/v3/pkg/action"
	"helm.sh/helm/v3/pkg/storage"
	"helm.sh/helm/v3/pkg/storage/driver"
	"time"
	v1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/apimachinery/pkg/watch"
	applycorev1 "k8s.io/client-go/applyconfigurations/core/v1"
	"k8s.io/client-go/kubernetes"
	corev1 "k8s.io/client-go/kubernetes/typed/core/v1"
	"k8s.io/cli-runtime/pkg/genericclioptions"
)

// SafeSecretClient wraps corev1.SecretInterface to restrict operations
// ONLY to secrets starting with "sh.helm.release.v1." as a defense-in-depth layer.
type SafeSecretClient struct {
	corev1.SecretInterface
}

func isSafeHelmSecret(name string) bool {
	return strings.HasPrefix(name, "sh.helm.release.v1.")
}

func (s *SafeSecretClient) Create(ctx context.Context, secret *v1.Secret, opts metav1.CreateOptions) (*v1.Secret, error) {
	if !isSafeHelmSecret(secret.Name) {
		return nil, fmt.Errorf("SafeSecretClient: Create operation denied for non-Helm secret %s", secret.Name)
	}
	return s.SecretInterface.Create(ctx, secret, opts)
}

func (s *SafeSecretClient) Update(ctx context.Context, secret *v1.Secret, opts metav1.UpdateOptions) (*v1.Secret, error) {
	if !isSafeHelmSecret(secret.Name) {
		return nil, fmt.Errorf("SafeSecretClient: Update operation denied for non-Helm secret %s", secret.Name)
	}
	return s.SecretInterface.Update(ctx, secret, opts)
}

func (s *SafeSecretClient) Delete(ctx context.Context, name string, opts metav1.DeleteOptions) error {
	if !isSafeHelmSecret(name) {
		return fmt.Errorf("SafeSecretClient: Delete operation denied for non-Helm secret %s", name)
	}
	return s.SecretInterface.Delete(ctx, name, opts)
}

func (s *SafeSecretClient) DeleteCollection(ctx context.Context, opts metav1.DeleteOptions, listOpts metav1.ListOptions) error {
	return fmt.Errorf("SafeSecretClient: DeleteCollection operation is fully denied")
}

func (s *SafeSecretClient) Get(ctx context.Context, name string, opts metav1.GetOptions) (*v1.Secret, error) {
	if !isSafeHelmSecret(name) {
		return nil, fmt.Errorf("SafeSecretClient: Get operation denied for non-Helm secret %s", name)
	}
	return s.SecretInterface.Get(ctx, name, opts)
}

func (s *SafeSecretClient) Patch(ctx context.Context, name string, pt types.PatchType, data []byte, opts metav1.PatchOptions, subresources ...string) (*v1.Secret, error) {
	if !isSafeHelmSecret(name) {
		return nil, fmt.Errorf("SafeSecretClient: Patch operation denied for non-Helm secret %s", name)
	}
	return s.SecretInterface.Patch(ctx, name, pt, data, opts, subresources...)
}

func (s *SafeSecretClient) Apply(ctx context.Context, secret *applycorev1.SecretApplyConfiguration, opts metav1.ApplyOptions) (*v1.Secret, error) {
	if secret.Name != nil && !isSafeHelmSecret(*secret.Name) {
		return nil, fmt.Errorf("SafeSecretClient: Apply operation denied for non-Helm secret %s", *secret.Name)
	}
	return s.SecretInterface.Apply(ctx, secret, opts)
}

func (s *SafeSecretClient) List(ctx context.Context, opts metav1.ListOptions) (*v1.SecretList, error) {
	list, err := s.SecretInterface.List(ctx, opts)
	if err != nil {
		return nil, err
	}
	filtered := []v1.Secret{}
	for _, sec := range list.Items {
		if isSafeHelmSecret(sec.Name) {
			filtered = append(filtered, sec)
		}
	}
	list.Items = filtered
	return list, nil
}

func (s *SafeSecretClient) Watch(ctx context.Context, opts metav1.ListOptions) (watch.Interface, error) {
	return s.SecretInterface.Watch(ctx, opts)
}

// Ensure interface compatibility
var _ corev1.SecretInterface = &SafeSecretClient{}


// ExecuteHelmUpgrade performs a Helm rollback using the official Helm SDK.
func ExecuteHelmUpgrade(k8sClient kubernetes.Interface, namespace, releaseName string, targetRevision int) error {
	// Initialize a standard action configuration.
	flags := genericclioptions.NewConfigFlags(false)
	flags.Namespace = &namespace

	cfg := new(action.Configuration)
	if err := cfg.Init(flags, namespace, "secrets", func(format string, v ...interface{}) {
		log.Printf(format, v...)
	}); err != nil {
		return fmt.Errorf("failed to init helm configuration: %w", err)
	}

	// ---------------------------------------------------------------------
	// Defense-in-depth: Override the storage backend to use our SafeSecretClient.
	// This ensures Helm can only modify `sh.helm.release.v1.*` secrets.
	// ---------------------------------------------------------------------
	safeSecrets := &SafeSecretClient{SecretInterface: k8sClient.CoreV1().Secrets(namespace)}
	cfg.Releases = storage.Init(driver.NewSecrets(safeSecrets))

	client := action.NewRollback(cfg)
	client.Version = targetRevision
	client.Wait = true // Equivalent to --wait
	client.Timeout = 300 * time.Second

	if err := client.Run(releaseName); err != nil {
		return fmt.Errorf("helm rollback failed: %w", err)
	}

	return nil
}
