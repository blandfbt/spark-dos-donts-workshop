# Databricks notebook source
# MAGIC %md
# MAGIC # Lab helpers
# MAGIC
# MAGIC Included by `01_bronze_to_gold_lab` with `%run ./lab_helpers`; you do not run this notebook on its own.
# MAGIC
# MAGIC * `check("<exercise>")` verifies your result against the reference solution.
# MAGIC * `reveal("<exercise>")` prints a reference solution.
# MAGIC * `catch_up("<exercise>")` builds the result from the reference solution, so you can keep going.
# MAGIC * `counter()`, `bar()`, `line()`, `table()` and `publish_dashboard()` build an AI/BI dashboard from code.
# MAGIC
# MAGIC With the `auto_solve` widget set to `true` (the bundle job does this), every check that fails runs
# MAGIC `catch_up` automatically, so the whole lab can run unattended.

# COMMAND ----------

import json
import re

dbutils.widgets.dropdown("auto_solve", "false", ["false", "true"], "Auto-solve exercises")
dbutils.widgets.text("warehouse_id", "", "SQL warehouse ID (dashboard)")
AUTO_SOLVE = dbutils.widgets.get("auto_solve") == "true"

LAB_RAW = f"{VOLUME}/lab"
LAB_CHECKPOINTS = f"{VOLUME}/_checkpoints/endtoend"
LAB_DASHBOARD_NAME = f"Apex Motorsports Parts - December sales ({SCHEMA})"


