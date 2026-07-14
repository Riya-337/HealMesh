#!/bin/bash
set -eo pipefail

echo "Generating TLS certs..."
openssl req -x509 -newkey rsa:2048 -keyout tls.key -out tls.crt -days 365 -nodes -subj "/CN=host.docker.internal" -addext "subjectAltName = DNS:host.docker.internal"

echo "Updating webhook.yaml with CABundle..."
CABUNDLE=$(cat tls.crt | base64 | tr -d '\n')
cat infra/k8s/webhook.yaml | sed "s/caBundle: .*/caBundle: $CABUNDLE/g" | sed "s/service:/url: \"https:\/\/host.docker.internal:8443\/validate-healpolicy\"/g" | sed "/name: healmesh-executor/d" | sed "/namespace: healmesh/d" | sed "/path: \"\/validate-healpolicy\"/d" > infra/k8s/webhook-local.yaml

echo "Building executor..."
cd healmesh-k8s
go build -o executor_bin cmd/executor/main.go
cd ..

