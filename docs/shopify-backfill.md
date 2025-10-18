# Shopify Historical Backfill Runbook

This guide explains how to backfill historical Shopify order data using the bulk export workflow that already lives in this repository.

---
## Prerequisites

- `infrastructure/shopify/shopify-bulk-workflow.yaml`
- Container images in ECR:
  - `marsmen-shopify-bulk-export`
  - `marsmen-shopify-bulk-poll`
  - `marsmen-shopify-bulk-download`
- Secrets Manager secret `marsmen/shopify-api/production` (contains the Admin API token)
- AWS credentials (or GitHub OIDC role) with permission to deploy CloudFormation and start Step Functions executions
- Shopify app scopes already granted for bulk access (`read_all_orders`, etc.)

---
## 1. Deploy (or redeploy) the bulk workflow stack

### Option A – GitHub Actions (recommended)
1. Navigate to **GitHub → Actions → Deploy Infrastructure**.
2. Click **Run workflow**, leave `ingestion_job` as `shopify`, and start the run.
3. The workflow applies `ci/environments/prod/shopify/bulk-workflow.json` and will create or update the `marsmen-shopify-bulk-workflow` stack.

### Option B – AWS CLI
If you prefer to deploy manually:
```bash
aws cloudformation deploy \
  --stack-name marsmen-shopify-bulk-workflow \
  --template-file infrastructure/shopify/shopify-bulk-workflow.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1 \
  --parameter-overrides \
      Brand=marsmen \
      ShopifyShopDomain=c9095d-2.myshopify.com \
      ShopifyAccessTokenSecretArn=arn:aws:secretsmanager:us-east-1:631046354185:secret:marsmen/shopify-api/production-A5bdQY \
      BulkExportImageUri=631046354185.dkr.ecr.us-east-1.amazonaws.com/marsmen-shopify-bulk-export:latest \
      BulkPollImageUri=631046354185.dkr.ecr.us-east-1.amazonaws.com/marsmen-shopify-bulk-poll:latest \
      BulkDownloadImageUri=631046354185.dkr.ecr.us-east-1.amazonaws.com/marsmen-shopify-bulk-download:latest
```
(Optionally add `BulkWorkflowScheduleExpression` if you want a recurring schedule.)

---
## 2. Locate the Step Functions state machine

After deployment you should have:
```
arn:aws:states:us-east-1:631046354185:stateMachine:marsmen-shopify-bulk-orders
```
Verify with:
```bash
aws stepfunctions describe-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:631046354185:stateMachine:marsmen-shopify-bulk-orders \
  --profile marsmen-direct
```

---
## 3. Start backfill executions

Each execution expects JSON input with:
- `export_type`: currently only `"orders"`
- `start_date` / `end_date`: ISO8601 timestamps (UTC recommended)

Example (January 2024):
```bash
STATE_MACHINE_ARN=arn:aws:states:us-east-1:631046354185:stateMachine:marsmen-shopify-bulk-orders

aws stepfunctions start-execution \
  --state-machine-arn "$STATE_MACHINE_ARN" \
  --name backfill-2024-01 \
  --input '{"export_type":"orders","start_date":"2024-01-01T00:00:00Z","end_date":"2024-01-31T23:59:59Z"}' \
  --profile marsmen-direct
```
Run additional executions (`backfill-2024-02`, `backfill-2024-03`, etc.) until the desired history is covered.

---
## 4. Optional helper script

Use `scripts/run_backfill.py` to queue multiple windows automatically:
```bash
python scripts/run_backfill.py --start 2024-01-01 --end 2024-03-31 --window 7
```
The `--end` date is inclusive; the script adds one day internally so every Step Functions window spans the full range.

---
## 5. Monitoring

- Step Functions executions: `aws stepfunctions list-executions --state-machine-arn ...`
- CloudWatch logs:
  - `/aws/lambda/marsmen-shopify-bulk-export`
  - `/aws/lambda/marsmen-shopify-bulk-poll`
  - `/aws/lambda/marsmen-shopify-bulk-download`
  - `/aws/states/marsmen-shopify-bulk-orders`

---
## 6. Output data

Each successful execution writes Parquet files to:
```
s3://marsmen-data-lake-631046354185/raw/shopify/orders/snapshots/date=YYYY-MM-DD/orders_YYYYMMDD_HHMMSS.parquet
```
Use these snapshots for analytics or replay the data into downstream pipelines if needed.
