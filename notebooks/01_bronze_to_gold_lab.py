# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · From bronze to gold: a hands-on lab
# MAGIC
# MAGIC **Apex Motorsports Parts** (a fictional company) gets its December 2025 orders as raw JSON files from the
# MAGIC order system, and its dealer list as a CSV export. Neither file is clean. In this lab you take both all
# MAGIC the way to business-ready **gold** tables, answer questions with **SQL**, and publish an **AI/BI dashboard**.
# MAGIC
# MAGIC ![Bronze to gold](./images/medallion_lab.png)
# MAGIC
# MAGIC | layer | what it holds | you build |
# MAGIC |---|---|---|
# MAGIC | 🥉 **Bronze** | raw data exactly as delivered, plus where and when it arrived | `endtoend_bronze_orders_fact`, `endtoend_bronze_dealers_dim` |
# MAGIC | 🥈 **Silver** | typed, cleaned, de-duplicated, one row per business entity | `endtoend_silver_orders_fact`, `endtoend_silver_dealers_dim`, `endtoend_silver_parts_dim`, `endtoend_quarantine_orders_fact` |
# MAGIC | 🥇 **Gold** | aggregated tables shaped for a question or a dashboard | `endtoend_gold_daily_dealer_sales_fact`, `endtoend_gold_category_region_fact` |
# MAGIC
# MAGIC ### How the lab works
# MAGIC
# MAGIC Every step comes in three cells:
# MAGIC
# MAGIC | cell | what to do |
# MAGIC |---|---|
# MAGIC | 📘 **Example** | run it and read it. It's a complete, working version of the pattern |
# MAGIC | 🧑‍💻 **Your turn** | write the next piece yourself, in the same language as the example. A **🧞 Genie Code prompt** is there if you want help: open Genie Code (`Cmd/Ctrl + I` in the cell, or the assistant side panel) and paste it |
# MAGIC | ✅ **Check** | run it to verify your result. If you're stuck, `reveal("<exercise>")` prints a solution and `catch_up("<exercise>")` builds the result so you can keep going |
# MAGIC
# MAGIC Python cells use PySpark; SQL cells start with `%sql`. Both run on the same serverless compute, and
# MAGIC both see the same tables: the configuration cell sets the workshop schema as the default.
# MAGIC
# MAGIC **Before you start:** the setup job must have run once. Attach **serverless** compute (environment 5 or later).
# MAGIC **Set your catalog and schema** in the `catalog` / `schema` widgets at the top, or in the first cell of
# MAGIC `config.py` (✏️ *Your catalog and schema*). Left empty, the values saved by the setup job are used.
# MAGIC Plan on about 45 minutes. Afterwards, continue with `02_spark_dos_and_donts`.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ./config

# COMMAND ----------

# DBTITLE 1,⚙️ Lab helpers (check, reveal, catch_up, dashboard builders)
# MAGIC %run ./lab_helpers

# COMMAND ----------

# DBTITLE 1,Start fresh (optional)
# Set START_FRESH = True (or run reset_lab()) to start the lab over. It drops every endtoend_* table and the lab
# checkpoints; the raw files and the workshop data are kept.
START_FRESH = AUTO_SOLVE
if START_FRESH:
    reset_lab()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Bronze: land the raw data as it arrived
# MAGIC
# MAGIC Bronze is your safety net. Keep **everything** the source sent, **unchanged**, plus a little lineage
# MAGIC (which file it came from, when you loaded it). When a cleaning rule turns out to be wrong later, you can
# MAGIC rebuild silver from bronze without asking the source system to send the data again.
# MAGIC
# MAGIC ### 1a · Look at the raw files

# COMMAND ----------

# DBTITLE 1,📘 Example: list the raw files and peek at one
for folder in ["orders_json", "dealers_csv"]:
    files = [f for f in dbutils.fs.ls(f"{LAB_RAW}/{folder}") if not f.name.startswith("_")]
    print(f"{folder}: {len(files)} files, {sum(f.size for f in files) / 1024**2:,.0f} MB")

