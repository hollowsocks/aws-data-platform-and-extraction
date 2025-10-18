# KPI Definitions

| KPI | Formula | Notes |
| --- | --- | --- |
| **New Customer Orders** | `sum(new_customer_orders)` | Shopify orders placed by first-time buyers. |
| **Total Orders** | `sum(total_orders)` | All Shopify orders (new + returning). |
| **Returning Orders** | `sum(total_orders) - sum(new_customer_orders)` | Orders from repeat customers. |
| **New Customer Sales** | `sum(new_customer_sales)` | USD revenue from new customer orders. |
| **Total Sales** | `sum(total_sales)` | Includes returning revenue for blended KPIs. |
| **Net Sales** | `sum(total_sales) - sum(refund_money)` | Refund-adjusted revenue. |
| **Gross Profit** | `sum(total_sales) - sum(cost_of_goods) - sum(shipping_costs) - sum(payment_gateway_costs) - sum(handling_fees)` | Contribution after core fulfillment costs. |
| **Gross Margin** | `gross_profit / nullif(sum(total_sales), 0)` | Margin percentage. |
| **Total Spend** | `sum(meta_spend + google_spend)` | Paid media spend across Meta + Google. |
| **New Customer AOV** | `sum(new_customer_sales) / nullif(sum(new_customer_orders), 0)` | Average order value for new customers. |
| **New Customer CPP** | `sum(total_spend) / nullif(sum(new_customer_orders), 0)` | Customer acquisition cost proxy. |
| **New Customer ROAS** | `sum(new_customer_sales) / nullif(sum(total_spend), 0)` | Advertising efficiency against new customer revenue. |
| **Blended ROAS** | `sum(total_sales) / nullif(sum(total_spend), 0)` | MER-style blended return on ad spend. |
| **Discount Rate** | `sum(discount_amount) / nullif(sum(total_sales), 0)` | Percent of revenue given away in discounts. |
| **Refund Rate** | `sum(refund_money) / nullif(sum(total_sales), 0)` | Percent of revenue refunded. |
| **CTR** | `sum(clicks) / nullif(sum(impressions), 0)` | Paid-media click-through rate. |
| **CPC** | `sum(total_spend) / nullif(sum(clicks), 0)` | Cost per click. |
| **CPM** | `(sum(total_spend) * 1000) / nullif(sum(impressions), 0)` | Cost per thousand impressions. |
| **Onsite ROAS** | `sum(onsite_conversion_value) / nullif(sum(total_spend), 0)` | ROAS calculated from on-site conversions. |
| **Meta Purchases** | `sum(meta_purchases)` | Purchases attributed to Meta reporting. |
| **Onsite Purchases** | `sum(onsite_purchases)` | Purchases captured on-site (TripleWhale). |
| **Non-tracked Spend** | `sum(non_tracked_spend)` | Spend reported outside the tracked channels. |

Update this table whenever new columns are promoted to the dataset so dashboards
and downstream consumers stay aligned on the formulas.
