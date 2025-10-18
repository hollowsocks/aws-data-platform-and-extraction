# Shared CloudFormation Templates

Infrastructure components that are reused across ingestion jobs:

- `data-lake.yaml` – core S3 bucket definitions
- `dynamodb-tables.yaml` – hot storage tables
- `glue-catalog.yaml` – shared Glue databases and crawlers
- `secrets-manager.yaml` – baseline secrets for external integrations
- `s3-lifecycle-policy.json` – lifecycle configuration helper
