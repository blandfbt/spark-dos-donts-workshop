# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 03 · Create the Baseline Genie agent
# MAGIC
# MAGIC **What you'll learn:** how to create a Genie agent from Unity Catalog tables: the natural-language interface
# MAGIC where users ask questions and Genie writes the SQL.
# MAGIC
# MAGIC This is the **first of three agents** the workshop builds on the *same* Apex Motorsports Parts sales data, so we
# MAGIC can prove that **curation is what earns trust**:
# MAGIC
# MAGIC | Notebook | Agent | What it has |
# MAGIC |---|---|---|
# MAGIC | **03 (here)** | **Baseline** | Tables only, minimal instructions: the *before* |
# MAGIC | **03b** | **Metric View** | Built on governed metric views (semantic layer) |
# MAGIC | **04** | **Knowledge Store** | Column configs, synonyms, joins, measures, filters, example SQL: the *after* |
# MAGIC
# MAGIC Notebook **08** runs the same hard questions against all three and shows the accuracy difference.
# MAGIC
# MAGIC **Why start blank?** So the gain from curation is *measured*, not assumed. A tables-only agent has to guess join
# MAGIC paths and business formulas (is "margin %" an average of percentages or total margin ÷ total revenue? where does
# MAGIC a dealer's state live?). You'll watch it struggle in 08, then watch curation fix it.
# MAGIC
# MAGIC **The data.** Four tables from the bronze-to-gold lab, prebuilt by your instructor in the shared schema
# MAGIC (read-only for you):
# MAGIC
# MAGIC | table | grain |
# MAGIC |---|---|
# MAGIC | `endtoend_gold_daily_dealer_sales_fact` | one row per day × dealer, December 2025: orders, units, net revenue, margin |
# MAGIC | `endtoend_gold_category_region_fact` | one row per region × part category, December 2025 |
# MAGIC | `endtoend_silver_dealers_dim` | one row per dealer: name, region, state, tier |
# MAGIC | `endtoend_silver_parts_dim` | one row per part: name, category, list price, unit cost |
# MAGIC
# MAGIC > **Two ways to build: we show both.** This notebook creates the agent **programmatically** so everyone gets the
# MAGIC > same result by running the same cell. You can also do it in the **UI**: **New → Genie** in the sidebar, pick the
# MAGIC > tables, **Create**. Both call the same API.
# MAGIC
# MAGIC **Before you start:** set `USER_SCHEMA` in `CONFIG` (top of the repo). **Compute:** Serverless.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ../CONFIG

# COMMAND ----------

# DBTITLE 1,⚙️ Genie helpers
# MAGIC %run ./genie_helpers

# COMMAND ----------

# MAGIC %md
# MAGIC ## Connect to the workspace and pick a SQL warehouse
# MAGIC
# MAGIC `genie_helpers` already created the SDK client, the REST headers and the `genie_ui_room_url` link helper.
# MAGIC Genie runs its generated SQL on a **Pro or Serverless** SQL warehouse. `pick_warehouse()` (in `genie_helpers`)
# MAGIC uses `SQL_WAREHOUSE_ID` if set, otherwise a running/starting or serverless one.

# COMMAND ----------

warehouse_id = pick_warehouse()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build a minimal baseline agent
# MAGIC
# MAGIC The baseline gets the **four tables** and one short instruction: no measures, joins, synonyms or examples. That
# MAGIC comes in 03b and 04.
# MAGIC
# MAGIC We use the Genie REST API (`/api/2.0/genie/spaces`) with a `serialized_space` (v2) payload.
# MAGIC `create_or_update_genie_space` (in `genie_helpers`) is **idempotent**: if an agent with the same title already
# MAGIC exists, it PATCHes it instead of creating a duplicate. It's a `GET /api/2.0/genie/spaces` to look for the title,
# MAGIC then either `PATCH /api/2.0/genie/spaces/{id}` or `POST /api/2.0/genie/spaces` with
# MAGIC `{title, description, warehouse_id, serialized_space}`.

# COMMAND ----------

# The four shared tables (sorted: the API expects sorted identifiers).
tables_config = [{"identifier": t} for t in GENIE_SOURCE_TABLES]


def build_serialized_baseline():
    """Deliberately minimal: tables + one lean instruction, no curation.

    This is the 'before'. Notebook 04 adds the Knowledge Store that makes an agent trustworthy; here we want to
    see how Genie does with almost nothing.
    """
    baseline_instr = (
        "You answer questions using SQL against the attached tables only. "
        "Use fully qualified table names. "
        "Do not invent business rules or thresholds unless they appear in the data."
    )
    return json.dumps({
        "version": 2,
        "config": {"sample_questions": []},
        "data_sources": {"tables": tables_config},
        "instructions": {
            "text_instructions": [{"id": new_id(), "content": [baseline_instr]}],
            "example_question_sqls": [],
        },
    })


