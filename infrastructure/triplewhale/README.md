# TripleWhale Infrastructure Stack

`triplewhale.yaml` (to be added) will provision the ingestion Lambda, Step Functions orchestration, necessary IAM roles, and Glue resources for the TripleWhale pipeline.

## TODO
- Port resources from growth-reporting-engine/infra/template.yaml
- Parameterize shared resources (data lake bucket, Glue database, Athena result bucket)
- Export outputs consumed by Superset and downstream jobs
