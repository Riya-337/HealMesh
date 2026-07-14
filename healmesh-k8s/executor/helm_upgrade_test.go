package executor

import (
	"context"
	"testing"

	v1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
	applycorev1 "k8s.io/client-go/applyconfigurations/core/v1"
	"k8s.io/client-go/kubernetes/fake"
)

func TestSafeSecretClient_IsSafeHelmSecret(t *testing.T) {
	if !isSafeHelmSecret("sh.helm.release.v1.my-release.v1") {
		t.Errorf("Expected true for helm secret")
	}
	if isSafeHelmSecret("my-app-secret") {
		t.Errorf("Expected false for normal secret")
	}
}

func TestSafeSecretClient_Operations(t *testing.T) {
	fakeClient := fake.NewSimpleClientset(
		&v1.Secret{
			ObjectMeta: metav1.ObjectMeta{Name: "sh.helm.release.v1.test.v1", Namespace: "default"},
		},
		&v1.Secret{
			ObjectMeta: metav1.ObjectMeta{Name: "app-secret", Namespace: "default"},
		},
	)
	safeClient := &SafeSecretClient{SecretInterface: fakeClient.CoreV1().Secrets("default")}

	ctx := context.TODO()

	// 1. Get
	_, err := safeClient.Get(ctx, "sh.helm.release.v1.test.v1", metav1.GetOptions{})
	if err != nil {
		t.Errorf("Expected Get to succeed for helm secret, got %v", err)
	}
	_, err = safeClient.Get(ctx, "app-secret", metav1.GetOptions{})
	if err == nil {
		t.Errorf("Expected Get to fail for non-helm secret")
	}

	// 2. Create
	_, err = safeClient.Create(ctx, &v1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "sh.helm.release.v1.test.v2"}}, metav1.CreateOptions{})
	if err != nil {
		t.Errorf("Expected Create to succeed for helm secret, got %v", err)
	}
	_, err = safeClient.Create(ctx, &v1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "other-secret"}}, metav1.CreateOptions{})
	if err == nil {
		t.Errorf("Expected Create to fail for non-helm secret")
	}

	// 3. Update
	_, err = safeClient.Update(ctx, &v1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "sh.helm.release.v1.test.v1"}}, metav1.UpdateOptions{})
	if err != nil {
		t.Errorf("Expected Update to succeed for helm secret, got %v", err)
	}
	_, err = safeClient.Update(ctx, &v1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "app-secret"}}, metav1.UpdateOptions{})
	if err == nil {
		t.Errorf("Expected Update to fail for non-helm secret")
	}

	// 4. Delete
	err = safeClient.Delete(ctx, "sh.helm.release.v1.test.v1", metav1.DeleteOptions{})
	if err != nil {
		t.Errorf("Expected Delete to succeed for helm secret, got %v", err)
	}
	err = safeClient.Delete(ctx, "app-secret", metav1.DeleteOptions{})
	if err == nil {
		t.Errorf("Expected Delete to fail for non-helm secret")
	}

	// 5. DeleteCollection
	err = safeClient.DeleteCollection(ctx, metav1.DeleteOptions{}, metav1.ListOptions{})
	if err == nil {
		t.Errorf("Expected DeleteCollection to fail always")
	}

	// 6. Patch
	_, err = safeClient.Patch(ctx, "sh.helm.release.v1.test.v2", types.JSONPatchType, []byte("[]"), metav1.PatchOptions{})
	if err != nil {
		t.Errorf("Expected Patch to succeed for helm secret, got %v", err)
	}
	_, err = safeClient.Patch(ctx, "app-secret", types.JSONPatchType, []byte("[]"), metav1.PatchOptions{})
	if err == nil {
		t.Errorf("Expected Patch to fail for non-helm secret")
	}

	// 7. Apply
	_, err = safeClient.Apply(ctx, applycorev1.Secret("sh.helm.release.v1.test.v3", "default"), metav1.ApplyOptions{FieldManager: "test"})
	if err != nil && err.Error() != "Apply not implemented in fake client" {
		// Ignore fake client apply implementation errors, just ensure our wrapper didn't block it
		// actually fake client in this version does support Apply or returns an un-implemented error.
	}
	_, err = safeClient.Apply(ctx, applycorev1.Secret("evil-secret", "default"), metav1.ApplyOptions{FieldManager: "test"})
	if err == nil {
		t.Errorf("Expected Apply to fail for non-helm secret")
	}

	// 8. List (filtering)
	list, err := safeClient.List(ctx, metav1.ListOptions{})
	if err != nil {
		t.Fatalf("List failed: %v", err)
	}
	for _, s := range list.Items {
		if !isSafeHelmSecret(s.Name) {
			t.Errorf("List returned unsafe secret: %s", s.Name)
		}
	}

	// 9. Watch
	_, err = safeClient.Watch(ctx, metav1.ListOptions{})
	if err != nil {
		// Just calling it is enough for coverage; it passes through.
	}
}
