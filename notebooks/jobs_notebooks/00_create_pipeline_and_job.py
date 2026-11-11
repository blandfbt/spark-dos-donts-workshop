# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# MAGIC %md
# MAGIC # Bronze-to-gold as a pipeline and a job
# MAGIC
# MAGIC `01_bronze_to_gold_lab` builds bronze → silver → gold step by step in a notebook. In production the same logic
# MAGIC runs as a **Lakeflow Spark Declarative Pipeline**, orchestrated by a **Lakeflow Job**. This notebook sets both up
# MAGIC for you, from the source files in `pipeline/`:
# MAGIC
# MAGIC | file | what it declares | lab section it replaces |
# MAGIC |---|---|---|
# MAGIC | `pipeline/01_bronze.py` | `lakeflow_bronze_orders_fact` (Auto Loader streaming table), `lakeflow_bronze_dealers_dim` | 1 · Bronze |
# MAGIC | `pipeline/02_silver.sql` | typed orders with **expectations**, **AUTO CDC** de-duplication, quarantine, dealers and parts dims | 2 · Silver |
# MAGIC | `pipeline/03_gold.sql` | `lakeflow_gold_daily_dealer_sales_fact`, `lakeflow_gold_category_region_fact` (materialized views) | 3 · Gold |
# MAGIC
# MAGIC **What changes compared with the notebook:** you declare *what* each table is, and the pipeline works out the
# MAGIC order, runs it incrementally, manages Auto Loader's checkpoint and schema, tracks data quality, and keeps lineage.
# MAGIC Nothing in the code says "run this, then that".
# MAGIC
# MAGIC The job has two tasks: **`bronze_to_gold_pipeline`** (a pipeline task) and **`check_gold`** (a notebook task,
# MAGIC `01_check_pipeline_output`) that runs only after the pipeline succeeds and compares your gold tables with the
# MAGIC instructor's reference copy in `shared`.
# MAGIC
# MAGIC Everything reads the shared raw files (read-only) and writes to **your** schema. Tables are prefixed `lakeflow_`,
# MAGIC so they sit next to your lab's `lab_*` tables without colliding. Rerunning this notebook updates the pipeline
# MAGIC and job in place instead of creating duplicates.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ../../CONFIG

# COMMAND ----------

# DBTITLE 1,✏️ Pipeline and job settings
PIPELINE_NAME = f"apex_bronze_to_gold_{USER_SCHEMA}"
JOB_NAME = f"Apex bronze-to-gold ({USER_SCHEMA})"

DEVELOPMENT_MODE = True   # development mode: no automatic retries, so errors surface fast while you iterate
FULL_REFRESH = False      # True = the job's pipeline task recomputes every table from scratch on each run
SCHEDULE_CRON = ""        # Quartz cron for a scheduled job, e.g. "0 0 6 * * ?" (daily 06:00). Empty = run on demand
SCHEDULE_TIMEZONE = "UTC"
RUN_NOW = True            # start a job run at the end of this notebook
WAIT_FOR_RUN = True       # wait for the run to finish and print the result (a first run takes a few minutes)

# COMMAND ----------

# DBTITLE 1,Paths and the API client
import os
import time

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
HOST = w.config.host.rstrip("/")
api = w.api_client.do  # plain REST calls work with every databricks-sdk version on serverless

NOTEBOOK_DIR = os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get())
PIPELINE_DIR = f"{NOTEBOOK_DIR}/pipeline"
PIPELINE_FILES = [f"{PIPELINE_DIR}/{f}" for f in ("01_bronze.py", "02_silver.sql", "03_gold.sql")]
CHECK_NOTEBOOK = f"{NOTEBOOK_DIR}/01_check_pipeline_output"

for f in PIPELINE_FILES:
    assert os.path.exists(f"/Workspace{f}"), f"Pipeline source file not found: {f}"
