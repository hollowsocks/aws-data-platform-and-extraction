#!/bin/bash
set -e

# =============================================================================
# Shopify EventBridge Webhooks Deployment Script
# =============================================================================
# This script helps deploy EventBridge webhook subscriptions using Shopify CLI
#
# Prerequisites:
# 1. Shopify CLI installed (npm install -g @shopify/cli @shopify/app)
# 2. Shopify Partners account with app created
# 3. AWS account (631046354185) with EventBridge enabled
# 4. Partner event source configured in Shopify Partners dashboard
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/shopify.app.toml"
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="631046354185"
APP_ID="4bc5548b8c12fee05ea56760bdfc6f34"
SHOP_ID="286352670721"

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# =============================================================================
# Pre-flight Checks
# =============================================================================

check_prerequisites() {
    print_header "Pre-flight Checks"

    # Check if Shopify CLI is installed
    if ! command -v shopify &> /dev/null; then
        print_error "Shopify CLI not found"
        echo ""
        echo "Install with: npm install -g @shopify/cli @shopify/app"
        exit 1
    fi
    print_success "Shopify CLI installed"

    # Check if config file exists
    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "Config file not found: $CONFIG_FILE"
        exit 1
    fi
    print_success "Config file found"

    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        print_warning "AWS CLI not found (optional but recommended)"
    else
        print_success "AWS CLI installed"
    fi

    # Check if event source name is configured
    if grep -q "<EVENT-SOURCE-NAME>" "$CONFIG_FILE"; then
        print_error "Event source name not configured in shopify.app.toml"
        echo ""
        echo "You need to replace <EVENT-SOURCE-NAME> with your actual event source name."
        echo "See instructions below to get your event source name."
        echo ""
        return 1
    fi
    print_success "Event source name configured"

    return 0
}

# =============================================================================
# Authentication Explanation
# =============================================================================

explain_authentication() {
    print_header "Understanding Shopify Authentication"

    echo "There are TWO different sets of credentials:"
    echo ""

    echo "1. Partner App Credentials (for this deployment script)"
    echo "   ─────────────────────────────────────────────────────"
    echo "   - Used by Shopify CLI to deploy webhook configurations"
    echo "   - Managed through Shopify Partners portal"
    echo "   - App Client ID: ${APP_ID}"
    echo "   - Authentication: Browser-based login when you run 'shopify app deploy'"
    echo "   - Access: Partners dashboard (https://partners.shopify.com/)"
    echo ""

    echo "2. Store Admin API Credentials (already in AWS Secrets Manager)"
    echo "   ────────────────────────────────────────────────────────────"
    echo "   - Used by Lambda functions to call Shopify APIs"
    echo "   - Secret: marsmen/shopify-api/production"
    echo "   - Contains: access_token, shop_domain"
    echo "   - Access: Direct API calls for bulk operations, data fetching"
    echo ""

    echo "How Authentication Works:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "When you run './deploy-eventbridge-webhooks.sh --deploy':"
    echo ""
    echo "1. Shopify CLI will open your browser"
    echo "2. You'll log in to Shopify Partners (not your store admin)"
    echo "3. Select your store to install/configure the app"
    echo "4. CLI deploys webhook subscriptions to that store"
    echo "5. Webhooks start sending events to EventBridge"
    echo ""
    echo "After deployment, your Lambdas will use the credentials in"
    echo "Secrets Manager to make API calls for bulk operations."
    echo ""
}

# =============================================================================
# Get Event Source Name
# =============================================================================

get_event_source_instructions() {
    print_header "How to Get Your Event Source Name"

    echo "STEP 1: Create EventBridge Partner Source in Shopify Partners"
    echo "────────────────────────────────────────────────────────────"
    echo "1. Go to: https://partners.shopify.com/"
    echo "2. Navigate to Apps → [Your App] → Extensions"
    echo "3. Click 'Create extension'"
    echo "4. Select 'Amazon EventBridge' as the extension type"
    echo "5. Fill in the details:"
    echo "   - AWS Account ID: ${AWS_ACCOUNT_ID}"
    echo "   - AWS Region: ${AWS_REGION}"
    echo "   - Event Source Name: Choose a unique name (e.g., 'marsmen-production')"
    echo ""
    echo "6. After creation, copy the full event source name"
    echo "   Format: aws.partner/shopify.com/${SHOP_ID}/<YOUR-EVENT-SOURCE-NAME>"
    echo ""

    echo "STEP 2: Update shopify.app.toml"
    echo "────────────────────────────────────────────────────────────"
    echo "Replace all instances of <EVENT-SOURCE-NAME> in shopify.app.toml with your"
    echo "event source name (just the last part, not the full ARN)"
    echo ""
    echo "Example:"
    echo "  Before: .../<EVENT-SOURCE-NAME>"
    echo "  After:  .../marsmen-production"
    echo ""

    echo "STEP 3: Accept Partner Event Source in AWS"
    echo "────────────────────────────────────────────────────────────"
    echo "Run this command to list pending partner event sources:"
    echo ""
    echo "  aws events list-partner-event-sources \\"
    echo "    --name-prefix 'aws.partner/shopify.com' \\"
    echo "    --region ${AWS_REGION} \\"
    echo "    --profile marsmen-direct"
    echo ""
    echo "Then create the event bus:"
    echo ""
    echo "  export PARTNER_SOURCE='aws.partner/shopify.com/${SHOP_ID}/<YOUR-EVENT-SOURCE-NAME>'"
    echo "  aws events create-event-bus \\"
    echo "    --name \$PARTNER_SOURCE \\"
    echo "    --event-source-name \$PARTNER_SOURCE \\"
    echo "    --region ${AWS_REGION} \\"
    echo "    --profile marsmen-direct"
    echo ""
}

