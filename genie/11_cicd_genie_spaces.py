# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 11 · CI/CD for Genie agents
# MAGIC
# MAGIC **What you'll learn:** how to promote Genie agents across environments (dev → staging → prod) with code, not
# MAGIC manual clicks.
# MAGIC
# MAGIC **Why CI/CD for Genie?** In production you don't want to recreate agents by hand. You want to:
# MAGIC - **Export** an agent definition from dev (JSON)
# MAGIC - **Transform** it (swap catalog/schema references for the target environment)
# MAGIC - **Deploy** it to prod via the API
# MAGIC
# MAGIC This is the same export → transform → deploy pattern used for dashboards and pipelines. **This notebook is
# MAGIC optional**: it's for teams ready to operationalize their agents. The concepts apply whether you use GitHub Actions,
# MAGIC Azure DevOps or Databricks Asset Bundles.
# MAGIC
# MAGIC **Before you start:** run **04** (the Knowledge Store agent). **Compute:** Serverless.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Current state
# MAGIC
# MAGIC | Mechanism | Notes |
# MAGIC |---|---|
# MAGIC | **Genie REST APIs** | `POST`, `GET`, `PATCH` on `/api/2.0/genie/spaces`: the supported CI/CD path today |
# MAGIC | **Databricks Asset Bundles** | Check the current [bundle resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources) for Genie space support in your CLI version |
# MAGIC | **Terraform** | Check the Databricks provider docs for Genie space support |

# COMMAND ----------

# MAGIC %md
# MAGIC ## The 3-phase promotion pattern
# MAGIC
# MAGIC ```
# MAGIC ┌──────────┐     ┌─────────────┐     ┌──────────┐
# MAGIC │  EXPORT  │ ──> │  TRANSFORM  │ ──> │  DEPLOY  │
# MAGIC │  (dev)   │     │  (CI / Git) │     │  (prod)  │
# MAGIC └──────────┘     └─────────────┘     └──────────┘
# MAGIC ```
# MAGIC
# MAGIC 1. **Export:** `GET /api/2.0/genie/spaces/{id}?include_serialized_space=true`
# MAGIC 2. **Transform:** remap `catalog.schema` references in `serialized_space`, commit the JSON to Git
# MAGIC 3. **Deploy:** `POST` (create) or `PATCH` (update) in the target workspace
# MAGIC
# MAGIC **Key gotcha:** table and metric-view identifiers inside `serialized_space` are hardcoded as
# MAGIC `catalog.schema.table`, and so is every example SQL. In this workshop an agent can reference **two** schemas: the
# MAGIC shared source schema (`dbx_workshop_dev.shared`, for tables) and **your** schema (for the metric views). Both must
# MAGIC be remapped when you promote.

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
# MAGIC Read the Knowledge Store agent id; the SDK client and REST headers from `genie_helpers` are used for the promotion steps below.

# COMMAND ----------

import copy

GENIE_SPACE_ID = load_config().get(CFG_KEY_CURATED, "")
if not GENIE_SPACE_ID:
    raise RuntimeError("genie_space_id not found in workshop_config. Run notebook 04 first.")