first_json = next(f.path for f in dbutils.fs.ls(f"{LAB_RAW}/orders_json") if f.name.endswith(".json"))
print("\nFirst lines of", first_json.split("/")[-1])
print(dbutils.fs.head(first_json, 700))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1b · Ingest the orders with Auto Loader
# MAGIC
# MAGIC **Auto Loader** (`cloudFiles`) reads only files it hasn't seen before. Its checkpoint remembers the rest,
# MAGIC so you can rerun this cell every day and it picks up just the new files. A few choices are typical for bronze:
# MAGIC * **Every column stays a string.** Auto Loader infers JSON columns as strings unless you ask it to infer
# MAGIC   types. Typing happens in silver, where you can handle bad values on purpose.
# MAGIC * **`_rescued_data`** collects any field that doesn't fit the schema, so nothing is silently lost.
# MAGIC * **`_metadata.file_path`** records the source file of every row.
# MAGIC * **`trigger(availableNow=True)`** processes what's there and stops, like a batch job.
# MAGIC
# MAGIC 📚 [Auto Loader](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/) · [Schema inference and evolution](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema) · [File metadata column](https://docs.databricks.com/aws/en/ingestion/file-metadata-column)

# COMMAND ----------

# DBTITLE 1,📘 Example: Auto Loader → endtoend_bronze_orders_fact (Python)
(
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", f"{LAB_CHECKPOINTS}/bronze_orders")  # where the inferred schema is tracked
    .load(f"{LAB_RAW}/orders_json")
    .select(
        "*",
        F.col("_metadata.file_path").alias("_source_file"),
        F.current_timestamp().alias("_ingested_at"),
    )
    .writeStream.option("checkpointLocation", f"{LAB_CHECKPOINTS}/bronze_orders")
    .trigger(availableNow=True)
    .toTable("endtoend_bronze_orders_fact")
    .awaitTermination()
)

spark.sql("COMMENT ON TABLE endtoend_bronze_orders_fact IS 'December 2025 order lines exactly as delivered (JSON), with lineage columns'")
bronze_orders = spark.table("endtoend_bronze_orders_fact")
print(f"endtoend_bronze_orders_fact: {bronze_orders.count():,} rows")
bronze_orders.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1c · 🧑‍💻 Your turn: land the dealer list in bronze (Python)
# MAGIC
# MAGIC Load `raw_files/lab/dealers_csv/` into a table called **`endtoend_bronze_dealers_dim`**:
# MAGIC * read the CSV with its header row and keep **every column as a string** (don't infer types)
# MAGIC * add the same two lineage columns as the example: **`_source_file`** and **`_ingested_at`**
# MAGIC * keep **all** rows, including duplicates (that's silver's job)
# MAGIC * overwrite the table if it already exists, so the cell can be rerun
# MAGIC
# MAGIC This file is small and arrives in full every time, so a plain batch read (`spark.read`) is fine here.
# MAGIC Auto Loader is for folders that keep receiving new files.
# MAGIC
# MAGIC > 🧞 **Genie Code prompt:** *"Read the CSV files in the folder in `LAB_RAW + '/dealers_csv'` with PySpark, keeping
# MAGIC > all columns as strings. Add `_source_file` from `_metadata.file_path` and `_ingested_at` with the current
# MAGIC > timestamp, then overwrite the Delta table `endtoend_bronze_dealers_dim`."*

# COMMAND ----------

# DBTITLE 1,🧑‍💻 Your turn: endtoend_bronze_dealers_dim (Python)
# Write your code here: read f"{LAB_RAW}/dealers_csv", add _source_file and _ingested_at,
# and overwrite the table endtoend_bronze_dealers_dim.

pass

# COMMAND ----------

# DBTITLE 1,✅ Check: endtoend_bronze_dealers_dim
check("bronze_dealers")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1d · Profile bronze before you clean it
# MAGIC
# MAGIC Before writing cleaning rules, measure the problems. This query counts each kind of issue in the raw
# MAGIC orders. Every number here becomes a rule in silver.

# COMMAND ----------

