# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 04 · The Knowledge Store (curation that earns trust)
# MAGIC
# MAGIC This is the heart of the Genie workshop. Teams that see low Genie adoption almost always **skipped this step**:
# MAGIC they attach tables, stuff every rule into one giant instructions blob, and hope. The
# MAGIC **[Knowledge Store](https://docs.databricks.com/aws/en/genie/best-practices)** is the structured alternative, and
# MAGIC it's what makes an agent trustworthy.
# MAGIC
# MAGIC **The anti-pattern (what not to do):** one enormous `text_instructions` blob holding every formula, join and
# MAGIC classification. It eats the context window, invites contradictions, and Genie applies it inconsistently.
# MAGIC
# MAGIC **The fix: structured components**, each doing one job:
# MAGIC
# MAGIC | Component | What it pins | Apex Motorsports Parts example |
# MAGIC |---|---|---|
# MAGIC | **Column configs** | descriptions, **synonyms**, hidden columns | `net_revenue` → "sales", "revenue"; `dealer_name` → "store", "shop"; hide `updated_at` |
# MAGIC | **Joins** | the correct join paths | daily dealer sales → dealers dim on `dealer_id` (many-to-one), for the dealer's state |
# MAGIC | **Measures** | KPI formulas | Margin % = `100 × SUM(margin) / SUM(net_revenue)` (never `AVG(margin_pct)`) |
# MAGIC | **Filters** | reusable conditions | Platinum dealers only; weekend days |
# MAGIC | **Fields / expressions** | row-level derivations | order week (Monday start), day of week |
# MAGIC | **Example SQL** | question → SQL patterns | "top N dealers in a region" with the right `ORDER BY ... LIMIT` |
# MAGIC | **Text instructions** | *only* clarifications and formatting | state names → two-letter codes; 2-decimal percentages |
# MAGIC
# MAGIC **Priority order:** measures/filters/fields → example SQL → text **last**. Genie's own docs show example SQL is the
# MAGIC single biggest accuracy jump.
# MAGIC
# MAGIC This notebook builds all of that **programmatically** via `serialized_space` (v2) and creates the **primary agent**
# MAGIC (`genie_space_id`) that later notebooks benchmark and deploy.
# MAGIC
# MAGIC > **Schema note.** Before your session, confirm the `serialized_space` shape against a live agent:
# MAGIC > `GET /api/2.0/genie/spaces/<id>?include_serialized_space=true`. If a field differs, adjust the builders below;
# MAGIC > the structure is what matters.
# MAGIC
# MAGIC **Before you start:** run **03** (baseline). **Compute:** Serverless.

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
# MAGIC `genie_helpers` created the SDK client and REST headers; pick the warehouse the Knowledge Store agent will use.

# COMMAND ----------

warehouse_id = pick_warehouse()

# Short names used inside SQL snippets (Genie resolves them against the attached tables)
DAILY = "endtoend_gold_daily_dealer_sales_fact"
CATREG = "endtoend_gold_category_region_fact"
DEALERS = "endtoend_silver_dealers_dim"
PARTS = "endtoend_silver_parts_dim"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Column configs: descriptions, synonyms and hidden columns
# MAGIC
# MAGIC Teach Genie the business vocabulary (**synonyms**) and hide columns that only confuse it. Here we hide
# MAGIC `updated_at` (a technical load timestamp in the dealers dim) and explain the columns people misuse, such as
# MAGIC `margin_pct` in the category table (a per-row percentage that must not be averaged). Entity matching (which needs
# MAGIC format assistance) is turned on for the text columns users filter on: region, tier, state, category, dealer name.

# COMMAND ----------

def col(name, description=None, synonyms=None, exclude=False, entity_matching=False, format_assist=False):
    return {
        "column_name": name,
        "description": [description] if description else [],
        "synonyms": synonyms or [],
        "exclude": exclude,
        "enable_entity_matching": entity_matching,
        "enable_format_assistance": format_assist or entity_matching,
    }


REVENUE_SYNONYMS = ["sales", "revenue", "net sales", "turnover"]
DEALER_SYNONYMS = ["dealer", "store", "shop", "retailer", "location"]