print("Pipeline source files:", *PIPELINE_FILES, sep="\n  ")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1 · Create (or update) the pipeline
# MAGIC
# MAGIC A pipeline is a set of source files plus settings: the target catalog and schema, serverless compute, and
# MAGIC **configuration** values that the source files read (`spark.conf.get("source_volume")` in Python,
# MAGIC `${source_schema}` in SQL). That's how the same code can point at dev or prod data without edits.
# MAGIC
# MAGIC 📚 [Lakeflow Spark Declarative Pipelines](https://docs.databricks.com/aws/en/ldp/) · [Pipeline configuration](https://docs.databricks.com/aws/en/ldp/configure-pipeline)

# COMMAND ----------

# DBTITLE 1,Create or update the pipeline
pipeline_spec = {
    "name": PIPELINE_NAME,
    "catalog": CATALOG,
    "schema": USER_SCHEMA,            # every table the pipeline declares lands in your schema
    "serverless": True,
    "development": DEVELOPMENT_MODE,
    "continuous": False,              # triggered: process what's new, then stop (the job decides when)
    "channel": "CURRENT",
    "root_path": PIPELINE_DIR,        # the folder the Lakeflow Pipelines Editor shows
    "libraries": [{"file": {"path": p}} for p in PIPELINE_FILES],
    "configuration": {
        "source_catalog": CATALOG,
        "source_schema": SOURCE_SCHEMA,
        "source_volume": SOURCE_VOLUME,
    },
}

existing = api("GET", "/api/2.0/pipelines", query={"filter": f"name LIKE '{PIPELINE_NAME}'"}).get("statuses", [])
existing = [p for p in existing if p.get("name") == PIPELINE_NAME]
if existing:
    PIPELINE_ID = existing[0]["pipeline_id"]
    api("PUT", f"/api/2.0/pipelines/{PIPELINE_ID}", body={**pipeline_spec, "id": PIPELINE_ID})
    print(f"Updated pipeline {PIPELINE_NAME}")
else:
    PIPELINE_ID = api("POST", "/api/2.0/pipelines", body=pipeline_spec)["pipeline_id"]
    print(f"Created pipeline {PIPELINE_NAME}")