# DBTITLE 1,📘 Example: profile the raw orders (SQL)
# MAGIC %sql
# MAGIC SELECT
# MAGIC   count(*)                                                                    AS raw_rows,
# MAGIC   count(*) - count(DISTINCT order_id)                                         AS duplicate_rows,
# MAGIC   count_if(order_ts NOT LIKE '____-__-__T%')                                  AS non_iso_timestamps,
# MAGIC   count_if(try_cast(unit_price AS DOUBLE) IS NULL)                            AS prices_not_plain_numbers,  -- '$12.50', 'N/A'
# MAGIC   count_if(try_cast(quantity AS INT) <= 0)                                    AS non_positive_quantities,
# MAGIC   count_if(dealer_id IS NULL)                                                 AS missing_dealers,
# MAGIC   count(DISTINCT channel)                                                     AS channel_spellings,
# MAGIC   count_if(_rescued_data IS NOT NULL)                                         AS rescued_rows
# MAGIC FROM endtoend_bronze_orders_fact

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Silver: typed, clean, one row per order
# MAGIC
# MAGIC ### 2a · Clean the orders
# MAGIC
# MAGIC The example below does what most silver tables do, in one SQL cell:
# MAGIC 1. **Type** every column, using `try_cast` / `try_to_timestamp` so bad values become `NULL` instead of failing the job.
# MAGIC 2. **Standardize** text (`initcap(trim(channel))`) and parse prices like `$12.50`.
# MAGIC 3. **De-duplicate**: when an order was sent twice, keep the latest version (`QUALIFY row_number() ... = 1`).
# MAGIC 4. **Quarantine** the rows that fail a rule, with the reason, instead of silently dropping them.
# MAGIC
# MAGIC 📚 [`try_to_timestamp`](https://docs.databricks.com/aws/en/sql/language-manual/functions/try_to_timestamp) · [`QUALIFY`](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-qualify) · [Medallion architecture](https://docs.databricks.com/aws/en/lakehouse/medallion)

# COMMAND ----------

# DBTITLE 1,📘 Example: endtoend_silver_orders_fact + endtoend_quarantine_orders_fact (SQL)
# MAGIC %sql
# MAGIC -- 1 + 2: type and standardize (bad values become NULL, nothing fails)
# MAGIC CREATE OR REPLACE TEMP VIEW endtoend_orders_typed AS
# MAGIC SELECT
# MAGIC   try_cast(order_id AS BIGINT)                                         AS order_id,
# MAGIC   coalesce(try_to_timestamp(order_ts, "yyyy-MM-dd'T'HH:mm:ss'Z'"),
# MAGIC            try_to_timestamp(order_ts, 'MM/dd/yyyy HH:mm:ss'))          AS order_ts,
# MAGIC   try_cast(customer_id AS BIGINT)                                      AS customer_id,
# MAGIC   try_cast(dealer_id AS INT)                                           AS dealer_id,
# MAGIC   try_cast(part_id AS INT)                                             AS part_id,
# MAGIC   try_cast(quantity AS INT)                                            AS quantity,
# MAGIC   try_cast(regexp_replace(unit_price, '[$,]', '') AS DOUBLE)           AS unit_price,
# MAGIC   try_cast(discount_pct AS DOUBLE)                                     AS discount_pct,
# MAGIC   initcap(trim(channel))                                               AS channel,
# MAGIC   promo_code,
# MAGIC   try_to_timestamp(sent_at, "yyyy-MM-dd'T'HH:mm:ss'Z'")                AS sent_at,
# MAGIC   _source_file,
# MAGIC   _ingested_at
# MAGIC FROM endtoend_bronze_orders_fact;
# MAGIC
# MAGIC -- 3: keep the rows that pass every rule, latest version of each order
# MAGIC CREATE OR REPLACE TABLE endtoend_silver_orders_fact
# MAGIC COMMENT 'December 2025 order lines: typed, cleaned, one row per order_id'
# MAGIC AS
# MAGIC SELECT *, quantity * unit_price * (1 - discount_pct) AS net_revenue
# MAGIC FROM endtoend_orders_typed
# MAGIC WHERE order_ts IS NOT NULL AND dealer_id IS NOT NULL AND quantity > 0 AND unit_price IS NOT NULL
# MAGIC QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY sent_at DESC) = 1;
# MAGIC
# MAGIC -- 4: quarantine the rest, with the reason
# MAGIC CREATE OR REPLACE TABLE endtoend_quarantine_orders_fact
# MAGIC COMMENT 'Order lines that failed a silver rule'
# MAGIC AS
# MAGIC SELECT *,
# MAGIC   CASE WHEN order_ts IS NULL THEN 'unparseable timestamp'
# MAGIC        WHEN dealer_id IS NULL THEN 'missing dealer'
# MAGIC        WHEN quantity IS NULL OR quantity <= 0 THEN 'invalid quantity'
# MAGIC        WHEN unit_price IS NULL THEN 'unparseable price' END AS reject_reason
# MAGIC FROM endtoend_orders_typed
# MAGIC WHERE order_ts IS NULL OR dealer_id IS NULL OR quantity IS NULL OR quantity <= 0 OR unit_price IS NULL;
# MAGIC
# MAGIC SELECT 'silver' AS layer, count(*) AS rows FROM endtoend_silver_orders_fact
# MAGIC UNION ALL SELECT concat('quarantine: ', reject_reason), count(*) FROM endtoend_quarantine_orders_fact GROUP BY reject_reason

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2b · Protect silver with constraints
# MAGIC
# MAGIC Cleaning rules in a query only protect the data that query writes. A Delta **CHECK constraint** protects
# MAGIC the table itself: any later write that breaks the rule fails, whoever runs it. The next cell adds two
# MAGIC constraints, then tries to insert a bad row on purpose.
# MAGIC
# MAGIC 📚 [Constraints on Databricks](https://docs.databricks.com/aws/en/tables/constraints)

