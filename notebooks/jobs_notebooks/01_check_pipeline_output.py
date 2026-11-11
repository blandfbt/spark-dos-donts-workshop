# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Check the pipeline's output
# MAGIC
# MAGIC Runs as the **`check_gold`** task of the job created by `00_create_pipeline_and_job`, after the pipeline task
# MAGIC succeeds (you can also run it by hand). It compares your pipeline's gold tables with the reference copy the
# MAGIC instructor built from the **same raw files** with the notebook version of the lab (`shared.endtoend_gold_*`),
# MAGIC and shows the data quality results the pipeline recorded. If anything differs, the task fails, so the job run
# MAGIC is marked failed too.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ../../CONFIG

# COMMAND ----------

# DBTITLE 1,Compare gold with the reference
# Same keys and counts exactly; money within a cent. Doubles summed in a different order can round to a
# different last cent (e.g. 1234.565 → 1234.57 vs 1234.56), and that's not a real difference.
from functools import reduce
from operator import or_

from pyspark.sql import functions as F

CHECKS = [  # (your table, reference table, key columns, exact columns, money columns)
    ("pipeline_gold_daily_dealer_sales_fact", "endtoend_gold_daily_dealer_sales_fact",
     ["order_date", "dealer_id"], ["region", "dealer_name", "dealer_tier", "orders", "units"], ["net_revenue", "margin"]),
    ("pipeline_gold_category_region_fact", "endtoend_gold_category_region_fact",
     ["region", "category"], ["orders", "units"], ["net_revenue", "margin", "margin_pct"]),
]
problems = []
for mine, reference, keys, exact, money in CHECKS:
    a = spark.table(T(mine)).alias("a")
    b = spark.table(SRC(reference)).alias("b")
    joined = a.join(b, keys, "full_outer")
    differs = reduce(or_, [F.col(f"a.{exact[0]}").isNull(), F.col(f"b.{exact[0]}").isNull()]
                     + [~F.col(f"a.{c}").eqNullSafe(F.col(f"b.{c}")) for c in exact]
                     + [F.abs(F.col(f"a.{c}") - F.col(f"b.{c}")) > 0.011 for c in money])
    bad = joined.where(differs).count()
    if bad:
        problems.append(mine)
        print(f"❌ {mine}: {bad} rows differ from {SOURCE_SCHEMA}.{reference}")
    else:
        print(f"✅ {mine}: {a.count():,} rows, same as {SOURCE_SCHEMA}.{reference}")

for layer in ["pipeline_silver_orders_fact", "pipeline_quarantine_orders_fact", "pipeline_silver_dealers_dim"]:
    print(f"   {layer:34} {spark.table(T(layer)).count():>10,} rows")

# COMMAND ----------

# DBTITLE 1,Data quality: what each expectation dropped (from the pipeline event log)
try:
    pipeline_id = dbutils.widgets.get("pipeline_id")
except Exception:
    pipeline_id = ""
if pipeline_id:
    try:
        display(spark.sql(f"""
            SELECT e.timestamp, x.name AS expectation, x.dataset, x.passed_records, x.failed_records
            FROM event_log('{pipeline_id}') e
            LATERAL VIEW explode(from_json(e.details:flow_progress.data_quality.expectations,
                'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) t AS x
            WHERE e.event_type = 'flow_progress' AND e.details:flow_progress.data_quality IS NOT NULL
            ORDER BY e.timestamp DESC, expectation
            LIMIT 20"""))
    except Exception as e:  # the event log needs the pipeline owner's (or a granted) access
        print(f"Couldn't read the event log: {str(e).splitlines()[0][:200]}")
else:
    print("Run inside the job (it passes pipeline_id) to see the expectation results here, or open the pipeline page.")

# COMMAND ----------

# DBTITLE 1,Verdict
assert not problems, f"Pipeline output differs from the reference: {problems}"
print("✅ The pipeline produces the same gold tables as the notebook lab.")
