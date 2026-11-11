# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Notebook 03b · Metric Views: the governed semantic layer
# MAGIC
# MAGIC **The single most important idea in this workshop:** a Genie agent is only as good as the data foundation under
# MAGIC it. **Move the logic to the left**: define your KPIs and joins **once**, in a governed object in Unity Catalog,
# MAGIC instead of hoping Genie re-derives them correctly on every question.
# MAGIC
# MAGIC A **[metric view](https://docs.databricks.com/aws/en/metric-views/)** is that object. It pins:
# MAGIC - the **join paths** between fact and dimension tables,
# MAGIC - the **exact formula** for each KPI (margin %, average revenue per order, ...). Margin % is total margin ÷ total
# MAGIC   net revenue, **never** an average of daily or regional percentages,
# MAGIC - the **dimensions** you're allowed to slice by.
# MAGIC
# MAGIC Genie (and dashboards, and SQL users) then all read the *same* trusted definitions.
# MAGIC
# MAGIC | | Tables (03, 04) | Metric view (here) |
# MAGIC |---|---|---|
# MAGIC | KPI formula | Genie must learn it (examples/measures) | **Fixed** in the view |
# MAGIC | Joins | Genie must pick them | **Fixed** in the view |
# MAGIC | Governance | per-table grants | one governed object, reusable |
# MAGIC | Flexibility | open-ended exploration | limited to the view's perimeter |
# MAGIC
# MAGIC **Two things make a metric-view agent actually perform** (both below):
# MAGIC 1. **Well-scoped views**: the dimensions and measures the questions need, with formulas baked in.
# MAGIC 2. **A curated agent**: a clear instruction plus **example `MEASURE()` queries**, so Genie writes the metric-view
# MAGIC    dialect correctly.
# MAGIC
# MAGIC **Two views, because the gold layer has two grains.** `endtoend_gold_daily_dealer_sales_fact` knows the *day* and
# MAGIC the *dealer* but not the part category; `endtoend_gold_category_region_fact` knows the *category* but not the day
# MAGIC or dealer. So:
# MAGIC
# MAGIC | metric view (in **your** schema) | source (shared) | slice by |
# MAGIC |---|---|---|
# MAGIC | `mv_dealer_sales` | daily dealer sales, joined to the dealers dim | date, week, region, dealer tier, dealer, dealer state |
# MAGIC | `mv_category_sales` | category × region sales | region, category |
# MAGIC
# MAGIC **Perimeter trade-off (teach this):** a metric view is deterministic *within its scope* but can't answer questions
# MAGIC outside it. "Margin % for Brakes **at Platinum dealers**" can't be answered by either view, because no gold table
# MAGIC has both category and dealer. That question goes back to silver (or to a new gold table). Pair metric views with
# MAGIC the table-based Knowledge Store agent in 04 for exploration.
# MAGIC
# MAGIC > **Verify the DDL in your workspace.** Metric-view YAML syntax has evolved across releases; if
# MAGIC > `CREATE VIEW ... WITH METRICS` errors, check the docs for your workspace version.
# MAGIC
# MAGIC **Before you start:** run **03** (baseline agent). **Compute:** Serverless.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ../CONFIG

# COMMAND ----------

# DBTITLE 1,⚙️ Genie helpers
# MAGIC %run ./genie_helpers

# COMMAND ----------

# MAGIC %md
# MAGIC ## Connect to the workspace and pick a warehouse
# MAGIC
# MAGIC `genie_helpers` already created the SDK client and REST headers; pick the SQL warehouse the agent runs its SQL on
# MAGIC (`SQL_WAREHOUSE_ID` if set, otherwise auto-selected).

# COMMAND ----------

warehouse_id = pick_warehouse()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Create the metric views
# MAGIC
# MAGIC `mv_dealer_sales` sits on the daily dealer sales table and joins to the dealers dimension (for the dealer's state).
# MAGIC `mv_category_sales` sits on the category × region table. Both expose the **same measure names** with the formulas
# MAGIC baked in: `margin_percent` is `100 × SUM(margin) / SUM(net_revenue)`, so nobody averages percentages by mistake.
# MAGIC Money and percentage measures are **rounded to 2 decimals in the view**, so every consumer reports the same number.
# MAGIC
# MAGIC The views are created in **your** schema; they read the shared tables, which stay read-only.

# COMMAND ----------

