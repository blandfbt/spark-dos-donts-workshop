# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Create the participant schemas and grants (instructor, before the workshop)
# MAGIC
# MAGIC > 🧑‍🏫 **Instructor only.** Participants can't create schemas; this notebook does it for them.
# MAGIC
# MAGIC For every participant email below it:
# MAGIC
# MAGIC | object | grant |
# MAGIC |---|---|
# MAGIC | catalog `dbx_workshop_dev` | `USE CATALOG` |
# MAGIC | schema `dbx_workshop_dev.shared` | `USE SCHEMA`, `SELECT`, `READ VOLUME` (read-only) |
# MAGIC | schema `dbx_workshop_dev.<firstname_lastname>` (created here) | `ALL PRIVILEGES` (tables, views, metric views, volumes, functions, tags) |
# MAGIC
# MAGIC The schema name comes from the email: `jane.doe@company.com` → `jane_doe`. That's the value each participant
# MAGIC puts in `USER_SCHEMA` in `CONFIG`. A `scratch_files` volume is created in each schema for checkpoints and
# MAGIC landing files. Rerunning is safe: existing schemas and grants are left as they are.
# MAGIC
# MAGIC **Outside Unity Catalog** (not done here): participants also need **CAN USE** on a SQL warehouse (lab dashboard,
# MAGIC Genie spaces) and Genie enabled in the workspace. `genie/10_monitoring_observability` reads `system.access.audit`
# MAGIC and `system.query.history`, which needs a metastore admin to grant `USE SCHEMA` + `SELECT` on those system schemas.

# COMMAND ----------

# DBTITLE 1,✏️ Participants
PARTICIPANTS = [
    # "jane.doe@company.com",
    # "john.smith@company.com",
]

# Optional: an account group that contains every participant. If set, the catalog and shared-schema grants go to the
# group once instead of to each user (the personal schemas are still granted per user).
PARTICIPANT_GROUP = ""

# COMMAND ----------

# DBTITLE 1,⚙️ Instructor mode
INSTRUCTOR_SETUP = True

# COMMAND ----------

# MAGIC %run ../CONFIG

# COMMAND ----------

# DBTITLE 1,Create schemas and grant access
from collections import Counter

emails = [e.strip().lower() for e in PARTICIPANTS if e.strip()]
assert emails, "Add the participants' emails to PARTICIPANTS in the cell above."
schemas = {e: suggested_user_schema(e) for e in emails}
clashes = [s for s, n in Counter(schemas.values()).items() if n > 1]
assert not clashes, f"Two participants map to the same schema name {clashes}; create those by hand."
assert SOURCE_SCHEMA not in schemas.values(), f"A participant would get the shared schema name '{SOURCE_SCHEMA}'."


def grant(sql):
    spark.sql(sql)
    return sql


read_principals = [PARTICIPANT_GROUP] if PARTICIPANT_GROUP else emails
for p in read_principals:
    grant(f"GRANT USE CATALOG ON CATALOG `{CATALOG}` TO `{p}`")
    grant(f"GRANT USE SCHEMA, SELECT, READ VOLUME ON SCHEMA `{CATALOG}`.`{SOURCE_SCHEMA}` TO `{p}`")

rows = []
for email, schema in schemas.items():
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{schema}` COMMENT 'Workshop schema for {email}'")
    grant(f"GRANT ALL PRIVILEGES ON SCHEMA `{CATALOG}`.`{schema}` TO `{email}`")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS `{CATALOG}`.`{schema}`.`scratch_files`")
    try:
        spark.sql(f"ALTER SCHEMA `{CATALOG}`.`{schema}` SET TAGS ('{WORKSHOP_TAG_KEY}' = '{WORKSHOP_TAG}')")
    except Exception:
        pass  # tagging is a convenience
    rows.append((email, schema, f'USER_SCHEMA = "{schema}"'))

display(spark.createDataFrame(rows, "email STRING, schema STRING, line_for_CONFIG STRING"))

# COMMAND ----------

# DBTITLE 1,Review the grants
display(spark.sql(f"SHOW GRANTS ON SCHEMA `{CATALOG}`.`{SOURCE_SCHEMA}`"))