print(f"Agent: {GENIE_SPACE_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Phase 1: Export
# MAGIC
# MAGIC Fetch the full agent configuration including `serialized_space`.

# COMMAND ----------

export_resp = requests.get(
    f"{host_url}/api/2.0/genie/spaces/{GENIE_SPACE_ID}?include_serialized_space=true",
    headers=headers,
)
export_resp.raise_for_status()
exported = export_resp.json()
_ss = exported.get("serialized_space")
space_def = json.loads(_ss) if isinstance(_ss, str) else (_ss if isinstance(_ss, dict) else {})

print(f"Title: {exported.get('title') or exported.get('display_name')}")
print(f"Tables: {len(space_def.get('data_sources', {}).get('tables', []))}")
print(f"Example SQL: {len(space_def.get('instructions', {}).get('example_question_sqls', []))}")
print(f"Sample questions: {len(space_def.get('config', {}).get('sample_questions', []))}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Phase 2: Transform (remap catalog and schemas)
# MAGIC
# MAGIC Every table identifier and SQL reference must point at the target environment. Here "prod" is a catalog named
# MAGIC like the workshop catalog with `_prod` instead of `_dev`; the schema names stay the same.

# COMMAND ----------

TARGET_CATALOG = CATALOG[:-4] + "_prod" if CATALOG.endswith("_dev") else f"{CATALOG}_prod"
REMAP = {
    SOURCE_FQN: f"{TARGET_CATALOG}.{SOURCE_SCHEMA}",   # shared tables
    FULL_SCHEMA: f"{TARGET_CATALOG}.{USER_SCHEMA}",    # your metric views (used by the Metric View agent)
}


def remap_references(space_dict, mapping):
    """Replace every catalog.schema prefix in the serialized space. Longest keys first, so no prefix clobbers another."""
    raw = json.dumps(space_dict)
    for src in sorted(mapping, key=len, reverse=True):
        raw = raw.replace(src, mapping[src])
    return json.loads(raw)


prod_space_def = remap_references(copy.deepcopy(space_def), REMAP)

dev_tables = [t["identifier"] for t in space_def.get("data_sources", {}).get("tables", [])]
prod_tables = [t["identifier"] for t in prod_space_def.get("data_sources", {}).get("tables", [])]
print("DEV: ", dev_tables[:4])
print("PROD:", prod_tables[:4])

# In CI you would commit this file to Git. Here we just show its size.
print(f"\nPromotable JSON: {len(json.dumps(prod_space_def, indent=2)):,} chars")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Phase 3: Deploy (demo: create a copy in the same workspace)
# MAGIC
# MAGIC In production you would deploy `prod_space_def` to another workspace or catalog. The `_prod` catalog doesn't exist
# MAGIC here, so the demo deploys the **un-remapped** definition as a `[CICD DEMO]` copy. Re-running updates that copy
# MAGIC instead of creating another one.

# COMMAND ----------

import html as _html

warehouse_id = pick_warehouse()
_demo_title = GENIE_TITLE_CICD_DEMO   # per-user: "[CICD DEMO] Apex Motorsports Parts - Knowledge Store (<your schema>)"
new_id_, demo_url = create_or_update_genie_space(
    _demo_title, f"CI/CD deployed copy. Source: {GENIE_SPACE_ID}", json.dumps(space_def), warehouse_id
)
displayHTML(f'<a href="{_html.escape(demo_url, quote=True)}" target="_blank" rel="noopener">Open CI/CD deployed agent</a>')

# COMMAND ----------

# MAGIC %md
# MAGIC ## PATCH pattern (update an existing prod agent)
# MAGIC
# MAGIC When promoting **changes** to an agent that already exists, use the round-trip update:
# MAGIC
# MAGIC ```python
# MAGIC # 1. Fetch the existing prod agent
# MAGIC prod_resp = requests.get(f"{host}/api/2.0/genie/spaces/{PROD_ID}?include_serialized_space=true", headers=headers)
# MAGIC prod_existing = json.loads(prod_resp.json()["serialized_space"])
# MAGIC
# MAGIC # 2. Apply targeted changes from the dev export
# MAGIC prod_existing["instructions"] = prod_space_def["instructions"]
# MAGIC
# MAGIC # 3. Sort example_question_sqls by id (API requirement)
# MAGIC prod_existing.get("instructions", {}).get("example_question_sqls", []).sort(key=lambda x: x.get("id", ""))
# MAGIC
# MAGIC # 4. PATCH back
# MAGIC requests.patch(f"{host}/api/2.0/genie/spaces/{PROD_ID}", headers=headers,
# MAGIC                json={"serialized_space": json.dumps(prod_existing)})
# MAGIC ```
# MAGIC
# MAGIC Always fetch first, apply targeted changes, then PATCH. This preserves opaque IDs and server-managed fields.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Reference architecture
# MAGIC
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────┐
# MAGIC │               Git repository                │
# MAGIC │  genie_spaces/                              │
# MAGIC │    apex_motorsports_sales.json              │
# MAGIC │    transform.py                             │
# MAGIC │    deploy.py                                │
# MAGIC └────────────────────────┬────────────────────┘
# MAGIC                          │ PR merge triggers CI
# MAGIC                          ▼
# MAGIC ┌─────────────────────────────────────────────┐
# MAGIC │         GitHub Actions / Azure DevOps       │
# MAGIC │  1. Checkout repo                           │
# MAGIC │  2. transform.py (remap dev → prod)         │
# MAGIC │  3. deploy.py (POST or PATCH)               │
# MAGIC │  4. Run benchmarks (notebook 08 as a job)   │
# MAGIC │  5. Pass → done. Fail → alert + rollback.   │
# MAGIC └─────────────────────────────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC A reference agent definition for this workshop's data is in `genie/templates/apex_motorsports_genie_configured.json`.
# MAGIC
# MAGIC ### Field-built tools (open source)
# MAGIC
# MAGIC | Tool | What it does |
# MAGIC |---|---|
# MAGIC | [SpaceOps CLI](https://github.com/charotAmine/databricks-spaceops) | YAML-driven config, snapshot + deploy across environments |
# MAGIC | [genie-space-cicd](https://github.com/mohade09/genie-space-cicd) | Sample CI/CD repo for Genie agents |
# MAGIC | [genie-migration-tool](https://github.com/reynoldspravindev/databricks-genie-migration-tool) | CLI wrapper for the CRUD APIs |
# MAGIC
# MAGIC ### Further reading
# MAGIC
# MAGIC - [GitHub Actions for Databricks](https://docs.databricks.com/aws/en/dev-tools/ci-cd/github)
# MAGIC - [Genie REST API reference](https://docs.databricks.com/api/workspace/genie)
