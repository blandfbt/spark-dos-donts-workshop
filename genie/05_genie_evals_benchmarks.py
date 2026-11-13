# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Notebook 05 · Benchmarks and evaluation
# MAGIC
# MAGIC **What you'll learn:** how to define **[benchmark questions](https://docs.databricks.com/aws/en/genie/benchmarks)**
# MAGIC for your Genie agent: questions with known SQL answers that let you measure accuracy over time.
# MAGIC
# MAGIC **Why this matters:** when you change instructions, add examples, or Databricks updates the model, benchmarks tell
# MAGIC you whether Genie got better or worse. Think of them as **unit tests for your Genie agent**.
# MAGIC
# MAGIC **What this notebook does:**
# MAGIC 1. Defines **two** benchmark suites: a 12-question table-based suite and a 5-question metric-view suite.
# MAGIC 2. Verifies each ground-truth query runs against the shared data.
# MAGIC 3. Pushes benchmarks to **all three agents** (Baseline, Metric View, Knowledge Store) via the `serialized_space` API.
# MAGIC 4. Guides you to **run benchmarks in the Genie UI** (the most accurate evaluator) and compare pass rates.
# MAGIC 5. Shows how to **fix failures by updating instructions** programmatically.
# MAGIC 6. Runs a 4-question smoke test through the Conversation API.
# MAGIC
# MAGIC **Before you start:** run **03** (baseline), **03b** (metric view) and **04** (Knowledge Store) so all three agents
# MAGIC exist. **Compute:** Serverless.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tips for writing good benchmarks
# MAGIC
# MAGIC - Ask for **one clear number or small result** per question (easy to score automatically).
# MAGIC - Compute expected answers in **SQL from the same tables** Genie uses: no manual guesswork.
# MAGIC - Mix **counts, sums, ratios and filters** (net revenue, orders, margin %, revenue per order).
# MAGIC - Use questions **real users would ask**; update benchmarks when the schema changes.
# MAGIC - In notebook 08 (compare), allow a small tolerance for rounding on ratio queries.
# MAGIC - The **example SQL** in notebook 04 teaches Genie *style*; benchmarks here track *correctness* over time.
# MAGIC - If the API step errors, you can add the same questions under **Benchmark** in the Genie UI.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ../CONFIG

# COMMAND ----------

# DBTITLE 1,⚙️ Genie helpers
# MAGIC %run ./genie_helpers

# COMMAND ----------

# MAGIC %md
# MAGIC ## Connect and load your agent IDs
# MAGIC
# MAGIC Read the Baseline / Metric View / Knowledge Store ids saved by notebooks 03 to 04 in your `genie_workshop_config` table.

# COMMAND ----------

_cfg = load_config()
PRIMARY_SPACE_ID = _cfg.get(CFG_KEY_CURATED, "")
BLANK_SPACE_ID = _cfg.get(CFG_KEY_BASELINE, "")        # Baseline (03)
METRIC_SPACE_ID = _cfg.get(CFG_KEY_METRIC_VIEW, "")    # Metric View (03b)

if not PRIMARY_SPACE_ID:
    raise RuntimeError("genie_space_id not found in genie_workshop_config. Run notebook 04 first.")

print("Your Genie agents (click to open):")
print(f"  Knowledge Store (primary): {genie_ui_room_url(PRIMARY_SPACE_ID)}")
if METRIC_SPACE_ID:
    print(f"  Metric View:               {genie_ui_room_url(METRIC_SPACE_ID)}")
if BLANK_SPACE_ID:
    print(f"  Baseline (no curation):    {genie_ui_room_url(BLANK_SPACE_ID)}")
