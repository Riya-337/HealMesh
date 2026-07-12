#!/usr/bin/env bash
# HealMesh — Failure Injection Script for testing
# ONLY run against kind/minikube or other test clusters. NEVER production.

set -euo pipefail

FAILURE_TYPES=(CrashLoopBackOff OOMKilled ImagePullBackOff FailedRollout ResourceQuotaExceeded)
NAMESPACE=${2:-healmesh-test}

if [ $# -lt 1 ]; then
    echo "Usage: $0 <failure-type> [namespace]"
    echo "Failure types: ${FAILURE_TYPES[*]}"
    exit 1
fi

FAILURE_TYPE=$1
echo "[inject_failure] Injecting ${FAILURE_TYPE} into namespace ${NAMESPACE}"
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

case "${FAILURE_TYPE}" in
    CrashLoopBackOff)
        kubectl run healmesh-crash-test --image=busybox --restart=Always \
            --namespace="${NAMESPACE}" -- sh -c 'echo crashing; exit 1'
        ;;
    OOMKilled)
        cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: healmesh-oom-test
  namespace: ${NAMESPACE}
spec:
  containers:
  - name: stress
    image: polinux/stress
    args:
    - stress
    - --vm
    - "1"
    - --vm-bytes
    - 50M
    - --timeout
    - 30s
    resources:
      limits:
        memory: 10Mi
  restartPolicy: Always
EOF
        ;;
    ImagePullBackOff)
        kubectl run healmesh-image-test \
            --image=this-image-does-not-exist-healmesh-test:v999 \
            --namespace="${NAMESPACE}"
        ;;
    FailedRollout)
        kubectl create deployment healmesh-rollout-test --image=nginx:1.25 \
            --namespace="${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
        sleep 2
        kubectl set image deployment/healmesh-rollout-test \
            nginx=this-image-does-not-exist-healmesh-test:v999 \
            --namespace="${NAMESPACE}"
        ;;
    ResourceQuotaExceeded)
        # Apply a tight quota that only allows 1 pod
        cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: healmesh-tight-quota
  namespace: ${NAMESPACE}
spec:
  hard:
    pods: "1"
EOF
        # Run first pod directly (succeeds, fills the quota)
        kubectl run healmesh-quota-test-1 --image=nginx:1.25 \
            --namespace="${NAMESPACE}" || true
        sleep 2
        # Create a Deployment trying to run 3 replicas — controller will emit
        # FailedCreate events for replicas 2 and 3 which are detectable via watch
        cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: healmesh-quota-deploy
  namespace: ${NAMESPACE}
spec:
  replicas: 3
  selector:
    matchLabels:
      app: healmesh-quota-test
  template:
    metadata:
      labels:
        app: healmesh-quota-test
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
EOF
        ;;
    *)
        echo "Unknown failure type: ${FAILURE_TYPE}"
        exit 1
        ;;
esac

echo "[inject_failure] Done. Watch: kubectl get events -n ${NAMESPACE} -w"
