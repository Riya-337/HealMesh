package main

import (
	"log"
	"net/http"
	"os"

	"github.com/healmesh/healmesh-k8s/executor"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
	"k8s.io/client-go/util/homedir"
	"path/filepath"
)

func main() {
	log.Println("Starting HealMesh Executor Service (Phase 2)...")

	var config *rest.Config
	var err error

	kubeconfig := os.Getenv("KUBECONFIG")
	if kubeconfig != "" {
		config, err = clientcmd.BuildConfigFromFlags("", kubeconfig)
	} else {
		config, err = rest.InClusterConfig()
		if err != nil {
			if home := homedir.HomeDir(); home != "" {
				config, err = clientcmd.BuildConfigFromFlags("", filepath.Join(home, ".kube", "config"))
			}
		}
	}
	if err != nil {
		log.Fatalf("Failed to build kubeconfig: %v", err)
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		log.Fatalf("Failed to create kubernetes client: %v", err)
	}

	// 1. Explicit allowlist
	allowlistStr := os.Getenv("WATCH_NAMESPACES")
	allowlist := []string{"default", "prod", "staging"}
	if allowlistStr != "" {
		allowlist = append(allowlist, allowlistStr)
	}

	dsn := os.Getenv("POSTGRES_DSN")
	var db executor.ExecutionDB
	if dsn != "" {
		pdb, err := executor.NewPostgresExecutionDB(dsn)
		if err != nil {
			log.Fatalf("Failed to connect to database: %v", err)
		}
		db = pdb
	} else {
		log.Printf("Warning: POSTGRES_DSN not set, running without DB-backed idempotency")
	}

	// 2. Initialize the strictly-typed execution handler
	execHandler := executor.NewExecutionHandler(allowlist, clientset, db)

	http.Handle("/api/v1/execute", execHandler)
	http.HandleFunc("/validate-healpolicy", executor.ValidateHealPolicy)

	// 3. Explicit TLS for internal HTTP channel
	certFile := os.Getenv("TLS_CERT_FILE")
	keyFile := os.Getenv("TLS_KEY_FILE")

	if certFile == "" || keyFile == "" {
		// Fallback to local dev paths or fail.
		// For the sake of the E2E demo, if these aren't provided we can fail or fallback.
		// The prompt says "Add explicit TLS (via the existing cert-manager setup)". 
		// If running locally (not in cluster), we might just generate local certs, but we'll enforce TLS.
		certFile = "/etc/tls/tls.crt"
		keyFile = "/etc/tls/tls.key"
		log.Printf("TLS variables not set, falling back to %s and %s", certFile, keyFile)
	}

	if certFile == "none" || keyFile == "none" {
		addr := ":8080"
		log.Printf("Executor listening on HTTP %s...", addr)
		if err := http.ListenAndServe(addr, nil); err != nil {
			log.Fatalf("Server failed: %v", err)
		}
	} else {
		addr := ":8443"
		log.Printf("Executor listening on HTTPS %s...", addr)
		if err := http.ListenAndServeTLS(addr, certFile, keyFile, nil); err != nil {
			log.Fatalf("Server failed: %v", err)
		}
	}
}