column_configs_by_table = {
    GOLD_DAILY_TABLE: [
        col("order_date", synonyms=["date", "day", "sales date"], description="Calendar day, December 2025 only."),
        col("region", synonyms=["sales region", "territory"], entity_matching=True,
            description="Dealer's sales region: Northeast, Southeast, Midwest, Southwest, West or Northwest."),
        col("dealer_name", synonyms=DEALER_SYNONYMS, entity_matching=True),
        col("dealer_tier", synonyms=["tier", "dealer level", "partner tier"], entity_matching=True,
            description="Platinum, Gold or Standard."),
        col("orders", synonyms=["order lines", "order count", "number of orders"],
            description="Number of order lines that day for that dealer."),
        col("units", synonyms=["quantity", "units sold", "items sold"]),
        col("net_revenue", synonyms=REVENUE_SYNONYMS,
            description="Revenue in USD after discounts: quantity x unit_price x (1 - discount)."),
        col("margin", synonyms=["gross margin", "profit", "gross profit"],
            description="net_revenue minus quantity x unit_cost, in USD."),
    ],
    GOLD_CATEGORY_TABLE: [
        col("region", synonyms=["sales region", "territory"], entity_matching=True),
        col("category", synonyms=["part category", "product category", "product line"], entity_matching=True,
            description="Part category, e.g. Brakes, Engine, Tires, Suspension, Aero."),
        col("net_revenue", synonyms=REVENUE_SYNONYMS),
        col("margin", synonyms=["gross margin", "profit", "gross profit"]),
        col("margin_pct", synonyms=["margin percent", "margin rate"],
            description="Margin % of THIS region x category row only. Never average it across rows: "
                        "recompute 100 * SUM(margin) / SUM(net_revenue)."),
    ],
    DEALERS_TABLE: [
        col("state", synonyms=["dealer state", "US state"], entity_matching=True,
            description="Two-letter US state code of the dealer (TX = Texas, CA = California, MI = Michigan, ...)."),
        col("dealer_name", synonyms=DEALER_SYNONYMS, entity_matching=True),
        col("dealer_tier", synonyms=["tier", "dealer level"], entity_matching=True),
        col("region", synonyms=["sales region"], entity_matching=True),
        col("updated_at", description="Technical load timestamp: hidden from the agent.", exclude=True),
    ],
    PARTS_TABLE: [
        col("category", synonyms=["part category", "product line"], entity_matching=True),
        col("list_price", synonyms=["price", "MSRP", "list"]),
        col("unit_cost", synonyms=["cost", "unit cost"]),
    ],
}


def table_entry(identifier):
    cfgs = sorted(column_configs_by_table.get(identifier, []), key=lambda c: c["column_name"])
    e = {"identifier": identifier}
    if cfgs:
        e["column_configs"] = cfgs
    return e


tables = sorted([table_entry(t) for t in GENIE_SOURCE_TABLES], key=lambda e: e["identifier"])
print(f"{len(tables)} tables; hidden: updated_at; synonyms on revenue, dealer, tier, state, category, ...")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Joins: pin the correct paths
# MAGIC
# MAGIC Each join records the relationship type in the required `--rt=FROM_RELATIONSHIP_TYPE_*--` marker. The daily gold
# MAGIC table already carries region, tier and dealer name; the dealers dimension adds the **state**. Just as important
# MAGIC is what we **don't** join: the category table has no dealer or date, and the parts table has no sales, so there
# MAGIC is no valid join from either one to the daily table (the text instructions say so).

# COMMAND ----------

def join_spec(l_id, l_alias, l_col, r_id, r_alias, r_col, rel):
    return {
        "id": new_id(),
        "left": {"identifier": l_id, "alias": l_alias},
        "right": {"identifier": r_id, "alias": r_alias},
        "sql": [f"`{l_alias}`.`{l_col}` = `{r_alias}`.`{r_col}`",
                f"--rt=FROM_RELATIONSHIP_TYPE_{rel}--"],
        "comment": [],
        "instruction": [],
    }


joins = [
    join_spec(GOLD_DAILY_TABLE, "s", "dealer_id", DEALERS_TABLE, "d", "dealer_id", "MANY_TO_ONE"),
]
print(f"{len(joins)} join defined")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Measures, filters and fields (SQL snippets)
# MAGIC
# MAGIC **Measures** are the KPI formulas: the math Genie should never re-invent. **Filters** are reusable conditions.
# MAGIC **Fields/expressions** are row-level derivations. This is where the logic that used to live in the giant text blob
# MAGIC actually belongs.

# COMMAND ----------

def snippet(display_name, sql, synonyms=None, instruction=None):
    return {
        "id": new_id(),
        "display_name": display_name,
        "sql": [sql],
        "synonyms": synonyms or [],
        "instruction": [instruction] if instruction else [],
        "comment": [],
    }