for t in GENIE_SOURCE_TABLES:
    print(" ", t)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create the baseline agent and save its ID
# MAGIC
# MAGIC The ID is stored in **your** `workshop_config` table under `genie_space_id_blank` so notebook **08** can compare
# MAGIC it against the curated and metric-view agents. `save_config_keys` upserts, so 03 / 03b / 04 don't clobber each other.

# COMMAND ----------

baseline_id, baseline_url = create_or_update_genie_space(
    GENIE_TITLE_BASELINE, GENIE_DESC_BASELINE, build_serialized_baseline(), warehouse_id
)

save_config_keys([
    {"key": CFG_KEY_BASELINE, "value": baseline_id,
     "space_name": GENIE_TITLE_BASELINE, "space_url": baseline_url},
])

print()
print("=" * 70)
print("BASELINE AGENT CREATED")
print("=" * 70)
print(f"  {GENIE_TITLE_BASELINE}")
print(f"  {baseline_url}")
print("=" * 70)
print()
print('Try asking it: "What was the margin % for Platinum dealers in December 2025?"')
print("With no curated joins or measures it may average percentages or pick the wrong")
print("table: exactly the gap 03b and 04 close.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Your agents as clickable links
# MAGIC
# MAGIC Render every agent id saved in your `workshop_config` table as a link you can open.

# COMMAND ----------

import html

for _r in spark.sql(f"SELECT key, value, space_name FROM {CONFIG_TABLE} ORDER BY key").collect():
    _u = genie_ui_room_url(_r["value"])
    displayHTML(
        "<p><b>" + html.escape(str(_r["key"])) + "</b> &mdash; "
        + '<a href="' + html.escape(_u, quote=True)
        + '" target="_blank" rel="noopener">' + html.escape(str(_r["space_name"]))
        + '</a><br/><code style="font-size:11px">' + html.escape(_u) + "</code></p>"
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Try these questions
# MAGIC
# MAGIC Open your new agent with the link above, then copy/paste any of these. The first six are the **canonical**
# MAGIC questions we use throughout the workshop: ask the **same** ones of the Metric View (03b) and Knowledge Store (04)
# MAGIC agents to compare answers.
# MAGIC
# MAGIC 1. **What was the total net revenue in December 2025?**
# MAGIC 2. **What was the margin % for Platinum dealers in December 2025?**
# MAGIC 3. **What is the margin % for the Brakes category across all regions?**
# MAGIC 4. **What was the net revenue of dealers located in Texas?**
# MAGIC 5. **Which 5 dealers had the highest net revenue in the Midwest?**
# MAGIC 6. **What was the average revenue per order by dealer tier?**
# MAGIC
# MAGIC More to explore on your own:
# MAGIC
# MAGIC 7. **Which region had the highest margin %?**
# MAGIC 8. **Show weekly net revenue by region.**
# MAGIC 9. **Which part category sold the most units in the West?**
# MAGIC 10. **How many dealers do we have in each state?**
# MAGIC 11. **Which day of the week has the highest average net revenue?**
# MAGIC 12. **Compare net revenue and margin for each dealer tier.**
# MAGIC
# MAGIC This is the **baseline** agent (tables only), so watch for it **averaging percentages** (`AVG(margin_pct)`) instead
# MAGIC of total margin ÷ total net revenue, **averaging daily averages**, not knowing that "Texas" is `state = 'TX'` in the
# MAGIC dealers table, or not knowing it has to join to that table to get a state at all. Curation in 03b and 04 fixes
# MAGIC exactly those.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Call to Action for Consumers
# MAGIC
# MAGIC As a consumer of Genie agents, your feedback is critical to keeping the agent curated so it gives you the insights
# MAGIC you need. Use the 👍 / 👎 buttons on every answer and **request a review** when a response looks wrong or needs a
# MAGIC second look; the agent's owner sees all of it in the Monitoring tab (notebook 10).
# MAGIC
# MAGIC 📝 [How to give response feedback in Genie](https://learn.microsoft.com/en-us/azure/databricks/genie-agents/monitor#-response-feedback)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC - **03b · Metric Views:** build a governed semantic layer, then a metric-view-based agent.
# MAGIC - **04 · Knowledge Store:** curate the tables with column configs, synonyms, joins, measures, filters and example
# MAGIC   SQL. This becomes the **primary** agent your users trust.
# MAGIC
# MAGIC Then **08** compares Baseline vs. Metric View vs. Knowledge Store head-to-head.
