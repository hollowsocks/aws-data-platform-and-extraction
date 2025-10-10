# Manual Setup Guide - Shopify Data Platform

This guide covers the **manual steps** required to set up the Shopify data ingestion platform. These steps cannot be automated and must be completed in the Shopify Admin UI and AWS Console.

---

## Prerequisites

Before starting, ensure you have:
- ✅ Access to Shopify Admin (with permissions to create webhooks and API credentials)
- ✅ AWS Console access with permissions for EventBridge, Secrets Manager, and IAM
- ✅ AWS CLI configured with appropriate profile
- ✅ (Optional) Recharge admin access if using subscription platform
- ✅ (Optional) Stripe admin access if tracking payment events

---

## ✅ Step 1: Create Shopify Admin API Access Token - COMPLETED

### Status
**Already configured** for Marsmen production environment.

### Configuration Details
- **Secret Name**: `marsmen/shopify-api/production`
- **Secret ARN**: `arn:aws:secretsmanager:us-east-1:631046354185:secret:marsmen/shopify-api/production-A5bdQY`
- **Shop Domain**: `c9095d-2.myshopify.com`
- **Region**: `us-east-1`
- **Account**: `631046354185`

### Keys in Secret
- ✅ `access_token` - Shopify Admin API token
- ✅ `shop_domain` - Store domain

---

<details>
<summary>📖 Instructions (for reference - already completed)</summary>

1. **Log into Shopify Admin**
   - Navigate to: `https://[your-shop].myshopify.com/admin`

2. **Go to Apps & Sales Channels**
   - Click **Settings** (bottom left)
   - Click **Apps and sales channels**