measures = [
    snippet("Net revenue", f"ROUND(SUM({DAILY}.net_revenue), 2)", synonyms=REVENUE_SYNONYMS,
            instruction="Total net revenue in USD."),
    snippet("Margin %", f"ROUND(100.0 * SUM({DAILY}.margin) / NULLIF(SUM({DAILY}.net_revenue), 0), 2)",
            synonyms=["margin percent", "margin rate", "gross margin %"],
            instruction="Weighted margin %: total margin / total net revenue. Never AVG a percentage."),
    snippet("Category margin %", f"ROUND(100.0 * SUM({CATREG}.margin) / NULLIF(SUM({CATREG}.net_revenue), 0), 2)",
            synonyms=["margin % by category"],
            instruction="Use for any margin % question that mentions a part category. Never AVG(margin_pct)."),
    snippet("Average revenue per order", f"ROUND(SUM({DAILY}.net_revenue) / NULLIF(SUM({DAILY}.orders), 0), 2)",
            synonyms=["average order value", "AOV", "revenue per order"],
            instruction="Total net revenue / total orders, never an average of daily averages."),
    snippet("Active dealers", f"COUNT(DISTINCT {DAILY}.dealer_id)",
            synonyms=["number of dealers with sales", "selling dealers"]),
]

filters = [
    snippet("Platinum dealers", f"{DAILY}.dealer_tier = 'Platinum'", synonyms=["top-tier dealers", "platinum"]),
    snippet("Weekend days", f"DAYOFWEEK({DAILY}.order_date) IN (1, 7)", synonyms=["weekends", "Saturday and Sunday"],
            instruction="DAYOFWEEK returns 1 for Sunday and 7 for Saturday."),
]

expressions = [
    snippet("Order week", f"CAST(DATE_TRUNC('WEEK', {DAILY}.order_date) AS DATE)",
            synonyms=["week", "week starting", "weekly"], instruction="Weeks start on Monday."),
    snippet("Day of week", f"DATE_FORMAT({DAILY}.order_date, 'EEEE')", synonyms=["weekday"]),
    snippet("Unit margin at list price", f"{PARTS}.list_price - {PARTS}.unit_cost",
            synonyms=["list margin", "margin per unit"]),
]
print(f"{len(measures)} measures, {len(filters)} filters, {len(expressions)} fields")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Example SQL: the highest-impact curation
# MAGIC
# MAGIC A natural-language question paired with its correct SQL. Genie matches new questions to these patterns. Some
# MAGIC carry **parameters** (`:state`, `:region`) so one example covers many values.

# COMMAND ----------

def param(name, type_hint, description, default=None):
    p = {"name": name, "type_hint": type_hint, "description": [description]}
    if default is not None:
        p["default_value"] = {"values": [str(default)]}
    return p


def example(question, sql, parameters=None, usage_guidance=None):
    return {
        "id": new_id(),
        "question": [question],
        "sql": [sql],
        "parameters": sorted(parameters or [], key=lambda p: p["name"]),
        "usage_guidance": [usage_guidance] if usage_guidance else [],
    }


examples = [
    example(
        "What was the margin % by dealer tier?",
        f"SELECT dealer_tier, ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) AS margin_pct "
        f"FROM {GOLD_DAILY_TABLE} GROUP BY dealer_tier ORDER BY margin_pct DESC",
        usage_guidance="Weighted margin % by a dimension of the daily table."),
    example(
        "What was the net revenue of dealers in {state}?",
        f"SELECT ROUND(SUM(s.net_revenue), 2) AS net_revenue FROM {GOLD_DAILY_TABLE} s "
        f"JOIN {DEALERS_TABLE} d ON s.dealer_id = d.dealer_id WHERE d.state = :state",
        parameters=[param("state", "STRING", "Two-letter US state code, e.g. OH for Ohio", "OH")],
        usage_guidance="Dealer state lives only in the dealers dim; map state names to two-letter codes."),
    example(
        "Top 5 dealers by net revenue in the {region} region",
        f"SELECT dealer_name, ROUND(SUM(net_revenue), 2) AS net_revenue FROM {GOLD_DAILY_TABLE} "
        f"WHERE region = :region GROUP BY dealer_name ORDER BY net_revenue DESC LIMIT 5",
        parameters=[param("region", "STRING", "Sales region, e.g. Northeast", "Northeast")],
        usage_guidance="Ranking dealers: aggregate over all days first, then order and limit."),
    example(
        "What is the margin % for each part category across all regions?",
        f"SELECT category, ROUND(100.0 * SUM(margin) / NULLIF(SUM(net_revenue), 0), 2) AS margin_pct "
        f"FROM {GOLD_CATEGORY_TABLE} GROUP BY category ORDER BY margin_pct DESC",
        usage_guidance="Category questions use the category x region table; recompute the % from sums."),
    example(
        "Weekly net revenue by region",
        f"SELECT CAST(DATE_TRUNC('WEEK', order_date) AS DATE) AS order_week, region, "
        f"ROUND(SUM(net_revenue), 2) AS net_revenue FROM {GOLD_DAILY_TABLE} "
        f"GROUP BY ALL ORDER BY order_week, region",
        usage_guidance="Weeks start on Monday."),
]
print(f"{len(examples)} example SQLs")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Text instructions: kept short on purpose
# MAGIC
# MAGIC With the logic now in measures, joins and examples, text instructions shrink to what only prose can express:
# MAGIC **which table answers what**, **when to ask for clarification** and **formatting rules**. This is the opposite
# MAGIC of the monolithic blob: a handful of lines.

