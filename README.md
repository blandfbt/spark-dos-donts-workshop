# Spark Do's & Don'ts workshop

A hands-on workshop, deployable as a Databricks Asset Bundle. It runs the most common Spark anti-patterns
**side by side** with the fix, on realistic data, using serverless compute. Each section has a
📖 *Why* cell (with a diagram), a 🚫 *Don't* cell that really hurts (slow, memory-hungry or wrong), and a
✅ *Do* cell that gives the same answer properly. Every run is timed and collected into a scoreboard.
The workshop ends with a **Genie Code challenge**: participants ask Genie Code to optimize a job that
contains many of the anti-patterns at once.

The data belongs to **Apex Motorsports Parts**, a fictional company: a parts-sales star schema, a
300-column test-telemetry table, 1 Hz car telemetry with session windows, and raw CSV/Parquet files in a
Unity Catalog volume.

```
databricks.yml                               bundle, variables (catalog, schema, ...), targets
resources/jobs.yml                           setup job + end-to-end workshop job (serverless)
notebooks/00_generate_workshop_data.py       generates all tables and raw files (setup job)
notebooks/01_spark_dos_and_donts.py          ← the workshop
notebooks/02_genie_code_challenge_solution.py reference solution for the challenge
notebooks/config.py                          widgets, table names, timing/scoreboard helpers (%run)
notebooks/images/                            diagrams used in the markdown cells
assets/src/make_graphics.py                  regenerates the diagrams (SVG -> PNG, needs rsvg-convert)
presentation/                                15-20 min slide deck (single HTML + PDF) that goes with the workshop
```

## What's covered

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
| 12 | Scoreboard | Don't vs Do timings and speedups, saved to `workshop_scoreboard` |

**How the Don'ts stay short and safe.** Each Do runs the full workload. Most Don'ts run a slice of the
same work (for example 4% of the orders, or 50 of the 500 dealers), so they finish in roughly 10–60 s.
The cell then prints the projected full-size time and, where it matters, the driver memory the full run
would need compared with the driver's actual RAM. That's how `collect()` shows "≈ 52 GB on a 16 GB
driver → out of memory" without crashing anything. A watchdog cancels any Spark work still running after
`dont_timeout_seconds` (default 120 s) as a safety net.

**Restart-safe.** Every result is appended to the `workshop_scoreboard` table the moment it's measured.
Every section starts with a `%run ./config` resume point, so after a detach or restart you can
continue from any section without rerunning the ones before it. Each *Why* cell ends with links to the
Spark and Databricks documentation behind the advice.

## Prerequisites

* Databricks CLI ≥ 0.250 (`databricks -v`).
* A workspace with Unity Catalog, serverless jobs and serverless notebooks, and Genie Code (Databricks Assistant) enabled for section 11.
* An existing catalog on which you have `USE CATALOG` and `CREATE SCHEMA` (or an existing schema with `CREATE TABLE` and `CREATE VOLUME`).
* About 10 GB of storage for the generated data at the default size.

## Deploy into your workspace

You choose three things: the **workspace**, the **catalog** and the **schema**.

```bash
# 1. authenticate once (creates a CLI profile)
databricks auth login --host https://<your-workspace-url> --profile <profile>

# 2. deploy: pick the catalog and schema at deploy time
databricks bundle deploy -t dev -p <profile> \
  --var="catalog=<your_catalog>" --var="schema=spark_dos_donts"

# 3. generate the data (one run, ~5 min at the default 100M order lines)
databricks bundle run -t dev -p <profile> \
  --var="catalog=<your_catalog>" --var="schema=spark_dos_donts" spark_dos_donts_setup
```

Instead of passing `--var` and `-p` every time, you can set them once in `databricks.yml` under
`targets.dev` (`workspace.host` and `variables.catalog` / `variables.schema`), or export
`BUNDLE_VAR_catalog` / `BUNDLE_VAR_schema`.

**Smaller/faster:** add `--var="fact_rows=20000000"` for a quick smoke test. The Don'ts still lose, but by less.

## Run the workshop

1. In the workspace, open
   `/Workspace/Users/<you>/.bundle/spark_dos_donts_workshop/dev/files/notebooks/01_spark_dos_and_donts`.
2. Attach **serverless** compute. In the *Environment* side panel, choose environment version **5** or later.
3. Leave the `catalog`/`schema` widgets empty: the setup job wrote `_workshop_config.json` next to the
   notebooks, and `config.py` picks it up. Or fill the widgets in by hand.
4. Run the cells top to bottom, section by section.

**Instructor dry run / pre-warm:** `databricks bundle run -t dev -p <profile> spark_dos_donts_workshop` runs
notebook 01 and the challenge solution end to end (about 20 minutes, measured) and writes the timings to `workshop_scoreboard`.

### Several participants in one workspace

* **Everyone deploys their own copy** (simplest): each participant runs the `dev` target with their own
  `schema` (for example `--var="schema=sdd_<name>"`). Development mode keeps each person's bundle in their
  own folder and prefixes job names with `[dev <user>]`.
* **One shared dataset:** the instructor deploys once with `-t shared` and runs the setup job.
  Participants clone the notebooks into their own folder and set the widgets to the shared catalog/schema.
  The scratch tables the notebook writes are then shared too, so give each participant their own schema
  if they will run section 9 (writes) at the same time.

## Configuration

| variable | default | meaning |
|---|---|---|
| `catalog` | *(required)* | existing UC catalog |
| `schema` | `spark_dos_donts` | schema for all tables and the `raw_files` volume (created if missing) |
| `fact_rows` | `100000000` | size of `fact_orders` (the other tables are fixed size) |
| `dont_timeout_seconds` | `120` | watchdog limit per Don't (also a notebook widget) |
| `environment_version` | `5` | serverless environment; ≥ 5 is needed for `df.cache()` |
| `performance_target` | `PERFORMANCE_OPTIMIZED` | serverless job performance mode |

## Clean up

```bash
databricks bundle destroy -t dev -p <profile>        # removes the jobs and the bundle files
```

The generated data stays until you drop it: `DROP SCHEMA <catalog>.<schema> CASCADE` (this also drops the
volume). The last cell of notebook 01 can drop just the `scratch_*` tables the workshop wrote.

## Notes

* All data is synthetic and generated on the executors from `spark.range` with seeded random functions.
  Reruns of the setup job replace everything they wrote.
* Timings depend on serverless scaling and caching. The ratios between Don't and Do are what matter.
* Regenerate the diagrams after editing them: `python3 assets/src/make_graphics.py`.
