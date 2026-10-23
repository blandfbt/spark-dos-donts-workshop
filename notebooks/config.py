# Databricks notebook source
# MAGIC %md
# MAGIC # Workshop configuration and helpers
# MAGIC
# MAGIC Included by the workshop notebooks with `%run ./config`; you do not run this notebook on its own.
# MAGIC
# MAGIC * **Where the data lives.** `catalog` and `schema` come from the notebook widgets. When the
# MAGIC   notebook runs as a bundle job they are filled from the job parameters. When you open a notebook
# MAGIC   by hand and leave the widgets empty, the values are read from `_workshop_config.json`, which the
# MAGIC   setup job writes next to the notebooks.
# MAGIC * **Shared DataFrames** (`orders`, `parts`, `wide`, ...) are defined here, so `%run ./config` at the
# MAGIC   top of any section restores everything that section needs, for example after a restart.
# MAGIC * **`run_timed(...)`** runs one Don't or Do, times it, prints the outcome and appends it to the
# MAGIC   `workshop_scoreboard` table right away, so results survive a crashed or restarted notebook.
# MAGIC   * A Don't usually runs on a **fraction** of the Do's workload so that it finishes in under a minute.
# MAGIC     The full-size time (and driver memory) is then **projected** from the measured run.
# MAGIC   * A watchdog is the safety net. After `dont_timeout_seconds` it cancels the cell's Spark work
# MAGIC     (`spark.interruptAll()`). Work that runs on the driver itself, such as converting rows to
# MAGIC     pandas, can't be cancelled, and the printout says how long that took.

# COMMAND ----------

import json
import os
import threading
import time

import numpy as np
import pandas as pd
import psutil
from pyspark.sql import functions as F
from pyspark.sql.window import Window

_NOTEBOOK_DIR = "/Workspace" + os.path.dirname(
    dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
)
CONFIG_FILE = f"{_NOTEBOOK_DIR}/_workshop_config.json"

dbutils.widgets.text("catalog", "", "Catalog")
dbutils.widgets.text("schema", "", "Schema")
dbutils.widgets.text("dont_timeout_seconds", "120", "Don't timeout (s)")
dbutils.widgets.text("workshop_tag", "spark_dos_donts", "Workshop tag")

_saved = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        _saved = json.load(f)

CATALOG = dbutils.widgets.get("catalog").strip() or _saved.get("catalog", "")
SCHEMA = dbutils.widgets.get("schema").strip() or _saved.get("schema", "")
DONT_TIMEOUT_S = int(dbutils.widgets.get("dont_timeout_seconds") or 120)
WORKSHOP_TAG_KEY = "workshop_name"  # same key as the bundle's presets.tags
WORKSHOP_TAG = dbutils.widgets.get("workshop_tag").strip() or "spark_dos_donts"

if not CATALOG or not SCHEMA:
    raise ValueError(
        "No catalog/schema configured. Fill the 'catalog' and 'schema' widgets at the top of the "
        "notebook, or run the setup job first (it writes _workshop_config.json next to the notebooks)."
    )

VOLUME = f"/Volumes/{CATALOG}/{SCHEMA}/raw_files"

# Make the workshop schema the default, so SQL cells can use short table names (fact_orders, lab_silver_orders, ...)
spark.sql(f"USE CATALOG `{CATALOG}`")
spark.sql(f"USE SCHEMA `{SCHEMA}`")


def T(name):
    """Fully qualified name of a workshop table."""
    return f"`{CATALOG}`.`{SCHEMA}`.`{name}`"


