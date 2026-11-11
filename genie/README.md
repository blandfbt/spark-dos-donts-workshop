# Genie agents on the Apex Motorsports Parts gold layer

The Genie part of the workshop teaches you to **build, curate, evaluate and operate** a Databricks Genie agent on the
gold tables from the bronze-to-gold lab, and to prove with benchmarks that curation is what earns trust. You build
**three agents on the same data**:

- **Baseline** (03): tables only, the "before"
- **Metric View** (03b): governed metric views with pinned joins and KPI formulas
- **Knowledge Store** (04): column configs, synonyms, joins, measures, filters and example SQL: the "after" and the
  primary agent

Adapted from the [genie-spaces-workshop](https://github.com/blandfbt/genie-spaces-workshop) (manufacturing data),
retargeted to this repo's data. Its security notebook (09) is not included.

## Data

The agents read four tables that the instructor prebuilds in the shared, **read-only** schema (default
`dbx_workshop_dev.shared`) by running lab 01 auto-solved:

| table | grain |
|---|---|
| `lab_gold_daily_dealer_sales_fact` | day × dealer, December 2025: orders, units, net revenue, margin |
| `lab_gold_category_region_fact` | region × part category: orders, units, net revenue, margin, margin % |
| `lab_silver_dealers_dim` | dealer: name, region, state, tier |
| `lab_silver_parts_dim` | part: name, category, list price, unit cost |

Everything you create goes to **your** schema (`USER_SCHEMA` in `CONFIG`): the metric views `genie_mv_dealer_sales` and
`genie_mv_category_sales`, the `genie_workshop_config` table (your agent IDs) and `genie_benchmark_runs`. Agent titles include
your schema name, for example `Apex Motorsports Parts - Knowledge Store (jane_doe)`, so agents don't collide in a
shared workspace. The same goes for the Genie Code agent (07) and the CI/CD demo copy (11); `genie_helpers` prints all
five names when it runs.

## Run order

Set `USER_SCHEMA` in `CONFIG` (top of the repo) first. Every notebook starts with `%run ../CONFIG` and
`%run ./genie_helpers`.

| # | notebook | what you do |
|---|---|---|
| 03 | `03_create_genie_spaces` | create the tables-only baseline agent |
| 03b | `03b_metric_views` | create two metric views, time them against raw SQL, and build an agent on them |
| 04 | `04_knowledge_store` | curate the primary agent programmatically |
| 05 | `05_genie_evals_benchmarks` | push benchmarks to all three agents (12 table-based to Baseline + Knowledge Store, 5 metric-view to Metric View), run them in the UI, fix failures, 4-question smoke test |
| 06 | `06_talk_with_data` | ask questions in the Genie UI and check them against reference SQL |
| 07 | `07_genie_code_skills` | install the skill in `skill/` and have Genie Code build an agent and a notebook |
| 08 | `08_compare_genie_spaces` | the same 4 hard questions on all three agents; saves results to `genie_benchmark_runs` |
| 10 | `10_monitoring_observability` | Monitoring tab, benchmark history, audit logs, query history |
| 11 | `11_cicd_genie_spaces` *(optional)* | export → remap → deploy an agent |

`genie_helpers` holds the shared settings (agent title prefix, warehouse, benchmark tolerance) and the REST
plumbing. `templates/apex_motorsports_genie_configured.json` is a reference agent definition; `skill/` is the
Genie Code skill used in 07.

## Prerequisites

- **Genie** (AI/BI) and **Genie Code** enabled in the workspace.
- **CAN USE** on a Pro or Serverless SQL warehouse (Genie runs its SQL there). Set `SQL_WAREHOUSE_ID` in
  `genie_helpers` to pin one; otherwise a running or serverless warehouse is picked.
- `USE CATALOG` on the workshop catalog, `USE SCHEMA` + `SELECT` on the shared schema, and full access to your own
  schema (the instructor grants these; `CREATE TABLE` there covers metric views).
- The instructor has run the shared prebuild, so the four tables above exist. `genie_helpers` stops with a clear
  message if they don't.
- *Optional, notebook 10 parts 3 to 4:* `SELECT` on `system.access.audit` and `system.query.history` (metastore-admin
  granted). Without it those cells print a permissions message; the rest of the notebook works.
