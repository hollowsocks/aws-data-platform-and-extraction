# TripleWhale Hourly Dataset

| Column | Source | Description |
| --- | --- | --- |
| `timestamp_utc` | orders + ads | UTC hour bucket for the metric row |
| `region` | derived | Region label (US, CA, UK, AU) inferred from ad account mapping and shipping country |
| `meta_spend` | ads_table | Meta/Facebook spend for the hour & region |
| `google_spend` | ads_table | Google Ads spend for the hour & region |
| `total_spend` | derived | `meta_spend + google_spend` |
| `non_tracked_spend` | ads_table | Spend reported outside tracked channels |
| `new_customer_orders` | orders_table | Shopify orders placed by first-time buyers |
| `total_orders` | orders_table | All Shopify orders (new + returning) |
| `returning_orders` | derived | `total_orders - new_customer_orders` (clipped at 0) |
| `new_customer_sales` | orders_table | Revenue from new customers (USD) |
| `total_sales` | orders_table | Total Shopify revenue (new + returning) |
| `returning_sales` | derived | `total_sales - new_customer_sales` |
| `net_sales` | derived | `total_sales - refund_money` |
| `gross_sales` | orders_table | Gross revenue before discounts/refunds |
| `gross_product_sales` | orders_table | Gross product revenue |
| `refund_money` | orders_table | Refunds applied during the hour |
| `discount_amount` | orders_table | Total discounts (product + shipping) |
| `cost_of_goods` | orders_table | Cost of goods sold |
| `shipping_costs` | orders_table | Actual shipping spend |
| `estimated_shipping_costs` | orders_table | Estimated shipping costs (TripleWhale) |
| `handling_fees` | orders_table | Handling fee expenses |
| `payment_gateway_costs` | orders_table | Payment processor fees |
| `gross_profit` | derived | `total_sales - cost_of_goods - shipping_costs - handling_fees - payment_gateway_costs` |
| `gross_margin` | derived | `gross_profit / total_sales` |
| `discount_rate` | derived | `discount_amount / total_sales` |
| `refund_rate` | derived | `refund_money / total_sales` |
| `new_customer_aov` | derived | `new_customer_sales / new_customer_orders` |
| `new_customer_cpp` | derived | `total_spend / new_customer_orders` |
| `new_customer_roas` | derived | `new_customer_sales / total_spend` |
| `blended_roas` | derived | `total_sales / total_spend` |
| `currency` | orders_table | ISO currency (normalized to USD) |
| `impressions` | ads_table | Paid impressions for the hour |
| `clicks` | ads_table | Paid clicks for the hour |
| `ctr` | derived | `clicks / impressions` |
| `cpc` | derived | `total_spend / clicks` |
| `cpm` | derived | `(total_spend * 1000) / impressions` |
| `meta_purchases` | ads_table | Purchases attributed to Meta in-platform reporting |
| `onsite_purchases` | ads_table | On-site purchases captured by TripleWhale |
| `onsite_conversion_value` | ads_table | Revenue attributed to on-site purchases |
| `onsite_roas` | derived | `onsite_conversion_value / total_spend` |
| `search_impression_share` | ads_table | Weighted average search impression share (0-1) |
| `search_top_impression_share` | ads_table | Weighted average top-of-page impression share (0-1) |
| `search_absolute_top_impression_share` | ads_table | Weighted average absolute-top impression share (0-1) |
| `search_budget_lost_top_impression_share` | ads_table | Share of impressions lost to budget at top position |
| `search_budget_lost_absolute_top_impression_share` | ads_table | Share of impressions lost to budget at absolute top |
| `search_rank_lost_top_impression_share` | ads_table | Share of impressions lost to rank at top position |
| `search_rank_lost_impression_share` | ads_table | Share of impressions lost to rank overall |
| `search_top_impressions` | ads_table | Count of impressions shown in top slots |
| `search_absolute_top_impressions` | ads_table | Count of impressions shown in absolute top slot |
| `search_budget_lost_top_impressions` | ads_table | Impressions missed due to budget limits (top position) |
| `search_budget_lost_absolute_top_impressions` | ads_table | Impressions missed due to budget limits (absolute top) |
| `search_rank_lost_top_impressions` | ads_table | Impressions missed due to low rank (top position) |
| `search_rank_lost_impressions` | ads_table | Impressions missed due to low rank overall |
| `campaign_ai_recommendation` | ads_table | TripleWhale AI recommendation payload at campaign level (JSON string) |
| `campaign_ai_roas_pacing` | ads_table | AI pacing diagnostics for campaign ROAS (JSON string) |
| `adset_ai_recommendation` | ads_table | TripleWhale AI recommendation payload at ad set level (JSON string) |
| `adset_ai_roas_pacing` | ads_table | AI pacing diagnostics for ad set ROAS (JSON string) |
| `ad_ai_recommendation` | ads_table | TripleWhale AI recommendation payload at ad level (JSON string) |
| `ad_ai_roas_pacing` | ads_table | AI pacing diagnostics for ad ROAS (JSON string) |
| `channel_ai_recommendation` | ads_table | Channel-level AI recommendation payload (JSON string) |
| `channel_ai_roas_pacing` | ads_table | Channel-level AI pacing diagnostics (JSON string) |
| `local_datetime` | derived | Hour timestamp in the region's local timezone |
| `local_date` | derived | Local calendar date |
| `local_hour` | derived | String hour bucket in local time (YYYY-MM-DD HH:00) |
| `central_datetime` | derived | Timestamp converted to America/Chicago |
| `central_hour` | derived | Hour bucket in central time |

When adding new metrics, update both the ingestion transforms (in
`data-ingestion/triplewhale/`) and the Glue schema in
`infrastructure/triplewhale/triplewhale.yaml` so Athena and Superset stay in sync.