def tag_workshop_objects(catalog, schema, value):
    """Put the workshop tag on the schema, the raw-files volume and every table in it (for easy filtering)."""
    tagged, skipped = 0, []
    targets = [("SCHEMA", f"`{catalog}`.`{schema}`"), ("VOLUME", f"`{catalog}`.`{schema}`.`raw_files`")]
    targets += [("TABLE", f"`{catalog}`.`{schema}`.`{t.tableName}`")
                for t in spark.sql(f"SHOW TABLES IN `{catalog}`.`{schema}`").where("NOT isTemporary").collect()]
    for kind, name in targets:
        try:
            spark.sql(f"ALTER {kind} {name} SET TAGS ('{WORKSHOP_TAG_KEY}' = '{value}')")
            tagged += 1
        except Exception as e:  # e.g. missing APPLY TAG privilege; tagging is a convenience, never a blocker
            skipped.append(f"{name}: {str(e).strip().splitlines()[0][:80]}")
    print(f"🏷️  tagged {tagged} objects with {WORKSHOP_TAG_KEY} = {value}" + (f" ({len(skipped)} skipped)" if skipped else ""))
    for s in skipped[:3]:
        print("   ", s)


# COMMAND ----------

# Shared inputs. All lazy: defining them reads no data.
orders = spark.table(T("fact_orders"))
parts = spark.table(T("dim_part"))
dealers = spark.table(T("dim_dealer"))
customers = spark.table(T("dim_customer"))
customer_history = spark.table(T("dim_customer_history"))
wide = spark.table(T("telemetry_wide"))
readings = spark.table(T("telemetry_readings"))
sessions = spark.table(T("track_sessions"))

net_revenue = F.col("quantity") * F.col("unit_price") * (1 - F.col("discount_pct"))


def sample_orders(fraction):
    """A deterministic slice of fact_orders: `fraction` of the rows, chosen by order_id."""
    return orders.where(F.col("order_id") % 1000 < int(round(fraction * 1000)))


# COMMAND ----------

CURRENT_USER = spark.sql("SELECT current_user()").first()[0]
DRIVER_RAM_GB = psutil.virtual_memory().total / 1024**3
SCOREBOARD = T("workshop_scoreboard")
if spark.catalog.tableExists(SCOREBOARD.replace("`", "")) and "projected_seconds" not in spark.table(SCOREBOARD).columns:
    spark.sql(f"DROP TABLE {SCOREBOARD}")  # left over from an older version of the workshop
spark.sql(f"""
  CREATE TABLE IF NOT EXISTS {SCOREBOARD} (
    user STRING, scenario STRING, variant STRING, status STRING, seconds DOUBLE, fraction DOUBLE,
    projected_seconds DOUBLE, driver_mem_gb DOUBLE, projected_mem_gb DOUBLE, detail STRING,
    recorded_at TIMESTAMP)
""")


def driver_memory_gb():
    """Resident memory (RSS) of this notebook's Python process: where collect()/toPandas() results land.
    The Spark engine and executors run remotely on serverless and are not included."""
    return psutil.Process().memory_info().rss / 1024**3


def _fmt_seconds(s):
    return f"{s:,.1f} s" if s < 90 else (f"{s / 60:,.1f} min" if s < 5400 else f"{s / 3600:,.1f} h")