# COMMAND ----------

# DBTITLE 1,📘 Example: CHECK constraints catch a bad write (Python + SQL)
for name, rule in [("positive_quantity", "quantity > 0"), ("known_dealer", "dealer_id IS NOT NULL")]:
    spark.sql(f"ALTER TABLE endtoend_silver_orders_fact DROP CONSTRAINT IF EXISTS {name}")
    spark.sql(f"ALTER TABLE endtoend_silver_orders_fact ADD CONSTRAINT {name} CHECK ({rule})")
    print(f"constraint {name}: CHECK ({rule})")

try:
    spark.sql("""
        INSERT INTO endtoend_silver_orders_fact (order_id, order_ts, dealer_id, part_id, quantity, unit_price, discount_pct, channel)
        VALUES (1, current_timestamp(), 7, 42, -5, 10.0, 0.0, 'Online')""")
    print("⚠️  the bad row was accepted")
except Exception as e:
    print("🛡️  rejected as expected:", str(e).strip().splitlines()[0][:160])

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2c · 🧑‍💻 Your turn: clean the dealers (SQL)
# MAGIC
# MAGIC Create **`endtoend_silver_dealers_dim`** from `endtoend_bronze_dealers_dim`, with **one row per `dealer_id`**:
# MAGIC * `dealer_id` as an `INT`, `updated_at` as a `TIMESTAMP`
# MAGIC * when a dealer appears more than once, keep the row with the **latest `updated_at`** (the old one has a stale tier)
# MAGIC * `region` trimmed and in title case (`"  MIDWEST"` → `Midwest`), `state` trimmed and upper case
# MAGIC * a blank `dealer_name` becomes `Unknown dealer <dealer_id>`
# MAGIC * keep `dealer_tier` as it is
# MAGIC
# MAGIC The silver orders example above has every function you need (`try_cast`, `trim`, `initcap`, `QUALIFY`).
# MAGIC
# MAGIC > 🧞 **Genie Code prompt:** *"Write a Databricks SQL `CREATE OR REPLACE TABLE endtoend_silver_dealers_dim AS SELECT ...` from
# MAGIC > `endtoend_bronze_dealers_dim` that keeps one row per dealer_id with the latest updated_at, casts dealer_id to INT and
# MAGIC > updated_at to TIMESTAMP, trims and title-cases region, upper-cases state, and replaces blank dealer_name with
# MAGIC > 'Unknown dealer ' followed by the id."*

# COMMAND ----------

