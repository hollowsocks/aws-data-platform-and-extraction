# Shopify Data Ingestion - Greenfield Best Practices Guide

## Executive Summary

This guide outlines the **best-practice architecture** for ingesting Shopify data into AWS from scratch, following modern data engineering patterns, AWS Well-Architected Framework principles, and Shopify's recommended integration approaches.

**Key Principles:**
- Event-driven architecture (webhooks via EventBridge)
- Separation of raw/processed data layers
- Immutable raw data storage
- Schema evolution support
- Cost-optimized storage (S3 lifecycle policies)
- Real-time and batch processing capabilities
- Comprehensive monitoring and alerting
- GDPR/data governance compliance

---

## Architecture Overview

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                       DATA SOURCES                                   │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  SHOPIFY     │  │  RECHARGE    │  │  STRIPE      │              │
│  │  Orders      │  │  Subscriptions│  │  Payments    │              │
│  │  Customers   │  │  Charges     │  │  Failures    │              │
│  │  Products    │  │  Cancels     │  │  Disputes    │              │
│  │  Carts       │  └──────────────┘  └──────────────┘              │
│  └──────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AWS INGESTION LAYER                           │
│                                                                   │
│  ┌──────────────────┐              ┌─────────────────────┐      │
│  │  EventBridge     │              │  Step Functions     │      │
│  │  Partner Events  │              │  Bulk Operations    │      │
│  │  (Real-time)     │              │  Orchestrator       │      │
│  └──────────────────┘              └─────────────────────┘      │
│           │                                    │                 │
│           ▼                                    ▼                 │
│  ┌──────────────────┐              ┌─────────────────────┐      │
│  │  Lambda          │              │  Lambda             │      │
│  │  Event Processor │              │  Bulk Downloader    │      │
│  └──────────────────┘              └─────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAKE (S3)                             │
│                                                                   │
│  s3://[brand]-data-lake-[env]-[account]/                         │
│                                                                   │
│  ├── raw/                    ← Immutable source of truth         │
│  │   └── shopify/                                                │
│  │       ├── orders/                                             │
│  │       │   ├── events/           ← Real-time webhook events    │
│  │       │   │   └── date=YYYY-MM-DD/hour=HH/*.json              │
│  │       │   └── snapshots/        ← Daily bulk exports          │
│  │       │       └── date=YYYY-MM-DD/*.parquet                   │
│  │       ├── customers/                                          │
│  │       ├── products/                                           │
│  │       └── fulfillments/                                       │
│  │                                                                │
│  ├── processed/              ← Cleaned, enriched data            │
│  │   └── shopify/                                                │
│  │       └── orders_enriched/                                    │
│  │           └── date=YYYY-MM-DD/*.parquet                       │
│  │                                                                │
│  └── curated/                ← Business-ready analytics tables   │
│      ├── subscription_orders/                                    │
│      ├── customer_cohorts/                                       │
│      └── churn_metrics/                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    QUERY & CACHE LAYER                           │
│                                                                   │
│  ┌──────────────────┐              ┌─────────────────────┐      │
│  │  AWS Glue        │              │  DynamoDB           │      │
│  │  Data Catalog    │              │  Hot Cache          │      │
│  │  (Metadata)      │              │  (Last 30 days)     │      │
│  └──────────────────┘              └─────────────────────┘      │
│           │                                    │                 │
│           ▼                                    ▼                 │
│  ┌──────────────────┐              ┌─────────────────────┐      │
│  │  Amazon Athena   │              │  Mission Control    │      │
│  │  (Ad-hoc SQL)    │              │  Dashboard          │      │
│  └──────────────────┘              └─────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Coverage & Analytics Capabilities

### Complete Shopify Data Capture

**✅ Raw Data Preservation:** The architecture stores the **complete, unmodified Shopify webhook payload** in S3 (`raw/shopify/orders/events/`), ensuring you never lose any data that Shopify provides.

**✅ Enriched Fields Extracted:** Key fields are extracted into structured formats for fast querying:

#### Attribution & Source Tracking
- `source_name` - Origin of order (web, POS, draft order, API, subscription app)
- `referring_site` - External site that referred customer
- `landing_site` - First page customer landed on
- `landing_site_ref` - URL parameters from landing page (UTM tracking)
- `source_url` - Full URL where order originated
- `checkout_token`, `cart_token` - Session tracking

**Use case:** Track which marketing channels drive subscriptions vs. one-time orders

#### Customer Lifetime Value
- `customer_orders_count` - Total orders by this customer
- `customer_total_spent` - Lifetime spend
- `customer_created_at` - Customer acquisition date
- `customer_tags` - Segmentation tags
- `customer_accepts_marketing` - Marketing consent

**Use case:** Calculate LTV, identify high-value customers, cohort by acquisition month

#### Churn Analysis
- `cancelled_at`, `cancel_reason` - Subscription cancellations
- `refunds[]` - Full refund history
- `financial_status` - Payment success/failure
- `tags` - Subscription status tags

**Use case:** Identify cancellation patterns, calculate churn rate by cohort, analyze refund reasons

#### Revenue Attribution
- `discount_codes[]` - Applied coupon codes
- `discount_applications[]` - Discount details (amount, type, allocation)
- `total_price`, `subtotal_price`, `total_discounts` - Revenue breakdown
- `line_items[]` - Product-level details (SKU, quantity, price, variant)

**Use case:** Calculate true revenue per order, discount effectiveness, product mix analysis

#### Subscription-Specific
- `is_subscription` - Boolean flag (derived from tags/SKUs)
- `subscription_type` - monthly, quarterly (derived)
- `rebill_number` - Which subscription cycle (calculated)
- `days_since_acquisition` - Customer tenure (calculated)

**Use case:** Subscription retention curves, MRR calculations, cohort retention

#### Fulfillment & Operations
- `fulfillments[]` - Tracking numbers, carrier, status
- `fulfillment_status` - fulfilled, partial, unfulfilled
- `shipping_address` - Full address details

**Use case:** Shipping performance, carrier analysis, geographic trends

#### Test vs. Production
- `test` - Boolean flag for test orders
- `confirmed` - Order confirmation status

**Use case:** Filter test data from production analytics

### What's NOT Captured (and Why)

**Customer Payment Details:** Shopify doesn't include credit card numbers or payment tokens in webhooks (PCI compliance). You get `gateway` and `payment_gateway_names` only.

**Inventory Levels:** Not included in order webhooks. Use separate Product/Inventory webhooks if needed.

**Shop Settings:** Not included in order data. Access via Shopify Admin API if needed.

### Analytics Queries You Can Run

With this data structure, you can answer:

1. **Churn Analysis**
   ```sql
   -- Monthly churn rate by acquisition cohort
   SELECT
     DATE_TRUNC('month', customer_created_at) as cohort_month,
     COUNT(DISTINCT CASE WHEN cancelled_at IS NOT NULL THEN customer_id END) /
     COUNT(DISTINCT customer_id) as churn_rate
   FROM orders_enriched
   WHERE is_subscription = true
   GROUP BY cohort_month;
   ```

2. **Source Attribution**
   ```sql
   -- Revenue by acquisition source
   SELECT
     source_name,
     COUNT(DISTINCT order_id) as orders,
     SUM(total_price) as revenue,
     AVG(total_price) as avg_order_value
   FROM orders_enriched
   GROUP BY source_name;
   ```

3. **Discount Impact**
   ```sql
   -- Compare discounted vs. non-discounted orders
   SELECT
     CASE WHEN total_discounts > 0 THEN 'Discounted' ELSE 'Full Price' END as order_type,
     COUNT(*) as order_count,
     AVG(total_price) as avg_revenue,
     COUNT(DISTINCT customer_id) as unique_customers
   FROM orders_enriched
   GROUP BY order_type;
   ```

4. **Subscription Retention**
   ```sql
   -- Retention curve by cohort
   SELECT
     cohort_month,
     rebill_number,
     COUNT(DISTINCT customer_id) as active_customers,
     SUM(total_price) as revenue
   FROM subscription_orders
   GROUP BY cohort_month, rebill_number
   ORDER BY cohort_month, rebill_number;
   ```

5. **Geographic Analysis**
   ```sql
   -- Orders by state
   SELECT
     shipping_state,
     COUNT(*) as order_count,
     SUM(total_price) as total_revenue,
     AVG(total_price) as avg_order_value
   FROM orders_enriched
   WHERE shipping_country = 'US'
   GROUP BY shipping_state
   ORDER BY total_revenue DESC;
   ```

---

## Phase 1: Foundation Setup

### 1.1 S3 Bucket Architecture

**Best Practice: Single Data Lake Bucket (Production Only)**

```bash
# Bucket naming convention
[brand]-data-lake-[account-id]

# Example
marsmen-data-lake-631046354185
```

**Bucket Structure:**

```
s3://marsmen-data-lake-631046354185/
│
├── raw/                           # Raw, immutable source data
│   ├── shopify/
│   │   ├── orders/
│   │   │   ├── events/           # Real-time webhook events
│   │   │   │   ├── date=2025-01-01/hour=00/
│   │   │   │   │   ├── event-12345.json
│   │   │   │   │   └── event-12346.json
│   │   │   │   └── date=2025-01-01/hour=01/
│   │   │   └── snapshots/        # Daily full snapshots via Bulk Operations
│   │   │       ├── date=2025-01-01/
│   │   │       │   └── orders.parquet
│   │   │       └── date=2025-01-02/
│   │   ├── customers/
│   │   │   ├── events/           # Customer create/update/delete
│   │   │   └── snapshots/
│   │   ├── products/
│   │   │   ├── events/           # Product/variant changes
│   │   │   └── snapshots/
│   │   ├── carts/
│   │   │   └── events/           # Abandoned carts
│   │   ├── checkouts/
│   │   │   └── events/           # Abandoned checkouts
│   │   └── fulfillments/
│   │       └── events/
│   ├── recharge/                 # Subscription platform (Recharge/Bold/etc)
│   │   ├── subscriptions/
│   │   │   └── events/           # Status changes, cancellations, pauses
│   │   ├── charges/
│   │   │   └── events/           # Billing attempts, successes, failures
│   │   └── customers/
│   │       └── events/
│   └── stripe/                   # Payment gateway
│       ├── charges/
│       │   └── events/           # Payment successes/failures
│       ├── payment_intents/
│       │   └── events/
│       ├── invoices/
│       │   └── events/           # Subscription billing invoices
│       └── disputes/
│           └── events/           # Chargebacks
│
├── processed/                     # Cleaned, validated, enriched
│   └── shopify/
│       ├── orders_enriched/
│       │   └── date=2025-01-01/
│       │       └── orders.parquet
│       ├── customers_enriched/
│       └── products_enriched/
│
├── curated/                       # Business-ready analytics tables
│   ├── subscription_orders/       # Subscription orders only
│   │   ├── subscription_type=monthly/date=2025-01-01/
│   │   └── subscription_type=quarterly/date=2025-01-01/
│   ├── customer_cohorts/          # Cohort analysis
│   │   └── cohort_month=2025-01/
│   └── churn_metrics/             # Pre-aggregated metrics
│       └── metric_date=2025-01-01/
│
└── metadata/                      # Schema definitions, data quality results
    ├── schemas/
    │   └── orders_v1.json
    └── data_quality/
        └── date=2025-01-01/
```

**S3 Bucket Configuration:**

```bash
# Create bucket
aws s3api create-bucket \
  --bucket marsmen-data-lake-631046354185 \
  --region us-east-1 \
  --profile marsmen-direct

# Enable versioning (for compliance/audit)
aws s3api put-bucket-versioning \
  --bucket marsmen-data-lake-631046354185 \
  --versioning-configuration Status=Enabled \
  --profile marsmen-direct

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket marsmen-data-lake-631046354185 \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }' \
  --profile marsmen-direct

# Set lifecycle policy
aws s3api put-bucket-lifecycle-configuration \
  --bucket marsmen-data-lake-631046354185 \
  --lifecycle-configuration file://s3-lifecycle-policy.json \
  --profile marsmen-direct
```

**s3-lifecycle-policy.json:**

```json
{
  "Rules": [
    {
      "Id": "TransitionRawEventsToIA",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "raw/shopify/orders/events/"
      },
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 180,
          "StorageClass": "GLACIER"
        }
      ]
    },
    {
      "Id": "DeleteProcessedAfter2Years",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "processed/"
      },
      "Expiration": {
        "Days": 730
      }
    },
    {
      "Id": "TransitionSnapshotsToIA",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "raw/shopify/orders/snapshots/"
      },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 365,
          "StorageClass": "GLACIER_IR"
        }
      ]
    }
  ]
}
```

### 1.2 DynamoDB Hot Cache

**Best Practice: Single table for real-time queries**

```bash
# Table naming convention
[brand]-orders-cache

# Example
marsmen-orders-cache
```

**Table Schema:**

```json
{
  "TableName": "marsmen-orders-cache",
  "KeySchema": [
    {
      "AttributeName": "order_id",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "created_at",
      "KeyType": "RANGE"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "order_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "created_at",
      "AttributeType": "S"
    },
    {
      "AttributeName": "customer_email",
      "AttributeType": "S"
    },
    {
      "AttributeName": "order_number",
      "AttributeType": "S"
    }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "customer-email-index",
      "KeySchema": [
        {
          "AttributeName": "customer_email",
          "KeyType": "HASH"
        },
        {
          "AttributeName": "created_at",
          "KeyType": "RANGE"
        }
      ],
      "Projection": {
        "ProjectionType": "ALL"
      }
    },
    {
      "IndexName": "order-number-index",
      "KeySchema": [
        {
          "AttributeName": "order_number",
          "KeyType": "HASH"
        }
      ],
      "Projection": {
        "ProjectionType": "ALL"
      }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST",
  "StreamSpecification": {
    "StreamEnabled": true,
    "StreamViewType": "NEW_AND_OLD_IMAGES"
  },
  "TimeToLiveSpecification": {
    "Enabled": true,
    "AttributeName": "ttl"
  },
  "Tags": [
    {
      "Key": "Application",
      "Value": "shopify-ingestion"
    },
    {
      "Key": "Brand",
      "Value": "marsmen"
    }
  ]
}
```

**Create Table:**

```bash
aws dynamodb create-table \
  --cli-input-json file://dynamodb-table-definition.json \
  --region us-east-1 \
  --profile marsmen-direct
```

---

## Phase 2: Real-Time Ingestion (EventBridge)

### 2.1 Shopify EventBridge Setup

**Step 1: Create Partner Event Source in Shopify**

1. Navigate to Shopify Admin → Settings → Notifications
2. Click "Create webhook" → Select "Amazon EventBridge"
3. Configure:
   - **AWS Account ID:** 631046354185
   - **AWS Region:** us-east-1
   - **Event Topics:**
     - orders/create
     - orders/updated
     - orders/cancelled
     - fulfillments/create
     - fulfillments/update
     - customers/create
     - customers/update

4. Copy the **Partner Event Source ARN** (format: `arn:aws:events:us-east-1:631046354185:event-source/aws.partner/shopify.com/[shop-id]/default`)

**Step 2: Accept Partner Event Source in AWS**

```bash
# List the pending partner event source that Shopify just created
aws events list-partner-event-sources \
  --region us-east-1 \
  --profile marsmen-direct \
  --name-prefix aws.partner/shopify.com/[shop-id]

# Create a partner event bus that is linked to the Shopify source
aws events create-event-bus \
  --name marsmen-shopify-partner-bus \
  --event-source-name aws.partner/shopify.com/[shop-id]/default \
  --region us-east-1 \
  --profile marsmen-direct

# (Optional) Confirm the bus is ACTIVE
aws events describe-event-bus \
  --name marsmen-shopify-partner-bus \
  --region us-east-1 \
  --profile marsmen-direct
```

Save the event bus name (`marsmen-shopify-partner-bus` in the example above) for the CloudFormation deployment parameter.

### 2.2 EventBridge Rules

**CloudFormation Template: eventbridge-rules.yaml**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'EventBridge rules for Shopify webhook processing'

Parameters:
  Brand:
    Type: String
    Default: marsmen

  PartnerEventSourceName:
    Type: String
    Description: 'Shopify partner event source name (aws.partner/shopify.com/[shop-id]/default)'

  EventBusName:
    Type: String
    Default: marsmen-shopify-partner-bus
    Description: 'Friendly name for the partner event bus'

Resources:
  # Event Bus for Shopify events
  ShopifyEventBus:
    Type: AWS::Events::EventBus
    Properties:
      Name: !Ref EventBusName
      EventSourceName: !Ref PartnerEventSourceName
      Tags:
        - Key: Brand
          Value: !Ref Brand

  # Rule for Order Events
  OrderEventsRule:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub '${Brand}-shopify-order-events'
      Description: 'Route Shopify order events to Lambda processor'
      EventBusName: !Ref ShopifyEventBus
      EventPattern:
        source:
          - !Ref PartnerEventSourceName
        detail-type:
          - 'orders/create'
          - 'orders/updated'
          - 'orders/cancelled'
      State: ENABLED
      Targets:
        - Arn: !GetAtt OrderProcessorFunction.Arn
          Id: OrderProcessorTarget
          RetryPolicy:
            MaximumRetryAttempts: 3
            MaximumEventAge: 3600
          DeadLetterConfig:
            Arn: !GetAtt OrderEventsDLQ.Arn

  # Rule for Fulfillment Events
  FulfillmentEventsRule:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub '${Brand}-shopify-fulfillment-events'
      Description: 'Route Shopify fulfillment events to Lambda processor'
      EventBusName: !Ref ShopifyEventBus
      EventPattern:
        source:
          - !Ref PartnerEventSourceName
        detail-type:
          - 'fulfillments/create'
          - 'fulfillments/update'
      State: ENABLED
      Targets:
        - Arn: !GetAtt FulfillmentProcessorFunction.Arn
          Id: FulfillmentProcessorTarget

  # Dead Letter Queue for failed events
  OrderEventsDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${Brand}-shopify-order-events-dlq'
      MessageRetentionPeriod: 1209600  # 14 days
      Tags:
        - Key: Brand
          Value: !Ref Brand

  # CloudWatch Log Group
  OrderProcessorLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub '/aws/lambda/${Brand}-shopify-order-processor'
      RetentionInDays: 30

  # Lambda Execution Role
  OrderProcessorRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${Brand}-shopify-order-processor-role'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: S3Access
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:PutObject
                  - s3:GetObject
                Resource: !Sub 'arn:aws:s3:::${Brand}-data-lake-${AWS::AccountId}/*'
        - PolicyName: DynamoDBAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - dynamodb:PutItem
                  - dynamodb:UpdateItem
                  - dynamodb:GetItem
                Resource: !Sub 'arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${Brand}-orders-cache'

  # Order Processor Lambda
  OrderProcessorFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: !Sub '${Brand}-shopify-order-processor'
      Runtime: python3.11
      Handler: index.handler
      Role: !GetAtt OrderProcessorRole.Arn
      Timeout: 60
      MemorySize: 512
      Environment:
        Variables:
          BRAND: !Ref Brand
          S3_BUCKET: !Sub '${Brand}-data-lake-${AWS::AccountId}'
          DYNAMODB_TABLE: !Sub '${Brand}-orders-cache'
      Code:
        ZipFile: |
          # Placeholder - will be replaced with actual code
          def handler(event, context):
              print(f"Received event: {event}")
              return {'statusCode': 200}

  # Permission for EventBridge to invoke Lambda
  OrderProcessorInvokePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref OrderProcessorFunction
      Action: lambda:InvokeFunction
      Principal: events.amazonaws.com
      SourceArn: !GetAtt OrderEventsRule.Arn

Outputs:
  EventBusNameOutput:
    Description: 'Name of the Shopify partner event bus'
    Value: !Ref ShopifyEventBus

  EventBusArn:
    Description: 'ARN of the Shopify partner event bus'
    Value: !GetAtt ShopifyEventBus.Arn
    Export:
      Name: !Sub '${Brand}-shopify-eventbus'

  OrderProcessorFunctionArn:
    Description: 'ARN of Order Processor Lambda'
    Value: !GetAtt OrderProcessorFunction.Arn
```

### 2.3 Order Processor Lambda (Best Practices)

**File: lambdas/shopify-order-processor/index.py**

```python
"""
Shopify Order Event Processor
Processes real-time order events from EventBridge and stores in S3 + DynamoDB
"""
import json
import os
import boto3
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Environment variables
BRAND = os.environ['BRAND']
S3_BUCKET = os.environ['S3_BUCKET']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']

# Constants
TTL_DAYS = 30


def handler(event, context):
    """
    Process Shopify order events from EventBridge

    Event structure:
    {
        "version": "0",
        "id": "event-id",
        "detail-type": "orders/create",
        "source": "aws.partner/shopify.com",
        "account": "123456789012",
        "time": "2025-10-03T12:00:00Z",
        "region": "us-east-1",
        "resources": [],
        "detail": {
            "id": 5678901234567,
            "email": "customer@example.com",
            "created_at": "2025-10-03T12:00:00-04:00",
            ...
        }
    }
    """
    try:
        logger.info(f"Processing event: {event['detail-type']}")

        # Extract order data from event detail
        order_data = event.get('detail', {})
        event_type = event.get('detail-type')
        event_time = event.get('time')

        if not order_data:
            logger.warning("No order data in event detail")
            return {'statusCode': 400, 'body': 'No order data'}

        order_id = str(order_data.get('id'))

        # Store raw event in S3 (immutable audit trail)
        s3_key = store_raw_event(order_data, event_type, event_time)
        logger.info(f"Stored raw event to S3: {s3_key}")

        # Process and enrich order data
        enriched_order = enrich_order(order_data, event_type)

        # Store in DynamoDB hot cache (if recent order)
        if is_recent_order(enriched_order):
            store_in_dynamodb(enriched_order)
            logger.info(f"Stored order {order_id} in DynamoDB")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'order_id': order_id,
                's3_key': s3_key,
                'event_type': event_type
            })
        }

    except Exception as e:
        logger.error(f"Error processing event: {str(e)}", exc_info=True)
        raise


def store_raw_event(order_data: Dict[str, Any], event_type: str, event_time: str) -> str:
    """
    Store raw event in S3 for immutable audit trail

    Path: raw/shopify/orders/events/date=YYYY-MM-DD/hour=HH/event-{order_id}-{timestamp}.json
    """
    order_id = order_data.get('id')
    event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))

    # Generate S3 key with date/hour partitioning
    s3_key = (
        f"raw/shopify/orders/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"hour={event_dt.strftime('%H')}/"
        f"event-{order_id}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    # Add metadata
    event_with_metadata = {
        'event_type': event_type,
        'event_time': event_time,
        'ingested_at': datetime.now(timezone.utc).isoformat(),
        'data': order_data
    }

    # Upload to S3
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(event_with_metadata, default=str),
        ContentType='application/json',
        Metadata={
            'event-type': event_type,
            'order-id': str(order_id)
        }
    )

    return s3_key


def enrich_order(order_data: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """
    Enrich order data with derived fields and business logic
    """
    customer = order_data.get('customer', {})
    shipping = order_data.get('shipping_address', {})
    billing = order_data.get('billing_address', {})

    # Extract and normalize data
    enriched = {
        'order_id': str(order_data.get('id')),
        'order_number': str(order_data.get('order_number')) if order_data.get('order_number') is not None else None,
        'created_at': order_data.get('created_at'),
        'updated_at': order_data.get('updated_at'),
        'processed_at': order_data.get('processed_at'),
        'closed_at': order_data.get('closed_at'),

        # Customer info
        'customer_id': str(customer.get('id')) if customer.get('id') else None,
        'customer_email': customer.get('email'),
        'customer_first_name': customer.get('first_name'),
        'customer_last_name': customer.get('last_name'),
        'customer_phone': customer.get('phone') or shipping.get('phone'),
        'customer_created_at': customer.get('created_at'),
        'customer_orders_count': customer.get('orders_count'),
        'customer_total_spent': customer.get('total_spent'),
        'customer_tags': customer.get('tags'),
        'customer_accepts_marketing': customer.get('accepts_marketing'),
        'customer_marketing_opt_in_level': customer.get('marketing_opt_in_level'),

        # Financial
        'total_price': Decimal(str(order_data.get('total_price', '0'))),
        'subtotal_price': Decimal(str(order_data.get('subtotal_price', '0'))),
        'total_discounts': Decimal(str(order_data.get('total_discounts', '0'))),
        'total_tax': Decimal(str(order_data.get('total_tax', '0'))),
        'total_shipping': Decimal(str(order_data.get('total_shipping_price_set', {}).get('shop_money', {}).get('amount', '0'))),
        'total_line_items_price': Decimal(str(order_data.get('total_line_items_price', '0'))),
        'currency': order_data.get('currency', 'USD'),

        # Status
        'financial_status': order_data.get('financial_status'),
        'fulfillment_status': order_data.get('fulfillment_status'),
        'cancelled_at': order_data.get('cancelled_at'),
        'cancel_reason': order_data.get('cancel_reason'),
        'confirmed': order_data.get('confirmed'),
        'test': order_data.get('test', False),

        # Shipping
        'shipping_city': shipping.get('city'),
        'shipping_state': shipping.get('province'),
        'shipping_zip': shipping.get('zip'),
        'shipping_country': shipping.get('country'),
        'shipping_address_1': shipping.get('address1'),
        'shipping_address_2': shipping.get('address2'),
        'shipping_company': shipping.get('company'),
        'shipping_name': shipping.get('name'),

        # Billing
        'billing_city': billing.get('city'),
        'billing_state': billing.get('province'),
        'billing_zip': billing.get('zip'),
        'billing_country': billing.get('country'),
        'billing_address_1': billing.get('address1'),
        'billing_address_2': billing.get('address2'),
        'billing_company': billing.get('company'),
        'billing_name': billing.get('name'),

        # Attribution & Source Tracking (CRITICAL for churn analysis)
        'source_name': order_data.get('source_name'),  # e.g., "web", "shopify_draft_order", "pos"
        'source_identifier': order_data.get('source_identifier'),
        'source_url': order_data.get('source_url'),
        'referring_site': order_data.get('referring_site'),
        'landing_site': order_data.get('landing_site'),
        'landing_site_ref': order_data.get('landing_site_ref'),
        'checkout_token': order_data.get('checkout_token'),
        'cart_token': order_data.get('cart_token'),

        # Discounts (for cohort analysis)
        'discount_codes': json.dumps(order_data.get('discount_codes', [])),
        'discount_applications': json.dumps(order_data.get('discount_applications', [])),

        # Tags and metadata
        'tags': order_data.get('tags', ''),
        'note': order_data.get('note'),
        'note_attributes': json.dumps(order_data.get('note_attributes', [])),

        # Payment info
        'gateway': order_data.get('gateway'),
        'payment_gateway_names': json.dumps(order_data.get('payment_gateway_names', [])),
        'processing_method': order_data.get('processing_method'),

        # Subscription detection
        'is_subscription': is_subscription_order(order_data),
        'subscription_type': get_subscription_type(order_data),

        # Fulfillment tracking
        'fulfillments': json.dumps(order_data.get('fulfillments', [])),
        'refunds': json.dumps(order_data.get('refunds', [])),

        # Complete line items (stored as JSON for flexibility)
        'line_items': json.dumps(order_data.get('line_items', []), default=str),

        # Metadata
        'event_type': event_type,
        '_ingested_at': datetime.now(timezone.utc).isoformat(),
        '_brand': BRAND,
    }

    # Calculate line items summary
    line_items = order_data.get('line_items', [])
    enriched['line_item_count'] = len(line_items)
    enriched['total_quantity'] = sum(item.get('quantity', 0) for item in line_items)

    # Remove None values
    return {k: v for k, v in enriched.items() if v is not None}


def is_subscription_order(order_data: Dict[str, Any]) -> bool:
    """
    Determine if order is a subscription order
    """
    # Check for subscription tags
    tags = order_data.get('tags', '').lower()
    if 'subscription' in tags or 'recurring' in tags:
        return True

    # Check line items for subscription SKUs
    subscription_skus = [
        'marstestsupport',
        'marsupgrade90_02',
        'mars_monthly',
        'mars_quarterly_3x',
        'quarterly_mars_03'
    ]

    for item in order_data.get('line_items', []):
        sku = (item.get('sku') or '').lower()
        if any(sub_sku in sku for sub_sku in subscription_skus):
            return True

    return False


def get_subscription_type(order_data: Dict[str, Any]) -> Optional[str]:
    """
    Determine subscription type (monthly, quarterly, etc.)
    """
    if not is_subscription_order(order_data):
        return None

    # Check line items for subscription type indicators
    for item in order_data.get('line_items', []):
        sku = (item.get('sku') or '').lower()

        if 'monthly' in sku or 'mars_monthly' in sku:
            return 'monthly'
        elif 'quarterly' in sku or '3x' in sku:
            return 'quarterly'

    # Default to monthly if can't determine
    return 'monthly'


def is_recent_order(order_data: Dict[str, Any]) -> bool:
    """
    Check if order is recent (within TTL window) for DynamoDB caching
    """
    created_at = order_data.get('created_at')
    if not created_at:
        return True  # Default to caching if no date

    try:
        created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        cutoff = datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)
        return created_dt > cutoff
    except (ValueError, TypeError):
        return True


def store_in_dynamodb(order_data: Dict[str, Any]):
    """
    Store order in DynamoDB hot cache with TTL
    """
    table = dynamodb.Table(DYNAMODB_TABLE)

    # Set TTL (30 days from now)
    ttl = int((datetime.now(timezone.utc) + timedelta(days=TTL_DAYS)).timestamp())

    item = {
        **order_data,
        'ttl': ttl
    }

    # Convert floats to Decimal for DynamoDB
    item = json.loads(json.dumps(item, default=str), parse_float=Decimal)

    table.put_item(Item=item)
```

**Dockerfile:**

```dockerfile
FROM public.ecr.aws/lambda/python:3.11

# Copy requirements
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code
COPY index.py ${LAMBDA_TASK_ROOT}/

# Set handler
CMD ["index.handler"]
```

**requirements.txt:**

```
boto3>=1.28.0
```

---

## Phase 2b: Additional Shopify Webhooks

### 2.4 Customer Event Processor

Track customer changes independently of orders (important for marketing opt-in/out, tag changes, etc.)

**File: lambdas/shopify-customer-processor/index.py**

```python
"""
Shopify Customer Event Processor
Processes customer create/update/delete events
"""
import json
import os
import boto3
from datetime import datetime, timezone
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BRAND = os.environ['BRAND']
S3_BUCKET = os.environ['S3_BUCKET']
CUSTOMER_TABLE = os.environ.get('CUSTOMER_TABLE', f"{BRAND}-customers-cache")


def handler(event, context):
    """Process customer events from EventBridge"""
    try:
        customer_data = event.get('detail', {})
        event_type = event.get('detail-type')  # customers/create, customers/update, customers/delete
        event_time = event.get('time')

        customer_id = str(customer_data.get('id'))

        # Store raw event in S3
        s3_key = store_raw_customer_event(customer_data, event_type, event_time)
        logger.info(f"Stored customer event to S3: {s3_key}")

        # Update customer cache in DynamoDB
        if event_type in ['customers/create', 'customers/update']:
            store_customer_in_dynamodb(customer_data)
        elif event_type == 'customers/delete':
            delete_customer_from_dynamodb(customer_id)

        return {'statusCode': 200, 'customer_id': customer_id}

    except Exception as e:
        logger.error(f"Error processing customer event: {str(e)}", exc_info=True)
        raise


def store_raw_customer_event(customer_data, event_type, event_time):
    """Store raw customer event in S3"""
    customer_id = customer_data.get('id')
    event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))

    s3_key = (
        f"raw/shopify/customers/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"hour={event_dt.strftime('%H')}/"
        f"customer-{customer_id}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    event_with_metadata = {
        'event_type': event_type,
        'event_time': event_time,
        'ingested_at': datetime.now(timezone.utc).isoformat(),
        'data': customer_data
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(event_with_metadata, default=str),
        ContentType='application/json'
    )

    return s3_key


def store_customer_in_dynamodb(customer_data):
    """Store customer in DynamoDB cache"""
    table = dynamodb.Table(CUSTOMER_TABLE)

    item = {
        'customer_id': str(customer_data.get('id')),
        'email': customer_data.get('email'),
        'first_name': customer_data.get('first_name'),
        'last_name': customer_data.get('last_name'),
        'phone': customer_data.get('phone'),
        'created_at': customer_data.get('created_at'),
        'updated_at': customer_data.get('updated_at'),
        'orders_count': customer_data.get('orders_count', 0),
        'total_spent': customer_data.get('total_spent', '0'),
        'tags': customer_data.get('tags', ''),
        'accepts_marketing': customer_data.get('accepts_marketing', False),
        'marketing_opt_in_level': customer_data.get('marketing_opt_in_level'),
        'state': customer_data.get('state'),  # enabled, disabled, invited, declined
        '_updated_at': datetime.now(timezone.utc).isoformat(),
    }

    # Remove None values
    item = {k: v for k, v in item.items() if v is not None}

    table.put_item(Item=item)


def delete_customer_from_dynamodb(customer_id):
    """Remove customer from DynamoDB (GDPR deletion)"""
    table = dynamodb.Table(CUSTOMER_TABLE)
    table.delete_item(Key={'customer_id': customer_id})
```

### 2.5 Product Event Processor

Track product/variant changes over time to maintain accurate historical product data.

**File: lambdas/shopify-product-processor/index.py**

```python
"""
Shopify Product Event Processor
Tracks product and variant changes over time
"""
import json
import os
import boto3
from datetime import datetime, timezone
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
S3_BUCKET = os.environ['S3_BUCKET']


def handler(event, context):
    """Process product events from EventBridge"""
    try:
        product_data = event.get('detail', {})
        event_type = event.get('detail-type')  # products/create, products/update, products/delete
        event_time = event.get('time')

        product_id = str(product_data.get('id'))

        # Store raw event in S3
        s3_key = store_raw_product_event(product_data, event_type, event_time)
        logger.info(f"Stored product event to S3: {s3_key}")

        return {'statusCode': 200, 'product_id': product_id}

    except Exception as e:
        logger.error(f"Error processing product event: {str(e)}", exc_info=True)
        raise


def store_raw_product_event(product_data, event_type, event_time):
    """Store raw product event in S3"""
    product_id = product_data.get('id')
    event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))

    s3_key = (
        f"raw/shopify/products/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"hour={event_dt.strftime('%H')}/"
        f"product-{product_id}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    event_with_metadata = {
        'event_type': event_type,
        'event_time': event_time,
        'ingested_at': datetime.now(timezone.utc).isoformat(),
        'data': product_data
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(event_with_metadata, default=str),
        ContentType='application/json'
    )

    return s3_key
```

### 2.6 Abandoned Cart/Checkout Processor

Capture abandoned carts and checkouts for recovery analysis.

**File: lambdas/shopify-cart-processor/index.py**

```python
"""
Shopify Cart/Checkout Event Processor
Tracks abandoned carts and checkouts for recovery campaigns
"""
import json
import os
import boto3
from datetime import datetime, timezone
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BRAND = os.environ['BRAND']
S3_BUCKET = os.environ['S3_BUCKET']
ABANDONED_CART_TABLE = os.environ.get('ABANDONED_CART_TABLE', f"{BRAND}-abandoned-carts")


def handler(event, context):
    """Process cart/checkout events from EventBridge"""
    try:
        data = event.get('detail', {})
        event_type = event.get('detail-type')  # checkouts/create, checkouts/update, carts/create, carts/update
        event_time = event.get('time')

        cart_id = str(data.get('id') or data.get('token'))

        # Store raw event in S3
        if 'checkout' in event_type:
            s3_key = store_checkout_event(data, event_type, event_time)
        else:
            s3_key = store_cart_event(data, event_type, event_time)

        logger.info(f"Stored cart/checkout event to S3: {s3_key}")

        # Track abandoned checkouts in DynamoDB for recovery campaigns
        if 'checkout' in event_type and not data.get('completed_at'):
            track_abandoned_checkout(data, event_type)

        return {'statusCode': 200, 'cart_id': cart_id}

    except Exception as e:
        logger.error(f"Error processing cart/checkout event: {str(e)}", exc_info=True)
        raise


def store_checkout_event(checkout_data, event_type, event_time):
    """Store checkout event in S3"""
    checkout_token = checkout_data.get('token')
    event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))

    s3_key = (
        f"raw/shopify/checkouts/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"checkout-{checkout_token}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    event_with_metadata = {
        'event_type': event_type,
        'event_time': event_time,
        'ingested_at': datetime.now(timezone.utc).isoformat(),
        'data': checkout_data
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(event_with_metadata, default=str),
        ContentType='application/json'
    )

    return s3_key


def store_cart_event(cart_data, event_type, event_time):
    """Store cart event in S3"""
    cart_id = cart_data.get('id')
    event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))

    s3_key = (
        f"raw/shopify/carts/events/"
        f"date={event_dt.strftime('%Y-%m-%d')}/"
        f"cart-{cart_id}-{event_dt.strftime('%Y%m%d%H%M%S')}.json"
    )

    event_with_metadata = {
        'event_type': event_type,
        'event_time': event_time,
        'ingested_at': datetime.now(timezone.utc).isoformat(),
        'data': cart_data
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(event_with_metadata, default=str),
        ContentType='application/json'
    )

    return s3_key


def track_abandoned_checkout(checkout_data, event_type):
    """Track abandoned checkouts in DynamoDB for recovery"""
    table = dynamodb.Table(ABANDONED_CART_TABLE)

    item = {
        'checkout_token': checkout_data.get('token'),
        'customer_email': checkout_data.get('email'),
        'created_at': checkout_data.get('created_at'),
        'updated_at': checkout_data.get('updated_at'),
        'abandoned_checkout_url': checkout_data.get('abandoned_checkout_url'),
        'total_price': checkout_data.get('total_price'),
        'currency': checkout_data.get('currency'),
        'line_items': json.dumps(checkout_data.get('line_items', [])),
        'customer_id': str(checkout_data.get('customer', {}).get('id')) if checkout_data.get('customer') else None,
        '_tracked_at': datetime.now(timezone.utc).isoformat(),
    }

    # Remove None values
    item = {k: v for k, v in item.items() if v is not None}

    table.put_item(Item=item)
```

---

## Phase 3: Subscription Platform Integration (Recharge)

### 3.1 Recharge Webhook Setup

Recharge (or Bold, Appstle, etc.) manages the actual subscription lifecycle. This is **critical** for true churn analysis.

**What Recharge Provides:**
- Subscription status (active, cancelled, paused, expired)
- Next charge date
- Billing frequency changes
- Charge attempt results (success/failure)
- Cancellation reasons
- Subscription swaps/upgrades

### 3.2 Recharge Event Processor

**File: lambdas/recharge-event-processor/index.py**

```python
"""
Recharge Subscription Event Processor
Processes subscription lifecycle events from Recharge
"""
import json
import os
import boto3
from datetime import datetime, timezone
import logging
import hmac
import hashlib

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

BRAND = os.environ['BRAND']
S3_BUCKET = os.environ['S3_BUCKET']
SUBSCRIPTION_TABLE = os.environ.get('SUBSCRIPTION_TABLE', f"{BRAND}-subscriptions")
RECHARGE_WEBHOOK_SECRET = os.environ['RECHARGE_WEBHOOK_SECRET']
ALERT_TOPIC_ARN = os.environ.get('ALERT_TOPIC_ARN')


def handler(event, context):
    """
    Process Recharge webhooks

    Event types:
    - subscription/created
    - subscription/updated
    - subscription/cancelled
    - subscription/activated
    - subscription/paused
    - charge/paid
    - charge/failed
    - charge/refunded
    """
    try:
        # Verify webhook signature
        if not verify_recharge_signature(event):
            logger.warning("Invalid Recharge webhook signature")
            return {'statusCode': 401, 'body': 'Invalid signature'}

        body = json.loads(event.get('body', '{}'))
        event_type = body.get('type')
        payload = body.get('data', {})

        logger.info(f"Processing Recharge event: {event_type}")

        # Store raw event in S3
        s3_key = store_recharge_event(payload, event_type)

        # Route to appropriate handler
        if event_type.startswith('subscription/'):
            handle_subscription_event(payload, event_type)
        elif event_type.startswith('charge/'):
            handle_charge_event(payload, event_type)

        # Alert on critical events
        if event_type == 'subscription/cancelled':
            alert_on_cancellation(payload)
        elif event_type == 'charge/failed':
            alert_on_payment_failure(payload)

        return {'statusCode': 200}

    except Exception as e:
        logger.error(f"Error processing Recharge event: {str(e)}", exc_info=True)
        raise


def verify_recharge_signature(event):
    """Verify Recharge webhook signature"""
    signature = event.get('headers', {}).get('x-recharge-hmac-sha256')
    body = event.get('body', '')

    if not signature:
        return False

    computed_signature = hmac.new(
        RECHARGE_WEBHOOK_SECRET.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, computed_signature)


def store_recharge_event(payload, event_type):
    """Store raw Recharge event in S3"""
    now = datetime.now(timezone.utc)

    # Determine S3 path based on event type
    if 'subscription' in event_type:
        prefix = 'raw/recharge/subscriptions/events/'
        id_field = 'id'
    elif 'charge' in event_type:
        prefix = 'raw/recharge/charges/events/'
        id_field = 'id'
    else:
        prefix = 'raw/recharge/other/events/'
        id_field = 'id'

    record_id = payload.get(id_field, 'unknown')

    s3_key = (
        f"{prefix}"
        f"date={now.strftime('%Y-%m-%d')}/"
        f"hour={now.strftime('%H')}/"
        f"{event_type.replace('/', '-')}-{record_id}-{now.strftime('%Y%m%d%H%M%S')}.json"
    )

    event_with_metadata = {
        'event_type': event_type,
        'ingested_at': now.isoformat(),
        'data': payload
    }

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(event_with_metadata, default=str),
        ContentType='application/json'
    )

    logger.info(f"Stored Recharge event to S3: {s3_key}")
    return s3_key


def handle_subscription_event(subscription, event_type):
    """Update subscription status in DynamoDB"""
    table = dynamodb.Table(SUBSCRIPTION_TABLE)

    item = {
        'subscription_id': str(subscription.get('id')),
        'customer_id': str(subscription.get('customer_id')),
        'shopify_customer_id': str(subscription.get('shopify_customer_id')),
        'status': subscription.get('status'),  # active, cancelled, expired, paused
        'created_at': subscription.get('created_at'),
        'updated_at': subscription.get('updated_at'),
        'cancelled_at': subscription.get('cancelled_at'),
        'cancellation_reason': subscription.get('cancellation_reason'),
        'cancellation_reason_comments': subscription.get('cancellation_reason_comments'),
        'next_charge_scheduled_at': subscription.get('next_charge_scheduled_at'),
        'order_interval_frequency': subscription.get('order_interval_frequency'),
        'order_interval_unit': subscription.get('order_interval_unit'),  # day, week, month
        'product_title': subscription.get('product_title'),
        'price': subscription.get('price'),
        'quantity': subscription.get('quantity'),
        'shopify_product_id': str(subscription.get('shopify_product_id')) if subscription.get('shopify_product_id') else None,
        'shopify_variant_id': str(subscription.get('shopify_variant_id')) if subscription.get('shopify_variant_id') else None,
        'sku': subscription.get('sku'),
        'event_type': event_type,
        '_updated_at': datetime.now(timezone.utc).isoformat(),
    }

    # Remove None values
    item = {k: v for k, v in item.items() if v is not None}

    table.put_item(Item=item)
    logger.info(f"Updated subscription {item['subscription_id']} with status {item['status']}")


def handle_charge_event(charge, event_type):
    """Process charge events (billing attempts)"""
    table = dynamodb.Table(f"{BRAND}-subscription-charges")

    item = {
        'charge_id': str(charge.get('id')),
        'subscription_id': str(charge.get('subscription_id')),
        'customer_id': str(charge.get('customer_id')),
        'shopify_order_id': str(charge.get('shopify_order_id')) if charge.get('shopify_order_id') else None,
        'status': charge.get('status'),  # success, error, queued, skipped, refunded, partially_refunded
        'type': charge.get('type'),  # checkout, recurring
        'scheduled_at': charge.get('scheduled_at'),
        'processed_at': charge.get('processed_at'),
        'total_price': charge.get('total_price'),
        'subtotal_price': charge.get('subtotal_price'),
        'error': charge.get('error'),
        'error_type': charge.get('error_type'),
        'retry_date': charge.get('retry_date'),
        'billing_attempt_count': charge.get('billing_attempt_count', 0),
        'event_type': event_type,
        '_updated_at': datetime.now(timezone.utc).isoformat(),
    }

    item = {k: v for k, v in item.items() if v is not None}

    table.put_item(Item=item)
    logger.info(f"Recorded charge {item['charge_id']} with status {item['status']}")


def alert_on_cancellation(subscription):
    """Send alert when subscription is cancelled"""
    if not ALERT_TOPIC_ARN:
        return

    message = f"""
Subscription Cancelled

Subscription ID: {subscription.get('id')}
Customer ID: {subscription.get('customer_id')}
Product: {subscription.get('product_title')}
Cancellation Reason: {subscription.get('cancellation_reason')}
Comments: {subscription.get('cancellation_reason_comments')}
Cancelled At: {subscription.get('cancelled_at')}
"""

    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject='Subscription Cancelled',
        Message=message
    )


def alert_on_payment_failure(charge):
    """Send alert when charge fails"""
    if not ALERT_TOPIC_ARN:
        return

    # Only alert on multiple failures
    if charge.get('billing_attempt_count', 0) >= 2:
        message = f"""
Payment Failure Alert

Charge ID: {charge.get('id')}
Subscription ID: {charge.get('subscription_id')}
Customer ID: {charge.get('customer_id')}
Attempt Count: {charge.get('billing_attempt_count')}
Error: {charge.get('error')}
Error Type: {charge.get('error_type')}
Retry Date: {charge.get('retry_date')}
Amount: ${charge.get('total_price')}
"""

        sns.publish(
            TopicArn=ALERT_TOPIC_ARN,
            Subject=f'Payment Failure - Attempt #{charge.get("billing_attempt_count")}',
            Message=message
        )
```

---

## Phase 4: Payment Gateway Integration (Stripe)

### 4.1 Stripe Webhook Setup

Stripe webhooks provide payment-level detail not available in Shopify.

**What Stripe Provides:**
- Payment intent successes/failures
- Declined card reasons
- Disputes/chargebacks
- Invoice payment attempts (for subscriptions)
- Refund processing

### 4.2 Stripe Event Processor

**File: lambdas/stripe-event-processor/index.py**

```python
"""
Stripe Payment Event Processor
Processes payment events from Stripe
"""
import json
import os
import boto3
from datetime import datetime, timezone
import logging
import stripe

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

BRAND = os.environ['BRAND']
S3_BUCKET = os.environ['S3_BUCKET']
STRIPE_WEBHOOK_SECRET = os.environ['STRIPE_WEBHOOK_SECRET']
ALERT_TOPIC_ARN = os.environ.get('ALERT_TOPIC_ARN')

stripe.api_key = os.environ['STRIPE_API_KEY']


def handler(event, context):
    """
    Process Stripe webhooks

    Key event types:
    - charge.succeeded, charge.failed
    - payment_intent.succeeded, payment_intent.payment_failed
    - invoice.payment_succeeded, invoice.payment_failed
    - customer.subscription.updated, customer.subscription.deleted
    - charge.dispute.created, charge.dispute.closed
    """
    try:
        # Verify webhook signature
        signature = event.get('headers', {}).get('stripe-signature')
        body = event.get('body', '')

        try:
            stripe_event = stripe.Webhook.construct_event(
                body, signature, STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.warning("Invalid Stripe webhook payload")
            return {'statusCode': 400}
        except stripe.error.SignatureVerificationError:
            logger.warning("Invalid Stripe webhook signature")
            return {'statusCode': 401}

        event_type = stripe_event['type']
        payload = stripe_event['data']['object']

        logger.info(f"Processing Stripe event: {event_type}")

        # Store raw event in S3
        s3_key = store_stripe_event(stripe_event, event_type)

        # Route to handlers
        if 'charge' in event_type:
            handle_charge_event(payload, event_type)
        elif 'payment_intent' in event_type:
            handle_payment_intent_event(payload, event_type)
        elif 'invoice' in event_type:
            handle_invoice_event(payload, event_type)
        elif 'dispute' in event_type:
            handle_dispute_event(payload, event_type)

        return {'statusCode': 200}

    except Exception as e:
        logger.error(f"Error processing Stripe event: {str(e)}", exc_info=True)
        raise


def store_stripe_event(stripe_event, event_type):
    """Store raw Stripe event in S3"""
    now = datetime.now(timezone.utc)

    # Determine prefix based on event type
    if 'charge' in event_type and 'dispute' not in event_type:
        prefix = 'raw/stripe/charges/events/'
    elif 'payment_intent' in event_type:
        prefix = 'raw/stripe/payment_intents/events/'
    elif 'invoice' in event_type:
        prefix = 'raw/stripe/invoices/events/'
    elif 'dispute' in event_type:
        prefix = 'raw/stripe/disputes/events/'
    else:
        prefix = 'raw/stripe/other/events/'

    event_id = stripe_event.get('id', 'unknown')

    s3_key = (
        f"{prefix}"
        f"date={now.strftime('%Y-%m-%d')}/"
        f"hour={now.strftime('%H')}/"
        f"{event_type.replace('.', '-')}-{event_id}-{now.strftime('%Y%m%d%H%M%S')}.json"
    )

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(stripe_event, default=str),
        ContentType='application/json'
    )

    logger.info(f"Stored Stripe event to S3: {s3_key}")
    return s3_key


def handle_charge_event(charge, event_type):
    """Track charge successes/failures"""
    table = dynamodb.Table(f"{BRAND}-payment-attempts")

    item = {
        'charge_id': charge['id'],
        'customer_id': charge.get('customer'),
        'amount': charge['amount'] / 100,  # Convert from cents
        'currency': charge['currency'].upper(),
        'status': charge['status'],  # succeeded, pending, failed
        'paid': charge['paid'],
        'failure_code': charge.get('failure_code'),
        'failure_message': charge.get('failure_message'),
        'payment_method': charge.get('payment_method'),
        'created': datetime.fromtimestamp(charge['created'], tz=timezone.utc).isoformat(),
        'event_type': event_type,
        '_updated_at': datetime.now(timezone.utc).isoformat(),
    }

    # Extract metadata (often contains Shopify order ID)
    metadata = charge.get('metadata', {})
    if metadata:
        item['shopify_order_id'] = metadata.get('order_id')
        item['shopify_customer_id'] = metadata.get('customer_id')

    item = {k: v for k, v in item.items() if v is not None}

    table.put_item(Item=item)

    # Alert on high-value failed charges
    if event_type == 'charge.failed' and charge['amount'] > 10000:  # > $100
        alert_on_high_value_failure(charge)


def handle_payment_intent_event(payment_intent, event_type):
    """Track payment intent lifecycle"""
    logger.info(f"Payment intent {payment_intent['id']}: {payment_intent['status']}")

    # Store in DynamoDB if needed for real-time dashboard
    # Most data is preserved in S3 raw events


def handle_invoice_event(invoice, event_type):
    """Track subscription invoice payments"""
    table = dynamodb.Table(f"{BRAND}-invoice-payments")

    item = {
        'invoice_id': invoice['id'],
        'subscription_id': invoice.get('subscription'),
        'customer_id': invoice.get('customer'),
        'amount_due': invoice['amount_due'] / 100,
        'amount_paid': invoice['amount_paid'] / 100,
        'amount_remaining': invoice['amount_remaining'] / 100,
        'currency': invoice['currency'].upper(),
        'status': invoice['status'],  # draft, open, paid, uncollectible, void
        'attempt_count': invoice.get('attempt_count', 0),
        'next_payment_attempt': datetime.fromtimestamp(invoice['next_payment_attempt'], tz=timezone.utc).isoformat() if invoice.get('next_payment_attempt') else None,
        'created': datetime.fromtimestamp(invoice['created'], tz=timezone.utc).isoformat(),
        'event_type': event_type,
        '_updated_at': datetime.now(timezone.utc).isoformat(),
    }

    item = {k: v for k, v in item.items() if v is not None}
    table.put_item(Item=item)


def handle_dispute_event(dispute, event_type):
    """Track chargebacks/disputes"""
    table = dynamodb.Table(f"{BRAND}-disputes")

    item = {
        'dispute_id': dispute['id'],
        'charge_id': dispute.get('charge'),
        'amount': dispute['amount'] / 100,
        'currency': dispute['currency'].upper(),
        'reason': dispute['reason'],  # fraudulent, duplicate, product_not_received, etc.
        'status': dispute['status'],  # warning_needs_response, warning_under_review, won, lost
        'created': datetime.fromtimestamp(dispute['created'], tz=timezone.utc).isoformat(),
        'event_type': event_type,
        '_updated_at': datetime.now(timezone.utc).isoformat(),
    }

    item = {k: v for k, v in item.items() if v is not None}
    table.put_item(Item=item)

    # Always alert on disputes
    alert_on_dispute(dispute, event_type)


def alert_on_high_value_failure(charge):
    """Alert on high-value failed payment"""
    if not ALERT_TOPIC_ARN:
        return

    message = f"""
High-Value Payment Failure

Charge ID: {charge['id']}
Amount: ${charge['amount'] / 100:.2f} {charge['currency'].upper()}
Customer: {charge.get('customer')}
Failure Code: {charge.get('failure_code')}
Failure Message: {charge.get('failure_message')}
"""

    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f'High-Value Payment Failure - ${charge["amount"] / 100:.2f}',
        Message=message
    )


def alert_on_dispute(dispute, event_type):
    """Alert on chargeback/dispute"""
    if not ALERT_TOPIC_ARN:
        return

    message = f"""
Chargeback/Dispute Alert

Dispute ID: {dispute['id']}
Charge ID: {dispute.get('charge')}
Amount: ${dispute['amount'] / 100:.2f} {dispute['currency'].upper()}
Reason: {dispute['reason']}
Status: {dispute['status']}
Event: {event_type}
"""

    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f'Chargeback Alert - ${dispute["amount"] / 100:.2f}',
        Message=message
    )
```

---

## Phase 5: Data Quality Monitoring

### 5.1 Data Quality Checker Lambda

**File: lambdas/data-quality-checker/index.py**

```python
"""
Data Quality Monitoring Lambda
Runs hourly to check for data gaps, anomalies, and schema issues
"""
import json
import os
import boto3
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')
cloudwatch = boto3.client('cloudwatch')

BRAND = os.environ['BRAND']
S3_BUCKET = os.environ['S3_BUCKET']
ALERT_TOPIC_ARN = os.environ['ALERT_TOPIC_ARN']
ORDERS_TABLE = os.environ.get('ORDERS_TABLE', f"{BRAND}-orders-cache")


def handler(event, context):
    """
    Run data quality checks:
    1. Check for hourly data gaps
    2. Validate order counts are within expected range
    3. Check DynamoDB item counts
    4. Detect anomalies (sudden drops)
    """
    try:
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'checks': []
        }

        # Check 1: Hourly data gaps in S3
        gap_check = check_hourly_data_gaps()
        results['checks'].append(gap_check)

        # Check 2: Order count anomaly detection
        anomaly_check = check_order_count_anomalies()
        results['checks'].append(anomaly_check)

        # Check 3: DynamoDB health
        dynamodb_check = check_dynamodb_health()
        results['checks'].append(dynamodb_check)

        # Store results in S3
        store_quality_results(results)

        # Send CloudWatch metrics
        send_cloudwatch_metrics(results)

        # Alert on failures
        failed_checks = [c for c in results['checks'] if c['status'] == 'FAIL']
        if failed_checks:
            alert_on_quality_issues(failed_checks)

        return {'statusCode': 200, 'results': results}

    except Exception as e:
        logger.error(f"Error in data quality check: {str(e)}", exc_info=True)
        raise


def check_hourly_data_gaps():
    """Check if we have data for each hour in the last 24 hours"""
    now = datetime.now(timezone.utc)
    hours_to_check = 24
    missing_hours = []

    for hours_ago in range(hours_to_check):
        check_time = now - timedelta(hours=hours_ago)
        date_str = check_time.strftime('%Y-%m-%d')
        hour_str = check_time.strftime('%H')

        prefix = f"raw/shopify/orders/events/date={date_str}/hour={hour_str}/"

        response = s3.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=prefix,
            MaxKeys=1
        )

        if response.get('KeyCount', 0) == 0:
            missing_hours.append(f"{date_str} {hour_str}:00")

    status = 'PASS' if len(missing_hours) == 0 else 'FAIL'

    return {
        'check': 'hourly_data_gaps',
        'status': status,
        'missing_hours': missing_hours,
        'message': f"Found {len(missing_hours)} hours with no data"
    }


def check_order_count_anomalies():
    """Check if order count is suspiciously low compared to average"""
    # Get order count from last hour
    now = datetime.now(timezone.utc)
    last_hour = now - timedelta(hours=1)
    date_str = last_hour.strftime('%Y-%m-%d')
    hour_str = last_hour.strftime('%H')

    prefix = f"raw/shopify/orders/events/date={date_str}/hour={hour_str}/"

    response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    current_count = response.get('KeyCount', 0)

    # Get average from previous 7 days at same hour
    total_count = 0
    days_checked = 0

    for days_ago in range(1, 8):
        check_time = now - timedelta(days=days_ago)
        date_str = check_time.strftime('%Y-%m-%d')
        hour_str = check_time.strftime('%H')
        prefix = f"raw/shopify/orders/events/date={date_str}/hour={hour_str}/"

        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
        total_count += response.get('KeyCount', 0)
        days_checked += 1

    avg_count = total_count / days_checked if days_checked > 0 else 0

    # Alert if current count is < 50% of average
    threshold = avg_count * 0.5
    status = 'PASS' if current_count >= threshold or avg_count == 0 else 'FAIL'

    return {
        'check': 'order_count_anomaly',
        'status': status,
        'current_count': current_count,
        'average_count': round(avg_count, 1),
        'threshold': round(threshold, 1),
        'message': f"Current: {current_count}, Average: {round(avg_count, 1)}, Threshold: {round(threshold, 1)}"
    }


def check_dynamodb_health():
    """Check DynamoDB table health"""
    table = dynamodb.Table(ORDERS_TABLE)

    try:
        # Get item count
        response = table.scan(Select='COUNT', Limit=1000)
        item_count = response.get('Count', 0)

        # Check table status
        table_desc = table.meta.client.describe_table(TableName=ORDERS_TABLE)
        table_status = table_desc['Table']['TableStatus']

        status = 'PASS' if table_status == 'ACTIVE' else 'FAIL'

        return {
            'check': 'dynamodb_health',
            'status': status,
            'item_count': item_count,
            'table_status': table_status,
            'message': f"Table {table_status}, ~{item_count} items"
        }
    except Exception as e:
        return {
            'check': 'dynamodb_health',
            'status': 'FAIL',
            'error': str(e),
            'message': f"Error accessing DynamoDB: {str(e)}"
        }


def store_quality_results(results):
    """Store quality check results in S3"""
    now = datetime.now(timezone.utc)
    date_str = now.strftime('%Y-%m-%d')

    s3_key = f"metadata/data_quality/date={date_str}/quality-check-{now.strftime('%Y%m%d%H%M%S')}.json"

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(results, indent=2),
        ContentType='application/json'
    )


def send_cloudwatch_metrics(results):
    """Send data quality metrics to CloudWatch"""
    metrics = []

    for check in results['checks']:
        metrics.append({
            'MetricName': f"DataQuality_{check['check']}",
            'Value': 1 if check['status'] == 'PASS' else 0,
            'Unit': 'None',
            'Timestamp': datetime.now(timezone.utc)
        })

    if metrics:
        cloudwatch.put_metric_data(
            Namespace=f'{BRAND}/DataQuality',
            MetricData=metrics
        )


def alert_on_quality_issues(failed_checks):
    """Send SNS alert for failed quality checks"""
    if not ALERT_TOPIC_ARN:
        return

    message = "Data Quality Issues Detected:\n\n"

    for check in failed_checks:
        message += f"❌ {check['check']}: {check['message']}\n"
        if 'missing_hours' in check and check['missing_hours']:
            message += f"   Missing hours: {', '.join(check['missing_hours'][:5])}\n"

    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f'Data Quality Alert - {len(failed_checks)} Failed Checks',
        Message=message
    )
```

---

## Phase 3: Batch Historical Ingestion (Bulk Operations)

### 3.1 Shopify Bulk Operations Overview

**Best Practice: Use GraphQL Bulk Operations for historical data exports**

Benefits:
- No rate limiting (dedicated queue)
- Export entire dataset in single operation
- Returns JSONL files (easy to parse)
- Can export millions of records
- Free API calls (doesn't count against limits)

### 3.2 Bulk Export Lambda

**File: lambdas/shopify-bulk-export/index.py**

```python
"""
Shopify Bulk Operations Export
Submits GraphQL bulk queries to export historical order data
"""
import json
import os
import boto3
import logging
from datetime import datetime, timezone
from typing import Dict, Any
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3 = boto3.client('s3')
stepfunctions = boto3.client('stepfunctions')

# Environment variables
SHOPIFY_SHOP = os.environ['SHOPIFY_SHOP']
SHOPIFY_ACCESS_TOKEN = os.environ['SHOPIFY_ACCESS_TOKEN']
S3_BUCKET = os.environ['S3_BUCKET']
ENVIRONMENT = os.environ['ENVIRONMENT']

# Shopify GraphQL endpoint
GRAPHQL_URL = f"https://{SHOPIFY_SHOP}/admin/api/2024-01/graphql.json"


def handler(event, context):
    """
    Submit bulk operation to export orders

    Parameters (from event):
    - start_date: ISO format date to start export (optional)
    - end_date: ISO format date to end export (optional)
    - export_type: 'orders', 'customers', 'products' (default: 'orders')
    """
    try:
        export_type = event.get('export_type', 'orders')
        start_date = event.get('start_date')
        end_date = event.get('end_date')

        logger.info(f"Starting bulk export for {export_type}")

        # Build GraphQL query
        query = build_bulk_query(export_type, start_date, end_date)

        # Submit bulk operation
        operation_id = submit_bulk_operation(query)

        logger.info(f"Bulk operation submitted: {operation_id}")

        return {
            'statusCode': 200,
            'operation_id': operation_id,
            'export_type': export_type,
            'start_date': start_date,
            'end_date': end_date
        }

    except Exception as e:
        logger.error(f"Error submitting bulk operation: {str(e)}", exc_info=True)
        raise


def build_bulk_query(export_type: str, start_date: str = None, end_date: str = None) -> str:
    """
    Build GraphQL bulk query based on export type
    """
    if export_type == 'orders':
        # Build query filter
        filters = []
        if start_date:
            filters.append(f'created_at:>={start_date}')
        if end_date:
            filters.append(f'created_at:<={end_date}')

        query_filter = ' AND '.join(filters) if filters else ''

        # Complete orders query with all needed fields
        query = f"""
        mutation {{
          bulkOperationRunQuery(
            query: \"\"\"
            {{
              orders(query: "{query_filter}") {{
                edges {{
                  node {{
                    id
                    name
                    email
                    createdAt
                    updatedAt
                    cancelledAt
                    cancelReason
                    totalPriceSet {{
                      shopMoney {{
                        amount
                        currencyCode
                      }}
                    }}
                    subtotalPriceSet {{
                      shopMoney {{
                        amount
                        currencyCode
                      }}
                    }}
                    totalDiscountsSet {{
                      shopMoney {{
                        amount
                        currencyCode
                      }}
                    }}
                    totalTaxSet {{
                      shopMoney {{
                        amount
                        currencyCode
                      }}
                    }}
                    financialStatus
                    fulfillmentStatus
                    tags
                    note
                    customer {{
                      id
                      email
                      firstName
                      lastName
                      phone
                      tags
                    }}
                    shippingAddress {{
                      city
                      province
                      zip
                      country
                      phone
                    }}
                    billingAddress {{
                      city
                      province
                      zip
                      country
                    }}
                    lineItems {{
                      edges {{
                        node {{
                          id
                          name
                          quantity
                          sku
                          variant {{
                            id
                            title
                          }}
                          originalUnitPriceSet {{
                            shopMoney {{
                              amount
                              currencyCode
                            }}
                          }}
                        }}
                      }}
                    }}
                    fulfillments {{
                      id
                      status
                      createdAt
                      updatedAt
                      trackingInfo {{
                        number
                        url
                        company
                      }}
                    }}
                  }}
                }}
              }}
            }}
            \"\"\"
          ) {{
            bulkOperation {{
              id
              status
            }}
            userErrors {{
              field
              message
            }}
          }}
        }}
        """

        return query.strip()

    else:
        raise ValueError(f"Unsupported export type: {export_type}")


def submit_bulk_operation(query: str) -> str:
    """
    Submit GraphQL bulk operation to Shopify
    """
    headers = {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN
    }

    response = requests.post(
        GRAPHQL_URL,
        headers=headers,
        json={'query': query},
        timeout=30
    )

    response.raise_for_status()
    result = response.json()

    # Check for errors
    if 'errors' in result:
        raise Exception(f"GraphQL errors: {result['errors']}")

    data = result.get('data', {}).get('bulkOperationRunQuery', {})

    if data.get('userErrors'):
        raise Exception(f"User errors: {data['userErrors']}")

    operation = data.get('bulkOperation', {})
    operation_id = operation.get('id')

    if not operation_id:
        raise Exception(f"No operation ID returned: {result}")

    return operation_id
```

### 3.3 Bulk Poll Status Lambda

**File: lambdas/shopify-bulk-poll/index.py**

```python
"""
Shopify Bulk Operations Status Poller
Polls bulk operation status until complete
"""
import json
import os
import logging
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SHOPIFY_SHOP = os.environ['SHOPIFY_SHOP']
SHOPIFY_ACCESS_TOKEN = os.environ['SHOPIFY_ACCESS_TOKEN']

GRAPHQL_URL = f"https://{SHOPIFY_SHOP}/admin/api/2024-01/graphql.json"


def handler(event, context):
    """
    Poll bulk operation status

    Returns:
    - status: RUNNING, COMPLETED, FAILED
    - url: Download URL (if COMPLETED)
    """
    try:
        # Check current bulk operation status
        status_info = get_bulk_operation_status()

        logger.info(f"Bulk operation status: {status_info['status']}")

        return {
            'statusCode': 200,
            'status': status_info['status'],
            'url': status_info.get('url'),
            'error_code': status_info.get('error_code'),
            'object_count': status_info.get('object_count')
        }

    except Exception as e:
        logger.error(f"Error polling bulk operation: {str(e)}", exc_info=True)
        raise


def get_bulk_operation_status() -> dict:
    """
    Query current bulk operation status via GraphQL
    """
    query = """
    {
      currentBulkOperation {
        id
        status
        errorCode
        createdAt
        completedAt
        objectCount
        fileSize
        url
      }
    }
    """

    headers = {
        'Content-Type': 'application/json',
        'X-Shopify-Access-Token': SHOPIFY_ACCESS_TOKEN
    }

    response = requests.post(
        GRAPHQL_URL,
        headers=headers,
        json={'query': query},
        timeout=30
    )

    response.raise_for_status()
    result = response.json()

    operation = result.get('data', {}).get('currentBulkOperation', {})

    if not operation:
        return {'status': 'NONE'}

    return {
        'status': operation.get('status'),
        'url': operation.get('url'),
        'error_code': operation.get('errorCode'),
        'object_count': operation.get('objectCount'),
        'file_size': operation.get('fileSize')
    }
```

### 3.4 Bulk Download Lambda

**File: lambdas/shopify-bulk-download/index.py**

```python
"""
Shopify Bulk Operations Downloader
Downloads JSONL file from Shopify and converts to Parquet
"""
import json
import os
import boto3
import logging
from datetime import datetime, timezone
import requests
import pyarrow as pa
import pyarrow.parquet as pq
from io import BytesIO
import gzip

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3 = boto3.client('s3')

# Environment variables
S3_BUCKET = os.environ['S3_BUCKET']
ENVIRONMENT = os.environ['ENVIRONMENT']
BRAND = os.environ['BRAND']


def handler(event, context):
    """
    Download bulk operation results and store in S3

    Parameters:
    - url: Download URL from bulk operation
    - export_type: 'orders', 'customers', etc.
    """
    try:
        download_url = event['url']
        export_type = event.get('export_type', 'orders')

        logger.info(f"Downloading bulk {export_type} from {download_url}")

        # Download JSONL file from Shopify
        jsonl_data = download_bulk_file(download_url)

        # Parse JSONL
        records = parse_jsonl(jsonl_data)
        logger.info(f"Parsed {len(records)} records")

        # Convert to Parquet
        parquet_buffer = convert_to_parquet(records)

        # Upload to S3
        s3_key = upload_to_s3(parquet_buffer, export_type)

        logger.info(f"Uploaded to s3://{S3_BUCKET}/{s3_key}")

        return {
            'statusCode': 200,
            's3_key': s3_key,
            'record_count': len(records),
            'export_type': export_type
        }

    except Exception as e:
        logger.error(f"Error downloading bulk file: {str(e)}", exc_info=True)
        raise


def download_bulk_file(url: str) -> bytes:
    """
    Download JSONL file from Shopify (may be gzipped)
    """
    response = requests.get(url, timeout=300, stream=True)
    response.raise_for_status()

    # Shopify returns gzipped JSONL
    content = response.content

    try:
        # Try to decompress
        return gzip.decompress(content)
    except:
        # Not gzipped
        return content


def parse_jsonl(data: bytes) -> list:
    """
    Parse JSONL data into list of records
    """
    records = []

    for line in data.decode('utf-8').splitlines():
        if line.strip():
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse line: {e}")
                continue

    return records


def convert_to_parquet(records: list) -> BytesIO:
    """
    Convert records to Parquet format
    """
    if not records:
        raise ValueError("No records to convert")

    # Flatten nested structures if needed
    flattened = [flatten_record(r) for r in records]

    # Create PyArrow table
    table = pa.Table.from_pylist(flattened)

    # Write to buffer
    buffer = BytesIO()
    pq.write_table(table, buffer, compression='snappy')
    buffer.seek(0)

    return buffer


def flatten_record(record: dict) -> dict:
    """
    Flatten nested Shopify GraphQL response
    """
    flat = {}

    for key, value in record.items():
        if isinstance(value, dict):
            # Flatten nested dicts (e.g., totalPriceSet.shopMoney.amount)
            for subkey, subvalue in value.items():
                flat[f"{key}_{subkey}"] = subvalue
        elif isinstance(value, list):
            # Convert lists to JSON strings
            flat[key] = json.dumps(value)
        else:
            flat[key] = value

    return flat


def upload_to_s3(buffer: BytesIO, export_type: str) -> str:
    """
    Upload Parquet file to S3 with date partitioning
    """
    today = datetime.now(timezone.utc)

    s3_key = (
        f"raw/shopify/{export_type}/snapshots/"
        f"date={today.strftime('%Y-%m-%d')}/"
        f"{export_type}_{today.strftime('%Y%m%d_%H%M%S')}.parquet"
    )

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=buffer.getvalue(),
        ContentType='application/octet-stream',
        Metadata={
            'export-type': export_type,
            'export-date': today.isoformat()
        }
    )

    return s3_key
```

### 3.5 Step Functions Orchestration

**File: infrastructure/step-functions/bulk-export-workflow.json**

```json
{
  "Comment": "Shopify Bulk Export Workflow",
  "StartAt": "SubmitBulkOperation",
  "States": {
    "SubmitBulkOperation": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:631046354185:function:marsmen-shopify-bulk-export-production",
      "ResultPath": "$.operation",
      "Next": "WaitForCompletion"
    },
    "WaitForCompletion": {
      "Type": "Wait",
      "Seconds": 30,
      "Next": "CheckStatus"
    },
    "CheckStatus": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:631046354185:function:marsmen-shopify-bulk-poll-production",
      "ResultPath": "$.status",
      "Next": "IsComplete"
    },
    "IsComplete": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.status.status",
          "StringEquals": "COMPLETED",
          "Next": "DownloadResults"
        },
        {
          "Variable": "$.status.status",
          "StringEquals": "FAILED",
          "Next": "OperationFailed"
        }
      ],
      "Default": "WaitForCompletion"
    },
    "DownloadResults": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:631046354185:function:marsmen-shopify-bulk-download-production",
      "InputPath": "$.status",
      "ResultPath": "$.download",
      "Next": "Success"
    },
    "Success": {
      "Type": "Succeed"
    },
    "OperationFailed": {
      "Type": "Fail",
      "Error": "BulkOperationFailed",
      "Cause": "Shopify bulk operation failed"
    }
  }
}
```

---

## Phase 4: Data Processing & Transformation

### 4.1 AWS Glue ETL Job

**Best Practice: Use Glue for processing raw events into curated datasets**

**File: glue/jobs/process_orders.py**

```python
"""
AWS Glue ETL Job: Process Raw Shopify Orders
Reads raw events, deduplicates, enriches, and writes to processed layer
"""
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import datetime

# Initialize contexts
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'S3_BUCKET', 'PROCESSING_DATE'])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# Parameters
S3_BUCKET = args['S3_BUCKET']
PROCESSING_DATE = args['PROCESSING_DATE']  # Format: YYYY-MM-DD

print(f"Processing orders for date: {PROCESSING_DATE}")

# Read raw events from S3
raw_events_path = f"s3://{S3_BUCKET}/raw/shopify/orders/events/date={PROCESSING_DATE}/"
raw_snapshots_path = f"s3://{S3_BUCKET}/raw/shopify/orders/snapshots/date={PROCESSING_DATE}/"

# Try to read from both sources
try:
    events_df = spark.read.json(raw_events_path)
    print(f"Loaded {events_df.count()} events from events path")
except:
    events_df = None
    print("No events found")

try:
    snapshots_df = spark.read.parquet(raw_snapshots_path)
    print(f"Loaded {snapshots_df.count()} snapshots from snapshots path")
except:
    snapshots_df = None
    print("No snapshots found")

# Combine data sources
if events_df and snapshots_df:
    raw_df = events_df.union(snapshots_df)
elif events_df:
    raw_df = events_df
elif snapshots_df:
    raw_df = snapshots_df
else:
    raise Exception(f"No data found for {PROCESSING_DATE}")

print(f"Total raw records: {raw_df.count()}")

# Deduplicate by order_id (keep latest by updated_at)
window_spec = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc())
deduped_df = raw_df.withColumn("row_num", F.row_number().over(window_spec)) \
                   .filter(F.col("row_num") == 1) \
                   .drop("row_num")

print(f"After deduplication: {deduped_df.count()}")

# Add derived fields
enriched_df = deduped_df.withColumn(
    "is_subscription",
    F.when(
        (F.col("tags").contains("subscription")) |
        (F.col("tags").contains("recurring")),
        True
    ).otherwise(False)
).withColumn(
    "order_year",
    F.year(F.col("created_at"))
).withColumn(
    "order_month",
    F.month(F.col("created_at"))
).withColumn(
    "order_day",
    F.dayofmonth(F.col("created_at"))
).withColumn(
    "processing_timestamp",
    F.lit(datetime.now().isoformat())
)

# Write to processed layer
output_path = f"s3://{S3_BUCKET}/processed/shopify/orders_enriched/date={PROCESSING_DATE}/"

enriched_df.write \
    .mode("overwrite") \
    .parquet(output_path, compression="snappy")

print(f"Wrote {enriched_df.count()} processed orders to {output_path}")

# Write subscription orders to curated layer
subscription_df = enriched_df.filter(F.col("is_subscription") == True)

curated_monthly_path = f"s3://{S3_BUCKET}/curated/subscription_orders/subscription_type=monthly/date={PROCESSING_DATE}/"
curated_quarterly_path = f"s3://{S3_BUCKET}/curated/subscription_orders/subscription_type=quarterly/date={PROCESSING_DATE}/"

# Split by subscription type and write
subscription_df.filter(F.col("subscription_type") == "monthly") \
    .write.mode("overwrite").parquet(curated_monthly_path, compression="snappy")

subscription_df.filter(F.col("subscription_type") == "quarterly") \
    .write.mode("overwrite").parquet(curated_quarterly_path, compression="snappy")

print(f"Wrote {subscription_df.count()} subscription orders to curated layer")

job.commit()
```

### 4.2 Glue Crawler for Schema Discovery

**CloudFormation: glue-catalog.yaml**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Glue Catalog for Shopify Data Lake'

Parameters:
  Brand:
    Type: String
    Default: marsmen

  AccountId:
    Type: String
    Default: '631046354185'

Resources:
  # Glue Database
  ShopifyDatabase:
    Type: AWS::Glue::Database
    Properties:
      CatalogId: !Ref AWS::AccountId
      DatabaseInput:
        Name: !Sub '${Brand}_shopify'
        Description: 'Shopify data lake catalog'

  # Crawler for raw orders (events)
  RawOrdersEventsCrawler:
    Type: AWS::Glue::Crawler
    Properties:
      Name: !Sub '${Brand}-raw-orders-events'
      Role: !GetAtt GlueCrawlerRole.Arn
      DatabaseName: !Ref ShopifyDatabase
      Targets:
        S3Targets:
          - Path: !Sub 's3://${Brand}-data-lake-${AccountId}/raw/shopify/orders/events/'
      SchemaChangePolicy:
        UpdateBehavior: UPDATE_IN_DATABASE
        DeleteBehavior: LOG
      Schedule:
        ScheduleExpression: 'cron(0 2 * * ? *)'  # Daily at 2 AM

  # Crawler for processed orders
  ProcessedOrdersCrawler:
    Type: AWS::Glue::Crawler
    Properties:
      Name: !Sub '${Brand}-processed-orders'
      Role: !GetAtt GlueCrawlerRole.Arn
      DatabaseName: !Ref ShopifyDatabase
      Targets:
        S3Targets:
          - Path: !Sub 's3://${Brand}-data-lake-${AccountId}/processed/shopify/orders_enriched/'
      SchemaChangePolicy:
        UpdateBehavior: UPDATE_IN_DATABASE
        DeleteBehavior: LOG

  # Crawler for curated subscription orders
  CuratedSubscriptionOrdersCrawler:
    Type: AWS::Glue::Crawler
    Properties:
      Name: !Sub '${Brand}-curated-subscription-orders'
      Role: !GetAtt GlueCrawlerRole.Arn
      DatabaseName: !Ref ShopifyDatabase
      Targets:
        S3Targets:
          - Path: !Sub 's3://${Brand}-data-lake-${AccountId}/curated/subscription_orders/'
      SchemaChangePolicy:
        UpdateBehavior: UPDATE_IN_DATABASE
        DeleteBehavior: LOG

  # Glue Crawler IAM Role
  GlueCrawlerRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${Brand}-glue-crawler-role'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: glue.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole
      Policies:
        - PolicyName: S3Access
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - s3:GetObject
                  - s3:PutObject
                  - s3:ListBucket
                Resource:
                  - !Sub 'arn:aws:s3:::${Brand}-data-lake-${AccountId}'
                  - !Sub 'arn:aws:s3:::${Brand}-data-lake-${AccountId}/*'

Outputs:
  DatabaseName:
    Value: !Ref ShopifyDatabase
    Export:
      Name: !Sub '${Brand}-shopify-database'
```

---

## Phase 5: Deployment & Operations

### 5.1 Deployment Script

**File: deploy-shopify-ingestion.sh**

```bash
#!/bin/bash
set -e

BRAND=${1:-marsmen}
REGION=${2:-us-east-1}
PROFILE=${3:-marsmen-direct}

if [ -z "$4" ]; then
  echo "Usage: $0 <brand> <region> <profile> <partner-event-source-name> [event-bus-name]" >&2
  exit 1
fi

PARTNER_EVENT_SOURCE_NAME=$4
EVENT_BUS_NAME=${5:-${BRAND}-shopify-partner-bus}

echo "🚀 Deploying Shopify Ingestion Stack"
echo "  Brand: $BRAND"
echo "  Region: $REGION"
echo "  Partner Event Source: $PARTNER_EVENT_SOURCE_NAME"
echo "  Event Bus Name: $EVENT_BUS_NAME"

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $PROFILE)
S3_BUCKET="${BRAND}-data-lake-${ACCOUNT_ID}"

echo "  Account: $ACCOUNT_ID"
echo "  S3 Bucket: $S3_BUCKET"

# 1. Create S3 bucket
echo ""
echo "📦 Creating S3 Data Lake..."
aws s3api create-bucket \
  --bucket $S3_BUCKET \
  --region $REGION \
  --profile $PROFILE \
  2>/dev/null || echo "Bucket already exists"

aws s3api put-bucket-versioning \
  --bucket $S3_BUCKET \
  --versioning-configuration Status=Enabled \
  --profile $PROFILE

aws s3api put-bucket-encryption \
  --bucket $S3_BUCKET \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }' \
  --profile $PROFILE

echo "✅ S3 bucket configured"

# 2. Create DynamoDB table
echo ""
echo "💾 Creating DynamoDB table..."
aws dynamodb create-table \
  --table-name "${BRAND}-orders-cache" \
  --attribute-definitions \
    AttributeName=order_id,AttributeType=S \
    AttributeName=created_at,AttributeType=S \
    AttributeName=customer_email,AttributeType=S \
    AttributeName=order_number,AttributeType=S \
  --key-schema \
    AttributeName=order_id,KeyType=HASH \
    AttributeName=created_at,KeyType=RANGE \
  --global-secondary-indexes \
    "[
      {
        \"IndexName\": \"customer-email-index\",
        \"KeySchema\": [{\"AttributeName\":\"customer_email\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"order-number-index\",
        \"KeySchema\": [{\"AttributeName\":\"order_number\",\"KeyType\":\"HASH\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      }
    ]" \
  --billing-mode PAY_PER_REQUEST \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
  --region $REGION \
  --profile $PROFILE \
  2>/dev/null || echo "Table already exists"

# Enable TTL
aws dynamodb update-time-to-live \
  --table-name "${BRAND}-orders-cache" \
  --time-to-live-specification "Enabled=true,AttributeName=ttl" \
  --region $REGION \
  --profile $PROFILE

echo "✅ DynamoDB table configured"

# 3. Deploy EventBridge rules
echo ""
echo "📡 Deploying EventBridge infrastructure..."
aws cloudformation deploy \
  --template-file infrastructure/eventbridge-rules.yaml \
  --stack-name "${BRAND}-shopify-eventbridge" \
  --parameter-overrides \
    Brand=$BRAND \
    PartnerEventSourceName=$PARTNER_EVENT_SOURCE_NAME \
    EventBusName=$EVENT_BUS_NAME \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION \
  --profile $PROFILE

echo "✅ EventBridge stack deployed"

# 4. Deploy Lambda functions
echo ""
echo "λ Deploying Lambda functions..."

# Build and push Docker images
for FUNCTION in order-processor bulk-export bulk-poll bulk-download; do
  echo "  Building $FUNCTION..."

  cd lambdas/shopify-$FUNCTION

  # Build Docker image
  DOCKER_BUILDKIT=0 docker build --no-cache -t "${BRAND}-shopify-${FUNCTION}" .

  # Tag for ECR
  ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${BRAND}-shopify-${FUNCTION}"
  docker tag "${BRAND}-shopify-${FUNCTION}:latest" "$ECR_REPO:latest"

  # Create ECR repo if doesn't exist
  aws ecr create-repository \
    --repository-name "${BRAND}-shopify-${FUNCTION}" \
    --region $REGION \
    --profile $PROFILE \
    2>/dev/null || true

  # Login to ECR
  aws ecr get-login-password --region $REGION --profile $PROFILE | \
    docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

  # Push image
  docker push "$ECR_REPO:latest"

  echo "  ✅ $FUNCTION deployed"

  cd ../..
done

# 5. Deploy Glue catalog
echo ""
echo "🗂️  Deploying Glue Data Catalog..."
aws cloudformation deploy \
  --template-file infrastructure/glue-catalog.yaml \
  --stack-name "${BRAND}-shopify-glue" \
  --parameter-overrides \
    Brand=$BRAND \
    AccountId=$ACCOUNT_ID \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION \
  --profile $PROFILE

echo "✅ Glue catalog deployed"

echo ""
echo "✨ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Configure Shopify EventBridge partner event source"
echo "2. Add Shopify API credentials to Secrets Manager"
echo "3. Run initial bulk export"
echo "4. Test real-time event processing"
```

### 5.2 Monitoring & Alerting

**CloudFormation: monitoring.yaml**

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Monitoring and alerting for Shopify ingestion'

Parameters:
  Brand:
    Type: String
    Default: marsmen

  AlertEmail:
    Type: String
    Description: 'Email for alerts'

Resources:
  # SNS Topic for alerts
  AlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub '${Brand}-shopify-ingestion-alerts'
      Subscription:
        - Endpoint: !Ref AlertEmail
          Protocol: email

  # CloudWatch Alarm: Lambda errors
  OrderProcessorErrorAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${Brand}-order-processor-errors'
      AlarmDescription: 'Alert when order processor has errors'
      MetricName: Errors
      Namespace: AWS/Lambda
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 1
      Threshold: 5
      ComparisonOperator: GreaterThanThreshold
      Dimensions:
        - Name: FunctionName
          Value: !Sub '${Brand}-shopify-order-processor'
      AlarmActions:
        - !Ref AlertTopic

  # CloudWatch Alarm: DLQ messages
  DLQMessagesAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${Brand}-order-events-dlq'
      AlarmDescription: 'Alert when messages appear in DLQ'
      MetricName: ApproximateNumberOfMessagesVisible
      Namespace: AWS/SQS
      Statistic: Sum
      Period: 300
      EvaluationPeriods: 1
      Threshold: 1
      ComparisonOperator: GreaterThanThreshold
      Dimensions:
        - Name: QueueName
          Value: !Sub '${Brand}-shopify-order-events-dlq'
      AlarmActions:
        - !Ref AlertTopic

  # CloudWatch Dashboard
  IngestionDashboard:
    Type: AWS::CloudWatch::Dashboard
    Properties:
      DashboardName: !Sub '${Brand}-shopify-ingestion'
      DashboardBody: !Sub |
        {
          "widgets": [
            {
              "type": "metric",
              "properties": {
                "metrics": [
                  ["AWS/Lambda", "Invocations", {"stat": "Sum", "label": "Order Processor Invocations"}],
                  [".", "Errors", {"stat": "Sum", "label": "Errors"}],
                  [".", "Duration", {"stat": "Average", "label": "Avg Duration"}]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "${AWS::Region}",
                "title": "Order Processor Metrics",
                "yAxis": {
                  "left": {"label": "Count"}
                }
              }
            },
            {
              "type": "metric",
              "properties": {
                "metrics": [
                  ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", {"stat": "Sum"}],
                  [".", "ConsumedReadCapacityUnits", {"stat": "Sum"}]
                ],
                "period": 300,
                "stat": "Sum",
                "region": "${AWS::Region}",
                "title": "DynamoDB Capacity",
                "yAxis": {
                  "left": {"label": "Units"}
                }
              }
            }
          ]
        }
```

---

## Phase 6: Testing & Validation

### 6.1 Integration Tests

**File: tests/test_ingestion.py**

```python
"""
Integration tests for Shopify ingestion pipeline
"""
import boto3
import json
import time
from datetime import datetime, timezone

# AWS clients
lambda_client = boto3.client('lambda', region_name='us-east-1')
s3_client = boto3.client('s3', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Configuration
BRAND = 'marsmen'
ACCOUNT_ID = '631046354185'

S3_BUCKET = f"{BRAND}-data-lake-{ACCOUNT_ID}"
DYNAMODB_TABLE = f"{BRAND}-orders-cache"
ORDER_PROCESSOR_FUNCTION = f"{BRAND}-shopify-order-processor"


def test_event_processing():
    """Test that EventBridge events are processed correctly"""

    # Create mock Shopify order event
    mock_event = {
        "version": "0",
        "id": "test-event-123",
        "detail-type": "orders/create",
        "source": "aws.partner/shopify.com",
        "time": datetime.now(timezone.utc).isoformat(),
        "region": "us-east-1",
        "detail": {
            "id": 9999999999999,
            "email": "test@example.com",
            "created_at": "2025-10-03T12:00:00-04:00",
            "updated_at": "2025-10-03T12:00:00-04:00",
            "number": 12345,
            "order_number": 12345,
            "total_price": "99.99",
            "subtotal_price": "89.99",
            "total_tax": "10.00",
            "currency": "USD",
            "financial_status": "paid",
            "fulfillment_status": None,
            "tags": "subscription, monthly",
            "customer": {
                "id": 8888888888888,
                "email": "test@example.com",
                "first_name": "Test",
                "last_name": "Customer"
            },
            "shipping_address": {
                "city": "New York",
                "province": "NY",
                "zip": "10001",
                "country": "US"
            },
            "line_items": [
                {
                    "id": 7777777777777,
                    "sku": "MARS_Monthly",
                    "quantity": 1
                }
            ]
        }
    }

    # Invoke order processor Lambda
    print("Invoking order processor...")
    response = lambda_client.invoke(
        FunctionName=ORDER_PROCESSOR_FUNCTION,
        InvocationType='RequestResponse',
        Payload=json.dumps(mock_event)
    )

    result = json.loads(response['Payload'].read())
    print(f"Lambda response: {result}")

    assert result['statusCode'] == 200, "Lambda invocation failed"

    # Check S3 for raw event
    print("Checking S3 for raw event...")
    time.sleep(2)  # Wait for S3 eventual consistency

    today = datetime.now(timezone.utc)
    prefix = f"raw/shopify/orders/events/date={today.strftime('%Y-%m-%d')}/"

    s3_response = s3_client.list_objects_v2(
        Bucket=S3_BUCKET,
        Prefix=prefix
    )

    assert 'Contents' in s3_response, "No files found in S3"
    print(f"✅ Found {len(s3_response['Contents'])} files in S3")

    # Check DynamoDB for order
    print("Checking DynamoDB for order...")
    table = dynamodb.Table(DYNAMODB_TABLE)

    db_response = table.get_item(
        Key={
            'order_id': '9999999999999',
            'created_at': mock_event['detail']['created_at']
        }
    )

    assert 'Item' in db_response, "Order not found in DynamoDB"
    print(f"✅ Order found in DynamoDB: {db_response['Item']['order_id']}")

    print("\n✅ All tests passed!")


def test_bulk_export():
    """Test bulk export workflow"""

    # Start bulk export (last 7 days)
    bulk_export_function = f"{BRAND}-shopify-bulk-export"

    export_params = {
        'export_type': 'orders',
        'days_back': 7
    }

    print("Starting bulk export...")
    response = lambda_client.invoke(
        FunctionName=bulk_export_function,
        InvocationType='RequestResponse',
        Payload=json.dumps(export_params)
    )

    result = json.loads(response['Payload'].read())
    print(f"Bulk export response: {result}")

    assert result['statusCode'] == 200, "Bulk export failed"
    print(f"✅ Bulk export started: {result.get('operation_id')}")


if __name__ == '__main__':
    print("Running integration tests...\n")

    test_event_processing()
    print("\n" + "="*50 + "\n")

    test_bulk_export()
```

---

## Summary: Complete Greenfield Architecture

### Key Components

1. **S3 Data Lake** - Three-tier architecture (raw/processed/curated)
2. **EventBridge** - Real-time webhook ingestion from Shopify
3. **Lambda Functions** - Event processing, bulk operations
4. **DynamoDB** - Hot cache for recent orders (30-day TTL)
5. **AWS Glue** - Schema discovery, ETL transformations
6. **Step Functions** - Bulk export orchestration
7. **CloudWatch** - Monitoring, alerting, dashboards
8. **Athena** - Ad-hoc SQL queries on data lake

### Cost Estimate (Production)

- **S3 Storage**: ~$50/month (1TB standard, lifecycle policies)
- **DynamoDB**: ~$100/month (on-demand, 50K orders/month)
- **Lambda**: ~$50/month (real-time processing)
- **EventBridge**: ~$10/month (webhook events)
- **Glue**: ~$100/month (daily ETL jobs)
- **Total**: ~$310/month

### Implementation Timeline

- **Week 1**: Infrastructure setup (S3, DynamoDB, EventBridge)
- **Week 2**: Lambda development and deployment
- **Week 3**: Bulk operations and Step Functions
- **Week 4**: Glue ETL and data processing
- **Week 5**: Testing, monitoring, documentation
- **Week 6**: Production deployment and cutover

---

## Next Steps

### Status Checkpoint

- S3 data lake, DynamoDB hot stores, Glue catalog, and core Lambda images are scaffolded and ready for deployment via the new CloudFormation templates.
- Shopify Admin API token, Recharge webhook secret, and partner event source acceptance are still pending and block real-time ingestion.
- EventBridge routing, Recharge HTTP API, and Shopify bulk Step Functions workflow templates exist but require parameterization with live ECR image URIs before launch.
- Monitoring stack (SNS topic, alarms, dashboard) has not been deployed; no alert subscriptions are active yet.
- Glue ETL job and data quality scheduler templates are ready but still need the script upload, image URIs, and deployment to begin producing processed data and health metrics.
- CI/CD automation for building Lambda containers and updating CloudFormation stacks remains outstanding.

### Action Items

1. Populate Secrets Manager values for Shopify and Recharge, then create Shopify EventBridge webhooks and accept the partner event source in AWS once the shop is ready.
2. Run `scripts/build_push_lambdas.sh` to build/push all Lambda containers, capturing the resulting ECR image URIs for stack parameters.
3. Deploy `infrastructure/eventbridge-rules.yaml` with the partner source name and image URIs, then publish test orders/customers to confirm events reach the processors and DLQs stay empty.
4. Deploy `infrastructure/recharge-webhook.yaml`, update the Recharge portal to point at the new invoke URL, and validate signature handling plus DynamoDB writes.
5. Upload the Glue script to S3 and deploy `infrastructure/glue-jobs.yaml`, then execute the job to populate `processed/shopify/orders_enriched/` and (optionally) enable the scheduled trigger.
6. Deploy `infrastructure/shopify-bulk-workflow.yaml`, run a manual execution to confirm export → poll → download succeeds, and set a schedule once cadence is agreed.
7. Deploy `infrastructure/data-quality.yaml` with the alerts topic ARN so hourly quality checks publish metrics and SNS notifications.
8. Launch `infrastructure/monitoring.yaml` and configure the GitHub Actions workflows (secrets, production parameter files, job definitions) so image builds and stack deployments can run on demand.

This architecture follows AWS best practices and provides a scalable, cost-effective foundation for Shopify data ingestion. Let me know if you need clarification on any component!
