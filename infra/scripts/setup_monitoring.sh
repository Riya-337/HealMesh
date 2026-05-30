#!/bin/bash

# setup_monitoring.sh
# Installs Prometheus and Grafana into the prism namespace using Helm

set -e

NAMESPACE="prism"

echo "Adding Helm repositories..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

echo "Installing Prometheus..."
helm upgrade --install prometheus prometheus-community/prometheus \
  --namespace $NAMESPACE \
  --set alertmanager.enabled=true \
  --set server.persistentVolume.enabled=true

echo "Installing Grafana..."
helm upgrade --install grafana grafana/grafana \
  --namespace $NAMESPACE \
  --set persistence.enabled=true \
  --set adminPassword="admin"

echo "Monitoring stack installed successfully."
echo "Access Grafana: kubectl port-forward -n $NAMESPACE service/grafana 3000:80"
echo "Username: admin, Password: admin"
