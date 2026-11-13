# Databricks notebook source
# MAGIC %md
# MAGIC # Genie helpers
# MAGIC
# MAGIC Included by every notebook in `genie/` with `%run ./genie_helpers`, right after `%run ../CONFIG`. You do not
# MAGIC run it on its own, and there is nothing to edit here: the catalog and schemas come from `CONFIG`.
# MAGIC
# MAGIC * **Source data (read-only):** the gold and silver tables of the bronze-to-gold lab, prebuilt by the instructor
# MAGIC   in `dbx_workshop_dev.shared`. Every Genie agent points at these shared tables.
# MAGIC * **Your objects:** the metric views, the `genie_workshop_config` table (your agent IDs) and the
# MAGIC   `genie_benchmark_runs` table go to **your** schema (`USER_SCHEMA` in `CONFIG`).
# MAGIC * **Plumbing:** Genie REST API helpers (create-or-update an agent, ask a question, build UI links) shared by
# MAGIC   the notebooks so each one can focus on what it teaches.

# COMMAND ----------

# DBTITLE 1,Genie agent, benchmark and monitoring settings
GENIE_SPACE_PREFIX = "Apex Motorsports Parts"
SQL_WAREHOUSE_ID = ""             # leave blank to auto-select a running (or serverless) SQL warehouse

BENCHMARK_TOLERANCE_PCT = 0.1     # relative % difference for PASS (allows 2-decimal rounding of a margin %)
BENCHMARK_WARN_PCT = 1.0          # relative % difference for WARN
BENCHMARK_VERSION = "v1"
ALERT_ON_PASS_RATE_BELOW = 0.70   # alert if the benchmark pass rate drops below this

# COMMAND ----------

# DBTITLE 1,Table names (derived from CONFIG, do not edit)
# Genie identifiers are plain three-part names (no backticks).
SOURCE_FQN = f"{CATALOG}.{SOURCE_SCHEMA}"   # shared, read-only
FULL_SCHEMA = f"{CATALOG}.{USER_SCHEMA}"    # yours
fqn = FULL_SCHEMA                            # short alias used by some cells


def source_table(name: str) -> str:
    """3-part name of a shared source table (read-only)."""
    return f"{SOURCE_FQN}.{name}"


def full_table(name: str) -> str:
    """3-part name of an object in your own schema."""
    return f"{FULL_SCHEMA}.{name}"


# Shared lab tables the agents are built on (prebuilt by the instructor)
GOLD_DAILY_TABLE = source_table("lab_gold_daily_dealer_sales_fact")   # one row per order_date x dealer
GOLD_CATEGORY_TABLE = source_table("lab_gold_category_region_fact")  # one row per region x part category
DEALERS_TABLE = source_table("lab_silver_dealers_dim")               # one row per dealer
PARTS_TABLE = source_table("lab_silver_parts_dim")                   # one row per part
GENIE_SOURCE_TABLES = sorted([GOLD_DAILY_TABLE, GOLD_CATEGORY_TABLE, DEALERS_TABLE, PARTS_TABLE])

# Objects you create
CONFIG_TABLE = full_table("genie_workshop_config")
BENCHMARK_RUNS_TABLE = full_table("genie_benchmark_runs")
METRIC_VIEW_DEALER_SALES = full_table("genie_mv_dealer_sales")       # built in 02
METRIC_VIEW_CATEGORY_SALES = full_table("genie_mv_category_sales")   # built in 02

# COMMAND ----------

# MAGIC %md
# MAGIC ### Agent variants and the config-save helper
# MAGIC
# MAGIC Titles and descriptions for the three agents (Baseline / Metric View / Knowledge Store), plus `save_config_keys`,
# MAGIC which upserts each agent's id into your `genie_workshop_config` table.

# COMMAND ----------

# DBTITLE 1,Agent variants and genie_workshop_config keys
# The workshop builds three agents on the SAME data to show that curation is what earns trust:
#   Baseline         (01)  tables only, minimal instructions ... the "before"
#   Metric View      (02) built on governed metric views    ... semantic layer
#   Knowledge Store  (03)  measures/filters/joins/examples   ... the "after" (primary)
# Titles include your schema so participants' agents never collide in a shared workspace.
GENIE_TITLE_BASELINE = f"{GENIE_SPACE_PREFIX} - Baseline ({USER_SCHEMA})"
GENIE_TITLE_CURATED = f"{GENIE_SPACE_PREFIX} - Knowledge Store ({USER_SCHEMA})"
GENIE_TITLE_METRIC_VIEW = f"{GENIE_SPACE_PREFIX} - Metric View ({USER_SCHEMA})"
GENIE_TITLE_GENIE_CODE = f"{GENIE_SPACE_PREFIX} - Genie Code Built ({USER_SCHEMA})"   # built by Genie Code in 07
GENIE_TITLE_CICD_DEMO = f"[CICD DEMO] {GENIE_TITLE_CURATED}"                         # deployed copy in 08

