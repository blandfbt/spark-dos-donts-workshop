# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Notebook 06 · Explore your data with Genie
# MAGIC
# MAGIC **What you'll learn:** how to work with Genie through its chat UI and verify that it returns correct answers by
# MAGIC comparing with direct SQL.
# MAGIC
# MAGIC **How this works:** open your Knowledge Store agent in the browser and ask questions in plain English. Then run
# MAGIC the reference SQL here to confirm Genie's answers match the ground truth.
# MAGIC
# MAGIC **Before you start:** run **04** (the Knowledge Store agent). **Compute:** Serverless.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ../CONFIG

# COMMAND ----------

# DBTITLE 1,⚙️ Genie helpers
# MAGIC %run ./genie_helpers

# COMMAND ----------

# MAGIC %md
# MAGIC ## Connect to the workspace
# MAGIC
# MAGIC Read your Knowledge Store agent id from `genie_workshop_config` and build its clickable Genie link.

# COMMAND ----------

PRIMARY_SPACE_ID = load_config().get(CFG_KEY_CURATED, "")
if not PRIMARY_SPACE_ID:
    raise RuntimeError("genie_space_id not found in genie_workshop_config. Run notebook 04 first.")
print(f"Knowledge Store agent: {genie_ui_room_url(PRIMARY_SPACE_ID)}")

D, C, DL, P = GOLD_DAILY_TABLE, GOLD_CATEGORY_TABLE, DEALERS_TABLE, PARTS_TABLE

# COMMAND ----------

# MAGIC %md
# MAGIC ## Revenue and margin: try in Genie, then compare
# MAGIC
# MAGIC 1. **What was the margin % by region in December 2025?**
# MAGIC    - **Expected answer:** one row per region with margin % = `100 × SUM(margin) / SUM(net_revenue)` from the daily
# MAGIC      dealer sales table. Values should match reference table 1 below.
# MAGIC
# MAGIC 2. **Show daily net revenue for December 2025.**
# MAGIC    - **Expected answer:** one row per `order_date` with `SUM(net_revenue)`. A line chart is a good choice: ask
# MAGIC      Genie to "show it as a line chart".
# MAGIC
# MAGIC 3. **How do weekends compare with weekdays for average daily net revenue?**
# MAGIC    - **Expected answer:** two rows (weekend / weekday), each the total net revenue ÷ the number of days in the group.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Dealers and tiers: try in Genie, then compare
# MAGIC
# MAGIC 1. **Who were the top 10 dealers by net revenue?**
# MAGIC    - **Expected answer:** 10 rows, aggregated over the whole month, ordered by net revenue descending.
# MAGIC
# MAGIC 2. **How many dealers do we have in each state?**
# MAGIC    - **Expected answer:** counts from the dealers dimension grouped by `state` (two-letter codes).

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part categories: try in Genie, then compare
# MAGIC
# MAGIC 1. **Which part categories have the highest margin %?**
# MAGIC    - **Expected answer:** one row per category from the category × region table, margin % recomputed from the sums
# MAGIC      (not an average of the per-region `margin_pct`).
# MAGIC
# MAGIC 2. **What is the average list price per category?**
# MAGIC    - **Expected answer:** `AVG(list_price)` from the parts dimension grouped by category.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reference SQL: ground truth for the prompts above

# COMMAND ----------

print("=== 1. Margin % by region ===")
display(spark.sql(f"""
SELECT region, ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) AS margin_pct
FROM {D}
GROUP BY region
ORDER BY margin_pct DESC
"""))

print("=== 2. Daily net revenue ===")
display(spark.sql(f"""
SELECT order_date, ROUND(SUM(net_revenue), 2) AS net_revenue
FROM {D}
GROUP BY order_date
ORDER BY order_date
"""))

print("=== 3. Average daily net revenue: weekend vs weekday ===")
display(spark.sql(f"""
SELECT CASE WHEN DAYOFWEEK(order_date) IN (1, 7) THEN 'weekend' ELSE 'weekday' END AS day_type,
       ROUND(SUM(net_revenue) / COUNT(DISTINCT order_date), 2) AS avg_daily_net_revenue
FROM {D}
GROUP BY 1
"""))

print("=== 4. Top 10 dealers by net revenue ===")
display(spark.sql(f"""
SELECT dealer_name, region, dealer_tier, ROUND(SUM(net_revenue), 2) AS net_revenue
FROM {D}
GROUP BY ALL
ORDER BY net_revenue DESC
LIMIT 10
"""))

print("=== 5. Dealers per state ===")
display(spark.sql(f"""
SELECT state, COUNT(*) AS dealers
FROM {DL}
GROUP BY state
ORDER BY dealers DESC
"""))

print("=== 6. Margin % by part category ===")
display(spark.sql(f"""
SELECT category, ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) AS margin_pct
FROM {C}
GROUP BY category
ORDER BY margin_pct DESC
"""))

print("=== 7. Average list price per category ===")
display(spark.sql(f"""
SELECT category, ROUND(AVG(list_price), 2) AS avg_list_price
FROM {P}
GROUP BY category
ORDER BY avg_list_price DESC
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quick programmatic check
# MAGIC
# MAGIC Sends 3 questions to Genie through the Conversation API (`ask_genie` in `genie_helpers`) and compares them to the
# MAGIC ground truth. This confirms the agent answers correctly without copy-pasting into the UI.

# COMMAND ----------

spot_checks = [
    ("How many dealers are located in Texas?",
     f"SELECT COUNT(*) FROM {DL} WHERE state = 'TX'"),
    ("How many units were sold in December 2025 in total?",
     f"SELECT SUM(units) FROM {D}"),
    ("How many part categories are there?",
     f"SELECT COUNT(DISTINCT category) FROM {P}"),
]

print("Quick spot check: 3 questions against the Knowledge Store agent")
for q, gt_sql in spot_checks:
    gt = float(spark.sql(gt_sql).collect()[0][0])
    gv, err = ask_genie(q, PRIMARY_SPACE_ID, timeout=90)
    status = "PASS" if gv is not None and abs(gv - gt) / max(abs(gt), 1) < 0.05 else "FAIL"
    print(f"  {status}: {q} (GT={gt:,.0f}, Genie={gv}{f', err={err}' if err else ''})")
print()
print("Next: notebook 07 (Genie Code skills).")
