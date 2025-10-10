# CloudFormation Parameter Files

Store production CloudFormation parameter files under `ci/environments/prod/<job>/`.

Each JSON file should follow this structure:

```json
{
  "Parameters": {
    "Brand": "marsmen",
    "PartnerEventSourceName": "aws.partner/shopify.com/<shop-id>/default",
    "OrderProcessorImageUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/marsmen-shopify-order-processor:latest"
  },
  "Tags": {
    "Environment": "prod",
    "Owner": "data-platform"
  }
}
```

The filename should match the stack `name` defined in `ci/ingestion_jobs.json` (for example, `eventbridge.json` or `data-quality.json`). Any stack without a corresponding parameter file will be deployed with template defaults.