def run_timed(scenario, variant, fn, fraction=1.0, scaling="linear", timeout_s=None, note="", detail_fn=None):
    """Run fn(), print the outcome and append it to the workshop_scoreboard table.

    variant   "Don't", "Better" or "Do".
    fraction  share of the full workload fn() processes (a Don't is usually run on a slice so that it
              finishes quickly). The full-size time is projected as seconds / fraction ("linear") or
              seconds / fraction**2 ("quadratic", for costs that grow with the square of the input).
    timeout_s safety net (default: the dont_timeout_seconds widget). The watchdog cancels the Spark work
              still running at that point; driver-side Python work can't be interrupted.
    fn() may return a dict with a "note" key. detail_fn(seconds) is called afterwards even when fn() was
    cancelled, e.g. to report how far a loop got.
    Returns fn()'s result, or None if it failed.
    """
    timeout_s = timeout_s or DONT_TIMEOUT_S
    finished = threading.Event()
    cancelled_at = []

    def watchdog():
        if finished.wait(timeout_s):
            return
        cancelled_at.append(time.perf_counter() - start)
        # Keep cancelling until fn() returns, so a loop that starts new queries after the first
        # cancel stops too.
        while not finished.is_set():
            spark.interruptAll()
            finished.wait(1)

    mem_before = driver_memory_gb()
    mem_peak = [mem_before]

    def memory_sampler():  # peak, not just after-minus-before: memory freed before fn() returns still counts
        while not finished.wait(0.25):
            mem_peak[0] = max(mem_peak[0], driver_memory_gb())

    start = time.perf_counter()
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=memory_sampler, daemon=True).start()
    result, error = None, None
    try:
        result = fn()
    except Exception as e:  # the Don'ts are expected to fail sometimes; record instead of raising
        error = str(e).strip().splitlines()[0][:300] if str(e).strip() else type(e).__name__
    finally:
        finished.set()
    seconds = time.perf_counter() - start
    mem_delta = max(mem_peak[0], driver_memory_gb()) - mem_before  # peak growth during the cell

    status = "timed out" if cancelled_at else ("failed" if error else "ok")
    detail = note
    if isinstance(result, dict) and result.get("note"):
        detail = (detail + " " + result["note"]).strip()
    if detail_fn:
        detail = (detail + " " + detail_fn(seconds)).strip()

    factor = 1 / fraction if scaling == "linear" else 1 / fraction**2
    projected = seconds * factor
    projected_mem = mem_delta / fraction

    icon = {"ok": "✅", "timed out": "⏱️", "failed": "💥"}[status]
    print(f"{icon} {variant} | {scenario}")
    memory = (f"driver memory peaked at +{mem_delta:,.2f} GB" if mem_delta >= 0.05
              else "driver memory: no measurable growth (the work stayed in Spark)")
    print(f"   {status} after {_fmt_seconds(seconds)} · {memory}")
    if fraction < 1 and status != "failed":
        bound = "more than " if status == "timed out" else "≈ "
        line = f"   ran {fraction:.0%} of the workload → full size would take {bound}{_fmt_seconds(projected)}"
        if mem_delta >= 0.2:
            line += f" and need {bound}{projected_mem:,.0f} GB of driver memory (this driver has {DRIVER_RAM_GB:,.0f} GB"
            line += " → out of memory)" if projected_mem > 0.8 * DRIVER_RAM_GB else ")"
        print(line)
    if cancelled_at:
        overrun = seconds - cancelled_at[0]
        print(f"   the watchdog cancelled the Spark work at {cancelled_at[0]:,.0f} s", end="")
        print(f"; driver-side work kept the cell busy for another {overrun:,.0f} s" if overrun > 5 else "")
    if error and status != "timed out":
        print(f"   error: {error}")
    if detail:
        print(f"   {detail}")

    row = (CURRENT_USER, scenario, variant, status, round(seconds, 1), float(fraction),
           round(projected, 1), round(mem_delta, 2), round(projected_mem, 2), (detail or error or "")[:500])
    (
        spark.createDataFrame([row], "user STRING, scenario STRING, variant STRING, status STRING, seconds DOUBLE, "
                                     "fraction DOUBLE, projected_seconds DOUBLE, driver_mem_gb DOUBLE, "
                                     "projected_mem_gb DOUBLE, detail STRING")
        .withColumn("recorded_at", F.current_timestamp())
        .write.mode("append").saveAsTable(SCOREBOARD)
    )
    return result


