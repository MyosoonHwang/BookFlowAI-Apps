#!/usr/bin/env bash
# Build + push 5 mock images to ECR.
# Pre-req: aws cli logged into ECR, kubectl ctx pointing to bookflow-eks
#
# Usage:
#   AWS_PROFILE=bookflow-admin AWS_REGION=ap-northeast-1 ./build-all.sh
#
set -euo pipefail

REGION="${AWS_REGION:-ap-northeast-1}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

MOCKS=(
  azure-entra-mock
  azure-logic-apps-mock
  gcp-vertex-mock
  gcp-bigquery-mock
)

cd "$(dirname "$0")"

# ECR repo bootstrap (idempotent)
for m in "${MOCKS[@]}"; do
  aws ecr describe-repositories --repository-names "bookflow/${m}" --region "${REGION}" >/dev/null 2>&1 \
    || aws ecr create-repository --repository-name "bookflow/${m}" --region "${REGION}" >/dev/null
done

# ECR login
aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ECR}"

# Build + push each
for m in "${MOCKS[@]}"; do
  echo "=== build ${m} ==="
  docker build \
    --build-arg "MOCK_DIR=${m}" \
    -t "${ECR}/bookflow/${m}:latest" \
    -f Dockerfile .
  docker push "${ECR}/bookflow/${m}:latest"
done

# Apply k8s manifests with ECR substitution
kubectl apply -f k8s/namespace.yaml
sed "s|REPLACE_ME|${ECR}|g" k8s/deployments.yaml | kubectl apply -f -

echo
echo "Mocks deployed. Verify:"
echo "  kubectl get pods -n stubs"
echo "  kubectl get svc  -n stubs"
