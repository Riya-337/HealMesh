#!/bin/bash
set -eo pipefail

echo "==> Creating kind cluster 'healmesh'..."
kind create cluster --name healmesh || echo "Cluster may already exist."

echo "==> Loading images (if needed)..."
# Assuming docker build was already run or we run it now
# docker build -t healmesh-watcher:latest -f healmesh-k8s/Dockerfile healmesh-k8s/
# kind load docker-image healmesh-watcher:latest --name healmesh

echo "==> Applying Kubernetes configurations..."
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/rbac-watcher.yaml

echo "==> Validating RBAC (Negative test)..."
# Ensure the watcher ServiceAccount cannot create deployments
if kubectl auth can-i create deployments --as=system:serviceaccount:healmesh:healmesh-watcher -n default; then
  echo "ERROR: RBAC violation! watcher can create deployments."
  exit 1
else
  echo "SUCCESS: RBAC correctly restricts watcher from creating deployments."
fi

echo "==> Cluster is ready for Phase 1.5 Integration Testing."