print(f"  {HOST}/pipelines/{PIPELINE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2 · Create (or update) the job
# MAGIC
# MAGIC A Lakeflow Job orchestrates tasks of many types (pipelines, notebooks, SQL, dbt, other jobs, ...) with
# MAGIC dependencies, retries, parameters, notifications and triggers. Here: run the pipeline, then check its output.
# MAGIC Job **parameters** (`user_schema`, ...) reach every notebook task, which is how `CONFIG` finds your schema
# MAGIC when the check notebook runs inside the job.
# MAGIC
# MAGIC 📚 [Lakeflow Jobs](https://docs.databricks.com/aws/en/jobs/) · [Pipeline task](https://docs.databricks.com/aws/en/jobs/pipeline) · [Triggers](https://docs.databricks.com/aws/en/jobs/triggers)

# COMMAND ----------

# DBTITLE 1,Create or update the job
job_settings = {
    "name": JOB_NAME,
    "max_concurrent_runs": 1,
    "tags": {WORKSHOP_TAG_KEY: WORKSHOP_TAG},
    "parameters": [
        {"name": "catalog", "default": CATALOG},
        {"name": "source_schema", "default": SOURCE_SCHEMA},
        {"name": "user_schema", "default": USER_SCHEMA},
        {"name": "pipeline_id", "default": PIPELINE_ID},
    ],
    "tasks": [
        {
            "task_key": "bronze_to_gold_pipeline",
            "pipeline_task": {"pipeline_id": PIPELINE_ID, "full_refresh": FULL_REFRESH},
        },
        {
            "task_key": "check_gold",
            "depends_on": [{"task_key": "bronze_to_gold_pipeline"}],
            "notebook_task": {"notebook_path": CHECK_NOTEBOOK, "source": "WORKSPACE"},
        },
    ],
}
if SCHEDULE_CRON:
    job_settings["schedule"] = {"quartz_cron_expression": SCHEDULE_CRON, "timezone_id": SCHEDULE_TIMEZONE,
                                "pause_status": "UNPAUSED"}

jobs = [j for j in api("GET", "/api/2.2/jobs/list", query={"name": JOB_NAME}).get("jobs", [])
        if j["settings"]["name"] == JOB_NAME]
if jobs:
    JOB_ID = jobs[0]["job_id"]
    api("POST", "/api/2.2/jobs/reset", body={"job_id": JOB_ID, "new_settings": job_settings})
    print(f"Updated job {JOB_NAME}")
else:
    JOB_ID = api("POST", "/api/2.2/jobs/create", body=job_settings)["job_id"]
    print(f"Created job {JOB_NAME}")
print(f"  {HOST}/jobs/{JOB_ID}" + (f"   schedule: {SCHEDULE_CRON} ({SCHEDULE_TIMEZONE})" if SCHEDULE_CRON else "   (runs on demand)"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3 · Run it
# MAGIC
# MAGIC While it runs, open the **job** link to watch the two tasks, and the **pipeline** link to see the graph: each
# MAGIC table as a node, rows written, and the expectation results on `lakeflow_silver_orders_valid` (how many rows each
# MAGIC rule dropped). A first run takes a few minutes; a second run with no new files finishes much faster, because the
# MAGIC streaming tables only read what's new.

# COMMAND ----------

# DBTITLE 1,Run the job
if RUN_NOW:
    run_id = api("POST", "/api/2.2/jobs/run-now", body={"job_id": JOB_ID})["run_id"]
    print(f"Started run {run_id}\n  {HOST}/jobs/{JOB_ID}/runs/{run_id}")
    while WAIT_FOR_RUN:
        run = api("GET", "/api/2.2/jobs/runs/get", query={"run_id": run_id})
        state = run["state"]
        if state.get("life_cycle_state") in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR"):
            for t in run.get("tasks", []):
                print(f"  {t['task_key']:26} {t['state'].get('result_state', t['state'].get('life_cycle_state'))}")
            result = state.get("result_state")
            print(("✅ Job run succeeded" if result == "SUCCESS" else f"❌ Job run {result}: {state.get('state_message', '')}"))
            break
        print(f"  {time.strftime('%H:%M:%S')}  {state.get('life_cycle_state')}")
        time.sleep(20)
else:
    print("RUN_NOW is False: start the job from its page when you're ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Try next
# MAGIC
# MAGIC * Open the pipeline in the **Lakeflow Pipelines Editor** (the pipeline page → *Edit pipeline*): the three source
# MAGIC   files, the graph and data previews side by side. Change a rule in `02_silver.sql` and run just that file.
# MAGIC * Rerun the job. Auto Loader finds no new files, and the gold materialized views refresh incrementally.
# MAGIC * Set `SCHEDULE_CRON` above (or add a **file arrival** / **table update** trigger in the job UI) and rerun this notebook.
# MAGIC * Ask **Genie Code** in the pipeline editor: *"Add an expectation that discount_pct is between 0 and 0.5."*

# COMMAND ----------

# DBTITLE 1,🧹 Optional cleanup
# Deletes the job and the pipeline, then drops the lakeflow_* tables (deleting a pipeline leaves its tables behind).
# Your lab's lab_* tables are untouched.
CLEAN_UP = False
if CLEAN_UP:
    api("POST", "/api/2.2/jobs/delete", body={"job_id": JOB_ID})
    api("DELETE", f"/api/2.0/pipelines/{PIPELINE_ID}")
    for t in spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{USER_SCHEMA}` LIKE 'lakeflow_*'").collect():
        kind = spark.sql(f"DESCRIBE TABLE EXTENDED {T(t.tableName)}").where("col_name = 'Type'").first()
        keyword = "MATERIALIZED VIEW" if kind and "MATERIALIZED" in kind.data_type.upper() else "TABLE"
        spark.sql(f"DROP {keyword} IF EXISTS {T(t.tableName)}")
    print(f"Deleted job {JOB_NAME}, pipeline {PIPELINE_NAME} and its lakeflow_* tables")
