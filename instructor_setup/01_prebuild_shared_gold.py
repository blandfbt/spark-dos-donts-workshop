# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Prebuild the shared lab tables (instructor, run once after 00)
# MAGIC
# MAGIC > **Compute:** serverless, **environment version 5 or later** (Environment side panel).
# MAGIC >
# MAGIC > 🧑‍🏫 **Instructor only.** Participants don't run this notebook.
# MAGIC
# MAGIC Runs `notebooks/01_bronze_to_gold_lab` with every exercise **auto-solved**, writing into the shared source
# MAGIC schema (`dbx_workshop_dev.shared`) instead of a participant schema. That gives the Genie notebooks
# MAGIC (`genie/`) a complete, known-good set of lab tables to build on, even for participants who haven't
# MAGIC finished the lab:
# MAGIC
# MAGIC | layer | tables in `shared` |
# MAGIC |---|---|
# MAGIC | 🥈 silver | `endtoend_silver_orders_fact`, `endtoend_silver_dealers_dim`, `endtoend_silver_parts_dim` (+ bronze and quarantine) |
# MAGIC | 🥇 gold | `endtoend_gold_daily_dealer_sales_fact`, `endtoend_gold_category_region_fact` |
# MAGIC
# MAGIC Participants still do the lab themselves; their copies land in their own schemas. Takes about 5 minutes.
# MAGIC It also publishes the lab's AI/BI dashboard in your home folder (harmless; delete it if you like).

# COMMAND ----------

# DBTITLE 1,⚙️ Instructor mode (writes to the shared source schema)
INSTRUCTOR_SETUP = True

# COMMAND ----------

# MAGIC %run ../CONFIG

# COMMAND ----------

# DBTITLE 1,Run the lab auto-solved into the shared schema
result = dbutils.notebook.run(
    "../notebooks/01_bronze_to_gold_lab",
    3600,
    {
        "catalog": CATALOG,
        "source_schema": SOURCE_SCHEMA,
        "user_schema": SOURCE_SCHEMA,            # the lab's "own schema" is the shared schema for this one run
        "allow_source_schema_writes": "true",    # CONFIG refuses this unless explicitly allowed
        "auto_solve": "true",
        "warehouse_id": _job_param("warehouse_id", ""),
        "workshop_tag": WORKSHOP_TAG,
    },
)
print("Lab finished", result or "")

# COMMAND ----------

# DBTITLE 1,Check the tables the Genie notebooks need
needed = ["endtoend_gold_daily_dealer_sales_fact", "endtoend_gold_category_region_fact",
          "endtoend_silver_dealers_dim", "endtoend_silver_parts_dim", "endtoend_silver_orders_fact"]
missing = [t for t in needed if not spark.catalog.tableExists(f"{CATALOG}.{SOURCE_SCHEMA}.{t}")]
assert not missing, f"Missing in {CATALOG}.{SOURCE_SCHEMA}: {missing}"
for t in needed:
    print(f"✅ {CATALOG}.{SOURCE_SCHEMA}.{t:40} {spark.table(SRC(t)).count():>12,} rows")
tag_workshop_objects(SOURCE_SCHEMA)
