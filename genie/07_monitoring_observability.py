# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Notebook 07 · Monitor and improve your Genie agent
# MAGIC
# MAGIC **What you'll learn:** how to track Genie's accuracy over time, monitor user activity, find the questions that fail,
# MAGIC and build a continuous improvement loop.
# MAGIC
# MAGIC **Why this matters:** deploying a Genie agent is just the beginning. Schemas change, new questions emerge and models
# MAGIC get updated. Monitoring keeps your agent accurate and useful.
# MAGIC
# MAGIC > **⚠️ Heads-up on access:** Parts 3 and 4 read Databricks **system tables** (`system.access.audit`,
# MAGIC > `system.query.history`) that most workshop participants can't query. Those cells print a permissions message,
# MAGIC > which is expected. Parts 1, 2 and 5 need no system-table access.
# MAGIC
# MAGIC | Part | What it shows | Data source |
# MAGIC |---|---|---|
# MAGIC | **1** | Genie's built-in Monitoring tab | Genie UI |
# MAGIC | **2** | Benchmark pass rate over time | `genie_benchmark_runs` in your schema (written by notebook 06) |
# MAGIC | **3** | User activity and feedback | `system.access.audit` |
# MAGIC | **4** | Query performance (latency) | `system.query.history` |
# MAGIC | **5** | Continuous improvement workflow | Best practices |
# MAGIC
# MAGIC **Before you start:** run **03** (agents) and **06** (compare) for benchmark data. **Compute:** Serverless.

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
# MAGIC Read your Knowledge Store agent id; the SDK client from `genie_helpers` builds the monitoring links below.

# COMMAND ----------

import html

