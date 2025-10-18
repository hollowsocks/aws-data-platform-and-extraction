#!/usr/bin/env bash
set -euo pipefail

BRAND=${BRAND:-marsmen}
REGION=${REGION:-us-east-1}
PROFILE=${PROFILE:-}

export AWS_DEFAULT_REGION="$REGION"
if [[ -n "$PROFILE" ]]; then
  export AWS_PROFILE="$PROFILE"
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

DEFAULT_LAMBDAS=(
  shopify-order-processor
  shopify-customer-processor
  shopify-product-processor
  shopify-cart-processor
  recharge-event-processor
  shopify-bulk-export
  shopify-bulk-poll
  shopify-bulk-download
  data-quality-checker
)

if [[ -n "${LAMBDA_DIRS:-}" ]]; then
  IFS=',' read -r -a LAMBDA_DIRS_ARRAY <<<"$LAMBDA_DIRS"
else
  LAMBDA_DIRS_ARRAY=("${DEFAULT_LAMBDAS[@]}")
fi

for idx in "${!LAMBDA_DIRS_ARRAY[@]}"; do
  LAMBDA_DIRS_ARRAY[$idx]="$(echo "${LAMBDA_DIRS_ARRAY[$idx]}" | xargs)"
  if [[ -z "${LAMBDA_DIRS_ARRAY[$idx]}" ]]; then
    unset 'LAMBDA_DIRS_ARRAY[$idx]'
  fi
done

if [[ ${#LAMBDA_DIRS_ARRAY[@]} -eq 0 ]]; then
  echo "No Lambda directories supplied; set LAMBDA_DIRS or use defaults" >&2
  exit 1
fi

for dir in "${LAMBDA_DIRS_ARRAY[@]}"; do
  REPO_NAME="${BRAND}-${dir}"
  echo "Ensuring ECR repo $REPO_NAME exists"
  aws ecr describe-repositories \
    --repository-names "$REPO_NAME" \
    --region "$REGION" >/dev/null 2>&1 || \
  aws ecr create-repository \
    --repository-name "$REPO_NAME" \
    --image-scanning-configuration scanOnPush=true \
    --region "$REGION"

done

echo "Logging into ECR"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

for dir in "${LAMBDA_DIRS_ARRAY[@]}"; do
  REPO_NAME="${BRAND}-${dir}"
  IMAGE_TAG="latest"
  IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG"

  echo "Building $dir"
  docker build --platform linux/amd64 -t "$IMAGE_URI" "lambdas/$dir"
  docker push "$IMAGE_URI"
  echo "$dir -> $IMAGE_URI"

  FUNCTION_NAME="${BRAND}-${dir}"
  echo "Updating Lambda function $FUNCTION_NAME to $IMAGE_URI"
  if ! aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --image-uri "$IMAGE_URI" \
    --region "$REGION" >/dev/null 2>&1; then
    echo "Warning: unable to update Lambda function $FUNCTION_NAME (it may not exist yet)." >&2
  fi
done
