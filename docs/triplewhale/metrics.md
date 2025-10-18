# TripleWhale Hourly Dataset

| Column | Source | Description |
| --- | --- | --- |
| `timestamp_utc` | orders + ads | UTC hour bucket for the metric row |
| `region` | derived | Region label (US, CA, UK, AU) based on ad account mapping + shipping country |
| `meta_spend` | ads_table | Meta/Facebook spend for the hour & region |
| `google_spend` | ads_table | Google Ads spend for the hour & region |
| `total_spend` | derived | `meta_spend + google_spend` |
| `new_customer_orders` | orders_table | Orders flagged as new customers |
| `new_customer_sales` | orders_table | Revenue from new customers (USD) |
| `total_sales` | orders_table | Total Shopify revenue (new + returning) |
| `new_customer_cpp` | derived | `total_spend / new_customer_orders` (safe division) |
| `new_customer_aov` | derived | `new_customer_sales / new_customer_orders` |
| `new_customer_roas` | derived | `new_customer_sales / total_spend` |
| `blended_roas` | derived | `total_sales / total_spend` |
| `currency` | orders_table | Currency code (normalized to USD) |
| `local_datetime` | derived | Hour timestamp in the region's local timezone |
| `local_date` | derived | Local calendar date |
| `local_hour` | derived | String hour bucket in local time (YYYY-MM-DD HH:00) |
| `central_datetime` | derived | Timestamp converted to America/Chicago |
| `central_hour` | derived | String hour bucket in central time |

## Expansion Ideas

The TripleWhale SQL responses expose additional metrics that can be promoted into
this dataset when needed. Candidates include:

- **Orders**: `gross_sales`, `gross_product_sales`, `refund_money`, `discount_amount`,
  `cost_of_goods`, `shipping_costs`, `handling_fees`, `payment_gateway_costs`.
- **Advertising**: `impressions`, `clicks`, `onsite_purchases`, `onsite_conversion_value`,
  `meta_purchases`, `non_tracked_spend`, and attribution window breakdowns
  (`one_day_*`, `seven_day_*`, `twenty_eight_day_*`).
- **Engagement**: video view metrics (`three_second_video_view`, `thruplays`,
  `video_pXX_watched`) and Google Ads impression share statistics (`search_*`).

Whenever new columns are added:

1. Update the aggregation logic in `data-ingestion/triplewhale/src/triplewhale_ingestion/`.
2. Extend the Glue schema in `infrastructure/triplewhale/triplewhale.yaml`.
3. Regenerate the Superset dataset via `growth-reporting-engine/superset/bootstrap_dashboard.py`.