PRIMARY_SPACE_ID = load_config().get(CFG_KEY_CURATED, "")
GENIE_SPACE_ID = PRIMARY_SPACE_ID
if not PRIMARY_SPACE_ID:
    print("WARNING: genie_space_id not found in genie_workshop_config. Monitoring links will be incomplete. Run notebook 03 first.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 1: The Genie UI Monitoring tab
# MAGIC
# MAGIC The **built-in Monitoring tab** is your first stop. Open the agent and click **Monitoring** (requires **CAN MANAGE**,
# MAGIC which you have on agents you created).
# MAGIC
# MAGIC **What you can do there:**
# MAGIC - View **every question and answer** asked in the agent
# MAGIC - Filter by **time range, user, rating, status**
# MAGIC - See **thumbs up/down** feedback from users
# MAGIC - Read **review requests**: users can flag a response for review and add a comment
# MAGIC - **Re-run query results** from other users' messages with your own credentials to debug
# MAGIC - **Comment on review requests** to confirm or correct responses

# COMMAND ----------

m = re.search(r"adb-(\d+)\.", host_url)
o = f"?o={m.group(1)}" if m else ""
monitoring_url = f"{host_url}/genie/rooms/{GENIE_SPACE_ID}/monitoring{o}"
room_url = f"{host_url}/genie/rooms/{GENIE_SPACE_ID}{o}"
print("Monitoring (deep link):", monitoring_url)
print("Genie room (main UI):", room_url)
displayHTML(
    '<p><a href="' + html.escape(monitoring_url, quote=True) + '" target="_blank" rel="noopener">Open Genie Monitoring</a></p>'
    '<p style="color:#555;font-size:13px">If prompted, use <b>CAN MANAGE</b> on the agent. Fallback: <a href="'
    + html.escape(room_url, quote=True) + '" target="_blank" rel="noopener">open the room</a> then choose the Monitoring tab.</p>'
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 2: Benchmark run history
# MAGIC
# MAGIC Benchmark pass rate is the **most objective** measure of Genie accuracy. This reads the `genie_benchmark_runs`
# MAGIC table that notebook **06** writes to your schema. Track the pass rate over time as you tune instructions and
# MAGIC example SQL.
# MAGIC
# MAGIC ### 2a. Pass rate by run and agent

# COMMAND ----------

try:
    display(spark.sql(f"""
        SELECT
            run_timestamp,
            run_label,
            COUNT(*) AS total_questions,
            SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passed,
            ROUND(SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS pass_rate_pct,
            ROUND(SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) / COUNT(*), 2) < {ALERT_ON_PASS_RATE_BELOW} AS below_alert_threshold
        FROM {BENCHMARK_RUNS_TABLE}
        GROUP BY run_timestamp, run_label
        ORDER BY run_timestamp DESC, run_label
    """))
except Exception as e:
    print(f"Run notebook 06 first to create {BENCHMARK_RUNS_TABLE}: {str(e)[:150]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2b. Which questions fail most often?

# COMMAND ----------

try:
    display(spark.sql(f"""
        SELECT
            run_label,
            benchmark_id,
            question,
            COUNT(*) AS runs,
            SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passes,
            SUM(CASE WHEN status != 'PASS' THEN 1 ELSE 0 END) AS non_passes,
            ROUND(SUM(CASE WHEN status != 'PASS' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS non_pass_rate_pct
        FROM {BENCHMARK_RUNS_TABLE}
        GROUP BY run_label, benchmark_id, question
        ORDER BY non_pass_rate_pct DESC, run_label, benchmark_id
    """))
except Exception as e:
    print(f"Table not available: {str(e)[:150]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 3: Usage monitoring from audit logs
# MAGIC
# MAGIC `system.access.audit` captures every Genie interaction under `service_name = 'aibiGenie'`.
# MAGIC
# MAGIC | Action | Meaning |
# MAGIC |---|---|
# MAGIC | `genieStartConversationMessage` | New conversation started |
# MAGIC | `genieCreateConversationMessage` | Follow-up message in a conversation |
# MAGIC | `updateConversationMessageFeedback` | Thumbs up or thumbs down |
# MAGIC | `createConversationMessageComment` | Review request submitted |
# MAGIC | `genieExecuteMessageQuery` | SQL query executed by Genie |
# MAGIC
# MAGIC > **⚠️ Requires access you probably don't have.** Parts 3 and 4 need `SELECT` on the **`system`** catalog's
# MAGIC > `access` and `query` schemas, usually granted by a metastore admin. Without it the next cells print a permissions
# MAGIC > message; **that's expected**. They show the monitoring pattern and run wherever system-table access is granted.
# MAGIC > Skip to Part 5 if you don't have access.
# MAGIC
# MAGIC ### 3a. Active users per day

# COMMAND ----------

try:
    display(spark.sql("""
        SELECT
            event_date,
            COUNT(DISTINCT user_identity.email) AS active_users,
            COUNT(*) AS total_messages
        FROM system.access.audit
        WHERE service_name = 'aibiGenie'
          AND action_name IN ('genieStartConversationMessage', 'genieCreateConversationMessage')
          AND event_date >= current_date() - INTERVAL 30 DAYS
        GROUP BY event_date
        ORDER BY event_date
    """))
except Exception as e:
    print(f"system.access.audit not available: {str(e)[:200]}")
    print("Ask your metastore admin for SELECT access, or skip to Part 5.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b. Feedback ratings (thumbs up / thumbs down) for your agent

# COMMAND ----------

try:
    display(spark.sql(f"""
        SELECT
            event_date,
            user_identity.email AS user_email,
            request_params.space_id,
            request_params.feedback_rating
        FROM system.access.audit
        WHERE service_name = 'aibiGenie'
          AND action_name = 'updateConversationMessageFeedback'
          AND request_params.space_id = '{GENIE_SPACE_ID}'
          AND event_date >= current_date() - INTERVAL 30 DAYS
        ORDER BY event_date DESC
    """))
except Exception as e:
    print(f"Not available: {str(e)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3c. Weekly approval rate trend

# COMMAND ----------

try:
    display(spark.sql("""
        SELECT
            DATE_TRUNC('week', event_date) AS week,
            SUM(CASE WHEN request_params.feedback_rating = 'THUMBS_UP' THEN 1 ELSE 0 END) AS thumbs_up,
            SUM(CASE WHEN request_params.feedback_rating = 'THUMBS_DOWN' THEN 1 ELSE 0 END) AS thumbs_down,
            COUNT(*) AS total_ratings,
            ROUND(SUM(CASE WHEN request_params.feedback_rating = 'THUMBS_UP' THEN 1 ELSE 0 END) * 100.0
                  / NULLIF(COUNT(*), 0), 1) AS approval_rate_pct
        FROM system.access.audit
        WHERE service_name = 'aibiGenie'
          AND action_name = 'updateConversationMessageFeedback'
          AND event_date >= current_date() - INTERVAL 90 DAYS
        GROUP BY DATE_TRUNC('week', event_date)
        ORDER BY week
    """))
except Exception as e:
    print(f"Not available: {str(e)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3d. Review requests

# COMMAND ----------

try:
    display(spark.sql("""
        SELECT
            event_date,
            user_identity.email AS reviewer,
            request_params.space_id,
            action_name
        FROM system.access.audit
        WHERE service_name = 'aibiGenie'
          AND action_name = 'createConversationMessageComment'
          AND event_date >= current_date() - INTERVAL 30 DAYS
        ORDER BY event_date DESC
    """))
except Exception as e:
    print(f"Not available: {str(e)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3e. API error tracking (last 7 days)

# COMMAND ----------

try:
    display(spark.sql("""
        SELECT
            DATE_TRUNC('hour', event_time) AS hour,
            response.status_code,
            COUNT(*) AS request_count
        FROM system.access.audit
        WHERE service_name = 'aibiGenie'
          AND action_name IN ('genieStartConversationMessage', 'genieCreateConversationMessage')
          AND event_date >= current_date() - INTERVAL 7 DAYS
        GROUP BY DATE_TRUNC('hour', event_time), response.status_code
        ORDER BY hour DESC, response.status_code
    """))
except Exception as e:
    print(f"Not available: {str(e)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 4: Query performance from query history
# MAGIC
# MAGIC `system.query.history` captures execution details for Genie-originated SQL. Filter with
# MAGIC `client_application = 'Databricks SQL Genie Space'`.
# MAGIC
# MAGIC > **⚠️ Same access caveat as Part 3.**
# MAGIC
# MAGIC ### 4a. Genie query latency (p50, p95)

# COMMAND ----------

try:
    display(spark.sql("""
        SELECT
            DATE(start_time) AS query_date,
            COUNT(*) AS genie_queries,
            ROUND(percentile_approx(total_duration_ms, 0.5) / 1000.0, 2) AS p50_seconds,
            ROUND(percentile_approx(total_duration_ms, 0.95) / 1000.0, 2) AS p95_seconds,
            ROUND(AVG(total_duration_ms) / 1000.0, 2) AS avg_seconds
        FROM system.query.history
        WHERE client_application = 'Databricks SQL Genie Space'
          AND start_time >= current_date() - INTERVAL 30 DAYS
        GROUP BY DATE(start_time)
        ORDER BY query_date DESC
    """))
except Exception as e:
    print(f"system.query.history not available: {str(e)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4b. Recent Genie-executed SQL on the workshop tables

# COMMAND ----------

try:
    display(spark.sql(f"""
        SELECT
            start_time,
            executed_by,
            SUBSTRING(statement_text, 1, 200) AS sql_preview,
            total_duration_ms,
            produced_rows
        FROM system.query.history
        WHERE client_application = 'Databricks SQL Genie Space'
          AND statement_text ILIKE '%lab_%'
          AND start_time >= current_date() - INTERVAL 7 DAYS
        ORDER BY start_time DESC
        LIMIT 25
    """))
except Exception as e:
    print(f"Not available: {str(e)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 5: The continuous improvement loop
# MAGIC
# MAGIC Monitoring is only useful if it drives action. Here is the recommended workflow after deployment.
# MAGIC
# MAGIC ### Step 1: Triage feedback
# MAGIC
# MAGIC 1. Open the **Monitoring tab** in the Genie UI.
# MAGIC 2. Filter for **thumbs down** and **review requests** from the last week.
# MAGIC 3. For each thumbs-down response: look at the **question** and the **SQL Genie generated**, re-run it with your
# MAGIC    credentials, and categorize the failure: **wrong table**, **wrong join**, **wrong metric formula**,
# MAGIC    **wrong filter**, or **hallucinated column**.
# MAGIC
# MAGIC ### Step 2: Follow the fix order
# MAGIC
# MAGIC Fix in this order; each level resolves whole classes of downstream failures:
# MAGIC
# MAGIC | Priority | Fix | Example |
# MAGIC |---|---|---|
# MAGIC | **1. Data / views** | A gold table or metric view at the right grain | Add a gold table with category **and** dealer tier, so "Brakes revenue at Platinum dealers" becomes answerable |
# MAGIC | **2. Metadata** | Table and column comments in Unity Catalog | Comment `margin_pct` as "per-row %, never average it" |
# MAGIC | **3. Joins** | Missing or ambiguous join paths | daily dealer sales → dealers dim on `dealer_id` for state |
# MAGIC | **4. Example SQL** | Q-to-SQL pairs for the failing pattern | "net revenue by dealer state" |
# MAGIC | **5. Instructions** | Edge cases and formatting | "state names map to two-letter codes" |
# MAGIC
# MAGIC ### Step 3: Re-run benchmarks
# MAGIC
# MAGIC After each change, re-run the **Benchmark** tab and notebook **06**. You should see the pass rate improve run by run.
# MAGIC
# MAGIC ### Step 4: Convert good interactions to example SQL
# MAGIC
# MAGIC When users ask great questions that Genie answers correctly, **promote** them: copy the question and SQL from the
# MAGIC Monitoring tab and add them as a new `example_question_sqls` entry (via the PATCH pattern in notebooks 04 and 08).
# MAGIC
# MAGIC ### Step 5: Schedule automated benchmarks
# MAGIC
# MAGIC For production agents, schedule notebook **06** as a recurring job (weekly, or after instruction changes) and alert
# MAGIC when the pass rate drops below `ALERT_ON_PASS_RATE_BELOW`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Part 6: Community tools for Genie agent health
# MAGIC
# MAGIC | Tool | What it does | Link |
# MAGIC |---|---|---|
# MAGIC | **GenieRx** | Scores your agent config against best practices; suggests optimizations | [github.com/hiydavid/dbx-genie-rx](https://github.com/hiydavid/dbx-genie-rx) |
# MAGIC | **GenieIQ** | Scores agents 0-100, generates "fix notebooks", tracks progress | [github.com/ryancicak/genieiq](https://github.com/ryancicak/genieiq) |
# MAGIC | **Databricks Forge** | Quality / maturity grades across 40 checks; auto-improve loop | [althrussell.github.io/databricks-forge](https://althrussell.github.io/databricks-forge/) |
# MAGIC
# MAGIC ### Recommended reading
# MAGIC
# MAGIC - [How to build production-ready Genie spaces](https://www.databricks.com/blog/how-build-production-ready-genie-spaces-and-build-trust-along-way)
# MAGIC - [Curate an effective Genie space](https://docs.databricks.com/aws/en/genie/best-practices)
# MAGIC - [Genie audit log events](https://docs.databricks.com/aws/en/ai-bi/admin/audit)
# MAGIC
# MAGIC ## Privacy and compliance note
# MAGIC
# MAGIC - **Do not expose PII**: aggregate metrics only; don't surface individual user emails in shared dashboards without approval.
# MAGIC - **Query text may contain sensitive data**: `system.query.history.statement_text` can include filter values from user questions.
# MAGIC - **Retention**: system tables have limited retention. For long-term trends, materialize aggregates into your own Delta tables.
