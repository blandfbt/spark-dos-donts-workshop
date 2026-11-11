-- Gold: tables shaped for the business. Same queries as section 3 of notebooks/01_bronze_to_gold_lab.
-- As materialized views, they are refreshed incrementally when the pipeline can, and fully when it must.

CREATE OR REFRESH MATERIALIZED VIEW lakeflow_gold_daily_dealer_sales_fact
COMMENT 'Daily orders, units, net revenue and margin per dealer, December 2025'
AS SELECT
  to_date(o.order_ts)                                      AS order_date,
  d.region,
  d.dealer_id,
  d.dealer_name,
  d.dealer_tier,
  count(*)                                                 AS orders,
  sum(o.quantity)                                          AS units,
  round(sum(o.net_revenue), 2)                             AS net_revenue,
  round(sum(o.net_revenue - o.quantity * p.unit_cost), 2)  AS margin
FROM lakeflow_silver_orders_fact o
JOIN lakeflow_silver_dealers_dim d ON o.dealer_id = d.dealer_id
JOIN lakeflow_silver_parts_dim p ON o.part_id = p.part_id
GROUP BY ALL;

CREATE OR REFRESH MATERIALIZED VIEW lakeflow_gold_category_region_fact
COMMENT 'December 2025 orders, units, net revenue and margin by region and part category'
AS SELECT
  d.region,
  p.category,
  count(*)                                                        AS orders,
  sum(o.quantity)                                                 AS units,
  round(sum(o.net_revenue), 2)                                    AS net_revenue,
  round(sum(o.net_revenue - o.quantity * p.unit_cost), 2)         AS margin,
  round(100 * sum(o.net_revenue - o.quantity * p.unit_cost) / sum(o.net_revenue), 2) AS margin_pct
FROM lakeflow_silver_orders_fact o
JOIN lakeflow_silver_dealers_dim d ON o.dealer_id = d.dealer_id
JOIN lakeflow_silver_parts_dim p ON o.part_id = p.part_id
GROUP BY d.region, p.category;
