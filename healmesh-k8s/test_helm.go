package main

import (
	"fmt"
	"helm.sh/helm/v3/pkg/storage/driver"
	corev1 "k8s.io/client-go/kubernetes/typed/core/v1"
)

func main() {
	var s corev1.SecretInterface
	d := driver.NewSecrets(s)
	fmt.Printf("%T\n", d)
}