ddl_dealer = f"""
CREATE OR REPLACE VIEW {METRIC_VIEW_DEALER_SALES}
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: {GOLD_DAILY_TABLE}
joins:
  - name: dealer
    source: {DEALERS_TABLE}
    on: source.dealer_id = dealer.dealer_id
dimensions:
  - name: order_date
    expr: source.order_date
  - name: order_week
    expr: CAST(DATE_TRUNC('WEEK', source.order_date) AS DATE)
  - name: region
    expr: source.region
  - name: dealer_tier
    expr: source.dealer_tier
  - name: dealer_id
    expr: source.dealer_id
  - name: dealer_name
    expr: source.dealer_name
  - name: dealer_state
    expr: dealer.state
measures:
  - name: total_net_revenue
    expr: ROUND(SUM(source.net_revenue), 2)
  - name: total_margin
    expr: ROUND(SUM(source.margin), 2)
  - name: margin_percent
    expr: ROUND(100.0 * SUM(source.margin) / NULLIF(SUM(source.net_revenue), 0), 2)
  - name: total_orders
    expr: SUM(source.orders)
  - name: total_units
    expr: SUM(source.units)
  - name: avg_revenue_per_order
    expr: ROUND(SUM(source.net_revenue) / NULLIF(SUM(source.orders), 0), 2)
  - name: active_dealers
    expr: COUNT(DISTINCT source.dealer_id)
$$
"""

ddl_category = f"""
CREATE OR REPLACE VIEW {METRIC_VIEW_CATEGORY_SALES}
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: {GOLD_CATEGORY_TABLE}
dimensions:
  - name: region
    expr: region
  - name: category
    expr: category
measures:
  - name: total_net_revenue
    expr: ROUND(SUM(net_revenue), 2)
  - name: total_margin
    expr: ROUND(SUM(margin), 2)
  - name: margin_percent
    expr: ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2)
  - name: total_orders
    expr: SUM(orders)
  - name: total_units
    expr: SUM(units)
  - name: avg_revenue_per_order
    expr: ROUND(SUM(net_revenue) / NULLIF(SUM(orders), 0), 2)
$$
"""

spark.sql(ddl_dealer)
print("Created metric view:", METRIC_VIEW_DEALER_SALES)
spark.sql(ddl_category)
print("Created metric view:", METRIC_VIEW_CATEGORY_SALES)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Query them with `MEASURE()`
# MAGIC
# MAGIC Select dimensions and wrap measures in `MEASURE(...)`. The engine applies the pinned joins and formulas: the same
# MAGIC numbers every time, for everyone.

# COMMAND ----------

display(spark.sql(f"""
SELECT
  dealer_tier,
  ROUND(MEASURE(total_net_revenue), 2)     AS net_revenue,
  ROUND(MEASURE(margin_percent), 2)        AS margin_pct,
  ROUND(MEASURE(avg_revenue_per_order), 2) AS avg_revenue_per_order,
  MEASURE(active_dealers)                  AS dealers
FROM {METRIC_VIEW_DEALER_SALES}
GROUP BY dealer_tier
ORDER BY net_revenue DESC
"""))

