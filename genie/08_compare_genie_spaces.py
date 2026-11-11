# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 08 · Compare three agents: does curation actually help?
# MAGIC
# MAGIC The proof. We run the **same four questions** against the three agents built earlier, all on the same data, and
# MAGIC compare accuracy:
# MAGIC
# MAGIC | Agent | Built in | What it has |
# MAGIC |---|---|---|
# MAGIC | **Baseline** | 03 | Tables only, minimal instructions |
# MAGIC | **Metric View** | 03b | Two governed metric views (pinned joins + KPI formulas) + example `MEASURE()` SQL |
# MAGIC | **Knowledge Store** | 04 | Column configs, synonyms, joins, measures, filters, example SQL |
# MAGIC
# MAGIC **The questions are KPI-by-dimension**, exactly what both curated approaches are built for. Each one hinges on
# MAGIC something a **blank agent** typically gets wrong:
# MAGIC
# MAGIC | # | Question | Where a blank agent slips |
# MAGIC |---|---|---|
# MAGIC | Q1 | **Margin %**: Platinum dealers | averages daily percentages instead of `SUM(margin) / SUM(net_revenue)` |
# MAGIC | Q2 | **Margin %**: Brakes, all regions | `AVG(margin_pct)` over six regional rows instead of recomputing from the sums |
# MAGIC | Q3 | **Net revenue**: dealers in Texas | must join to the dealers dim and know Texas is `'TX'` (and not confuse it with the Southwest region) |
# MAGIC | Q4 | **Revenue per order**: Midwest, week of Dec 8 | Monday-start week + `SUM / SUM`, not an average of daily averages |
# MAGIC
# MAGIC **What to expect:** the Baseline guesses formulas and joins and misses several; the **Metric View** and **Knowledge
# MAGIC Store** agents both pin those and should score high. Curation is what makes an agent trustworthy.
# MAGIC
# MAGIC **Perimeter note:** the metric views are deterministic *within their scope*. A question that needs both category
# MAGIC and dealer (e.g. "Brakes revenue at Platinum dealers") is outside every gold table: pair metric views with the
# MAGIC table-based Knowledge Store agent, and add gold tables when such questions matter.
# MAGIC
# MAGIC **Before you start:** run **03** (baseline), **03b** (metric view), **04** (knowledge store). **Compute:** Serverless.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ../CONFIG

# COMMAND ----------

# DBTITLE 1,⚙️ Genie helpers
# MAGIC %run ./genie_helpers

# COMMAND ----------

# MAGIC %md
# MAGIC ## Connect and load the three agent IDs
# MAGIC
# MAGIC Read the Baseline, Metric View and Knowledge Store ids from your `workshop_config` table so we can compare them.

# COMMAND ----------

from datetime import datetime

from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

_cfg = load_config()
BASELINE_ID = _cfg.get(CFG_KEY_BASELINE, "")
CURATED_ID = _cfg.get(CFG_KEY_CURATED, "")
METRIC_ID = _cfg.get(CFG_KEY_METRIC_VIEW, "")

if not CURATED_ID:
    raise RuntimeError("genie_space_id (Knowledge Store agent) not found. Run notebook 04 first.")

AGENTS = [(name, sid) for name, sid in [
    ("Baseline", BASELINE_ID),
    ("Metric View", METRIC_ID),
    ("Knowledge Store", CURATED_ID),
] if sid]

print("Comparing:")
for name, sid in AGENTS:
    print(f"  {name:<16} {genie_ui_room_url(sid)}")
