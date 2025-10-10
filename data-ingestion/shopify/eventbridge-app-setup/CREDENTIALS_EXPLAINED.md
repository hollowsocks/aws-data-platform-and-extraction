# Shopify Credentials Explained

## TL;DR

**Two completely different sets of credentials:**

1. **Partner App Credentials** → Used by Shopify CLI to deploy webhooks (browser login)
2. **Store Admin API Token** → Used by Lambda functions to call APIs (in Secrets Manager)

---

## The Two Types of Credentials

### 1. Partner App Credentials (For Deployment)

**Purpose**: Deploy webhook configurations via Shopify CLI

**Where They Come From**:
- Created in **Shopify Partners portal** (https://partners.shopify.com/)
- App Client ID: `a61950a2cbd5f32876b0b55587ec7a27` (in shopify.app.toml)

**Authentication Flow**:
```
You run: ./deploy-eventbridge-webhooks.sh --deploy
    ↓
Shopify CLI opens browser
    ↓
You log in to Shopify Partners account
    ↓
CLI connects to Partner API
    ↓
Webhooks configured in your store
```

**Access Level**: Can manage app settings, webhooks, and extensions

**Stored Where**: Not stored! Browser-based OAuth login each time

**Used For**:
- ✅ Deploying webhook subscriptions
- ✅ Creating EventBridge extensions
- ✅ Managing app configuration
- ❌ NOT for making API calls to Shopify

---

### 2. Store Admin API Token (For Runtime)

**Purpose**: Lambda functions call Shopify APIs for bulk operations

**Where It Comes From**:
- Created in **Shopify Admin** → Apps → Custom Apps
- Stored in AWS Secrets Manager: `marsmen/shopify-api/production`

**Contains**:
```json
{
  "access_token": "shpat_xxxxxxxxxxxxx",
  "shop_domain": "c9095d-2.myshopify.com"
}
```

**Access Level**: Read-only scopes (orders, customers, products, fulfillments)

**Stored Where**:
- AWS Secrets Manager ARN: `arn:aws:secretsmanager:us-east-1:631046354185:secret:marsmen/shopify-api/production-A5bdQY`

**Used For**:
- ✅ Bulk GraphQL operations (historical data)
- ✅ API queries from Lambda functions
- ✅ Fetching order/customer/product data
- ❌ NOT for webhook deployment

---

## Visual Comparison

```
┌─────────────────────────────────────────────────────────────────┐
│                  DEPLOYMENT TIME                                 │
│                  (One-time setup)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  You → Shopify CLI → Partners API → Configure Webhooks          │
│                                                                  │
│  Authentication: Browser OAuth login to Partners portal          │
│  Credentials: Partner account (not stored locally)               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

                            ↓ (webhooks deployed)

┌─────────────────────────────────────────────────────────────────┐
│                    RUNTIME                                       │
│                    (Continuous operation)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Shopify → EventBridge → Lambda → (reads secret) → Shopify API  │
│                                                                  │
│  Authentication: Admin API token from Secrets Manager            │
│  Credentials: marsmen/shopify-api/production                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## What Happens When You Deploy

### Step 1: First Run (Authentication)

```bash
./deploy-eventbridge-webhooks.sh --deploy
```

**What happens**:
1. Script checks prerequisites
2. Shopify CLI runs: `shopify app deploy`
3. Browser opens → Log in to **Shopify Partners** (not store admin)
4. You select which store to install the app on
5. CLI sends webhook configuration to Shopify
6. Webhooks are created and start sending to EventBridge

**Important**: You're logging in to Partners portal (partners.shopify.com), not your store admin (c9095d-2.myshopify.com/admin)

### Step 2: Runtime (After Deployment)

**When an order is created**:
1. Shopify sends webhook → AWS EventBridge
2. EventBridge rule triggers Lambda
3. Lambda reads secret: `marsmen/shopify-api/production`
4. Lambda uses `access_token` to call Shopify Admin API (if needed)
5. Lambda stores data in S3/DynamoDB

---

## Common Confusion

### ❓ "Why do I need both?"

**Partner App Credentials**:
- Control the app's configuration (webhooks, scopes, extensions)
- Managed at the partner/organization level
- Can deploy to multiple stores

**Store Admin API Token**:
- Your app's access to a specific store's data
- Installed per store
- Used for reading/writing store data

### ❓ "Can I use my store admin login for deployment?"

**No**. The deployment uses Shopify Partners portal, which is separate from store admin.

- **Partners Portal** (partners.shopify.com) → Manage apps, deploy configurations
- **Store Admin** (yourstore.myshopify.com/admin) → Manage products, orders, customers

### ❓ "Where does the browser login get stored?"

It doesn't! Shopify CLI uses short-lived OAuth tokens that expire after the deployment session.

### ❓ "Do I need a Shopify Partners account?"

**Yes**, to deploy the app and configure webhooks. But you might already have one if you created the app with client_id `a61950a2cbd5f32876b0b55587ec7a27`.

---

## Security Comparison

| Aspect | Partner Credentials | Admin API Token |
|--------|-------------------|-----------------|
| **Scope** | App configuration | Store data access |
| **Duration** | Session-based (temporary) | Long-lived (until revoked) |
| **Storage** | Not stored (OAuth) | AWS Secrets Manager |
| **Rotation** | N/A (temporary tokens) | Manual (recommended quarterly) |
| **Access** | Partner account holders | Lambda IAM role only |
| **Risk if leaked** | App config could be changed | Store data could be read |

---

## How to Verify You Have Access

### Check Partner App Access

1. Go to https://partners.shopify.com/
2. Log in with your Shopify Partner account
3. Navigate to **Apps**
4. Look for app with Client ID: `a61950a2cbd5f32876b0b55587ec7a27`
5. You should see "Marsmen Data Platform" (or the app name)

If you don't see the app:
- You may not have access to the Partners organization
- Ask the original creator to add you as a collaborator
- Or create a new app (you'll get a new client_id)

### Check Store Admin API Token

```bash
# Verify secret exists
aws secretsmanager describe-secret \
  --secret-id marsmen/shopify-api/production \
  --profile marsmen-direct \
  --region us-east-1

# Get the token (will be masked)
aws secretsmanager get-secret-value \
  --secret-id marsmen/shopify-api/production \
  --profile marsmen-direct \
  --region us-east-1
```

---

## Deployment Workflow

### First Time Setup

```bash
# 1. Explain credentials (optional)
./deploy-eventbridge-webhooks.sh --auth

# 2. See setup instructions
./deploy-eventbridge-webhooks.sh --instructions

# 3. Create EventBridge extension in Partners portal
#    (manual step - see instructions)

# 4. Update config with event source name
./deploy-eventbridge-webhooks.sh --update marsmen-production

# 5. Deploy webhooks
./deploy-eventbridge-webhooks.sh --deploy
#    ↑ This will open browser for Partners login
```

### After Deployment

```bash
# Webhooks are now active
# EventBridge receives events automatically
# Lambdas use the Admin API token from Secrets Manager
# No manual authentication needed at runtime
```

---

## Troubleshooting

### "I don't have access to Shopify Partners"

**Solution**:
- Ask the app owner to invite you as a collaborator
- Or create a new custom app directly in your store admin (simpler for single-store use)

### "Browser login isn't working"

**Solution**:
- Make sure you're logging in to **partners.shopify.com** (not your store admin)
- Check if you have the correct permissions in the Partners organization
- Try logging out and back in to Partners portal first

### "Lambda can't access the secret"

**Solution**:
- This is the **Store Admin API token**, not Partner credentials
- Check Lambda IAM role has `secretsmanager:GetSecretValue` permission
- Verify secret exists: `aws secretsmanager describe-secret --secret-id marsmen/shopify-api/production`

---

## Summary

| Task | Credential Type | Authentication Method |
|------|----------------|----------------------|
| Deploy webhooks | Partner App | Browser OAuth login |
| Lambda API calls | Admin API token | Secrets Manager |
| EventBridge events | (none) | Automatic after setup |

**Key Takeaway**: You need Partners access for initial setup, but runtime uses the Admin API token that's already in Secrets Manager.