display(spark.sql(f"""
SELECT category, ROUND(MEASURE(margin_percent), 2) AS margin_pct, ROUND(MEASURE(total_net_revenue), 2) AS net_revenue
FROM {METRIC_VIEW_CATEGORY_SALES}
GROUP BY category
ORDER BY margin_pct DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2b. Performance: metric view vs. raw tables
# MAGIC
# MAGIC A governed semantic layer is only worth it if it doesn't cost much at query time. A metric view compiles to
# MAGIC essentially the **same** joins and aggregations you'd write by hand, plus a little semantic-layer planning.
# MAGIC
# MAGIC The cell below (1) tries `ANALYZE ... COMPUTE STATISTICS` on the shared source tables, (2) times each
# MAGIC metric-view query against its hand-written raw-table equivalent, warm, a few times, and (3) prints the medians
# MAGIC side by side.
# MAGIC
# MAGIC **About step 1:** you have only `SELECT` on the shared schema, and `ANALYZE` needs `MODIFY`, so it normally
# MAGIC prints a "skipped" note. That's fine: the instructor's prebuild already computed statistics, and both paths read
# MAGIC the same tables either way.
# MAGIC
# MAGIC On this small dataset expect the two to land **within a few hundred milliseconds**: the metric view adds a small,
# MAGIC roughly constant planning overhead that's swamped by fixed query cost. At production scale its pinned
# MAGIC aggregations and pruning typically make it the *faster* option. The real win isn't raw speed on small data; it's
# MAGIC pinned, governed, correct KPIs at negligible cost.

# COMMAND ----------

import statistics

# 1) Statistics help the planner optimize both paths fairly (needs MODIFY on the shared tables, so usually skipped).
for _t in [GOLD_DAILY_TABLE, GOLD_CATEGORY_TABLE, DEALERS_TABLE]:
    try:
        spark.sql(f"ANALYZE TABLE {_t} COMPUTE STATISTICS FOR ALL COLUMNS")
        print(f"  ANALYZE {_t}: done")
    except Exception as e:
        print(f"  ANALYZE {_t}: skipped (read-only shared table: {str(e).strip().splitlines()[0][:60]})")

# 2) Metric-view query vs. its hand-written raw-table equivalent (the patterns behind the 08 questions).
PAIRS = {
    "Margin % by dealer tier": (
        f"SELECT dealer_tier, MEASURE(margin_percent) FROM {METRIC_VIEW_DEALER_SALES} GROUP BY dealer_tier",
        f"SELECT dealer_tier, ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) "
        f"FROM {GOLD_DAILY_TABLE} GROUP BY dealer_tier",
    ),
    "Net revenue, Texas dealers": (
        f"SELECT MEASURE(total_net_revenue) FROM {METRIC_VIEW_DEALER_SALES} WHERE dealer_state = 'TX'",
        f"SELECT ROUND(SUM(s.net_revenue), 2) FROM {GOLD_DAILY_TABLE} s "
        f"JOIN {DEALERS_TABLE} d ON s.dealer_id = d.dealer_id WHERE d.state = 'TX'",
    ),
    "Margin % by category": (
        f"SELECT category, MEASURE(margin_percent) FROM {METRIC_VIEW_CATEGORY_SALES} GROUP BY category",
        f"SELECT category, ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) "
        f"FROM {GOLD_CATEGORY_TABLE} GROUP BY category",
    ),
}


def _median_secs(sql, runs=5):
    spark.sql(sql).collect()  # warm up (plan + cache)
    times = []
    for _ in range(runs):
        t0 = time.time()
        spark.sql(sql).collect()
        times.append(time.time() - t0)
    return statistics.median(times)


print(f"\n{'Question':<30}{'Metric view':>13}{'Raw tables':>13}{'Delta':>9}   Verdict")
print("-" * 82)
for label, (mv_sql, raw_sql) in PAIRS.items():
    mv_t, raw_t = _median_secs(mv_sql), _median_secs(raw_sql)
    # Both are dominated by fixed planning/round-trip cost here, so a sub-second band counts as parity.
    verdict = "comparable" if mv_t <= max(raw_t * 1.25, raw_t + 0.30) else "slower - investigate"
    print(f"{label:<30}{mv_t:>11.2f}s{raw_t:>12.2f}s{mv_t - raw_t:>+8.2f}s   {verdict}")
print("-" * 82)
print("The metric view adds a small constant planning overhead, negligible in absolute terms; it compiles to")
print("the same plan as the raw SQL, and at production scale it is typically the faster option.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Build a *curated* Genie agent on the metric views
# MAGIC
# MAGIC **Agent C.** Data sources: the two metric views only, so joins and KPI math are correct by construction. But we
# MAGIC don't stop there: the agent gets a clear instruction about the `MEASURE()` dialect **and example queries** for
# MAGIC the common patterns. That curation is what turns "has a metric view" into "answers reliably."

# COMMAND ----------

MV_D = METRIC_VIEW_DEALER_SALES
MV_C = METRIC_VIEW_CATEGORY_SALES

mv_instruction = (
    f"This agent answers questions from TWO governed metric views. "
    f"{MV_D}: December 2025 sales by order_date, order_week (Monday start), region, dealer_tier, dealer_id, "
    f"dealer_name and dealer_state (two-letter US state code, e.g. 'TX' for Texas). "
    f"{MV_C}: December 2025 sales by region and category (part category). "
    "Use the category view whenever a question mentions a part category; use the dealer view for dates, weeks, "
    "dealers, tiers and states. Query by selecting dimensions and wrapping measures in MEASURE(<measure_name>); "
    "filter on dimensions in WHERE and GROUP BY the requested dimensions. "
    "margin_percent is ALREADY a percentage (0-100) computed as total margin / total net revenue: never average it "
    "and never multiply it by 100 again. avg_revenue_per_order is total net revenue / total orders. "
    "'Sales' and 'revenue' mean total_net_revenue. 'Orders' means total_orders (order lines). "
    "total_net_revenue, total_margin, margin_percent and avg_revenue_per_order are pre-rounded to 2 decimals in "
    "the views: return them as-is. "
    "For a single-value question, return just the aggregated measure (a scalar). "
    "Do NOT recompute KPIs from base tables: the metric views already encode the joins and formulas."
)


def mv_example(question, sql):
    return {"id": new_id(), "question": [question], "sql": [sql], "parameters": [], "usage_guidance": []}


mv_examples = sorted([
    mv_example(
        "What was the margin % for Gold tier dealers in December 2025?",
        f"SELECT ROUND(MEASURE(margin_percent), 2) AS margin_pct FROM {MV_D} WHERE dealer_tier = 'Gold'"),
    mv_example(
        "What was the net revenue of dealers in Ohio?",
        f"SELECT ROUND(MEASURE(total_net_revenue), 2) AS net_revenue FROM {MV_D} WHERE dealer_state = 'OH'"),
    mv_example(
        "What was the average revenue per order by region for the week of December 15, 2025?",
        f"SELECT region, ROUND(MEASURE(avg_revenue_per_order), 2) AS avg_revenue_per_order FROM {MV_D} "
        f"WHERE order_week = DATE'2025-12-15' GROUP BY region ORDER BY avg_revenue_per_order DESC"),
    mv_example(
        "What is the margin % for the Engine category across all regions?",
        f"SELECT ROUND(MEASURE(margin_percent), 2) AS margin_pct FROM {MV_C} WHERE category = 'Engine'"),
    mv_example(
        "Net revenue by part category in the West region",
        f"SELECT category, ROUND(MEASURE(total_net_revenue), 2) AS net_revenue FROM {MV_C} "
        f"WHERE region = 'West' GROUP BY category ORDER BY net_revenue DESC"),
], key=lambda e: e["id"])


def build_serialized_metric_view():
    return json.dumps({
        "version": 2,
        "config": {"sample_questions": []},
        "data_sources": {
            "tables": [],
            "metric_views": sorted([
                {"identifier": MV_D, "description": [
                    "Governed December 2025 dealer sales. Measures (MEASURE()): total_net_revenue, total_margin, "
                    "margin_percent (already 0-100), total_orders, total_units, avg_revenue_per_order, active_dealers. "
                    "Dimensions: order_date, order_week, region, dealer_tier, dealer_id, dealer_name, dealer_state."]},
                {"identifier": MV_C, "description": [
                    "Governed December 2025 sales by region and part category. Measures (MEASURE()): "
                    "total_net_revenue, total_margin, margin_percent (already 0-100), total_orders, total_units, "
                    "avg_revenue_per_order. Dimensions: region, category."]},
            ], key=lambda m: m["identifier"]),
        },
        "instructions": {
            "text_instructions": [{"id": new_id(), "content": [mv_instruction]}],
            "example_question_sqls": mv_examples,
        },
    })


mv_id, mv_url = create_or_update_genie_space(
    GENIE_TITLE_METRIC_VIEW, GENIE_DESC_METRIC_VIEW, build_serialized_metric_view(), warehouse_id
)

save_config_keys([
    {"key": CFG_KEY_METRIC_VIEW, "value": mv_id,
     "space_name": GENIE_TITLE_METRIC_VIEW, "space_url": mv_url},
])

print()
print("Metric-view agent:", mv_url)
print('Try: "What was the margin % for Platinum dealers in December 2025?"')
print("The pinned formulas + example MEASURE() queries make it deterministic.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC - **04 · Knowledge Store:** curate the *tables* with column configs, synonyms, joins, measures, filters and
# MAGIC   example SQL (the primary agent).
# MAGIC - **08** compares Baseline vs. **Metric View** vs. Knowledge Store on KPI-by-dimension questions: both curated
# MAGIC   agents should clearly beat the baseline.
# MAGIC
# MAGIC **Takeaway for your own domain:** for the KPIs your business runs on, define them once in a metric view *and*
# MAGIC give the agent a couple of example `MEASURE()` queries. That combination is the highest-leverage thing you can do
# MAGIC before pointing Genie at your data.