3. **Create Custom App** (if you haven't already)
   - Click **Develop apps**
   - If prompted, click **Allow custom app development**
   - Click **Create an app**
   - Name: `AWS Data Platform`
   - App developer: Select your user

4. **Configure Admin API Scopes**
   - Click **Configure Admin API scopes**
   - Enable the following **read** permissions:
     - ✅ `read_orders` - Order data
     - ✅ `read_customers` - Customer information
     - ✅ `read_products` - Product catalog
     - ✅ `read_fulfillments` - Shipping/fulfillment data
     - ✅ `read_inventory` - Inventory levels (optional)
   - Click **Save**

5. **Install the App**
   - Click **Install app** (top right)
   - Confirm installation

6. **Reveal and Copy Access Token**
   - Click **API credentials** tab
   - Under **Admin API access token**, click **Reveal token once**
   - ⚠️ **IMPORTANT**: Copy this token immediately - you cannot view it again
   - Store it securely (you'll add it to AWS Secrets Manager in Step 2)

</details>

---

## ✅ Step 2: Store Shopify Credentials in AWS Secrets Manager - COMPLETED

### Status
**Already configured** - Using existing secret `marsmen/shopify-api/production`

### Configuration Details
- **Secret ARN**: `arn:aws:secretsmanager:us-east-1:631046354185:secret:marsmen/shopify-api/production-A5bdQY`
- **Encryption**: AWS managed key (`aws/secretsmanager`)
- **Structure**: JSON with `access_token` and `shop_domain` keys

### ⚠️ Important for Infrastructure Deployment
When deploying CloudFormation stacks, use this secret ARN:
```
arn:aws:secretsmanager:us-east-1:631046354185:secret:marsmen/shopify-api/production-A5bdQY
```

---

<details>
<summary>📖 Instructions (for reference - already completed)</summary>

1. **Option A: Using AWS Console**

   a. Navigate to **AWS Secrets Manager**
   - Go to: https://console.aws.amazon.com/secretsmanager/
   - Select your region (e.g., `us-east-1`)

   b. **Create Secret for Shopify**
   - Click **Store a new secret**
   - Secret type: **Other type of secret**
   - Key/value pairs:
     ```
     Key: access_token
     Value: [paste your Shopify admin API token from Step 1]

     Key: shop_domain
     Value: [your-shop].myshopify.com
     ```
   - Encryption key: Use default (`aws/secretsmanager`)
   - Click **Next**

   c. **Name the Secret**
   - Secret name: `ShopifyAdminApiSecret`
   - Description: `Shopify Admin API credentials for data platform`
   - Click **Next**

   d. **Configure Rotation** (optional for now)
   - Leave as **Disable automatic rotation**
   - Click **Next**

   e. **Review and Store**
   - Review settings
   - Click **Store**
   - **Copy the ARN** - you'll need this for CloudFormation parameters

2. **Option B: Using AWS CLI**

   ```bash
   # Set your profile and region
   export AWS_PROFILE=marsmen-direct
   export AWS_REGION=us-east-1

   # Create Shopify secret
   aws secretsmanager create-secret \
     --name ShopifyAdminApiSecret \
     --description "Shopify Admin API credentials for data platform" \
     --secret-string '{
       "access_token": "shpat_xxxxxxxxxxxxxxxxxxxxx",
       "shop_domain": "your-shop.myshopify.com"
     }' \
     --region $AWS_REGION \
     --profile $AWS_PROFILE

   # Copy the ARN from the output
   ```

3. **Record the Secret ARN**
   - Format: `arn:aws:secretsmanager:us-east-1:631046354185:secret:ShopifyAdminApiSecret-XXXXXX`
   - You'll use this when deploying infrastructure

</details>

---

## Step 3: Create Shopify EventBridge Webhooks

### Why This Is Needed
Shopify sends real-time events (orders, customers, etc.) to AWS EventBridge for processing.

### Prerequisites
- AWS Account ID: `631046354185`
- AWS Region: `us-east-1` (or your preferred region)

### Instructions

1. **Navigate to Shopify Notifications**
   - In Shopify Admin, go to: **Settings** → **Notifications**
   - Scroll to **Webhooks** section

2. **Create EventBridge Webhook for Orders**
   - Click **Create webhook**
   - **Event**: Select `Order creation`
   - **Format**: `JSON`
   - **URL/Endpoint**: Select **Amazon EventBridge**
   - **AWS Region**: `us-east-1` (or your region)
   - **AWS Account ID**: `631046354185` (replace with your account)
   - Click **Save webhook**

3. **Repeat for Additional Events**
   Create webhooks for each of these events:
   - ✅ `Order creation` - New orders
   - ✅ `Order updated` - Order changes (fulfillment, cancellation, etc.)
   - ✅ `Customer creation` - New customers
   - ✅ `Customer updated` - Customer changes
   - ✅ `Product creation` - New products
   - ✅ `Product updated` - Product/inventory changes
   - ✅ `Fulfillment creation` - Shipping events
   - ✅ `Carts create` - Shopping cart tracking
   - ✅ `Checkouts create` - Abandoned checkout tracking
   - ✅ `Checkouts update` - Checkout progress

4. **Record Partner Event Source Name**
   - After creating webhooks, Shopify generates a partner event source
   - Format: `aws.partner/shopify.com/[shop-id]/default`
   - You can find this in the webhook details or by running Step 4

---

## Step 4: Accept Partner Event Source in AWS

### Why This Is Needed
AWS requires you to explicitly accept partner event sources before they can send events.

### Instructions

1. **List Pending Partner Event Sources**

   ```bash
   # Set your profile and region
   export AWS_PROFILE=marsmen-direct
   export AWS_REGION=us-east-1

   # List partner event sources
   aws events list-partner-event-sources \
     --name-prefix "aws.partner/shopify.com" \
     --region $AWS_REGION \
     --profile $AWS_PROFILE
   ```

   Look for output like:
   ```json
   {
     "PartnerEventSources": [
       {
         "Arn": "arn:aws:events:us-east-1::event-source/aws.partner/shopify.com/12345678/default",
         "Name": "aws.partner/shopify.com/12345678/default",
         "State": "PENDING"
       }
     ]
   }
   ```

2. **Copy the Partner Source Name**
   - Example: `aws.partner/shopify.com/12345678/default`
   - ⚠️ **Save this** - you'll need it for the EventBridge deployment

3. **Create Partner Event Bus**

   ```bash
   # Replace with your actual partner source name
   export PARTNER_SOURCE="aws.partner/shopify.com/12345678/default"

   # Create the event bus
   aws events create-event-bus \
     --name $PARTNER_SOURCE \
     --event-source-name $PARTNER_SOURCE \
     --region $AWS_REGION \
     --profile $AWS_PROFILE
   ```

4. **Verify Event Bus Created**

   ```bash
   # List event buses
   aws events list-event-buses \
     --name-prefix "aws.partner/shopify" \
     --region $AWS_REGION \
     --profile $AWS_PROFILE
   ```

   Look for `State: ACTIVE`

---

## Step 5: (Optional) Configure Recharge Webhooks

### Why This Is Needed
If you use Recharge for subscriptions, webhooks capture subscription lifecycle events.

### Prerequisites
- Recharge account with admin access
- AWS infrastructure deployed (specifically `recharge-webhook.yaml` stack)

### Instructions

1. **Deploy Recharge Infrastructure First**
   - Deploy `infrastructure/recharge-webhook.yaml` (see deployment guide)
   - Note the **API Gateway invoke URL** from stack outputs

2. **Create Recharge Webhook Secret**

   ```bash
   # Generate a random webhook secret
   export WEBHOOK_SECRET=$(openssl rand -hex 32)

   # Store in Secrets Manager
   aws secretsmanager create-secret \
     --name RechargeWebhookSecret \
     --description "Recharge webhook signing secret" \
     --secret-string "{\"webhook_secret\": \"$WEBHOOK_SECRET\"}" \
     --region $AWS_REGION \
     --profile $AWS_PROFILE

   # Save this secret - you'll configure it in Recharge
   echo "Webhook Secret: $WEBHOOK_SECRET"
   ```

3. **Configure Recharge Webhook**
   - Log into Recharge admin
   - Go to **Integrations** → **Webhooks**
   - Click **Create webhook**
   - **URL**: [Your API Gateway invoke URL from stack outputs]
   - **Version**: `2021-11` (or latest)
   - **Events**: Select all subscription events:
     - `subscription/created`
     - `subscription/updated`
     - `subscription/cancelled`
     - `subscription/activated`
     - `charge/paid`
     - `charge/failed`
   - **Secret**: Paste the webhook secret from step 2
   - Click **Save**

4. **Test Webhook**
   - Send a test event from Recharge
   - Check CloudWatch Logs for the Recharge processor Lambda
   - Verify event appears in S3 and DynamoDB

---

## Step 6: (Optional) Configure Stripe Webhooks

### Why This Is Needed
Stripe webhooks capture payment events, failures, and disputes for churn analysis.

### Prerequisites
- Stripe account with admin access
- AWS infrastructure deployed (Lambda or API Gateway endpoint)

### Instructions

1. **Create Stripe Webhook Endpoint**
   - Log into Stripe Dashboard: https://dashboard.stripe.com/
   - Go to **Developers** → **Webhooks**
   - Click **Add endpoint**

2. **Configure Endpoint**
   - **Endpoint URL**: [Your Lambda function URL or API Gateway endpoint]
   - **Description**: `AWS Data Platform - Payment Events`
   - **Events to send**: Select:
     - ✅ `charge.succeeded`
     - ✅ `charge.failed`
     - ✅ `charge.refunded`
     - ✅ `payment_intent.succeeded`
     - ✅ `payment_intent.payment_failed`
     - ✅ `invoice.payment_succeeded`
     - ✅ `invoice.payment_failed`
     - ✅ `customer.subscription.created`
     - ✅ `customer.subscription.updated`
     - ✅ `customer.subscription.deleted`
     - ✅ `charge.dispute.created`

3. **Reveal Signing Secret**
   - After creating the webhook, click to reveal the **Signing secret**
   - Format: `whsec_xxxxxxxxxxxxx`

4. **Store in Secrets Manager**

   ```bash
   aws secretsmanager create-secret \
     --name StripeWebhookSecret \
     --description "Stripe webhook signing secret" \
     --secret-string '{
       "webhook_secret": "whsec_xxxxxxxxxxxxx",
       "api_key": "sk_live_xxxxxxxxxxxxx"
     }' \
     --region $AWS_REGION \
     --profile $AWS_PROFILE
   ```

---

## Step 7: Subscribe to Alerts

### Why This Is Needed
Receive notifications when data quality issues or ingestion failures occur.

### Instructions

1. **Find SNS Topic ARN**
   - After deploying `infrastructure/monitoring.yaml`
   - Look for output: `AlertsTopicArn`
   - Format: `arn:aws:sns:us-east-1:631046354185:marsmen-data-platform-alerts`

2. **Subscribe Email to Topic**

   ```bash
   # Set your email and topic ARN
   export ALERT_EMAIL="ops-team@example.com"
   export TOPIC_ARN="arn:aws:sns:us-east-1:631046354185:marsmen-data-platform-alerts"

   # Subscribe email
   aws sns subscribe \
     --topic-arn $TOPIC_ARN \
     --protocol email \
     --notification-endpoint $ALERT_EMAIL \
     --region $AWS_REGION \
     --profile $AWS_PROFILE
   ```

3. **Confirm Subscription**
   - Check email inbox for confirmation message from AWS
   - Click **Confirm subscription** link

4. **(Optional) Subscribe Slack**
   - Use AWS Chatbot or custom Lambda to forward SNS to Slack
   - See AWS Chatbot documentation

---

## Step 8: Validation Checklist

After completing all manual steps, verify everything is configured correctly:

### Shopify Configuration
- [ ] Admin API access token created and stored in Secrets Manager
- [ ] EventBridge webhooks created for all required events (orders, customers, products, etc.)
- [ ] Partner event source shows as `ACTIVE` in AWS

### AWS Configuration
- [ ] `ShopifyAdminApiSecret` exists in Secrets Manager with `access_token` and `shop_domain`
- [ ] Partner event bus created and active
- [ ] SNS alerts topic subscription confirmed

### Optional Integrations
- [ ] Recharge webhook configured with signing secret (if applicable)
- [ ] Stripe webhook configured with signing secret (if applicable)

### Testing
- [ ] Place a test order in Shopify
- [ ] Verify event appears in CloudWatch Logs for order processor Lambda
- [ ] Check S3 for raw event JSON file
- [ ] Check DynamoDB for order cache entry

---

## Common Issues & Troubleshooting

### Issue: Partner event source not showing in AWS

**Solution**:
- Wait 5-10 minutes after creating webhooks in Shopify
- Verify AWS account ID and region are correct in Shopify webhook settings
- Check that webhooks are using "Amazon EventBridge" format (not HTTP)

### Issue: Events not reaching Lambda

**Solution**:
- Verify partner event bus is `ACTIVE`
- Check EventBridge rules are deployed and enabled
- Verify Lambda permissions allow EventBridge invocation
- Check CloudWatch Logs for Lambda errors

### Issue: Lambda can't access secrets

**Solution**:
- Verify Lambda execution role has `secretsmanager:GetSecretValue` permission
- Check secret name matches exactly what's in Lambda environment variables
- Ensure secret is in the same region as Lambda

### Issue: "Access token is invalid"

**Solution**:
- Verify you copied the complete token from Shopify (starts with `shpat_`)
- Check the custom app is installed in Shopify
- Ensure required API scopes are granted

---

## Next Steps

After completing this manual setup:

1. **Deploy Infrastructure** - Run CloudFormation deployments (see README.md)
2. **Build Lambda Containers** - Build and push to ECR (see deployment scripts)
3. **Test End-to-End** - Place test order and verify data flow
4. **Run Bulk Backfill** - Load historical data via Step Functions
5. **Set Up Monitoring** - Configure dashboards and alerts

### Future Follow-Ups
- Swap the placeholder fulfillment processor image with a dedicated container once the Lambda implementation is available; update `FulfillmentProcessorImageUri` in `ci/environments/prod/shopify/eventbridge.json` accordingly.
- Review GitHub repository variables (`AUTO_BUILD_LAMBDAS`, `AUTO_DEPLOY_INFRASTRUCTURE`, etc.) before each deployment window to ensure automation aligns with change-management policies.
- Populate `marsmen/recharge/webhook` with the real signing secret as soon as Recharge integration goes live; the stack currently deploys with an empty placeholder value.

---

## Reference: Parameter Values for Deployments

After completing manual setup, you'll have these values for CloudFormation parameters:

```yaml
# AWS Account & Region
AWSAccountID: "631046354185"
AWSRegion: "us-east-1"
Brand: "marsmen"
Environment: "production"

# ✅ For eventbridge-rules.yaml
PartnerEventSourceName: "aws.partner/shopify.com/XXXXX/default"  # From Step 4 (TO DO)

# ✅ For shopify-bulk-workflow.yaml (CONFIGURED)
ShopifySecretArn: "arn:aws:secretsmanager:us-east-1:631046354185:secret:marsmen/shopify-api/production-A5bdQY"
ShopifyShopDomain: "c9095d-2.myshopify.com"

# For recharge-webhook.yaml (optional)
RechargeSecretArn: "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:RechargeWebhookSecret-XXXXX"  # From Step 5

# For stripe-event-processor (optional)
StripeSecretArn: "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:StripeWebhookSecret-XXXXX"  # From Step 6

# For monitoring.yaml
AlertsEmail: "ops-team@example.com"  # Your ops email
```

---

## Security Best Practices

- ✅ **Never commit secrets to git** - Use Secrets Manager or parameter files in `.gitignore`
- ✅ **Rotate credentials regularly** - Set up secret rotation schedules
- ✅ **Use least privilege IAM** - Grant only required permissions
- ✅ **Enable CloudTrail** - Audit all API calls
- ✅ **Enable encryption** - Use KMS for S3, Secrets Manager, DynamoDB
- ✅ **Restrict webhook endpoints** - Validate webhook signatures
- ✅ **Monitor for anomalies** - Set up CloudWatch alarms

---

## Support

For issues or questions:
- Check CloudWatch Logs for error details
- Review the `SHOPIFY_INGESTION_BEST_PRACTICES_GUIDE.md` for architecture details
- See `SHOPIFY_INGESTION_BACKLOG.md` for implementation roadmap
