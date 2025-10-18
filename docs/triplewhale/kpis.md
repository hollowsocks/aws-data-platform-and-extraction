# KPI Definitions

| KPI | Formula | Notes |
| --- | --- | --- |
| **New Customer Orders** | `sum(new_customer_orders)` | Shopify orders placed by first-time buyers. |
| **New Customer Sales** | `sum(new_customer_sales)` | USD revenue from new customer orders. |
| **Total Sales** | `sum(total_sales)` | Includes returning revenue for blended KPIs. |
| **Total Spend** | `sum(meta_spend + google_spend)` | Paid media spend across Meta + Google. |
| **New Customer AOV** | `sum(new_customer_sales) / nullif(sum(new_customer_orders), 0)` | Average order value for new customers. |
| **New Customer CPP** | `sum(total_spend) / nullif(sum(new_customer_orders), 0)` | Customer acquisition cost proxy. |
| **New Customer ROAS** | `sum(new_customer_sales) / nullif(sum(total_spend), 0)` | Advertising efficiency against new customer revenue. |
| **Blended ROAS** | `sum(total_sales) / nullif(sum(total_spend), 0)` | MER-style blended return on ad spend. |
| **Onsite Purchases** | `sum(onsite_purchases)` | Optional metric promoted from `ads_table` (counts checkout events). |
| **Onsite ROAS** | `sum(onsite_conversion_value) / nullif(sum(total_spend), 0)` | Optional – compare against platform-reported ROAS. |

Add new KPIs by updating the hourly dataset in `data-ingestion/triplewhale/` and
refreshing the Superset bootstrap script. Sync KPI definitions with stakeholders
so dashboards and SQL queries use consistent formulas.