GENIE_DESC_BASELINE = "Tables only, minimal instructions. The 'before': baseline for comparison."
GENIE_DESC_CURATED = "Fully curated Knowledge Store: column configs, synonyms, joins, measures, filters, example SQL."
GENIE_DESC_METRIC_VIEW = "Built on governed metric views (semantic layer): deterministic KPIs."

# CFG_KEY_CURATED is the PRIMARY agent that most downstream notebooks read.
CFG_KEY_CURATED = "genie_space_id"
CFG_KEY_BASELINE = "genie_space_id_blank"
CFG_KEY_METRIC_VIEW = "genie_space_id_metric_view"


def save_config_keys(new_rows):
    """Upsert rows into your genie_workshop_config table (read-modify-overwrite).

    Each row is a dict with keys: key, value, space_name, space_url. Lets 03 / 03b / 04 each write their own
    agent id without clobbering the others, and makes re-running any of them safe.
    """
    from pyspark.sql import Row
    cols = ["key", "value", "space_name", "space_url"]
    merged = {}
    try:
        for r in spark.table(CONFIG_TABLE).collect():
            merged[r["key"]] = {c: r[c] for c in cols}
    except Exception:
        pass  # table does not exist yet: the first writer creates it
    for nr in new_rows:
        merged[nr["key"]] = {c: nr.get(c) for c in cols}
    rows = [Row(**merged[k]) for k in sorted(merged)]
    (spark.createDataFrame(rows)
        .write.mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(CONFIG_TABLE))
    return merged


def load_config():
    """{key: agent_id} from your genie_workshop_config table ({} if no agent was created yet)."""
    try:
        return {r["key"]: r["value"] for r in spark.table(CONFIG_TABLE).collect()}
    except Exception:
        return {}


# COMMAND ----------

# MAGIC %md
# MAGIC ### Connect to the workspace
# MAGIC
# MAGIC The SDK client, the REST headers for the Genie API, and small helpers every notebook uses: pick a warehouse
# MAGIC (`SQL_WAREHOUSE_ID` first, then auto-select), create-or-update an agent, ask an agent a question, build UI links.

# COMMAND ----------

# DBTITLE 1,Genie REST API plumbing
import json
import re
import time
import uuid

import requests
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
host = w.config.host.rstrip("/")
host_url = host
# w.config.authenticate() works on serverless (w.config.token is None there).
headers = {**w.config.authenticate(), "Content-Type": "application/json"}


def genie_ui_room_url(space_id: str) -> str:
    """Clickable Genie UI link: /genie/rooms/<space_id>[?o=<workspace_id>].
    (REST APIs use /api/2.0/genie/spaces/... - a different path.)"""
    m = re.search(r"adb-(\d+)\.", host)
    q = f"?o={m.group(1)}" if m else ""
    return f"{host}/genie/rooms/{space_id}{q}"


def new_id():
    """Genie requires 32-char lowercase hex ids (no hyphens), unique within the space."""
    return uuid.uuid4().hex


def pick_warehouse():
    """SQL_WAREHOUSE_ID if set, else a running/starting warehouse, else a serverless one, else the first."""
    if SQL_WAREHOUSE_ID:  # honor the setting above; only auto-select when it's blank
        print(f"Using SQL_WAREHOUSE_ID: {SQL_WAREHOUSE_ID}")
        return SQL_WAREHOUSE_ID
    warehouses = list(w.warehouses.list())
    for wh in warehouses:
        if str(wh.state).upper().endswith(("RUNNING", "STARTING")):
            print(f"Using warehouse: {wh.name} ({wh.id}) state={wh.state}")
            return wh.id
    for wh in warehouses:
        if getattr(wh, "enable_serverless_compute", False) or "serverless" in (wh.name or "").lower():
            print(f"Using serverless warehouse: {wh.name} ({wh.id})")
            return wh.id
    if warehouses:
        print(f"Using first warehouse: {warehouses[0].name} ({warehouses[0].id}) state={warehouses[0].state}")
        return warehouses[0].id
    raise RuntimeError("No SQL warehouse found (or none you can use). Ask your instructor for CAN USE on one.")


def list_spaces():
    """All Genie spaces you can see (follows pagination)."""
    spaces, token = [], None
    while True:
        r = requests.get(f"{host}/api/2.0/genie/spaces", headers=headers,
                         params={"page_token": token} if token else None)
        r.raise_for_status()
        body = r.json()
        spaces += body.get("spaces", [])
        token = body.get("next_page_token")
        if not token:
            return spaces


