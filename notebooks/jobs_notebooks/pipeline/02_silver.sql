-- Silver: typed, cleaned, one row per business entity.
-- Same rules as section 2 of notebooks/01_bronze_to_gold_lab. What the pipeline adds:
--   * the cleaning rules are EXPECTATIONS: rows that break them are dropped and counted in the pipeline's data quality metrics
--   * de-duplication is AUTO CDC: keep the latest version of each order_id (by sent_at), incrementally
--
-- Pipeline configuration (set by ../00_create_pipeline_and_job):
--   source_catalog / source_schema   dbx_workshop_dev / shared   (where sdd_dim_part lives, read-only)

-- 1 + 2: type and standardize every order line; rows that fail a rule are dropped (and counted)
CREATE OR REFRESH STREAMING TABLE lakeflow_silver_orders_valid (
  CONSTRAINT parseable_timestamp EXPECT (order_ts IS NOT NULL)   ON VIOLATION DROP ROW,
  CONSTRAINT known_dealer        EXPECT (dealer_id IS NOT NULL)  ON VIOLATION DROP ROW,
  CONSTRAINT positive_quantity   EXPECT (quantity > 0)           ON VIOLATION DROP ROW,
  CONSTRAINT parseable_price     EXPECT (unit_price IS NOT NULL) ON VIOLATION DROP ROW
)
COMMENT 'Typed and standardized order lines that pass every silver rule (may still contain re-sent duplicates)'
AS SELECT
  *,
  quantity * unit_price * (1 - discount_pct) AS net_revenue
FROM (
  SELECT
    try_cast(order_id AS BIGINT)                                         AS order_id,
    coalesce(try_to_timestamp(order_ts, "yyyy-MM-dd'T'HH:mm:ss'Z'"),
             try_to_timestamp(order_ts, 'MM/dd/yyyy HH:mm:ss'))          AS order_ts,
    try_cast(customer_id AS BIGINT)                                      AS customer_id,
    try_cast(dealer_id AS INT)                                           AS dealer_id,
    try_cast(part_id AS INT)                                             AS part_id,
    try_cast(quantity AS INT)                                            AS quantity,
    try_cast(regexp_replace(unit_price, '[$,]', '') AS DOUBLE)           AS unit_price,
    try_cast(discount_pct AS DOUBLE)                                     AS discount_pct,
    initcap(trim(channel))                                               AS channel,
    promo_code,
    try_to_timestamp(sent_at, "yyyy-MM-dd'T'HH:mm:ss'Z'")                AS sent_at,
    _source_file,
    _ingested_at
  FROM STREAM(lakeflow_bronze_orders_fact)
);

-- 3: one row per order_id, the latest version wins (the lab's QUALIFY row_number() ... = 1, done incrementally)
CREATE OR REFRESH STREAMING TABLE lakeflow_silver_orders_fact
COMMENT 'December 2025 order lines: typed, cleaned, one row per order_id';

CREATE FLOW lakeflow_silver_orders_dedupe AS AUTO CDC INTO lakeflow_silver_orders_fact
FROM STREAM(lakeflow_silver_orders_valid)
KEYS (order_id)
SEQUENCE BY sent_at
STORED AS SCD TYPE 1;

-- 4: quarantine the rows that failed a rule, with the reason, instead of silently losing them
CREATE OR REFRESH STREAMING TABLE lakeflow_quarantine_orders_fact
COMMENT 'Order lines that failed a silver rule'
AS SELECT *,
  CASE WHEN order_ts IS NULL THEN 'unparseable timestamp'
       WHEN dealer_id IS NULL THEN 'missing dealer'
       WHEN quantity IS NULL OR quantity <= 0 THEN 'invalid quantity'
       WHEN unit_price IS NULL THEN 'unparseable price' END AS reject_reason
FROM (
  SELECT
    try_cast(order_id AS BIGINT)                                         AS order_id,
    coalesce(try_to_timestamp(order_ts, "yyyy-MM-dd'T'HH:mm:ss'Z'"),
             try_to_timestamp(order_ts, 'MM/dd/yyyy HH:mm:ss'))          AS order_ts,
    try_cast(dealer_id AS INT)                                           AS dealer_id,
    try_cast(quantity AS INT)                                            AS quantity,
    try_cast(regexp_replace(unit_price, '[$,]', '') AS DOUBLE)           AS unit_price,
    _source_file
  FROM STREAM(lakeflow_bronze_orders_fact)
)
WHERE order_ts IS NULL OR dealer_id IS NULL OR quantity IS NULL OR quantity <= 0 OR unit_price IS NULL;

-- Dealers: one row per dealer, latest version, cleaned text
CREATE OR REFRESH MATERIALIZED VIEW lakeflow_silver_dealers_dim
COMMENT 'Dealer reference: one row per dealer, latest version, cleaned text'
AS SELECT
  CAST(dealer_id AS INT)                                              AS dealer_id,
  coalesce(nullif(trim(dealer_name), ''), concat('Unknown dealer ', dealer_id)) AS dealer_name,
  initcap(trim(region))                                               AS region,
  upper(trim(state))                                                  AS state,
  dealer_tier,
  to_timestamp(updated_at)                                            AS updated_at
FROM lakeflow_bronze_dealers_dim
QUALIFY row_number() OVER (PARTITION BY dealer_id ORDER BY to_timestamp(updated_at) DESC) = 1;

-- Parts: conformed from the shared parts catalog (already a clean Delta table)
CREATE OR REFRESH MATERIALIZED VIEW lakeflow_silver_parts_dim
COMMENT 'Parts reference: one row per part, only the columns gold needs'
AS SELECT part_id, part_name, category, list_price, unit_cost
FROM ${source_catalog}.${source_schema}.sdd_dim_part;
