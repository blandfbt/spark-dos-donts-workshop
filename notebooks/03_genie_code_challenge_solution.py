# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Genie Code challenge: reference solution
# MAGIC
# MAGIC ## What was wrong with the slow version
# MAGIC
# MAGIC Try the challenge in section 11 of `02_spark_dos_and_donts` before you read this.
# MAGIC
# MAGIC `build_dealer_scorecard_slow` produces the right numbers, but the way it gets there is the problem:
# MAGIC
# MAGIC | # | in the slow version | why it hurts | in the fix |
# MAGIC |---|---|---|---|
# MAGIC | 1 | `collect()` the dealers and `for d in region_dealers:` | one query per dealer, run one after another (section 3) | one join + `groupBy` over all dealers |
# MAGIC | 2 | `date_format(order_date, 'yyyy-MM') == month` | a function around the column hides it from file statistics, so Delta can't skip files that are outside the month | `order_date >= start AND order_date < start + 1 month` |
# MAGIC | 3 | `if dealer_orders.count() == 0: continue` | one more full action per dealer (2b) | the inner join simply produces no row for dealers without orders |
# MAGIC | 4 | `toPandas()` per dealer, `merge` with a pandas copy of `dim_part` | ships every order line to the driver (1a/1b) | Spark join; the small dimension is broadcast automatically |
# MAGIC | 5 | `pdf.apply(lambda r: ..., axis=1)` | row-at-a-time Python, the pandas version of a Python UDF (4) | column expressions |
# MAGIC | 6 | `groupby(...).idxmax()` per dealer in pandas | driver-side work per key | `max_by(category, revenue)` in one aggregation |
# MAGIC | 7 | `withColumn` in a loop | plan bloat (5a); harmless for 2 columns, a habit that hurts at 300 | one `select` |
# MAGIC | 8 | `print(scorecard.count())` + `display(scorecard)` | two extra full executions in a job (1c, 2a) | row count from `DESCRIBE HISTORY` |
# MAGIC | 9 | `coalesce(1)` before the write | one task writes everything (9b) | a normal write |
# MAGIC
# MAGIC **Not an anti-pattern here:** `Window.orderBy(F.desc("net_revenue"))` with no `partitionBy` (section 8)
# MAGIC is fine **because it runs after the aggregation**, on a few dozen rows. The rule is "no global window
# MAGIC over big data", not "never a global window". Good Genie Code answers keep it. If an answer adds a
# MAGIC partition key it doesn't need, ask why.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ./config

# COMMAND ----------

# DBTITLE 1,✅ Optimized scorecard job
def build_dealer_scorecard_fast(region="Midwest", month="2025-12", target_table=T("dealer_scorecard_fast")):
    """Scorecard per dealer in `region` for `month` (YYYY-MM): orders, customers, net revenue, margin,
    margin %, top category and revenue rank. Overwrites target_table."""
    month_start = F.to_date(F.lit(f"{month}-01"))

    lines = (
        spark.table(T("fact_orders"))
        # (2) range on the raw clustering column -> data skipping reads ~1 month of files
        .where((F.col("order_date") >= month_start) & (F.col("order_date") < F.add_months(month_start, 1)))
        # (1)(3)(4) joins instead of a driver loop; dealers without orders drop out of the inner join
        .join(spark.table(T("dim_dealer")).where(F.col("region") == region).select("dealer_id", "dealer_name"), "dealer_id")
        .join(spark.table(T("dim_part")).select("part_id", "category", "unit_cost"), "part_id")
        # (5) column expressions instead of pandas apply
        .withColumn("net_revenue", F.col("quantity") * F.col("unit_price") * (1 - F.col("discount_pct")))
        .withColumn("margin", F.col("net_revenue") - F.col("quantity") * F.col("unit_cost"))
    )

    # (6) top category per dealer in one aggregation
    top_category = (
        lines.groupBy("dealer_id", "category").agg(F.sum("net_revenue").alias("category_revenue"))
        .groupBy("dealer_id").agg(F.max_by("category", "category_revenue").alias("top_category"))
    )

    # (7) one select instead of withColumn in a loop
    scorecard = (
        lines.groupBy("dealer_id", "dealer_name")
        .agg(
            F.count("*").alias("orders"),
            F.countDistinct("customer_id").alias("customers"),
            F.round(F.sum("net_revenue"), 2).alias("net_revenue"),
            F.round(F.sum("margin"), 2).alias("margin"),
        )
        .join(top_category, "dealer_id")
        .select(
            F.col("dealer_id").cast("long").alias("dealer_id"),
            "dealer_name", "orders", "customers", "net_revenue", "margin", "top_category",
            F.round(100 * F.col("margin") / F.col("net_revenue"), 2).alias("margin_pct"),
            # fine without partitionBy: this runs on one row per dealer, after the aggregation
            F.row_number().over(Window.orderBy(F.desc("net_revenue"))).alias("revenue_rank"),
        )
    )

    # (8)(9) a single action: a normal parallel write
    scorecard.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(target_table)
    rows = spark.sql(f"DESCRIBE HISTORY {target_table} LIMIT 1").first().operationMetrics["numOutputRows"]
    print(f"{target_table}: {rows} dealers written")
    return spark.table(target_table)

# COMMAND ----------

# DBTITLE 1,⏱️ Time it and check the result
run_timed("11 · Genie Code challenge: dealer scorecard", "Do", build_dealer_scorecard_fast)
check_dealer_scorecard(T("dealer_scorecard_fast"))

# COMMAND ----------

# DBTITLE 1,Scorecard
display(spark.table(T("dealer_scorecard_fast")).orderBy("revenue_rank"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Same job in SQL
# MAGIC
# MAGIC Genie Code might also suggest SQL. It runs on the same engine and is just as fast.

# COMMAND ----------

# DBTITLE 1,✅ The same job in SQL
display(spark.sql(f"""
WITH lines AS (
  SELECT o.dealer_id, d.dealer_name, o.customer_id, p.category,
         o.quantity * o.unit_price * (1 - o.discount_pct)                              AS net_revenue,
         o.quantity * o.unit_price * (1 - o.discount_pct) - o.quantity * p.unit_cost  AS margin
  FROM {T('fact_orders')} o
  JOIN {T('dim_dealer')} d ON o.dealer_id = d.dealer_id AND d.region = 'Midwest'
  JOIN {T('dim_part')}   p ON o.part_id   = p.part_id
  WHERE o.order_date >= DATE'2025-12-01' AND o.order_date < DATE'2026-01-01'
),
top_category AS (
  SELECT dealer_id, max_by(category, revenue) AS top_category
  FROM (SELECT dealer_id, category, sum(net_revenue) AS revenue FROM lines GROUP BY ALL)
  GROUP BY dealer_id
),
scorecard AS (
  SELECT dealer_id, dealer_name, count(*) AS orders, count(DISTINCT customer_id) AS customers,
         round(sum(net_revenue), 2) AS net_revenue, round(sum(margin), 2) AS margin
  FROM lines GROUP BY ALL
)
SELECT s.*, t.top_category,
       round(100 * s.margin / s.net_revenue, 2)        AS margin_pct,
       row_number() OVER (ORDER BY s.net_revenue DESC) AS revenue_rank
FROM scorecard s JOIN top_category t USING (dealer_id)
ORDER BY revenue_rank
"""))
