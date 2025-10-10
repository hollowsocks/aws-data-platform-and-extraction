# Shopify EventBridge Webhook Setup

This directory contains the configuration and deployment scripts for setting up Shopify webhooks with AWS EventBridge.

## Files

- `shopify.app.toml` - Shopify app configuration with EventBridge webhook subscriptions
- `deploy-eventbridge-webhooks.sh` - Deployment script with interactive setup
- `README.md` - This file

## Quick Start

### 1. Install Prerequisites

```bash
# Install Shopify CLI
npm install -g @shopify/cli @shopify/app

# Verify installation
shopify version
```

### 2. Configure Event Source (One-Time Setup)

Before deploying webhooks, you need to create an EventBridge partner source:

**In Shopify Partners Dashboard:**
1. Go to https://partners.shopify.com/
2. Navigate to **Apps** → **Marsmen Data Platform** → **Extensions**
3. Click **Create extension**
4. Select **Amazon EventBridge**
5. Fill in:
   - **AWS Account ID**: `631046354185`
   - **AWS Region**: `us-east-1`
   - **Event Source Name**: Choose a unique name (e.g., `marsmen-production`)
6. Click **Create**
7. Copy the event source name

**Update Configuration:**

Run the deployment script to update the configuration:

```bash
cd /Users/huntersneed/Documents/Personal/Workflowsy/aws-data-platform-and-extraction/data-ingestion/shopify/eventbridge-app-setup

# Interactive mode (recommended)
./deploy-eventbridge-webhooks.sh

# Or update directly
./deploy-eventbridge-webhooks.sh --update marsmen-production
```

**In AWS Console:**

Accept the partner event source:

```bash
# List pending partner event sources
aws events list-partner-event-sources \
  --name-prefix "aws.partner/shopify.com" \
  --region us-east-1 \
  --profile marsmen-direct

# Create event bus (replace <EVENT-SOURCE-NAME>)
export PARTNER_SOURCE="aws.partner/shopify.com/a61950a2cbd5f32876b0b55587ec7a27/<EVENT-SOURCE-NAME>"

aws events create-event-bus \
  --name $PARTNER_SOURCE \
  --event-source-name $PARTNER_SOURCE \
  --region us-east-1 \
  --profile marsmen-direct

# Verify event bus created
aws events describe-event-bus \
  --name $PARTNER_SOURCE \
  --region us-east-1 \
  --profile marsmen-direct
```

### 3. Deploy Webhooks

```bash
# Interactive deployment (recommended)
./deploy-eventbridge-webhooks.sh

# Or deploy directly
./deploy-eventbridge-webhooks.sh --deploy
```

### 4. Verify Setup

```bash
# Check webhook subscriptions in Shopify Admin
open https://c9095d-2.myshopify.com/admin/settings/notifications

# List event buses in AWS
aws events list-event-buses \
  --region us-east-1 \
  --profile marsmen-direct

# Check for partner event source
aws events list-partner-event-sources \
  --region us-east-1 \
  --profile marsmen-direct
```

## Webhook Topics Configured

The configuration includes webhooks for:

### Orders
- `orders/create` - New order created
- `orders/updated` - Order updated (payment, fulfillment, etc.)
- `orders/cancelled` - Order cancelled
- `orders/fulfilled` - Order fully fulfilled

### Customers
- `customers/create` - New customer created
- `customers/update` - Customer information updated

### Products
- `products/create` - New product created
- `products/update` - Product/variant/inventory updated

### Fulfillments
- `fulfillments/create` - New fulfillment created
- `fulfillments/update` - Fulfillment updated (tracking, status)

### Carts & Checkouts (Abandoned Cart Tracking)
- `carts/create` - Shopping cart created
- `carts/update` - Cart updated
- `checkouts/create` - Checkout initiated
- `checkouts/update` - Checkout progress updated

### App Lifecycle (HTTP Endpoints)
- `app/uninstalled` - App uninstalled (handled by app itself)
- `app/scopes_update` - App scopes changed (handled by app itself)