if len(AGENTS) < 3:
    print("\nNote: run 03 / 03b / 04 to compare all three. Continuing with what exists.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scoring function
# MAGIC
# MAGIC Sends a question to an agent through the Conversation API (`ask_genie`), waits for the answer, takes the number in
# MAGIC the first result row, and compares it to the ground-truth SQL within `BENCHMARK_TOLERANCE_PCT`.

# COMMAND ----------

def run_benchmarks(benchmarks, space_id, label):
    """Ask each question, score against ground truth. Returns (results, pass_rate)."""
    print(f"\n{label}")
    results, passes = [], 0
    for i, b in enumerate(benchmarks, 1):
        gt_val = float(spark.sql(b["gt"]).collect()[0][0])
        genie_val, err = ask_genie(b["q"], space_id, timeout=160)
        status = score(genie_val, gt_val)
        passes += status == "PASS"
        print(f"  Q{i}: {status} (GT={gt_val}, Genie={genie_val}{f', err={err}' if err else ''})")
        results.append((i, b["q"], gt_val, genie_val, status))
    rate = (passes / len(benchmarks) * 100) if benchmarks else 0
    print(f"  Pass rate: {rate:.0f}% ({passes}/{len(benchmarks)})")
    return results, rate


print("Scoring function ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The four KPI-by-dimension questions
# MAGIC
# MAGIC Ground truth is computed from the shared base tables, so it's independent of any agent's configuration.

# COMMAND ----------

D, C, DL = GOLD_DAILY_TABLE, GOLD_CATEGORY_TABLE, DEALERS_TABLE

questions = [
    {"q": "What was the margin % for Platinum tier dealers in December 2025?",
     "gt": f"SELECT CAST(ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) AS DOUBLE) FROM {D} "
           f"WHERE dealer_tier = 'Platinum'",
     "short": "Margin % - Platinum dealers"},
    {"q": "What is the margin % for the Brakes part category across all regions?",
     "gt": f"SELECT CAST(ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) AS DOUBLE) FROM {C} "
           f"WHERE category = 'Brakes'",
     "short": "Margin % - Brakes, all regions"},
    {"q": "What was the total net revenue of dealers located in Texas in December 2025?",
     "gt": f"SELECT CAST(ROUND(SUM(s.net_revenue), 2) AS DOUBLE) FROM {D} s JOIN {DL} d ON s.dealer_id = d.dealer_id "
           f"WHERE d.state = 'TX'",
     "short": "Net revenue - Texas dealers"},
    {"q": "What was the average net revenue per order in the Midwest region for the week starting Monday, December 8, 2025?",
     "gt": f"SELECT CAST(ROUND(SUM(net_revenue) / NULLIF(SUM(orders), 0), 2) AS DOUBLE) FROM {D} "
           f"WHERE region = 'Midwest' AND CAST(DATE_TRUNC('WEEK', order_date) AS DATE) = DATE'2025-12-08'",
     "short": "Revenue/order - Midwest, wk Dec 8"},
]
print(f"{len(questions)} questions ready.")
print("Ground truth:")
for i, b in enumerate(questions, 1):
    print(f"  Q{i} ({b['short']}): {spark.sql(b['gt']).collect()[0][0]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run the comparison
# MAGIC
# MAGIC Each question goes to every agent. This calls the live Genie API, so it takes a few minutes.

# COMMAND ----------

all_results = {}   # name -> (results, rate)
for name, sid in AGENTS:
    all_results[name] = run_benchmarks(questions, sid, f"=== {name} ===")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Results side by side

# COMMAND ----------

names = [n for n, _ in AGENTS]
header = f"{'Q#':<4} {'Question':<36}" + "".join(f"{n:<20}" for n in names)
print("=" * len(header))
print("THREE-WAY COMPARISON")
print("=" * len(header))
print(header)
print("-" * len(header))
for idx, hq in enumerate(questions):
    row = f"Q{idx + 1:<3} {hq['short']:<36}"
    for n in names:
        res = all_results[n][0][idx]
        row += f"{res[4] + ' (' + str(res[3]) + ')':<20}"
    print(row)
print("-" * len(header))
print(f"{'Pass rate':<41}" + "".join(f"{str(int(all_results[n][1])) + '%':<20}" for n in names))
print()
print("Reading the result:")
base = all_results.get("Baseline", (None, None))[1]
for n in ("Metric View", "Knowledge Store"):
    if n in all_results and base is not None:
        r = all_results[n][1]
        verdict = "beats" if r > base else ("matches" if r == base else "trails")
        print(f"  - {n}: {int(r)}%  ({verdict} Baseline {int(base)}%)")
print("  The baseline guesses formulas (averaging percentages), joins and state codes, and misses several.")
print("  Both curated agents pin those, so they answer reliably: that is what earns user trust.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save the run history
# MAGIC
# MAGIC Appends the results to `genie_benchmark_runs` in **your** schema so notebook **10** (monitoring) can chart
# MAGIC pass-rate trends.

# COMMAND ----------

ts = datetime.now().isoformat()
sch = StructType([
    StructField("benchmark_id", IntegerType()),
    StructField("question", StringType()),
    StructField("ground_truth", DoubleType()),
    StructField("genie_answer", DoubleType()),
    StructField("status", StringType()),
    StructField("run_timestamp", StringType()),
    StructField("pass_rate", DoubleType()),
    StructField("run_label", StringType()),
])
rows = []
for name, (results, rate) in all_results.items():
    label = "compare_" + name.lower().replace(" ", "_")
    rows += [(r[0], r[1], r[2], r[3], r[4], ts, float(rate), label) for r in results]

try:
    spark.createDataFrame(rows, sch).write.mode("append").saveAsTable(BENCHMARK_RUNS_TABLE)
except Exception:
    spark.sql(f"DROP TABLE IF EXISTS {BENCHMARK_RUNS_TABLE}")
    spark.createDataFrame(rows, sch).write.saveAsTable(BENCHMARK_RUNS_TABLE)
print(f"Saved {len(rows)} results to {BENCHMARK_RUNS_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validate in the UI (most accurate)
# MAGIC
# MAGIC The programmatic scorer compares one number with a tolerance. The Genie **Benchmark** tab compares full result sets
# MAGIC and is the most accurate evaluator.
# MAGIC
# MAGIC 1. Open the **Knowledge Store** and **Metric View** agent links above.
# MAGIC 2. Click the **Benchmark** tab → **Start new run**.
# MAGIC 3. Review failures; for each, **Review proposed fixes** and accept the knowledge snippets that match your
# MAGIC    conventions, or **Update ground truth** if Genie's SQL is equivalent.
# MAGIC 4. Re-run until green. Target **80%+ before UAT**, higher on clean data.
# MAGIC
# MAGIC **Next:** notebook **10**: monitor and improve your agent.