# COMMAND ----------

sample_questions = sorted(
    [{"id": new_id(), "question": [q]} for q in [
        "What was the total net revenue in December 2025?",
        "What was the margin % by dealer tier?",
        "Which part category has the highest margin %?",
    ]],
    key=lambda x: x["id"],
)

text_instructions = [{
    "id": new_id(),
    "content": [
        "All sales data covers December 2025 only; if a question asks about another period, say so.\n",
        "Questions about a part category use endtoend_gold_category_region_fact (no dates or dealers there); "
        "questions about days, weeks, dealers, tiers or states use endtoend_gold_daily_dealer_sales_fact.\n",
        "Dealer state is a two-letter code in endtoend_silver_dealers_dim.state (Texas = 'TX').\n",
        "Percentages and ratios are always SUM / SUM; never average a percentage. Format them to 2 decimals.\n",
    ],
}]
print(f"{len(text_instructions[0]['content'])} instruction lines (deliberately minimal)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Assemble, validate and create the agent
# MAGIC
# MAGIC We sort every array (Genie requires it), check the constraints locally, then create the **primary** Knowledge Store
# MAGIC agent and save it as `genie_space_id`.

# COMMAND ----------

def _by_id(items):
    return sorted(items, key=lambda e: e["id"])


serialized = {
    "version": 2,
    "config": {"sample_questions": sample_questions},
    "data_sources": {"tables": tables},
    "instructions": {
        "text_instructions": text_instructions,
        "example_question_sqls": _by_id(examples),
        "join_specs": _by_id(joins),
        "sql_snippets": {
            "measures": _by_id(measures),
            "filters": _by_id(filters),
            "expressions": _by_id(expressions),
        },
    },
}


def validate(s):
    problems = []
    hexre = re.compile(r"^[0-9a-f]{32}$")

    def check(items, label):
        for it in items:
            if not hexre.match(it.get("id", "")):
                problems.append(f"{label}: bad id {it.get('id')!r}")
        ids = [it["id"] for it in items]
        if ids != sorted(ids):
            problems.append(f"{label}: array not sorted by id")

    ins = s["instructions"]
    check(ins["example_question_sqls"], "example_question_sqls")
    check(ins["join_specs"], "join_specs")
    for k in ("measures", "filters", "expressions"):
        check(ins["sql_snippets"][k], f"sql_snippets.{k}")
    check(s["config"]["sample_questions"], "sample_questions")

    if sum(len(ins["sql_snippets"][k]) for k in ("measures", "filters", "expressions")) > 100:
        problems.append(">100 sql_snippets")
    if len(ins["text_instructions"]) > 1:
        problems.append(">1 text_instructions")
    if len(s["data_sources"]["tables"]) > 30:
        problems.append(">30 tables")
    for j in ins["join_specs"]:
        if len(j["sql"]) != 2 or "--rt=FROM_RELATIONSHIP_TYPE_" not in j["sql"][1]:
            problems.append("join_spec missing --rt marker")
    idents = [t["identifier"] for t in s["data_sources"]["tables"]]
    if idents != sorted(idents):
        problems.append("tables not sorted by identifier")
    return problems


problems = validate(serialized)
print("Local validation:", "OK" if not problems else problems)
serialized_str = json.dumps(serialized)
print(f"serialized_space: {len(serialized_str):,} chars")

# COMMAND ----------

cur_id, cur_url = create_or_update_genie_space(GENIE_TITLE_CURATED, GENIE_DESC_CURATED, serialized_str, warehouse_id)

save_config_keys([
    {"key": CFG_KEY_CURATED, "value": cur_id,
     "space_name": GENIE_TITLE_CURATED, "space_url": cur_url},
])

print()
print("=" * 70)
print("KNOWLEDGE STORE AGENT (primary) CREATED")
print("=" * 70)
print(f"  {cur_url}")
print("=" * 70)
print("Ask it the same questions you asked the baseline in 03:")
print("the curated joins, measures and examples make the difference.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next
# MAGIC
# MAGIC - **05 · Benchmarks:** measure this agent's accuracy against ground-truth SQL.
# MAGIC - **08 · Compare:** Baseline vs. Metric View vs. **Knowledge Store**, head-to-head.
# MAGIC
# MAGIC **Takeaway:** curation isn't one big instruction. It's a handful of small, structured, testable pieces. That's what
# MAGIC turns a demo into an agent people trust.