def show_scoreboard():
    """Latest Don't vs Do result per scenario for the current user (read from workshop_scoreboard)."""
    latest = (
        spark.table(SCOREBOARD).where(F.col("user") == CURRENT_USER)
        .groupBy("scenario", "variant")
        .agg(F.max_by(F.struct("status", "seconds", "fraction", "projected_seconds", "projected_mem_gb"), "recorded_at").alias("r"))
        .select("scenario", "variant", "r.*")
    )
    dont = latest.where(F.col("variant") == "Don't").select(
        "scenario", F.col("status").alias("dont_status"), F.col("seconds").alias("dont_measured_s"),
        F.col("fraction").alias("dont_fraction"), F.col("projected_seconds").alias("dont_full_size_s"),
        F.col("projected_mem_gb").alias("dont_driver_mem_gb"))
    do = latest.where((F.col("variant") == "Do") & (F.col("status") == "ok")).groupBy("scenario").agg(F.min("seconds").alias("do_s"))
    return (
        dont.join(do, "scenario", "full_outer")
        .withColumn("speedup", F.round(F.col("dont_full_size_s") / F.col("do_s"), 1))
        .withColumn(
            "speedup_label",
            F.concat(
                F.when(F.col("dont_status") == "timed out", F.lit("> "))
                .when(F.col("dont_fraction") < 1, F.lit("≈ ")).otherwise(F.lit("")),
                F.col("speedup").cast("string"), F.lit("x")),
        )
        .orderBy("scenario")
    )


def display_now(df, max_rows=10_000, show_rows=100):
    """Do the work display(df) does (run the whole plan, bring back up to 10,000 rows), then render
    only the first show_rows from memory.

    Used inside the timed cells: the timing covers the full query, and the notebook doesn't have to load
    a 10,000-row output, which can fail with "Failed to fetch the result".
    """
    pdf = df.limit(max_rows).toPandas()
    print(f"{len(pdf):,} rows fetched (what display() would return); showing the first {min(show_rows, len(pdf))}")
    display(pdf.head(show_rows))
    return len(pdf)


print(f"Workshop data: {CATALOG}.{SCHEMA}   raw files: {VOLUME}   Don't timeout: {DONT_TIMEOUT_S} s")

# COMMAND ----------

SCORECARD_COLUMNS = ["dealer_id", "dealer_name", "orders", "customers", "net_revenue", "margin",
                     "top_category", "margin_pct", "revenue_rank"]


def check_dealer_scorecard(table, region="Midwest", month="2025-12"):
    """Compare a Genie Code challenge result table with the expected scorecard. Prints a verdict."""
    month_start = F.to_date(F.lit(f"{month}-01"))
    lines = (
        spark.table(T("fact_orders"))
        .where((F.col("order_date") >= month_start) & (F.col("order_date") < F.add_months(month_start, 1)))
        .join(spark.table(T("dim_dealer")).where(F.col("region") == region), "dealer_id")
        .join(spark.table(T("dim_part")), "part_id")
        .withColumn("rev", F.col("quantity") * F.col("unit_price") * (1 - F.col("discount_pct")))
    )
    expected = lines.groupBy("dealer_id").agg(
        F.count("*").alias("e_orders"),
        F.countDistinct("customer_id").alias("e_customers"),
        F.round(F.sum("rev"), 2).alias("e_net_revenue"),
        F.round(F.sum(F.col("rev") - F.col("quantity") * F.col("unit_cost")), 2).alias("e_margin"),
    )
    actual = spark.table(table)
    missing_cols = [c for c in SCORECARD_COLUMNS if c not in actual.columns]
    if missing_cols:
        print(f"❌ {table} is missing columns {missing_cols}")
        return False
    joined = expected.join(actual.withColumn("dealer_id", F.col("dealer_id").cast("int")), "dealer_id", "full_outer")
    problems = joined.where(
        F.col("orders").isNull() | F.col("e_orders").isNull()
        | (F.col("orders") != F.col("e_orders"))
        | (F.col("customers") != F.col("e_customers"))
        | (F.abs(F.col("net_revenue") - F.col("e_net_revenue")) > 0.05)
        | (F.abs(F.col("margin") - F.col("e_margin")) > 0.05)
    )
    n_problems = problems.count()
    ranks_ok = actual.select(F.min("revenue_rank"), F.max("revenue_rank"), F.count("*")).first()
    if n_problems == 0 and ranks_ok[0] == 1 and ranks_ok[1] == ranks_ok[2]:
        print(f"✅ {table} matches the expected scorecard ({ranks_ok[2]} dealers)")
        return True
    print(f"❌ {table}: {n_problems} dealers differ from the expected result")
    display(problems.limit(20))
    return False
