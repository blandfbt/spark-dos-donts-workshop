# Databricks notebook source
# MAGIC %md
# MAGIC # Workshop helpers
# MAGIC
# MAGIC Included by the workshop notebooks with `%run ./workshop_helpers`, right after `%run ../CONFIG`; you do not
# MAGIC run this notebook on its own, and there is nothing to edit here (your settings live in `CONFIG`).
# MAGIC
# MAGIC * **Shared DataFrames** (`orders`, `parts`, `wide`, ...) over the read-only source tables in
# MAGIC   `dbx_workshop_dev.shared` are defined here, so `%run`-ing CONFIG and this notebook at the top of any
# MAGIC   section restores everything that section needs, for example after a restart.
# MAGIC * **`run_timed(...)`** runs one Don't or Do, times it and prints the outcome.
# MAGIC   * A Don't usually runs on a **fraction** of the Do's workload so that it finishes in under a minute.
# MAGIC     The full-size time (and driver memory) is then **projected** from the measured run.
# MAGIC   * A watchdog is the safety net. After `dont_timeout_seconds` it cancels the cell's Spark work
# MAGIC     (`spark.interruptAll()`). Work that runs on the driver itself, such as converting rows to
# MAGIC     pandas, can't be cancelled, and the printout says how long that took.

# COMMAND ----------

import threading
import time

import numpy as np
import pandas as pd
import psutil
from pyspark.sql import functions as F
from pyspark.sql.window import Window

DONT_TIMEOUT_S = int(_job_param("dont_timeout_seconds", "120"))  # _job_param is defined in CONFIG

# COMMAND ----------

# Shared inputs (read-only source tables). All lazy: defining them reads no data.
orders = spark.table(SRC("sdd_fact_orders"))
parts = spark.table(SRC("sdd_dim_part"))
dealers = spark.table(SRC("sdd_dim_dealer"))
customers = spark.table(SRC("sdd_dim_customer"))
customer_history = spark.table(SRC("sdd_dim_customer_history"))
wide = spark.table(SRC("sdd_telemetry_wide"))
readings = spark.table(SRC("sdd_telemetry_readings"))
sessions = spark.table(SRC("sdd_track_sessions"))

net_revenue = F.col("quantity") * F.col("unit_price") * (1 - F.col("discount_pct"))


def sample_orders(fraction):
    """A deterministic slice of sdd_fact_orders: `fraction` of the rows, chosen by order_id."""
    return orders.where(F.col("order_id") % 1000 < int(round(fraction * 1000)))


# COMMAND ----------

DRIVER_RAM_GB = psutil.virtual_memory().total / 1024**3


def driver_memory_gb():
    """Resident memory (RSS) of this notebook's Python process: where collect()/toPandas() results land.
    The Spark engine and executors run remotely on serverless and are not included."""
    return psutil.Process().memory_info().rss / 1024**3


def _fmt_seconds(s):
    return f"{s:,.1f} s" if s < 90 else (f"{s / 60:,.1f} min" if s < 5400 else f"{s / 3600:,.1f} h")


def run_timed(scenario, variant, fn, fraction=1.0, scaling="linear", timeout_s=None, note="", detail_fn=None):
    """Run fn(), time it and print the outcome.

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

    return result


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


print(f"Don't timeout: {DONT_TIMEOUT_S} s")

# COMMAND ----------

SCORECARD_COLUMNS = ["dealer_id", "dealer_name", "orders", "customers", "net_revenue", "margin",
                     "top_category", "margin_pct", "revenue_rank"]


def check_dealer_scorecard(table, region="Midwest", month="2025-12"):
    """Compare a Genie Code challenge result table with the expected scorecard. Prints a verdict."""
    month_start = F.to_date(F.lit(f"{month}-01"))
    lines = (
        spark.table(SRC("sdd_fact_orders"))
        .where((F.col("order_date") >= month_start) & (F.col("order_date") < F.add_months(month_start, 1)))
        .join(spark.table(SRC("sdd_dim_dealer")).where(F.col("region") == region), "dealer_id")
        .join(spark.table(SRC("sdd_dim_part")), "part_id")
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