# DBTITLE 1,🧑‍💻 Your turn: endtoend_silver_dealers_dim (SQL)
# MAGIC %sql
# MAGIC -- Write your CREATE OR REPLACE TABLE endtoend_silver_dealers_dim AS SELECT ... statement here,
# MAGIC -- replacing the placeholder query below.
# MAGIC
# MAGIC SELECT 'Replace this cell with your CREATE OR REPLACE TABLE endtoend_silver_dealers_dim statement' AS todo

# COMMAND ----------

# DBTITLE 1,✅ Check: endtoend_silver_dealers_dim
check("silver_dealers")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2d · Bring in the parts reference
# MAGIC
# MAGIC Not every silver table starts in bronze. The parts catalog is maintained in another system and is already a
# MAGIC clean Delta table (`dim_part`, shared with the rest of the workshop). Conform it into the lab with only the
# MAGIC columns gold needs. The lab's tables then follow one convention: `endtoend_<layer>_<entity>_<fact|dim>`.
# MAGIC Facts hold events (order lines, daily sales) and dims hold the things events refer to (dealers, parts).

# COMMAND ----------

# DBTITLE 1,📘 Example: endtoend_silver_parts_dim (SQL)
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE endtoend_silver_parts_dim
# MAGIC COMMENT 'Parts reference for the end-to-end lab: one row per part, only the columns gold needs'
# MAGIC AS
# MAGIC SELECT part_id, part_name, category, list_price, unit_cost
# MAGIC FROM dim_part;
# MAGIC
# MAGIC SELECT category, count(*) AS parts, round(avg(unit_cost / list_price), 3) AS avg_cost_ratio
# MAGIC FROM endtoend_silver_parts_dim GROUP BY category ORDER BY category

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Gold: tables shaped for the business
# MAGIC
# MAGIC Gold tables answer a specific need, such as a dashboard, a report or a model feature, so they are
# MAGIC aggregated and joined ahead of time. Consumers then read a few thousand rows instead of millions.
# MAGIC Add a `COMMENT` to every gold table. Genie spaces and Genie Code use these descriptions too.
# MAGIC
# MAGIC ### 3a · Daily sales per dealer

# COMMAND ----------

# DBTITLE 1,Make sure the earlier exercises exist
# Gold builds on your silver dealers and the parts dim. If one isn't there yet, this builds it from the reference
# solution, so the example below always works.
require("bronze_dealers", "silver_dealers", "silver_parts")

# COMMAND ----------

# DBTITLE 1,📘 Example: endtoend_gold_daily_dealer_sales_fact (SQL)
# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE endtoend_gold_daily_dealer_sales_fact
# MAGIC COMMENT 'Daily orders, units, net revenue and margin per dealer, December 2025'
# MAGIC AS
# MAGIC SELECT
# MAGIC   to_date(o.order_ts)                                      AS order_date,
# MAGIC   d.region,
# MAGIC   d.dealer_id,
# MAGIC   d.dealer_name,
# MAGIC   d.dealer_tier,
# MAGIC   count(*)                                                 AS orders,
# MAGIC   sum(o.quantity)                                          AS units,
# MAGIC   round(sum(o.net_revenue), 2)                             AS net_revenue,
# MAGIC   round(sum(o.net_revenue - o.quantity * p.unit_cost), 2)  AS margin
# MAGIC FROM endtoend_silver_orders_fact o
# MAGIC JOIN endtoend_silver_dealers_dim d ON o.dealer_id = d.dealer_id
# MAGIC JOIN endtoend_silver_parts_dim p ON o.part_id = p.part_id
# MAGIC GROUP BY ALL;
# MAGIC
# MAGIC SELECT * FROM endtoend_gold_daily_dealer_sales_fact ORDER BY order_date, net_revenue DESC LIMIT 10

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b · 🧑‍💻 Your turn: margin by region and category (SQL)
# MAGIC
# MAGIC The merchandising team wants to know which part categories make money in which regions. Create
# MAGIC **`endtoend_gold_category_region_fact`** with one row per **`region`** and **`category`** (from `endtoend_silver_parts_dim`) and these columns:
# MAGIC
# MAGIC | column | definition |
# MAGIC |---|---|
# MAGIC | `orders` | number of order lines |
# MAGIC | `units` | sum of `quantity` |
# MAGIC | `net_revenue` | sum of `net_revenue`, rounded to 2 decimals |
# MAGIC | `margin` | sum of `net_revenue - quantity * unit_cost`, rounded to 2 decimals |
# MAGIC | `margin_pct` | `100 * margin / net_revenue`, rounded to 2 decimals |
# MAGIC
# MAGIC > 🧞 **Genie Code prompt:** *"Create a gold table `endtoend_gold_category_region_fact` by joining `endtoend_silver_orders_fact` to
# MAGIC > `endtoend_silver_dealers_dim` on dealer_id and to `endtoend_silver_parts_dim` on part_id, grouped by region and category, with orders,
# MAGIC > units, net_revenue, margin (net_revenue minus quantity times unit_cost) and margin_pct, all rounded to 2 decimals."*