# =============================================================================
# Update Config File
# =============================================================================

update_event_source_name() {
    local event_source_name=$1

    print_header "Updating Configuration"

    # Backup original file
    cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
    print_info "Created backup: ${CONFIG_FILE}.backup"

    # Replace placeholder with actual event source name
    sed -i.tmp "s/<EVENT-SOURCE-NAME>/${event_source_name}/g" "$CONFIG_FILE"
    rm -f "${CONFIG_FILE}.tmp"

    print_success "Updated event source name in config"

    # Show sample of updated config
    echo ""
    echo "Sample webhook configuration:"
    grep -A 1 "orders/create" "$CONFIG_FILE" | head -3
}

# =============================================================================
# Deploy Webhooks
# =============================================================================

deploy_webhooks() {
    print_header "Deploying Webhooks to Shopify"

    print_info "This will deploy webhook subscriptions defined in shopify.app.toml"
    echo ""

    # Change to config directory
    cd "$SCRIPT_DIR"

    # Deploy using Shopify CLI
    print_info "Running: shopify app deploy"
    echo ""

    if shopify app deploy; then
        print_success "Webhooks deployed successfully!"
        return 0
    else
        print_error "Deployment failed"
        return 1
    fi
}

# =============================================================================
# Verify Deployment
# =============================================================================

verify_deployment() {
    print_header "Verification Steps"

    echo "1. Check Webhook Subscriptions in Shopify Admin:"
    echo "   https://c9095d-2.myshopify.com/admin/settings/notifications"
    echo ""

    echo "2. Verify Partner Event Source in AWS:"
    echo "   aws events list-partner-event-sources \\"
    echo "     --region ${AWS_REGION} \\"
    echo "     --profile marsmen-direct"
    echo ""

    echo "3. Check Event Bus Status:"
    echo "   aws events list-event-buses \\"
    echo "     --region ${AWS_REGION} \\"
    echo "     --profile marsmen-direct"
    echo ""

    echo "4. Test with a Sample Order:"
    echo "   - Place a test order in your Shopify store"
    echo "   - Check AWS EventBridge console for incoming events"
    echo "   - Monitor CloudWatch Logs for Lambda processor execution"
    echo ""
}

# =============================================================================
# Interactive Mode
# =============================================================================

interactive_setup() {
    print_header "Shopify EventBridge Webhook Setup"

    echo "This script will help you deploy EventBridge webhooks to Shopify."
    echo ""

    # Check if event source is already configured
    if grep -q "<EVENT-SOURCE-NAME>" "$CONFIG_FILE"; then
        echo "Event source name is not configured yet."
        echo ""
        read -p "Do you want to see instructions for getting your event source name? (y/n) " -n 1 -r
        echo ""

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            get_event_source_instructions
            echo ""
            echo -e "${YELLOW}Please complete the setup in Shopify Partners and AWS, then run this script again.${NC}"
            exit 0
        fi

        echo ""
        read -p "Enter your event source name (just the last part, e.g., 'marsmen-production'): " event_source_name

        if [ -z "$event_source_name" ]; then
            print_error "Event source name cannot be empty"
            exit 1
        fi

        update_event_source_name "$event_source_name"
    fi

    echo ""
    read -p "Ready to deploy webhooks? (y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if deploy_webhooks; then
            echo ""
            verify_deployment
        fi
    else
        print_info "Deployment cancelled"
        exit 0
    fi
}

# =============================================================================
# Main
# =============================================================================

main() {
    case "${1:-}" in
        --check)
            check_prerequisites
            ;;
        --auth|--explain-auth)
            explain_authentication
            ;;
        --instructions)
            get_event_source_instructions
            ;;
        --update)
            if [ -z "$2" ]; then
                print_error "Usage: $0 --update <event-source-name>"
                exit 1
            fi
            update_event_source_name "$2"
            ;;
        --deploy)
            if check_prerequisites; then
                deploy_webhooks
                verify_deployment
            fi
            ;;
        --help)
            echo "Usage: $0 [OPTION]"
            echo ""
            echo "Options:"
            echo "  (no args)         Interactive mode (recommended)"
            echo "  --check          Check prerequisites"
            echo "  --auth           Explain authentication and credentials"
            echo "  --instructions   Show setup instructions"
            echo "  --update NAME    Update event source name in config"
            echo "  --deploy         Deploy webhooks (requires setup)"
            echo "  --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Interactive setup"
            echo "  $0 --auth                             # Understand credentials"
            echo "  $0 --update marsmen-production        # Update event source name"
            echo "  $0 --deploy                           # Deploy webhooks"
            ;;
        *)
            interactive_setup
            ;;
    esac
}

main "$@"
