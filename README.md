# Spark Do's & Don'ts workshop

A hands-on workshop in three parts:

1. **Bronze-to-gold lab** (`01_bronze_to_gold_lab`, ~45 min). Participants take messy raw JSON and CSV files
   through bronze, silver and gold tables, answer questions in SQL and publish an AI/BI dashboard. Every
   step is a 📘 worked example followed by a 🧑‍💻 *your turn* cell (with a 🧞 Genie Code prompt) and a ✅ check.
   Python and SQL cells are mixed throughout.
2. **Spark Do's & Don'ts** (`02_spark_dos_and_donts`). It runs the most common Spark anti-patterns
**side by side** with the fix, on realistic data, using serverless compute. Each section has a
📖 *Why* cell (with a diagram), a 🚫 *Don't* cell that really hurts (slow, memory-hungry or wrong), and a
✅ *Do* cell that gives the same answer properly. Every run is timed.
The workshop ends with a **Genie Code challenge**: participants ask Genie Code to optimize a job that
contains many of the anti-patterns at once.
3. **Genie** (`genie/`). Build, curate, benchmark and operate Genie agents on the lab's gold tables: a baseline
   agent, a metric view, a Knowledge Store agent, benchmarks, a three-way comparison, Genie Code skills,
   monitoring and CI/CD. See [`genie/README.md`](genie/README.md).

The data belongs to **Apex Motorsports Parts**, a fictional company: a parts-sales star schema, a
300-column test-telemetry table, 1 Hz car telemetry with session windows, and raw CSV/Parquet files in a
Unity Catalog volume.

**One shared dataset, one schema per participant.** The instructor generates all source data once into
`dbx_workshop_dev.shared` (read-only for participants). Each participant gets their own schema,
`dbx_workshop_dev.<firstname_lastname>`, and everything they create (lab tables, scratch tables, checkpoints,
metric views, Genie config) goes there. The single place these names are set is [`CONFIG.py`](CONFIG.py).

```
CONFIG.py                                    ✏️ CATALOG, SOURCE_SCHEMA, USER_SCHEMA: the only file participants edit
notebooks/01_bronze_to_gold_lab.py           ← part 1: the hands-on lab
notebooks/02_spark_dos_and_donts.py          ← part 2: the do's and don'ts
notebooks/03_genie_code_challenge_solution.py reference solution for the challenge in part 2
notebooks/workshop_helpers.py                shared DataFrames over the source tables, timing helpers (%run)
notebooks/lab_helpers.py                     lab checks, reference solutions, reveal/catch_up, dashboard builders
notebooks/images/                            diagrams used in the markdown cells
genie/                                       ← part 3: Genie agents on the shared gold tables (see genie/README.md)
instructor_setup/                            🧑‍🏫 instructor only: generate shared data, prebuild gold, create participant schemas
databricks.yml, resources/jobs.yml           instructor bundle: setup job + optional dry-run job (serverless)
assets/src/make_graphics.py                  regenerates the diagrams (SVG -> PNG, needs rsvg-convert)
presentation/                                15-20 min slide deck (single HTML + PDF) that goes with the workshop
```

## What's covered

### Part 1 · Bronze-to-gold lab

| step | 📘 example | 🧑‍💻 your turn |
|---|---|---|
| 1 · Bronze | profile the raw files; Auto Loader ingests the JSON orders as strings with lineage columns (Python) | land the dealer CSV in bronze (Python) |
| 2 · Silver | type, standardize, de-duplicate with `QUALIFY`, quarantine rejects (SQL); Delta CHECK constraints catch a bad write (Python + SQL) | clean and de-duplicate the dealers (SQL) |
| 3 · Gold | daily sales per dealer (SQL) | margin by region × category (SQL) |
| 4 · SQL | top dealers; week-over-week change with `LAG` | top 3 dealers per region; top 5 days by online share |
| 5 · Dashboard | publish an AI/BI dashboard from code: counters, line, bar, table (Python) | add a chart of your gold table (code, or the dashboard assistant) |

`check("<exercise>")` verifies each result. When someone is stuck, `reveal("<exercise>")` prints a solution
and `catch_up("<exercise>")` builds it so they can keep going. Examples that depend on an exercise build
it automatically if it's missing.

### Part 2 · Spark Do's & Don'ts

