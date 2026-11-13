---
name: apex-motorsports-analytics
description: Apex Motorsports Parts sales domain knowledge (dealers, regions, tiers, part categories, net revenue, margin) + Genie agent best practices. Use this skill when building Genie agents, writing sales analytics on the lab_gold_* / lab_silver_* tables, or creating evaluation benchmarks.
---

# Apex Motorsports Parts analytics

## Part 1: Domain knowledge

Apex Motorsports Parts is a fictional company that sells performance parts (brakes, engine, tires, suspension, aero, ...)
through about 500 dealers across the US. The workshop data covers **December 2025** and comes from a bronze → silver →
gold lab. The instructor prebuilds it in a shared, read-only schema (by default `dbx_workshop_dev.shared`). Each
participant has their own schema for anything they create; **never write to the shared schema**.

### Tables and grain

| table | grain | columns |
|---|---|---|
| `lab_gold_daily_dealer_sales_fact` | one row per `order_date` × dealer | order_date, region, dealer_id, dealer_name, dealer_tier, orders, units, net_revenue, margin |
| `lab_gold_category_region_fact` | one row per region × part category | region, category, orders, units, net_revenue, margin, margin_pct |
| `lab_silver_dealers_dim` | one row per dealer | dealer_id, dealer_name, region, state, dealer_tier, updated_at |
| `lab_silver_parts_dim` | one row per part | part_id, part_name, category, list_price, unit_cost |

Silver tables `lab_silver_orders_fact` (order-line grain, with channel and customer) and the 100M-row star
schema (`sdd_fact_orders`, `sdd_dim_*`) also exist in the shared schema but are **not** part of the Genie agents.

### Key metrics

- **Net revenue:** `quantity × unit_price × (1 - discount_pct)` per order line, in USD. Stored pre-aggregated as
  `net_revenue`. Synonyms: sales, revenue, net sales.
- **Margin:** `net_revenue - quantity × unit_cost`, in USD. Synonyms: gross margin, profit.
- **Margin %:** `100 × SUM(margin) / SUM(net_revenue)`. **Always** recompute from sums. Never `AVG(margin_pct)` across
  rows of the category table and never average daily or per-dealer percentages.
- **Orders:** number of order lines (`orders` column). Sum it; don't count rows of a gold table.
- **Average revenue per order:** `SUM(net_revenue) / SUM(orders)`, never an average of daily averages.
- **Active dealers:** `COUNT(DISTINCT dealer_id)` in the daily table.

### Value conventions

- `region`: Northeast, Southeast, Midwest, Southwest, West, Northwest.
- `dealer_tier`: Platinum, Gold, Standard.
- `state` (dealers dim only): two-letter US state codes (MI, OH, IN, TX, CA, FL, NC, GA, AZ, WA, OR, NY, PA, IL, TN).
  Map state names to codes: "Texas" → `'TX'`. A dealer's state and region are independent attributes.
- `category`: Brakes, Engine, Tires, Suspension, Electrical, Aero, Body, Fluids, Exhaust, Drivetrain.
- Weeks start on Monday: `CAST(DATE_TRUNC('WEEK', order_date) AS DATE)`. December 2025 weeks start on Dec 1, 8, 15,
  22 and 29.
- Use exact matches (`= 'Midwest'`) for region, tier, state and category.

### Join paths

- `lab_gold_daily_dealer_sales_fact.dealer_id` → `lab_silver_dealers_dim.dealer_id` (many-to-one): the only
  way to get a dealer's **state**. Region, tier and name are already on the daily table.
- `lab_gold_category_region_fact` has **no** date or dealer: category questions can be sliced by region only.
- `lab_silver_parts_dim` has no sales: use it for catalog questions (list price, unit cost, part counts).
- A question that needs both part category and dealer/date/tier can't be answered from the gold tables; say so.

### Analysis patterns

**Revenue:** total and daily/weekly trend from the daily table; weekend vs weekday with `DAYOFWEEK(order_date) IN (1, 7)`.
**Margin:** margin % by region / tier / dealer (daily table) or by category (category table), always SUM / SUM.
**Dealers:** top/bottom N by net revenue (aggregate over all days first, then `ORDER BY ... LIMIT N`); by state via the
dealers dim.
**Categories:** margin % and revenue by category; region × category matrix from the category table.

---

## Part 2: Genie agent best practices

A well-configured Genie agent has a few structured components. Prefer structured components over a long instruction
blob.

### 1. Data sources

Attach only the tables the questions need (here: the four tables above). Table and column comments are read by Genie,
so make sure they describe the grain and units.

### 2. Column configs

Descriptions, synonyms and hidden columns per table (`column_configs`). Hide technical columns (`updated_at`). Turn on
entity matching (with format assistance) for text columns users filter on: region, dealer_tier, state, category,
dealer_name.

### 3. Joins (`join_specs`)

Pin the join paths, with the relationship type marker, e.g.
`` `s`.`dealer_id` = `d`.`dealer_id` `` and `--rt=FROM_RELATIONSHIP_TYPE_MANY_TO_ONE--`.

### 4. SQL snippets: measures, filters, expressions

- Measures: net revenue, margin %, category margin %, average revenue per order, active dealers.
- Filters: Platinum dealers, weekend days.
- Expressions: order week, day of week.

### 5. Example SQL (8-12)