## Configuration Details

### AWS Configuration
- **Account ID**: `631046354185`
- **Region**: `us-east-1`
- **Profile**: `marsmen-direct`

### Shopify Configuration
- **App Name**: Marsmen Data Platform
- **Client ID**: `a61950a2cbd5f32876b0b55587ec7a27`
- **Shop Domain**: `c9095d-2.myshopify.com`
- **API Version**: `2024-10`

### Required Scopes
- `read_orders` - Read order data
- `read_customers` - Read customer information
- `read_products` - Read product catalog
- `read_fulfillments` - Read shipping data
- `read_inventory` - Read inventory levels

## Deployment Script Usage

```bash
# Interactive mode (walks through setup)
./deploy-eventbridge-webhooks.sh

# Check prerequisites only
./deploy-eventbridge-webhooks.sh --check

# Show setup instructions
./deploy-eventbridge-webhooks.sh --instructions

# Update event source name
./deploy-eventbridge-webhooks.sh --update <event-source-name>

# Deploy webhooks (requires completed setup)
./deploy-eventbridge-webhooks.sh --deploy

# Show help
./deploy-eventbridge-webhooks.sh --help
```

## Troubleshooting

### Error: "Event source name not configured"

**Solution**: You need to replace `<EVENT-SOURCE-NAME>` in `shopify.app.toml` with your actual event source name from Shopify Partners.

```bash
./deploy-eventbridge-webhooks.sh --update marsmen-production
```

### Error: "Shopify CLI not found"

**Solution**: Install Shopify CLI:

```bash
npm install -g @shopify/cli @shopify/app
```

### Error: "Partner event source not found in AWS"

**Solution**: The partner event source hasn't been created yet or isn't accepted in AWS.

1. Verify you created the EventBridge extension in Shopify Partners
2. Check for pending partner event sources:
   ```bash
   aws events list-partner-event-sources \
     --name-prefix "aws.partner/shopify.com" \
     --region us-east-1 \
     --profile marsmen-direct
   ```
3. Accept the event source by creating an event bus (see step 2 above)

### Webhooks not appearing in Shopify Admin

**Solution**:
1. Ensure the app is installed on your store
2. Deploy webhooks with `shopify app deploy`
3. Check app scopes are approved in Shopify admin

### Events not reaching AWS EventBridge

**Solution**:
1. Verify event bus status is `ACTIVE`:
   ```bash
   aws events describe-event-bus \
     --name "aws.partner/shopify.com/a61950a2cbd5f32876b0b55587ec7a27/<EVENT-SOURCE-NAME>" \
     --region us-east-1 \
     --profile marsmen-direct
   ```
2. Check CloudWatch Logs for EventBridge errors
3. Verify webhook subscriptions are active in Shopify Admin
4. Test by placing an order and checking AWS CloudWatch Events

## Next Steps

After successfully deploying webhooks:

1. **Deploy EventBridge Rules** - Deploy `infrastructure/eventbridge-rules.yaml` to route events to Lambda processors
2. **Test Event Flow** - Place a test order and verify events reach Lambda
3. **Monitor CloudWatch** - Check Lambda logs for event processing
4. **Verify S3 Storage** - Confirm raw events are stored in S3
5. **Check DynamoDB** - Verify order cache is populated

## Reference Links

- [Shopify EventBridge Documentation](https://shopify.dev/docs/apps/build/webhooks/subscribe/get-started?deliveryMethod=eventBridge)
- [AWS EventBridge Partner Events](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-saas.html)
- [Shopify Webhook Topics](https://shopify.dev/docs/api/admin-rest/latest/resources/webhook#event-topics)
- [Shopify CLI Documentation](https://shopify.dev/docs/api/shopify-cli)

## Support

For issues:
1. Check the troubleshooting section above
2. Review CloudWatch Logs for error messages
3. Verify configuration in `shopify.app.toml`
4. Check AWS EventBridge console for event source status