| # | section | Don't → Do |
|---|---|---|
| 1 | Pulling data to the driver | `collect()` + Python loop → aggregate in Spark · `toPandas()` a 300-column table → select/aggregate first · `display()` in a job → no actions in prod paths |
| 2 | Repeated actions | `count()`/`display()` after every step → one write + `DESCRIBE HISTORY` metrics (or `cache()`) · `count() > 0` → `isEmpty()` |
| 3 | Driver-side loops | one query per dealer → one `groupBy` · one `INSERT` per row → one batch append / `MERGE` |
| 4 | Python UDFs | Python UDF → pandas UDF → built-in functions |
| 5 | Plan bloat | `withColumn` loop over 300 columns → `withColumns` · read+count+union per folder → one read |
| 6 | Ingesting files | `inferSchema` → explicit schema · 4,000 tiny files → compacted · full reload → Auto Loader |
| 7 | Joins | `BETWEEN` join → `range_join` hint · join on SCD2 history (inflated revenue) → `is_current` / point-in-time · `isin(<collected list>)` → semi join |
| 8 | Window functions | `Window.orderBy` with no partition → `partitionBy(customer_id)` |
| 9 | Writing data | `partitionBy(order_date, dealer_id)` → liquid clustering · `coalesce(1)` → parallel write |
| 10 | Cluster-era habits | `spark.conf` tuning, `sparkContext`, RDDs (rejected on serverless) → DataFrame APIs, hints |
| 11 | 🧞 Genie Code challenge | optimize `build_dealer_scorecard_slow`; a check cell validates the result |
| 12 | Cheat sheet | every Don't and its Do on one page |

**How the Don'ts stay short and safe.** Each Do runs the full workload. Most Don'ts run a slice of the
same work (for example 4% of the orders, or 50 of the 500 dealers), so they finish in roughly 10–60 s.
The cell then prints the projected full-size time and, where it matters, the driver memory the full run
would need compared with the driver's actual RAM. That's how `collect()` shows "≈ 52 GB on a 16 GB
driver → out of memory" without crashing anything. A watchdog cancels any Spark work still running after
`dont_timeout_seconds` (default 120 s) as a safety net.

**Restart-safe.** Every section starts with a `%run ../CONFIG` + `%run ./workshop_helpers` resume point, so after
a detach or restart you can continue from any section without rerunning the ones before it. Each *Why* cell ends
with links to the Spark and Databricks documentation behind the advice.

## Prerequisites

* A workspace with Unity Catalog, serverless notebooks and jobs, Genie and Genie Code (Databricks Assistant) enabled.
* The catalog `dbx_workshop_dev` (change `CATALOG` in `CONFIG.py` to use another).
* A SQL warehouse (serverless recommended) for the lab's dashboard and the Genie spaces; participants need **CAN USE** on it.
* About 10 GB of storage for the shared data at the default size, plus about 2 GB per participant.
* Instructor: Databricks CLI ≥ 0.250 (`databricks -v`) to deploy the setup bundle, and ownership of (or
  `CREATE SCHEMA` + `MANAGE`/grant rights on) the catalog.

## Who can do what

| principal | `dbx_workshop_dev` | `dbx_workshop_dev.shared` | `dbx_workshop_dev.<firstname_lastname>` |
|---|---|---|---|
| instructor | owner | writes everything (setup) | creates it, grants it |
| participant | `USE CATALOG` | `USE SCHEMA`, `SELECT`, `READ VOLUME` (read-only) | `ALL PRIVILEGES` (their own only) |

Participants never need `CREATE SCHEMA`. `CONFIG.py` refuses to run with an empty `USER_SCHEMA` or with
`USER_SCHEMA = "shared"`.

## Instructor: before the workshop

```bash
# 1. authenticate once (creates a CLI profile)
databricks auth login --host https://<your-workspace-url> --profile <profile>

# 2. deploy the instructor bundle (catalog/source schema default to dbx_workshop_dev / shared)
databricks bundle deploy -t dev -p <profile>

# 3. generate the shared data and prebuild the lab's gold tables into dbx_workshop_dev.shared (~10 min)
databricks bundle run -t dev -p <profile> workshop_setup
```

The setup job runs `instructor_setup/00_generate_workshop_data` (star schema, telemetry, raw files) and then
`instructor_setup/01_prebuild_shared_gold`, which runs the lab auto-solved into `shared` so the Genie notebooks
have `endtoend_gold_*` and `endtoend_silver_*_dim` tables to build on. You can also run both notebooks by hand.