def create_or_update_genie_space(title, description, serialized_space_str, warehouse_id):
    """Create the agent, or PATCH it if one with this title already exists (idempotent re-runs)."""
    payload = {"title": title, "description": description,
               "warehouse_id": warehouse_id, "serialized_space": serialized_space_str}
    for s in list_spaces():
        if s.get("title") == title:
            sid = s.get("space_id") or s.get("id")
            pr = requests.patch(f"{host}/api/2.0/genie/spaces/{sid}", headers=headers, json=payload)
            print(f"Updated existing: {title!r} -> {sid} ({pr.status_code})")
            if pr.status_code not in (200, 201):
                print("  ", pr.text[:400])
            return sid, genie_ui_room_url(sid)
    resp = requests.post(f"{host}/api/2.0/genie/spaces", headers=headers, json=payload)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Genie create failed {resp.status_code}: {resp.text[:800]}")
    sid = resp.json().get("space_id") or resp.json().get("id")
    print(f"Created: {title!r} -> {sid}")
    return sid, genie_ui_room_url(sid)


def _extract_number(value):
    if value is None:
        return None
    nums = re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(value).replace(",", ""))
    return float(nums[0]) if nums else None


def ask_genie(question, space_id, timeout=120):
    """Ask a Genie agent one question through the Conversation API.

    Returns (number, error): the last numeric cell of the first result row (so "Midwest | 123.4" gives 123.4),
    or (None, reason) when Genie didn't return a number.
    """
    try:
        s = requests.post(f"{host}/api/2.0/genie/spaces/{space_id}/start-conversation",
                          headers=headers, json={"content": question})
        if s.status_code != 200:
            return None, f"HTTP {s.status_code}"
        d = s.json()
        cid, mid = d.get("conversation_id"), d.get("message_id")
        for _ in range(timeout // 4):
            time.sleep(4)
            p = requests.get(f"{host}/api/2.0/genie/spaces/{space_id}/conversations/{cid}/messages/{mid}",
                             headers=headers)
            if p.status_code != 200:
                continue
            msg = p.json()
            if msg.get("status") == "COMPLETED":
                for att in msg.get("attachments", []):
                    aid = att.get("attachment_id") or att.get("id", "")
                    if not att.get("query") or not aid:
                        continue
                    qr = requests.get(
                        f"{host}/api/2.0/genie/spaces/{space_id}/conversations/{cid}/messages/{mid}/query-result/{aid}",
                        headers=headers)
                    if qr.status_code != 200:
                        continue
                    sr = qr.json().get("statement_response", {})
                    # The attachment query runs asynchronously; only read the result once it has SUCCEEDED.
                    state = sr.get("status", {}).get("state")
                    if state and state != "SUCCEEDED":
                        return None, f"query {state}"
                    arr = sr.get("result", {}).get("data_array", [])
                    if arr and arr[0]:
                        for cell in reversed(arr[0]):
                            n = _extract_number(cell)
                            if n is not None:
                                return n, None
                return None, "No numeric value"
            if msg.get("status") in ("FAILED", "CANCELLED"):
                return None, msg.get("status")
        return None, "Timeout"
    except Exception as e:
        return None, str(e)[:80]


def score(genie_val, gt_val, tolerance_pct=BENCHMARK_TOLERANCE_PCT):
    """PASS / FAIL for one numeric answer against ground truth (relative tolerance in %)."""
    if genie_val is None:
        return "FAIL"
    if gt_val == 0:
        return "PASS" if genie_val == 0 else "FAIL"
    return "PASS" if abs(genie_val - gt_val) / abs(gt_val) * 100 <= tolerance_pct else "FAIL"


# COMMAND ----------

# MAGIC %md
# MAGIC ### Check the source tables and print the configuration summary
# MAGIC
# MAGIC Confirms the shared gold tables are readable, then echoes your schemas and the **exact names** your Genie agents
# MAGIC will have, so you can find them in Genie.

# COMMAND ----------

# DBTITLE 1,Check the shared gold tables are there
_missing = [t for t in GENIE_SOURCE_TABLES if not spark.catalog.tableExists(t)]
if _missing:
    raise RuntimeError(
        f"These shared source tables are missing or you can't read them: {_missing}. "
        f"Ask your instructor to run instructor_setup/01_prebuild_shared_gold and to grant you SELECT on {SOURCE_FQN}."
    )

print("=" * 66)
print("Apex Motorsports Parts · Genie workshop")
print("=" * 66)
print(f"Source data (read-only) : {SOURCE_FQN}")
print(f"Your schema             : {FULL_SCHEMA}")
print(f"Warehouse ID            : {SQL_WAREHOUSE_ID or '(auto-select)'}")
print("Your Genie agents (look for these names in Genie):")
print(f"  Baseline         : {GENIE_TITLE_BASELINE}   (created in 01)")
print(f"  Metric View      : {GENIE_TITLE_METRIC_VIEW}   (created in 02)")
print(f"  Knowledge Store  : {GENIE_TITLE_CURATED}   (created in 03)")
print(f"  Genie Code Built : {GENIE_TITLE_GENIE_CODE}   (created by Genie Code in 05)")
print(f"  CI/CD demo copy  : {GENIE_TITLE_CICD_DEMO}   (created in 08)")
print("=" * 66)
