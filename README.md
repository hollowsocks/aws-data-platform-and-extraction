# Shopify Data Platform Infrastructure

This repository captures the AWS infrastructure and Lambda containers that support the Shopify ingestion platform. The CloudFormation templates live under `infrastructure/`, containerized Lambdas live under `lambdas/`, and helper scripts plus tests round things out.

## Deploying the Foundation

1. **Buckets & Tables** – Deploy `infrastructure/shared/data-lake.yaml` and `infrastructure/shared/dynamodb-tables.yaml` to provision the data lake and DynamoDB hot stores (orders, customers, abandoned carts, subscriptions, charges, invoices).
2. **Glue Catalog** – Deploy `infrastructure/shared/glue-catalog.yaml` to create the databases, crawlers, and IAM role needed for Glue discovery jobs.
3. **Secrets Manager** – Deploy `infrastructure/shared/secrets-manager.yaml` to create placeholder secrets for Shopify and Recharge. Populate the `access_token` and `webhook_secret` values before wiring any workloads.
4. **Lambda Containers** – Use `scripts/build_push_lambdas.sh` (set `PROFILE`, `BRAND`, `REGION` as needed) to create ECR repositories, build each Lambda image, and push the `latest` tag. Record each resulting image URI for CloudFormation parameters.
5. **Event Routing** – Deploy `infrastructure/shopify/eventbridge-rules.yaml`, supplying the Shopify partner event source name plus the ECR image URIs for the order, fulfillment, customer, product, and cart processors. This stack creates the partner event bus, DLQs, IAM roles, and Lambda targets.
6. **Recharge Ingress** – Deploy `infrastructure/recharge/recharge-webhook.yaml` with the Recharge image URI, secret ARN, and (optionally) an SNS alert topic ARN. The stack publishes the Lambda, HTTP API endpoint, and grants Dynamo/S3 access.
7. **Bulk Workflow** – Deploy `infrastructure/shopify/shopify-bulk-workflow.yaml` with the bulk export/poll/download image URIs, Shopify shop domain, and access-token secret ARN. Optionally provide a schedule expression to trigger the Step Functions workflow automatically.
8. **Glue ETL** – Upload `glue-scripts/orders_enriched_job.py` to an S3 location (for example `s3://[artifact-bucket]/glue/orders_enriched_job.py`) and deploy `infrastructure/shopify/glue-jobs.yaml`, supplying the script location, data lake bucket override (if any), worker configuration, and optional schedule.
9. **Monitoring & Alerts** – Deploy `infrastructure/monitoring/monitoring.yaml` to stand up the shared SNS alerts topic, CloudWatch alarms for every Lambda/DLQ, and dashboards summarizing platform health.
10. **Data Quality Checks** – Deploy `infrastructure/data-quality/data-quality.yaml` with the data quality container image URI, schedule expression, and (optionally) the alerts topic ARN from the monitoring stack to enable automated health checks.

## Shopify & Partner Configuration Checklist

- Create EventBridge webhooks in the Shopify admin for orders, fulfillments, customers, carts, and checkouts, targeting AWS account `631046354185` (region `us-east-1`). Capture the partner source name (`aws.partner/shopify.com/<shop-id>/default`) for the EventBridge stack.
- Approve the partner event source in AWS (`aws events create-event-bus ...`) so the EventBridge stack can bind the Lambda rules.
- Generate a private Admin API access token with read rights to Orders, Customers, Products, Fulfillment, and Bulk Operations. Store it in the `ShopifyAdminApiSecret` created above under the `access_token` key.
- Retrieve the Recharge webhook signing secret and store it under the `webhook_secret` key of the `RechargeWebhookSecret`. Update the HTTP API endpoint in Recharge to point at the output invoke URL.

## Observability & Operations

- CloudWatch alarms created by `monitoring.yaml` all push to the SNS topic `arn:aws:sns:<region>:<account>:<Brand>-data-platform-alerts`. Subscribe the operations email address during stack deployment (or afterward via the console).
- Step Functions executions for Shopify bulk loads are viewable under the state machine `${Brand}-shopify-bulk-orders`. Failed executions raise the `bulk-workflow-failed` alarm.
- Dead-letter queues (`${Brand}-shopify-*-events-dlq`) should remain empty; alarms fire the moment a single message appears.
- The data quality Lambda deployed via `data-quality.yaml` runs on the configured EventBridge schedule and publishes metrics to the `${Brand}/DataQuality` namespace.

## GitHub Actions

- **Lint & Test** (`.github/workflows/lint-test.yml`) – runs `cfn-lint` and `pytest` on every push and pull request using the dependencies in `requirements-dev.txt`.
- **Build & Push Lambda Images** (`.github/workflows/build-containers.yml`) – runs automatically on pushes to `main` when repository variable `AUTO_BUILD_LAMBDAS` is set to `true`; otherwise launch manually via `workflow_dispatch`. Override the ingestion job with `AUTO_BUILD_INGESTION_JOB` (defaults to `all` when unset). Keep the GitHub secret `AWS_DEPLOY_ROLE_ARN` pointed at the OIDC role `arn:aws:iam::631046354185:role/github-actions-oidc`.
- **Deploy Infrastructure** (`.github/workflows/deploy-infrastructure.yml`) – uses the same toggle pattern (`AUTO_DEPLOY_INFRASTRUCTURE` / `AUTO_DEPLOY_INGESTION_JOB`). Parameter overrides live under `ci/environments/prod/<job>/` (see `ci/environments/README.md`), and each stack name is derived from `<brand>-prod-<job>-<stack>`. If the variables are `false`/absent, trigger manually when you are ready.

## Next Steps

- Configure GitHub Actions secrets and populate `ci/environments/prod/<job>/` parameter files so the new build/deploy workflows can push images and update stacks in production. (Done for `shopify` but review before the first deploy if resource names change.)
- Implement the Step Functions schedule once export cadence is finalized (set `BulkWorkflowScheduleExpression` as a cron or rate expression).
- Build and push dedicated fulfillment Lambda image(s) for EventBridge once the processor implementation lands; `FulfillmentProcessorImageUri` is temporarily pointed at the order processor image.
- Extend `infrastructure/recharge/recharge-webhook.yaml` or author a companion template if additional Recharge or Shopify integrations are required.
- **TripleWhale ingestion (in progress)** – scaffolding now lives under `data-ingestion/triplewhale/`, `infrastructure/triplewhale/`, `lambdas/triplewhale/`, and `docs/triplewhale/`. Complete the migration by porting the Lambda + Step Functions resources from `growth-reporting-engine` and wiring the new GitHub Actions workflow (`deploy-triplewhale.yml`).
