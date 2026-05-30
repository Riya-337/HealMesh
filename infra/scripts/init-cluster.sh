#!/bin/bash

# init-cluster.sh
# Master setup script for the PRISM Self-Healing Mesh

set -e

echo "🚀 Initializing PRISM Infrastructure..."

# 1. Create Namespace
echo "Creating namespace 'prism'..."
kubectl apply -f ../k8s/namespace.yaml

# 2. Apply Secrets
# Note: User should fill these in secrets.yaml first
echo "Applying secrets..."
kubectl apply -f ../k8s/secrets.yaml

# 3. Apply Network Policies
echo "Applying network policies..."
kubectl apply -f ../k8s/network-policies.yaml

# 4. Setup Monitoring (Prometheus/Grafana)
echo "Setting up monitoring stack..."
bash ./setup_monitoring.sh

# 5. Install PRISM Stack via Helm
echo "Installing PRISM core components (n8n, OpenClaw, DBs)..."
# We run from the scripts directory, so helm chart is at ../helm/prism
helm upgrade --install prism ../helm/prism --namespace prism

# 6. Apply Grafana Dashboard (if possible via CLI, otherwise manual)
# This is usually done via API or sidecar, but we'll print a reminder
echo "Step 6: Import the Grafana dashboard from ../k8s/monitoring/grafana-dashboard.json"

echo "✅ PRISM Infrastructure is now online!"
echo "Check pods: kubectl get pods -n prism"