Question + SQL pairs are the single highest-impact component. Cover: simple totals, the dealers-dim join for state,
ratios (margin %, revenue per order), category × region, weekly/date-range filters, top-N. Use parameters
(`:state`, `:region`) so one example covers many values.

### 6. Text instructions (short)

Only what prose can express: which table answers what, state-name mapping, "never average a percentage", 2-decimal
formatting, "data covers December 2025 only".

### 7. Sample questions (3-5)

Conversation starters in the UI, e.g. "What was the total net revenue in December 2025?", "What was the margin % by
dealer tier?", "Which part category has the highest margin %?".

### 8. Benchmarks (8-15)

Questions with ground-truth SQL used to score accuracy, stored in `serialized_space.benchmarks.questions` and shown in
the **Benchmark** tab:

```json
{"id": "<32-char hex>", "question": ["..."], "answer": [{"format": "SQL", "content": ["SELECT ..."]}]}
```

- One scalar or a small result per question; compute ground truth with SQL on the same tables.
- Keep evaluation (north-star) questions separate from benchmarks: benchmarks teach patterns, evaluations test
  generalization.
- Target 100% on this synthetic data, 85%+ on real-world data. Re-run after every change.
- Track results in a `genie_benchmark_runs` table in your own schema; alert if the pass rate drops below 70%.

### Metric views

For governed KPIs, define a metric view (`CREATE VIEW ... WITH METRICS LANGUAGE YAML`) with the joins and measure
formulas pinned, and query it with `MEASURE(<measure>)`. Here: `genie_mv_dealer_sales` (daily table + dealers dim) and
`genie_mv_category_sales` (category table), both in the participant's own schema. A metric view can only answer questions
inside its perimeter.

### CI/CD

1. **Export:** `GET /api/2.0/genie/spaces/{id}?include_serialized_space=true`
2. **Transform:** remap every `catalog.schema` prefix (shared source schema and the participant's schema) in the JSON
3. **Deploy:** `POST /api/2.0/genie/spaces` or `PATCH /api/2.0/genie/spaces/{id}`

---

## Part 3: Genie REST API reference (for notebook authors)

> **Note for Genie Code:** this section is reference material for people writing notebooks that call the API
> directly. When a user asks you to **create or configure a Genie agent**, use your built-in agent creation capability
> rather than generating raw API code.

### Endpoints

- `GET /api/2.0/genie/spaces`: list agents (paginated with `page_token`)
- `POST /api/2.0/genie/spaces`: create an agent with `{title, description, warehouse_id, serialized_space}`
- `GET /api/2.0/genie/spaces/{id}?include_serialized_space=true`: read the full configuration
- `PATCH /api/2.0/genie/spaces/{id}`: update (`serialized_space` is a full replace)
- `POST /api/2.0/genie/spaces/{id}/start-conversation`: ask a question
- `GET /api/2.0/genie/spaces/{id}/conversations/{cid}/messages/{mid}`: poll for the answer
- `GET .../messages/{mid}/query-result/{attachment_id}`: get the query result

### Authentication on serverless

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
host = w.config.host.rstrip("/")
headers = {**w.config.authenticate(), "Content-Type": "application/json"}
```

Don't use `w.config.token` (it's `None` on serverless).

### `serialized_space` (version 2)

`serialized_space` is a **JSON string** in the POST/PATCH body:

```json
{
  "version": 2,
  "config": {"sample_questions": [{"id": "<hex>", "question": ["..."]}]},
  "data_sources": {
    "tables": [{"identifier": "catalog.schema.table", "column_configs": [...]}],
    "metric_views": [{"identifier": "catalog.schema.mv_name", "description": ["..."]}]
  },
  "instructions": {
    "text_instructions": [{"id": "<hex>", "content": ["line 1\n", "line 2\n"]}],
    "example_question_sqls": [{"id": "<hex>", "question": ["..."], "sql": ["SELECT ..."], "parameters": [], "usage_guidance": []}],
    "join_specs": [...],
    "sql_snippets": {"measures": [...], "filters": [...], "expressions": [...]}
  },
  "benchmarks": {"questions": [...]}
}
```

**Critical rules:**
- All `id` values are **32-character lowercase hex** (`uuid.uuid4().hex`).
- Every array with ids must be **sorted by `id`**; tables sorted by `identifier`. Unsorted arrays cause
  `INVALID_PARAMETER_VALUE`.
- `question`, `sql` and `content` are **arrays of strings**.
- At most 1 `text_instructions` item; preserve its `id` when updating.
- Always set `"version": 2`.

### Updating safely (GET-merge-PATCH)

1. GET with `include_serialized_space=true`
2. Modify only the section you need
3. Set `version = 2`, keep arrays sorted
4. PATCH with `json.dumps(config)`

### Idempotency

List agents first and PATCH the one with the same title instead of creating a duplicate. In a shared workshop
workspace, include the participant's schema in the title so agents don't collide.

### UI links

The UI uses `/genie/rooms/<space_id>` (the API uses `/genie/spaces/`). Azure workspaces need `?o=<workspace_id>`.

### Common errors

| Error | Cause | Fix |
|---|---|---|
| 401 "Credential was not sent" | `w.config.token` on serverless | use `w.config.authenticate()` |
| 400 `INVALID_PARAMETER_VALUE` | arrays not sorted by `id` | sort before POST/PATCH |
| 400 "unknown field" | flat fields in the POST body | put everything inside `serialized_space` |
| `PERMISSION_DENIED` on a table | no `SELECT` on the shared schema | ask the instructor for access |