# COMMAND ----------

# DBTITLE 1,🧑‍💻 Your turn: endtoend_gold_category_region_fact (SQL)
# MAGIC %sql
# MAGIC -- Write your CREATE OR REPLACE TABLE endtoend_gold_category_region_fact AS SELECT ... statement here,
# MAGIC -- replacing the placeholder query below.
# MAGIC
# MAGIC SELECT 'Replace this cell with your CREATE OR REPLACE TABLE endtoend_gold_category_region_fact statement' AS todo

# COMMAND ----------

# DBTITLE 1,✅ Check: endtoend_gold_category_region_fact
check("gold_category_region")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Ask questions with SQL
# MAGIC
# MAGIC Gold tables are small and well-named, so questions become short queries. The two examples show a
# MAGIC ranking and a window function (`LAG`) for period-over-period change. (December's last week has only 3 days,
# MAGIC which is why it drops: a good reason to compare complete periods.) The exercises then ask you to write
# MAGIC your own queries. Save each answer as a **temp view** so the check cell can read it.
# MAGIC
# MAGIC 📚 [Window functions](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-window-functions) · [`GROUP BY ALL`](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-qry-select-groupby)

# COMMAND ----------

# DBTITLE 1,📘 Example: top 10 dealers in December (SQL)
# MAGIC %sql
# MAGIC SELECT dealer_name, region, dealer_tier, sum(orders) AS orders, round(sum(net_revenue), 0) AS net_revenue
# MAGIC FROM endtoend_gold_daily_dealer_sales_fact
# MAGIC GROUP BY ALL
# MAGIC ORDER BY net_revenue DESC
# MAGIC LIMIT 10

# COMMAND ----------

# DBTITLE 1,📘 Example: week-over-week revenue change by region (SQL)
# MAGIC %sql
# MAGIC WITH weekly AS (
# MAGIC   SELECT region, date_trunc('week', order_date) AS week, sum(net_revenue) AS net_revenue
# MAGIC   FROM endtoend_gold_daily_dealer_sales_fact
# MAGIC   GROUP BY ALL
# MAGIC )
# MAGIC SELECT region, week, round(net_revenue, 0) AS net_revenue,
# MAGIC        round(100 * (net_revenue / lag(net_revenue) OVER (PARTITION BY region ORDER BY week) - 1), 1) AS wow_change_pct
# MAGIC FROM weekly
# MAGIC ORDER BY region, week

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4a · 🧑‍💻 Your turn: the top 3 dealers in every region (SQL)
# MAGIC
# MAGIC Create a temp view **`answer_top_dealers`** with the columns `region`, `dealer_name`, `net_revenue` (December
# MAGIC total) and `revenue_rank` (1 = highest in its region), keeping ranks 1–3 only. Use `endtoend_gold_daily_dealer_sales_fact`.
# MAGIC
# MAGIC > 🧞 **Genie Code prompt:** *"Using `endtoend_gold_daily_dealer_sales_fact`, create a temp view `answer_top_dealers` with the top
# MAGIC > 3 dealers by total net_revenue in each region: columns region, dealer_name, net_revenue, revenue_rank. Use a
# MAGIC > window function partitioned by region."*

# COMMAND ----------

# DBTITLE 1,🧑‍💻 Your turn: answer_top_dealers (SQL)
# MAGIC %sql
# MAGIC -- CREATE OR REPLACE TEMP VIEW answer_top_dealers AS
# MAGIC -- SELECT ...
# MAGIC
# MAGIC SELECT 'Replace this cell with your CREATE OR REPLACE TEMP VIEW answer_top_dealers statement' AS todo