4. **Create the participant schemas:** open `instructor_setup/02_create_participant_schemas`, paste the
   participants' emails into `PARTICIPANTS` and run it. It creates `dbx_workshop_dev.<firstname_lastname>` for each
   (from `jane.doe@company.com` → `jane_doe`), grants `ALL PRIVILEGES` on it, grants read-only access on `shared`,
   and prints the `USER_SCHEMA = "..."` line each person needs. Give participants **CAN USE** on the SQL warehouse.
5. **Optional rehearsal:** create a schema for yourself with step 4, then
   `databricks bundle run -t dev -p <profile> workshop_dry_run --params user_schema=<your_schema>`. It runs the
   lab auto-solved, every Don't/Do and the challenge solution against `shared`, writing only to your schema.

**Smaller/faster:** `databricks bundle run ... workshop_setup --params fact_rows=20000000` for a quick smoke test.

## Participants: during the workshop

1. In the workspace, **Workspace → your home folder → Create → Git folder**, and clone this repository.
2. Open **`CONFIG`** at the top of the repo and set `USER_SCHEMA = "<firstname_lastname>"` (your instructor will
   confirm the name). Leave `CATALOG` and `SOURCE_SCHEMA` as they are.
3. Open **`notebooks/01_bronze_to_gold_lab`**, attach **serverless** compute (environment version **5** or later in the
   *Environment* side panel) and run it top to bottom. Leave `auto_solve` at `false`.
4. Continue with **`notebooks/02_spark_dos_and_donts`**, then the **`genie/`** notebooks.

Ignore `instructor_setup/`: it's what the instructor ran beforehand.

## Configuration

`CONFIG.py` (participants and instructor):

| setting | default | meaning |
|---|---|---|
| `CATALOG` | `dbx_workshop_dev` | existing UC catalog |
| `SOURCE_SCHEMA` | `shared` | read-only source tables and the `raw_files` volume, generated by the instructor |
| `USER_SCHEMA` | *(empty, required)* | the participant's own schema; gets a `scratch_files` volume for checkpoints and landing files |

Instructor bundle variables (`--var=...`), passed to the notebooks as job parameters:

| variable | default | meaning |
|---|---|---|
| `catalog` / `source_schema` | `dbx_workshop_dev` / `shared` | override CONFIG for the jobs |
| `user_schema` | *(empty)* | target schema for `workshop_dry_run` |
| `fact_rows` | `100000000` | size of `fact_orders` (the other tables are fixed size) |
| `dont_timeout_seconds` | `120` | watchdog limit per Don't |
| `workshop_tag` | `spark_dos_donts` | value of the `workshop_name` tag on jobs and Unity Catalog objects |
| `warehouse_id` | *(empty)* | SQL warehouse for the lab dashboard; empty = first serverless warehouse found |
| `environment_version` | `5` | serverless environment; ≥ 5 is needed for `df.cache()` |
| `performance_target` | `PERFORMANCE_OPTIMIZED` | serverless job performance mode |

## Finding workshop assets

Everything the workshop creates is tagged **`workshop_name = spark_dos_donts`**: the bundle jobs (through
`presets.tags`), the `shared` schema, its volume and tables, and each participant's schema, volume and tables.

```sql
SELECT table_schema, table_name FROM dbx_workshop_dev.information_schema.table_tags
WHERE tag_name = 'workshop_name' AND tag_value = 'spark_dos_donts';
```

Tagging needs the `APPLY TAG` privilege (included in `ALL PRIVILEGES` on a participant's own schema). Without it,
the notebooks print a note and carry on. The lab's AI/BI dashboard can't be tagged; it's named
`Apex Motorsports Parts - December sales (<user_schema>)` in each participant's home folder.

## Clean up

* A participant's own tables: `reset_lab()` in notebook 01 and the last cell of notebook 02 (`CLEAN_UP = True`) drop the
  `endtoend_*` / `scratch_*` tables in their schema; `genie/README.md` lists what the Genie notebooks create.
* After the workshop (instructor): `DROP SCHEMA dbx_workshop_dev.<firstname_lastname> CASCADE` per participant,
  `DROP SCHEMA dbx_workshop_dev.shared CASCADE` for the source data, and `databricks bundle destroy -t dev -p <profile>`.

## Notes

* All data is synthetic and generated on the executors from `spark.range` with seeded random functions.
  Reruns of the setup job replace everything they wrote.
* Timings depend on serverless scaling and caching. The ratios between Don't and Do are what matter.
* In notebook 02, section 6c seeds each participant's landing zone with July–December 2025 from the shared order
  export the first time it runs (under a minute), because the shared volume is read-only.
* Regenerate the diagrams after editing them: `python3 assets/src/make_graphics.py`.