def reset_lab():
    """Drop every endtoend_* table and the lab's Auto Loader checkpoints. The raw files are kept."""
    for t in spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}` LIKE 'endtoend_*'").collect():
        spark.sql(f"DROP TABLE IF EXISTS {T(t.tableName)}")
    dbutils.fs.rm(LAB_CHECKPOINTS, True)
    print("Lab reset: endtoend_* tables dropped, checkpoints cleared.")


# COMMAND ----------

# Reference solutions. `code` is what you would write in the exercise cell; `expected` is a query that
# produces the correct result for checking.
SOLUTIONS = {
    "bronze_dealers": {
        "lang": "python",
        "code": '''
dealers_raw = (
    spark.read.option("header", True)        # every column stays a string in bronze
    .csv(f"{LAB_RAW}/dealers_csv")
    .select("*",
            F.col("_metadata.file_path").alias("_source_file"),
            F.current_timestamp().alias("_ingested_at"))
)
dealers_raw.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("endtoend_bronze_dealers_dim")
spark.sql("COMMENT ON TABLE endtoend_bronze_dealers_dim IS 'Dealer list exactly as delivered (CSV), with lineage columns'")
''',
    },
    "silver_dealers": {
        "lang": "sql",
        "code": '''
CREATE OR REPLACE TABLE endtoend_silver_dealers_dim
COMMENT 'Dealer reference: one row per dealer, latest version, cleaned text'
AS
SELECT
  CAST(dealer_id AS INT)                                              AS dealer_id,
  coalesce(nullif(trim(dealer_name), ''), concat('Unknown dealer ', dealer_id)) AS dealer_name,
  initcap(trim(region))                                               AS region,
  upper(trim(state))                                                  AS state,
  dealer_tier,
  to_timestamp(updated_at)                                            AS updated_at
FROM endtoend_bronze_dealers_dim
QUALIFY row_number() OVER (PARTITION BY dealer_id ORDER BY to_timestamp(updated_at) DESC) = 1
''',
    },
    "silver_parts": {
        "lang": "sql",
        "code": '''
CREATE OR REPLACE TABLE endtoend_silver_parts_dim
COMMENT 'Parts reference for the end-to-end lab: one row per part, only the columns gold needs'
AS
SELECT part_id, part_name, category, list_price, unit_cost
FROM dim_part
''',
    },
    "gold_category_region": {
        "lang": "sql",
        "code": '''
CREATE OR REPLACE TABLE endtoend_gold_category_region_fact
COMMENT 'December 2025 orders, units, net revenue and margin by region and part category'
AS
SELECT
  d.region,
  p.category,
  count(*)                                                        AS orders,
  sum(o.quantity)                                                 AS units,
  round(sum(o.net_revenue), 2)                                    AS net_revenue,
  round(sum(o.net_revenue - o.quantity * p.unit_cost), 2)         AS margin,
  round(100 * sum(o.net_revenue - o.quantity * p.unit_cost) / sum(o.net_revenue), 2) AS margin_pct
FROM endtoend_silver_orders_fact o
JOIN endtoend_silver_dealers_dim d ON o.dealer_id = d.dealer_id
JOIN endtoend_silver_parts_dim p ON o.part_id = p.part_id
GROUP BY d.region, p.category
''',
    },
    "top_dealers": {
        "lang": "sql",
        "code": '''
CREATE OR REPLACE TEMP VIEW answer_top_dealers AS
SELECT region, dealer_name, net_revenue, revenue_rank
FROM (
  SELECT region, dealer_name, sum(net_revenue) AS net_revenue,
         rank() OVER (PARTITION BY region ORDER BY sum(net_revenue) DESC) AS revenue_rank
  FROM endtoend_gold_daily_dealer_sales_fact
  GROUP BY region, dealer_name
)
WHERE revenue_rank <= 3
''',
    },
    "online_share": {
        "lang": "sql",
        "code": '''
CREATE OR REPLACE TEMP VIEW answer_online_share AS
SELECT
  to_date(order_ts) AS order_date,
  round(100 * sum(CASE WHEN channel = 'Online' THEN net_revenue END) / sum(net_revenue), 2) AS online_share_pct
FROM endtoend_silver_orders_fact
GROUP BY to_date(order_ts)
ORDER BY online_share_pct DESC
LIMIT 5
''',
    },
    "dashboard": {
        "lang": "python",
        "code": '''
my_datasets = [dataset("categories", "Margin by category",
                       "SELECT region, category, margin_pct FROM endtoend_gold_category_region_fact")]
my_widgets = [bar("b_categories", "categories", "category", "margin_pct", "Margin % by category and region",
                  x=0, y=17, w=6, color="region")]
publish_dashboard(datasets + my_datasets, widgets + my_widgets)
''',
    },
}


def reveal(name):
    """Print the reference solution for an exercise."""
    sol = SOLUTIONS[name]
    print(f"Reference solution ({sol['lang'].upper()}) for '{name}':\n")
    print(("%sql\n" if sol["lang"] == "sql" else "") + sol["code"].strip())


def catch_up(name, quiet=False):
    """Build an exercise's result from the reference solution."""
    sol = SOLUTIONS[name]
    if sol["lang"] == "python":
        exec(sol["code"], globals())
    else:
        for statement in [s for s in sol["code"].split(";") if s.strip()]:
            spark.sql(statement)
    if not quiet:
        print(f"⏩ '{name}' built from the reference solution. Carry on with the next step.")


# COMMAND ----------

def _select_of(name):
    """The SELECT body of a reference CREATE ... AS statement (used to compute the expected result)."""
    return re.split(r"(?:^|\s)AS\s*\n", SOLUTIONS[name]["code"].strip(), maxsplit=1)[1]


def _exists(table):
    return spark.catalog.tableExists(f"{CATALOG}.{SCHEMA}.{table}")


def _same_rows(actual, expected, keys, numeric=(), tol=0.05):
    """True if two DataFrames have the same keys and (within tol) the same numeric values."""
    a = actual.select(*keys, *[F.col(c).cast("double").alias(f"a_{c}") for c in numeric]).withColumn("_a", F.lit(1))
    e = expected.select(*keys, *[F.col(c).cast("double").alias(f"e_{c}") for c in numeric]).withColumn("_e", F.lit(1))
    cond = F.col("_a").isNull() | F.col("_e").isNull()
    for c in numeric:
        cond = cond | (F.abs(F.col(f"a_{c}") - F.col(f"e_{c}")) > tol)
    problems = a.join(e, keys, "full_outer").where(cond)
    return problems.count() == 0, problems


def _check_bronze_dealers():
    if not _exists("endtoend_bronze_dealers_dim"):
        return False, "Table endtoend_bronze_dealers_dim doesn't exist yet."
    df = spark.table("endtoend_bronze_dealers_dim")
    missing = {"dealer_id", "dealer_name", "region", "updated_at", "_source_file", "_ingested_at"} - set(df.columns)
    if missing:
        return False, f"Missing columns: {sorted(missing)}"
    raw = spark.read.option("header", True).csv(f"{LAB_RAW}/dealers_csv").count()
    if df.count() != raw:
        return False, f"Expected all {raw} raw rows (bronze keeps duplicates), found {df.count()}."
    return True, f"{raw} raw dealer rows, with lineage columns."


def _check_silver_dealers():
    if not _exists("endtoend_silver_dealers_dim"):
        return False, "Table endtoend_silver_dealers_dim doesn't exist yet."
    df = spark.table("endtoend_silver_dealers_dim")
    n, distinct = df.count(), df.select("dealer_id").distinct().count()
    if n != distinct:
        return False, f"{n} rows but {distinct} dealers: keep one row per dealer_id (the latest updated_at)."
    bad_regions = [r[0] for r in df.select("region").distinct().collect()
                   if r[0] not in ("Northeast", "Southeast", "Midwest", "Southwest", "West", "Northwest")]
    if bad_regions:
        return False, f"Regions still need cleaning: {bad_regions[:5]}"
    if df.where("dealer_name IS NULL OR trim(dealer_name) = ''").count():
        return False, "Some dealer names are blank: fill them in (e.g. 'Unknown dealer <id>')."
    stale = df.join(spark.table("dim_dealer").select("dealer_id", F.col("dealer_tier").alias("t")), "dealer_id") \
              .where("dealer_tier <> t").count()
    if stale:
        return False, f"{stale} dealers kept a stale version: order by updated_at and keep the latest."
    return True, f"{n} dealers, one row each, clean regions."


def _check_gold_category_region():
    if not _exists("endtoend_gold_category_region_fact"):
        return False, "Table endtoend_gold_category_region_fact doesn't exist yet."
    actual = spark.table("endtoend_gold_category_region_fact")
    expected = spark.sql(_select_of("gold_category_region"))
    missing = set(expected.columns) - set(actual.columns)
    if missing:
        return False, f"Missing columns: {sorted(missing)}"
    a = actual.withColumn("k", F.concat_ws("|", "region", "category"))
    e = expected.withColumn("k", F.concat_ws("|", "region", "category"))
    ok, _ = _same_rows(a.select("k", "net_revenue", "margin", "units"), e.select("k", "net_revenue", "margin", "units"),
                       ["k"], ["net_revenue", "margin", "units"], tol=1.0)
    return (True, f"{expected.count()} region × category rows match.") if ok else \
           (False, "Values differ from the expected result: check the joins and the margin formula.")


def _check_view(view, name, keys, numeric):
    try:
        actual = spark.table(view)
        actual.columns  # Spark Connect resolves lazily: force the lookup here
    except Exception:
        return False, f"Temp view {view} doesn't exist yet."
    expected = spark.sql(_select_of(name))
    if set(expected.columns) - set(actual.columns):
        return False, f"Expected columns {expected.columns}, found {actual.columns}"
    ok, _ = _same_rows(actual.select(*expected.columns), expected, keys, numeric)
    return (True, f"{expected.count()} rows match.") if ok else (False, "Rows differ from the expected answer.")


def _check_dashboard():
    base = len(globals().get("widgets", []))
    n = dashboard_widget_count()
    if n == 0:
        return False, "The dashboard doesn't exist yet: run the example cell in section 5 first."
    if n <= base:
        return False, f"The dashboard has {n} widgets, the same as the example. Add one to my_widgets and republish."
    return True, f"The dashboard has {n} widgets ({n - base} added by you)."


CHECKS = {
    "silver_parts": lambda: ((True, "parts dimension exists") if _exists("endtoend_silver_parts_dim")
                             else (False, "Table endtoend_silver_parts_dim doesn't exist yet: run the parts example in 2d.")),
    "dashboard": _check_dashboard,
    "bronze_dealers": _check_bronze_dealers,
    "silver_dealers": _check_silver_dealers,
    "gold_category_region": _check_gold_category_region,
    "top_dealers": lambda: _check_view("answer_top_dealers", "top_dealers", ["dealer_name"], ["net_revenue"]),
    "online_share": lambda: _check_view("answer_online_share", "online_share", ["order_date"], ["online_share_pct"]),
}


def check(name):
    """Verify an exercise. Prints ✅ or ❌ with a hint; with auto_solve=true a failure runs catch_up."""
    ok, msg = CHECKS[name]()
    if ok:
        print(f"✅ {name}: {msg}")
        return True
    print(f"❌ {name}: {msg}")
    if AUTO_SOLVE:
        catch_up(name)
        ok, msg = CHECKS[name]()
        print(f"{'✅' if ok else '❌'} {name} (auto-solved): {msg}")
        return ok
    print(f"   Stuck? reveal('{name}') shows a solution; catch_up('{name}') builds it so you can move on.")
    return False


def require(*names):
    """Make sure earlier exercises exist before an example that depends on them (builds missing ones)."""
    for name in names:
        ok, _ = CHECKS[name]()
        if not ok:
            catch_up(name, quiet=True)
            print(f"⏩ '{name}' wasn't finished yet, so it was built from the reference solution.")


# COMMAND ----------

# Dashboard building blocks. An AI/BI dashboard is JSON: datasets (SQL queries) and widgets laid out on
# a 6-column grid. These helpers write the JSON for the most common widget types.

def dataset(name, display_name, sql):
    return {"name": name, "displayName": display_name, "queryLines": [sql], "catalog": CATALOG, "schema": SCHEMA}


def _widget(name, ds, fields, spec, x, y, w, h):
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {
                "datasetName": ds, "disaggregated": True,
                "fields": [{"name": f, "expression": f"`{f}`"} for f in fields]}}],
            "spec": spec,
        },
        "position": {"x": x, "y": y, "width": w, "height": h},
    }


def counter(name, ds, field, title, x, y, w=2, h=3):
    spec = {"version": 2, "widgetType": "counter", "encodings": {"value": {"fieldName": field, "displayName": title}},
            "frame": {"showTitle": True, "title": title}}
    return _widget(name, ds, [field], spec, x, y, w, h)


def _xy(kind, name, ds, x_field, y_field, title, x, y, w, h, color=None, x_type="categorical"):
    enc = {"x": {"fieldName": x_field, "scale": {"type": x_type}, "displayName": x_field},
           "y": {"fieldName": y_field, "scale": {"type": "quantitative"}, "displayName": y_field}}
    fields = [x_field, y_field]
    if color:
        enc["color"] = {"fieldName": color, "scale": {"type": "categorical"}, "displayName": color}
        fields.append(color)
    spec = {"version": 3, "widgetType": kind, "encodings": enc, "frame": {"showTitle": True, "title": title}}
    return _widget(name, ds, fields, spec, x, y, w, h)


def bar(name, ds, x_field, y_field, title, x, y, w=3, h=6, color=None):
    return _xy("bar", name, ds, x_field, y_field, title, x, y, w, h, color)


def line(name, ds, x_field, y_field, title, x, y, w=6, h=6, color=None):
    return _xy("line", name, ds, x_field, y_field, title, x, y, w, h, color, x_type="temporal")


def table(name, ds, columns, title, x, y, w=6, h=6):
    spec = {"version": 2, "widgetType": "table",
            "encodings": {"columns": [{"fieldName": c, "displayName": c} for c in columns]},
            "frame": {"showTitle": True, "title": title}}
    return _widget(name, ds, columns, spec, x, y, w, h)


def text(name, markdown, x, y, w=6, h=2):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": [markdown]}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


def _warehouse_id(w):
    chosen = dbutils.widgets.get("warehouse_id").strip()
    if chosen:
        return chosen
    warehouses = sorted(w.warehouses.list(), key=lambda wh: (not wh.enable_serverless_compute, str(wh.state) != "State.RUNNING"))
    if not warehouses:
        raise RuntimeError("No SQL warehouse found. Create a serverless SQL warehouse, or set the warehouse_id widget.")
    return warehouses[0].id


def _dashboard_id(w, display_name):
    """ID of the dashboard with this name in your home folder, or None."""
    try:
        return w.workspace.get_status(f"/Users/{CURRENT_USER}/{display_name}.lvdash.json").resource_id
    except Exception:
        return None


def publish_dashboard(datasets, widgets, display_name=LAB_DASHBOARD_NAME):
    """Create (or update) and publish the dashboard in your home folder. Returns its URL."""
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.dashboards import Dashboard

    w = WorkspaceClient()
    serialized = json.dumps({"datasets": datasets,
                             "pages": [{"name": "overview", "displayName": "Overview", "pageType": "PAGE_TYPE_CANVAS",
                                        "layout": widgets}]})
    parent = f"/Users/{CURRENT_USER}"
    warehouse = _warehouse_id(w)
    spec = Dashboard(display_name=display_name, parent_path=parent, serialized_dashboard=serialized, warehouse_id=warehouse)
    existing_id = _dashboard_id(w, display_name)
    if existing_id:
        dash = w.lakeview.update(existing_id, dashboard=spec)
    else:
        dash = w.lakeview.create(dashboard=spec)
    w.lakeview.publish(dash.dashboard_id, warehouse_id=warehouse, embed_credentials=True)
    url = f"{w.config.host.rstrip('/')}/dashboardsv3/{dash.dashboard_id}/published"
    print(f"📊 {display_name}: {len(widgets)} widgets, {len(datasets)} datasets\n   {url}")
    return dash.dashboard_id, url


def dashboard_widget_count(display_name=LAB_DASHBOARD_NAME):
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    dashboard_id = _dashboard_id(w, display_name)
    if not dashboard_id:
        return 0
    full = json.loads(w.lakeview.get(dashboard_id).serialized_dashboard)
    return sum(len(p["layout"]) for p in full["pages"])