# COMMAND ----------

# DBTITLE 1,✅ Check: answer_top_dealers
check("top_dealers")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b · 🧑‍💻 Your turn: the five days with the highest online share (SQL)
# MAGIC
# MAGIC Marketing ran online promotions in December. Create a temp view **`answer_online_share`** with the 5 days
# MAGIC where the **Online** channel had the highest share of net revenue: columns `order_date` and
# MAGIC `online_share_pct` (0–100, rounded to 2 decimals). The gold table doesn't have the channel, so this
# MAGIC question goes back to **silver** (`endtoend_silver_orders_fact`). Knowing which layer can answer a question is part of the skill.
# MAGIC
# MAGIC > 🧞 **Genie Code prompt:** *"From `endtoend_silver_orders_fact`, compute for each day (to_date of order_ts) the percentage of
# MAGIC > net_revenue where channel = 'Online', rounded to 2 decimals, and create a temp view `answer_online_share` with the 5
# MAGIC > days with the highest share (columns order_date, online_share_pct)."*

# COMMAND ----------

# DBTITLE 1,🧑‍💻 Your turn: answer_online_share (SQL)
# MAGIC %sql
# MAGIC -- CREATE OR REPLACE TEMP VIEW answer_online_share AS
# MAGIC -- SELECT ...
# MAGIC
# MAGIC SELECT 'Replace this cell with your CREATE OR REPLACE TEMP VIEW answer_online_share statement' AS todo

# COMMAND ----------

# DBTITLE 1,✅ Check: answer_online_share
check("online_share")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5 · Build an AI/BI dashboard
# MAGIC
# MAGIC An AI/BI dashboard is a set of **datasets** (SQL queries, here over the gold tables) and **widgets** placed
# MAGIC on a 6-column grid. You usually build one in the dashboard editor. Here it's defined in code, so you can see
# MAGIC every part, version it, and recreate it in any workspace. The helpers `dataset()`, `counter()`, `line()`,
# MAGIC `bar()`, `table()` and `text()` write the dashboard JSON for you.
# MAGIC
# MAGIC The dashboard is saved in your home folder and published with your credentials. It runs on a SQL warehouse:
# MAGIC the first serverless warehouse it finds, or the one you set in the `warehouse_id` widget.
# MAGIC
# MAGIC 📚 [AI/BI dashboards](https://docs.databricks.com/aws/en/dashboards/) · [Lakeview API](https://docs.databricks.com/api/workspace/lakeview)

# COMMAND ----------