print()
print("Benchmarks are pushed to ALL THREE agents so you can compare pass rates in the UI:")
print("  - Baseline + Knowledge Store get the table-based suite (they see the four tables).")
print("  - Metric View gets a KPI-by-dimension suite scoped to genie_mv_dealer_sales / genie_mv_category_sales.")
print("After this notebook completes, open the Benchmark tab for each agent and click Run all benchmarks.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Define the benchmark suites
# MAGIC
# MAGIC **Table-based suite (`benchmarks_v1`, 12 questions)**: for the **Baseline** and **Knowledge Store** agents, which
# MAGIC see the four tables.
# MAGIC
# MAGIC - **Core (Q1 to Q7):** counts, sums and filters that any well-configured agent should get right.
# MAGIC - **Pattern-teaching (Q8 to Q12):** harder questions that teach the patterns Genie needs (weighted margin %, the
# MAGIC   dealers-dim join for state, revenue per order, Monday-start weeks). They are intentionally **different** from the
# MAGIC   4 evaluation questions in notebook 08: Genie must generalize from these patterns, not memorize answers.
# MAGIC
# MAGIC **Metric-view suite (`benchmarks_mv`, 5 questions)**: for the **Metric View** agent, which sees only the two
# MAGIC governed metric views. These are KPI-by-dimension questions answerable with `MEASURE()`. The table-based suite
# MAGIC would be unfair to it (it can't reach the parts dim or the raw columns), so it gets its own suite; the slices
# MAGIC differ from the metric-view agent's example SQL so they still test generalization. Ground truth is computed from
# MAGIC the **base tables**, so it's independent of the metric views.

# COMMAND ----------

D, C, DL, P = GOLD_DAILY_TABLE, GOLD_CATEGORY_TABLE, DEALERS_TABLE, PARTS_TABLE

benchmarks_v1 = [
    # --- Core benchmarks (Q1-Q7) ---
    {"q": "What was the total net revenue across all dealers in December 2025?",
     "gt": f"SELECT CAST(ROUND(SUM(net_revenue), 2) AS DOUBLE) AS net_revenue FROM {D}"},
    {"q": "How many distinct dealers had at least one order in December 2025?",
     "gt": f"SELECT CAST(COUNT(DISTINCT dealer_id) AS BIGINT) AS dealers FROM {D}"},
    {"q": "How many units were sold in the Northeast region in December 2025?",
     "gt": f"SELECT CAST(SUM(units) AS BIGINT) AS units FROM {D} WHERE region = 'Northeast'"},
    {"q": "How many dealers are located in Michigan?",
     "gt": f"SELECT CAST(COUNT(*) AS BIGINT) AS dealers FROM {DL} WHERE state = 'MI'"},
    {"q": "What is the average list price of parts in the Brakes category, rounded to 2 decimals?",
     "gt": f"SELECT CAST(ROUND(AVG(list_price), 2) AS DOUBLE) AS avg_list_price FROM {P} WHERE category = 'Brakes'"},
    {"q": "What was the total net revenue on December 24, 2025?",
     "gt": f"SELECT CAST(ROUND(SUM(net_revenue), 2) AS DOUBLE) AS net_revenue FROM {D} WHERE order_date = DATE'2025-12-24'"},
    {"q": "How many order lines did Standard tier dealers have in December 2025?",
     "gt": f"SELECT CAST(SUM(orders) AS BIGINT) AS orders FROM {D} WHERE dealer_tier = 'Standard'"},
    # --- Pattern-teaching benchmarks (Q8-Q12) ---
    # They teach the patterns the 4 evaluation questions in 08 need, with DIFFERENT tiers/regions/states/weeks.
    {"q": "What was the margin % for Gold tier dealers in December 2025, as total margin divided by total net revenue?",
     "gt": f"SELECT CAST(ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) AS DOUBLE) AS margin_pct "
            f"FROM {D} WHERE dealer_tier = 'Gold'"},
    {"q": "What was the margin % for the Suspension category in the Southeast region?",
     "gt": f"SELECT CAST(ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) AS DOUBLE) AS margin_pct "
            f"FROM {C} WHERE region = 'Southeast' AND category = 'Suspension'"},
    {"q": "How many order lines did dealers located in Ohio have in December 2025?",
     "gt": f"SELECT CAST(SUM(s.orders) AS BIGINT) AS orders FROM {D} s JOIN {DL} d ON s.dealer_id = d.dealer_id "
            f"WHERE d.state = 'OH'"},
    {"q": "What was the average revenue per order in the Northwest region in December 2025?",
     "gt": f"SELECT CAST(ROUND(SUM(net_revenue) / NULLIF(SUM(orders), 0), 2) AS DOUBLE) AS avg_revenue_per_order "
            f"FROM {D} WHERE region = 'Northwest'"},
    {"q": "What was the total net revenue in the week starting Monday, December 22, 2025?",
     "gt": f"SELECT CAST(ROUND(SUM(net_revenue), 2) AS DOUBLE) AS net_revenue FROM {D} "
            f"WHERE CAST(DATE_TRUNC('WEEK', order_date) AS DATE) = DATE'2025-12-22'"},
]
# --- Metric-view suite (for the Metric View agent; answerable from the two metric views) ---
benchmarks_mv = [
    {"q": "What was the net revenue for each region in December 2025?",
     "gt": f"SELECT region, CAST(ROUND(SUM(net_revenue), 2) AS DOUBLE) AS net_revenue FROM {D} GROUP BY region ORDER BY region"},
    {"q": "What is the margin % for each part category in the Northeast region?",
     "gt": f"SELECT category, CAST(ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) AS DOUBLE) AS margin_pct "
           f"FROM {C} WHERE region = 'Northeast' GROUP BY category ORDER BY category"},
    {"q": "How many dealers had sales in each dealer tier?",
     "gt": f"SELECT dealer_tier, CAST(COUNT(DISTINCT dealer_id) AS BIGINT) AS dealers FROM {D} GROUP BY dealer_tier ORDER BY dealer_tier"},
    {"q": "What was the average revenue per order for dealers located in California?",
     "gt": f"SELECT CAST(ROUND(SUM(s.net_revenue) / NULLIF(SUM(s.orders), 0), 2) AS DOUBLE) AS avg_revenue_per_order "
           f"FROM {D} s JOIN {DL} d ON s.dealer_id = d.dealer_id WHERE d.state = 'CA'"},
    {"q": "How many units were sold each week in December 2025?",
     "gt": f"SELECT CAST(DATE_TRUNC('WEEK', order_date) AS DATE) AS order_week, CAST(SUM(units) AS BIGINT) AS units "
           f"FROM {D} GROUP BY 1 ORDER BY 1"},
]
print(f"{len(benchmarks_v1)} table-based + {len(benchmarks_mv)} metric-view benchmarks defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify the ground truth in Spark
# MAGIC
# MAGIC Run each ground-truth query once. Fix definitions before pushing to Genie if any fail.

# COMMAND ----------

print("=== Table-based suite (Baseline + Knowledge Store) ===")
for i, b in enumerate(benchmarks_v1, 1):
    try:
        v = spark.sql(b["gt"]).collect()[0][0]
        print(f"OK  Q{i}: {v}")
    except Exception as e:
        print(f"FAIL Q{i}: {e}")

print("\n=== Metric-view suite (Metric View agent) ===")
for i, b in enumerate(benchmarks_mv, 1):
    try:
        rows = spark.sql(b["gt"]).collect()
        preview = rows[0][-1] if rows else "no rows"
        print(f"OK  MV Q{i}: {len(rows)} row(s), first value = {preview}")
    except Exception as e:
        print(f"FAIL MV Q{i}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Push benchmarks to the Genie Benchmark tab
# MAGIC
# MAGIC Pushes the table-based suite to the Knowledge Store and Baseline agents and the metric-view suite to the Metric
# MAGIC View agent, using the `serialized_space` API (`GET` with `include_serialized_space=true`, then
# MAGIC `PATCH`). This reads the current agent configuration, replaces only the `benchmarks.questions` section, and writes
# MAGIC the full blob back, preserving all other settings (instructions, example SQL, sample questions, tables).
# MAGIC
# MAGIC They appear in the **Benchmark** tab of the Genie UI (not the SQL Queries section). Existing benchmarks are
# MAGIC replaced, so the notebook is idempotent on re-run.
# MAGIC
# MAGIC > You can also add benchmarks manually in the Genie UI (Benchmark tab → Add question). The programmatic approach is
# MAGIC > convenient for bulk loading and reproducibility.

# COMMAND ----------

def push_benchmarks(benchmarks_list, space_id, label=""):
    """Push benchmarks via the serialized_space API (GET-merge-PATCH).

    Reads the current agent config with include_serialized_space=true, replaces only benchmarks.questions,
    and PATCHes the full blob back. All other config (instructions, example SQL, tables) is preserved.
    """
    # 1. READ the current agent config
    current = requests.get(
        f"{host}/api/2.0/genie/spaces/{space_id}",
        headers=headers,
        params={"include_serialized_space": "true"},
    ).json()
    config = json.loads(current.get("serialized_space", "{}"))
    if not config:
        print(f"ERROR: Could not read serialized_space for {space_id}. Is the agent ID correct?")
        return

    prev_count = len(config.get("benchmarks", {}).get("questions", []))

    # 2. MODIFY: build benchmark questions in the serialized_space format (sorted by id)
    benchmark_questions = sorted(
        [{"id": new_id(), "question": [b["q"]], "answer": [{"format": "SQL", "content": [b["gt"]]}]}
         for b in benchmarks_list],
        key=lambda x: x["id"],
    )
    config.setdefault("benchmarks", {})["questions"] = benchmark_questions
    config["version"] = 2

    # 3. WRITE back
    r = requests.patch(
        f"{host}/api/2.0/genie/spaces/{space_id}",
        headers=headers,
        json={"serialized_space": json.dumps(config)},
    )
    if r.status_code == 200:
        print(f"{label}: {len(benchmarks_list)} benchmarks pushed (replaced {prev_count} existing)")
    else:
        print(f"PATCH failed: {r.status_code} {r.text[:300]}")


push_benchmarks(benchmarks_v1, PRIMARY_SPACE_ID, "Knowledge Store benchmarks")
if BLANK_SPACE_ID:
    push_benchmarks(benchmarks_v1, BLANK_SPACE_ID, "Baseline benchmarks")
else:
    print("Baseline agent id not found: run notebook 03 to include it in the comparison.")
if METRIC_SPACE_ID:
    push_benchmarks(benchmarks_mv, METRIC_SPACE_ID, "Metric View benchmarks")
else:
    print("Metric View agent id not found: run notebook 03b to include it in the comparison.")

print("\nBenchmarks pushed. Open the Benchmark tab for each agent and click Run all benchmarks:")
print(f"  Knowledge Store: {genie_ui_room_url(PRIMARY_SPACE_ID)}")
if METRIC_SPACE_ID:
    print(f"  Metric View:     {genie_ui_room_url(METRIC_SPACE_ID)}")
if BLANK_SPACE_ID:
    print(f"  Baseline:        {genie_ui_room_url(BLANK_SPACE_ID)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run benchmarks in the Genie UI
# MAGIC
# MAGIC The benchmark evaluator runs in the **UI**. It:
# MAGIC
# MAGIC 1. Asks Genie each benchmark question
# MAGIC 2. Runs **both** Genie's generated SQL and your ground-truth SQL
# MAGIC 3. Compares the **full result sets** (not just a single number)
# MAGIC 4. Shows a SQL diff analysis for any mismatches
# MAGIC
# MAGIC **To run benchmarks:** open the agent link below → **Benchmark** tab → **Run all benchmarks** → wait for all questions →
# MAGIC review pass/fail; click any failed question to see the failure analysis.

# COMMAND ----------

print("Open the Benchmark tab to evaluate:")
print(f"  {genie_ui_room_url(PRIMARY_SPACE_ID)}")
print()
print("Click 'Run all benchmarks' and review the results.")
print("Note any failures: we'll fix them in the next steps.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Fix failures: two tools the UI gives you
# MAGIC
# MAGIC ### Tool 1: Accept knowledge snippets (primary fix)
# MAGIC
# MAGIC When a benchmark fails, the UI proposes **knowledge snippets**: patterns Genie can learn from the failure. Click
# MAGIC **Review proposed fixes** on any failed benchmark to see them, for example:
# MAGIC
# MAGIC | Category | Example | What it teaches Genie |
# MAGIC |---|---|---|
# MAGIC | **FILTER** | `lab_silver_dealers_dim.state = 'OH'` means "dealers in Ohio" | state names map to two-letter codes |
# MAGIC | **JOIN** | daily dealer sales JOIN dealers dim ON `dealer_id` | where a dealer's state comes from |
# MAGIC | **MEASURE** | `100 * SUM(margin) / SUM(net_revenue)` means "margin %" | weighted, not averaged |
# MAGIC | **MEASURE** | `SUM(net_revenue) / SUM(orders)` means "revenue per order" | not an average of daily averages |
# MAGIC | **FILTER** | `CAST(DATE_TRUNC('WEEK', order_date) AS DATE) = '2025-12-22'` means "week of Dec 22" | Monday-start weeks |
# MAGIC
# MAGIC **These are suggestions, not guaranteed fixes.** Review each one with your domain knowledge: "Is this the SQL
# MAGIC pattern I want Genie to use for all future questions like this?" Accept the ones that match your conventions.
# MAGIC
# MAGIC ### Tool 2: Update ground truth SQL (secondary fix)
# MAGIC
# MAGIC Some failures are **style differences**, not logic errors: Genie and your ground truth return the same result with
# MAGIC different SQL, for example `ROUND(x, 2)` vs. `CAST(ROUND(x, 2) AS DOUBLE)`, or `order_date BETWEEN '2025-12-22' AND
# MAGIC '2025-12-28'` vs. the `DATE_TRUNC('WEEK', ...)` filter. For these, click **Update ground truth** and use Genie's
# MAGIC version, but only after confirming both queries return the same result on this data.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Advanced: update instructions programmatically
# MAGIC
# MAGIC If snippets and ground-truth updates aren't enough (Genie keeps making the same mistake across questions), **add
# MAGIC rules to the agent instructions** via the API. The cell below reads the current configuration
# MAGIC (`include_serialized_space=true`), appends rules to `text_instructions`, and PATCHes it back. Everything else is
# MAGIC preserved. Edit `ADDITIONAL_RULES` based on the patterns you see failing, run the cell, and re-run benchmarks.

# COMMAND ----------

ADDITIONAL_RULES = [
    "When filtering by region, dealer_tier or category, use exact match (= 'Midwest'), not ILIKE or partial match.",
    "Map US state names to two-letter codes before filtering lab_silver_dealers_dim.state (Ohio = 'OH').",
    "For integer counts cast the final result with CAST(... AS BIGINT); for money and rates use CAST(ROUND(..., 2) AS DOUBLE).",
]

# 1. READ the current agent config
current = requests.get(
    f"{host}/api/2.0/genie/spaces/{PRIMARY_SPACE_ID}",
    headers=headers,
    params={"include_serialized_space": "true"},
).json()
config = json.loads(current.get("serialized_space", "{}"))
if not config:
    raise RuntimeError("Could not read serialized_space. Check that PRIMARY_SPACE_ID is correct.")

# 2. MODIFY: append rules to the existing text_instructions (content is a list of strings)
existing_ti = config.get("instructions", {}).get("text_instructions", [])
if existing_ti and existing_ti[0].get("content"):
    existing_content = existing_ti[0]["content"]
    existing_id = existing_ti[0].get("id", new_id())
else:
    existing_content = []
    existing_id = new_id()

if not any("Additional Rules:" in line for line in existing_content):
    updated_content = existing_content + ["\n", "Additional Rules:\n"] + [f"- {r}\n" for r in ADDITIONAL_RULES]
    print(f"Appending {len(ADDITIONAL_RULES)} rules to instructions.")
else:
    updated_content = existing_content
    print("Additional Rules already present: skipping to avoid duplicates.")

config.setdefault("instructions", {})["text_instructions"] = [{"id": existing_id, "content": updated_content}]
config["version"] = 2

# 3. WRITE back: full replace, but we read first so everything is preserved
r = requests.patch(
    f"{host}/api/2.0/genie/spaces/{PRIMARY_SPACE_ID}",
    headers=headers,
    json={"serialized_space": json.dumps(config)},
)
if r.status_code == 200:
    print(f"Instructions updated. Total lines: {len(updated_content)}")
else:
    print(f"PATCH failed: {r.status_code} {r.text[:300]}")

print("\nRe-run benchmarks in the UI to verify the improvement:")
print(f"  {genie_ui_room_url(PRIMARY_SPACE_ID)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Iterate until 100%
# MAGIC
# MAGIC 1. **Run benchmarks** in the UI (Benchmark tab, Run all benchmarks)
# MAGIC 2. **Review failures**: click each failed question to see the failure analysis
# MAGIC 3. **Accept knowledge snippets**: click Review proposed fixes, accept correct patterns
# MAGIC 4. **Update ground truth**: if the SQL is equivalent but styled differently
# MAGIC 5. **Programmatic fix** (optional): if a pattern keeps failing, add a rule in the cell above
# MAGIC 6. **Re-run** and check that the fixes worked
# MAGIC
# MAGIC **Targets:** **100%** on synthetic data like this workshop's; **85%+** on real customer data.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Smoke test: 4 hard questions
# MAGIC
# MAGIC Once your benchmarks are green in the UI, run these 4 questions against the primary (Knowledge Store) agent. They
# MAGIC are **not** benchmarks: they test whether Genie can **generalize** from your curation to questions it has never seen.
# MAGIC
# MAGIC | # | Question | What makes it hard |
# MAGIC |---|---|---|
# MAGIC | H1 | Net revenue, Platinum dealers in California, Dec 25 to 31 | tier filter + state join + date range |
# MAGIC | H2 | Dealers whose margin % beats the company-wide margin % | weighted ratio per dealer vs. a weighted overall ratio |
# MAGIC | H3 | Best week of net revenue in the Southwest | Monday-start weeks + MAX over a grouped subquery |
# MAGIC | H4 | Lowest-margin part category in the Northwest | the category table, not the daily table |
# MAGIC
# MAGIC Notebook **08** runs a separate set of KPI-by-dimension questions across all three agents.

# COMMAND ----------

TOLERANCE_PCT = 5.0

hard_questions = [
    {"q": "What was the net revenue of Platinum tier dealers located in California between December 25 and December 31, 2025?",
     "gt": f"SELECT CAST(ROUND(SUM(s.net_revenue), 2) AS DOUBLE) FROM {D} s JOIN {DL} d ON s.dealer_id = d.dealer_id "
           f"WHERE s.dealer_tier = 'Platinum' AND d.state = 'CA' AND s.order_date BETWEEN DATE'2025-12-25' AND DATE'2025-12-31'",
     "short": "Platinum CA, Dec 25-31"},
    {"q": "How many dealers had a December 2025 margin % (total margin / total net revenue) higher than the company-wide margin %?",
     "gt": f"SELECT CAST(COUNT(*) AS BIGINT) FROM (SELECT dealer_id, SUM(margin) / SUM(net_revenue) AS r FROM {D} "
           f"GROUP BY dealer_id) t WHERE r > (SELECT SUM(margin) / SUM(net_revenue) FROM {D})",
     "short": "Dealers above company margin %"},
    {"q": "In the Southwest region, what was the net revenue of the best week of December 2025? Weeks start on Monday; return only the highest weekly net revenue.",
     "gt": f"SELECT CAST(ROUND(MAX(rev), 2) AS DOUBLE) FROM (SELECT CAST(DATE_TRUNC('WEEK', order_date) AS DATE) AS wk, "
           f"SUM(net_revenue) AS rev FROM {D} WHERE region = 'Southwest' GROUP BY 1) t",
     "short": "Best Southwest week"},
    {"q": "Which part category has the lowest margin % in the Northwest region? Return that margin %.",
     "gt": f"SELECT CAST(ROUND(MIN(100.0 * margin / NULLIF(net_revenue, 0)), 2) AS DOUBLE) FROM {C} WHERE region = 'Northwest'",
     "short": "Lowest-margin category, Northwest"},
]

print("Smoke test: 4 hard questions against the primary (Knowledge Store) agent")
print(f"Agent: {genie_ui_room_url(PRIMARY_SPACE_ID)}\n")
passes = 0
for i, hq in enumerate(hard_questions, 1):
    gt_val = float(spark.sql(hq["gt"]).collect()[0][0])
    genie_val, err = ask_genie(hq["q"], PRIMARY_SPACE_ID)
    status = score(genie_val, gt_val, TOLERANCE_PCT)
    passes += status == "PASS"
    print(f"  H{i} ({hq['short']}): {status} (GT={gt_val}, Genie={genie_val}{f', err={err}' if err else ''})")

rate = passes / len(hard_questions) * 100
print(f"\nSmoke test: {passes}/{len(hard_questions)} ({rate:.0f}%)")
print("All 4 hard questions passed. Ready for notebook 06." if rate == 100
      else "Some questions failed. Review the instructions and example SQL in notebook 04.")
