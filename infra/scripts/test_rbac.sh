#!/bin/bash
echo "Applying RBAC..."
kubectl apply -f infra/k8s/executor-rbac.yaml
echo "--- Testing RBAC against system:serviceaccount:default:healmesh-executor ---"
echo "Expected YES:"
kubectl auth can-i patch deployments/scale --as=system:serviceaccount:healmesh:healmesh-executor -n default
echo "Expected NO:"
kubectl auth can-i delete deployments --as=system:serviceaccount:healmesh:healmesh-executor -n default
kubectl auth can-i create deployments --as=system:serviceaccount:healmesh:healmesh-executor -n default
kubectl auth can-i update deployments --as=system:serviceaccount:healmesh:healmesh-executor -n default
kubectl auth can-i patch deployments --as=system:serviceaccount:healmesh:healmesh-executor -n default
kubectl auth can-i delete pods --as=system:serviceaccount:healmesh:healmesh-executor -n default