# DBTITLE 1,📘 Example: publish the December sales dashboard (Python)
datasets = [
    dataset("kpis", "December KPIs", """
        SELECT round(sum(net_revenue) / 1e6, 2) AS net_revenue_musd, sum(orders) AS orders,
               round(100 * sum(margin) / sum(net_revenue), 1) AS margin_pct
        FROM endtoend_gold_daily_dealer_sales_fact"""),
    dataset("daily", "Daily revenue by region", """
        SELECT order_date, region, sum(net_revenue) AS net_revenue
        FROM endtoend_gold_daily_dealer_sales_fact GROUP BY ALL"""),
    dataset("tiers", "Revenue by dealer tier", """
        SELECT dealer_tier, sum(net_revenue) AS net_revenue
        FROM endtoend_gold_daily_dealer_sales_fact GROUP BY ALL"""),
    dataset("dealers", "Top dealers", """
        SELECT dealer_name, region, dealer_tier, sum(orders) AS orders, round(sum(net_revenue), 0) AS net_revenue
        FROM endtoend_gold_daily_dealer_sales_fact GROUP BY ALL ORDER BY net_revenue DESC LIMIT 20"""),
]
widgets = [
    text("title", "## Apex Motorsports Parts · December 2025\nBuilt from the gold tables of the bronze-to-gold lab.", 0, 0),
    counter("c_revenue", "kpis", "net_revenue_musd", "Net revenue ($M)", x=0, y=2),
    counter("c_orders", "kpis", "orders", "Order lines", x=2, y=2),
    counter("c_margin", "kpis", "margin_pct", "Margin %", x=4, y=2),
    line("l_daily", "daily", "order_date", "net_revenue", "Daily net revenue by region", x=0, y=5, color="region"),
    bar("b_tiers", "tiers", "dealer_tier", "net_revenue", "Net revenue by dealer tier", x=0, y=11),
    table("t_dealers", "dealers", ["dealer_name", "region", "dealer_tier", "orders", "net_revenue"], "Top 20 dealers",
          x=3, y=11, w=3),
]
dashboard_id, dashboard_url = publish_dashboard(datasets, widgets)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5a · 🧑‍💻 Your turn: put your gold table on the dashboard (Python)
# MAGIC
# MAGIC Add a chart built on **your** `endtoend_gold_category_region_fact` table: for example, a bar chart of `margin_pct` by
# MAGIC `category`, colored by `region`. Add one dataset to `my_datasets` and one widget to `my_widgets`, then run the
# MAGIC cell to republish. Place the widget below the others (`y=17`, full width `w=6`).
# MAGIC
# MAGIC > 🧞 **Genie Code prompt:** *"Using the helper functions `dataset()` and `bar()` defined in this notebook, add a dataset
# MAGIC > named 'categories' that selects region, category and margin_pct from `endtoend_gold_category_region_fact`, and a bar widget
# MAGIC > that shows margin_pct by category colored by region at x=0, y=17, w=6, then call publish_dashboard with
# MAGIC > datasets + my_datasets and widgets + my_widgets."*
# MAGIC
# MAGIC **Prefer clicking?** Open the dashboard, click **Edit draft**, and ask the dashboard's assistant: *"Add a bar
# MAGIC chart of margin_pct by category, colored by region, from endtoend_gold_category_region_fact."* Then publish.

# COMMAND ----------

# DBTITLE 1,🧑‍💻 Your turn: add a widget and republish (Python)
my_datasets = []  # e.g. dataset("categories", "Margin by category", "SELECT ... FROM endtoend_gold_category_region_fact")
my_widgets = []   # e.g. bar("b_categories", "categories", "category", "margin_pct", "Margin % by category", x=0, y=17, w=6, color="region")

publish_dashboard(datasets + my_datasets, widgets + my_widgets)

# COMMAND ----------

# DBTITLE 1,✅ Check: the dashboard has your widget
check("dashboard")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6 · What you built
# MAGIC
# MAGIC | | |
# MAGIC |---|---|
# MAGIC | 🥉 bronze | `endtoend_bronze_orders_fact` (Auto Loader, incremental) and `endtoend_bronze_dealers_dim` (batch), both with lineage columns |
# MAGIC | 🥈 silver | `endtoend_silver_orders_fact`, `endtoend_silver_dealers_dim` and `endtoend_silver_parts_dim`: typed, standardized, de-duplicated, protected by CHECK constraints; rejects in `endtoend_quarantine_orders_fact` |
# MAGIC | 🥇 gold | `endtoend_gold_daily_dealer_sales_fact` and `endtoend_gold_category_region_fact`, documented with comments |
# MAGIC | 📊 serving | SQL answers and a published AI/BI dashboard |
# MAGIC
# MAGIC **Look around before you move on**
# MAGIC * Open `endtoend_gold_category_region_fact` in **Catalog Explorer** → **Lineage** to see the path from the raw files to the dashboard.
# MAGIC * Rerun the Auto Loader cell in 1b: it processes **0** new files, because the checkpoint remembers what it already ingested.
# MAGIC * Ask Genie Code: *"Explain what each layer of this notebook does and what could break in production."*
# MAGIC
# MAGIC **Next:** `02_spark_dos_and_donts` shows what makes pipelines like this one fast or slow at 100M rows.

# COMMAND ----------

# DBTITLE 1,Summary of the lab tables
tag_workshop_objects(CATALOG, SCHEMA, WORKSHOP_TAG)  # tag the new endtoend_* tables like the rest of the workshop
display(spark.sql(f"""
    SELECT table_name, comment
    FROM `{CATALOG}`.information_schema.tables
    WHERE table_schema = '{SCHEMA}' AND table_name LIKE 'endtoend\\_%'
    ORDER BY table_name"""))
