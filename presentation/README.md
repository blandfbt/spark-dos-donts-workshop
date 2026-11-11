# Presentations

Two talks go with the workshop. Both are single self-contained HTML files (fonts, logos and diagrams embedded) with a
matching PDF, built from Python sources that share one style kit.

| deck | length | what it covers |
|---|---|---|
| `spark_at_scale.html` / `.pdf` | 19 slides, 15–20 min | *Spark at scale: Do's & Don'ts.* How Spark runs code at scale (driver and executors, lazy plans, the optimizer, shuffles, joins, data layout, what serverless handles for you), the five categories of do's and don'ts with the timings measured in the workshop, then the workshop and the Genie Code challenge. |
| `lakeflow_data_engineering.html` / `.pdf` | 33 slides, 30–40 min | *Data engineering with Lakeflow.* The Databricks data engineering toolkit end to end: Lakeflow Connect, Auto Loader and Zerobus Ingest; Spark Declarative Pipelines (streaming tables, materialized views, expectations, AUTO CDC, incremental and real-time mode) and the Pipelines Editor; Lakeflow Jobs (triggers, control flow, backfills, repair); Lakeflow Designer; Genie Code and Genie ZeroOps; governance, data quality monitoring, cost, bundles and migration; "when to use what", a reference architecture, and how each piece shows up in the workshop notebooks (including `notebooks/jobs_notebooks`, the lab as a declarative pipeline). Product statuses are as of November 2026. |

Suggested order: *Spark at scale* before the lab and the do's and don'ts, *Lakeflow* before `notebooks/jobs_notebooks`
and the Genie notebooks. The Lakeflow deck works on its own too.

| file | what it is |
|---|---|
| `src/build_deck.py` | source of the *Spark at scale* slides, plus the shared style kit (CSS, viewer, SVG helpers, slide templates) |
| `src/build_lakeflow_deck.py` | source of the *Lakeflow* slides; imports the kit from `build_deck.py` |
| `src/assets/` | DM Sans / DM Mono fonts and the Databricks logos used by both builds |
| `export_pdf.sh` | renders an HTML deck to a PDF with headless Chrome/Chromium/Edge |

## Presenting

Open the HTML file. Use **← / →** (or click) to move between slides, **N** to show speaker notes, and **F** for full
screen. A slide number in the URL (`#7`) jumps straight to that slide. Every slide has speaker notes.

## Rebuild and export

```bash
python3 presentation/src/build_deck.py               # -> presentation/spark_at_scale.html
python3 presentation/src/build_lakeflow_deck.py      # -> presentation/lakeflow_data_engineering.html
./presentation/export_pdf.sh                          # -> presentation/spark_at_scale.pdf
./presentation/export_pdf.sh presentation/lakeflow_data_engineering.html   # -> ...lakeflow_data_engineering.pdf
```

`export_pdf.sh` finds Chrome, Chromium or Edge automatically. Set `CHROME=/path/to/browser` to choose one.
Styling follows the Databricks corporate slide template (navy title and section slides, oat content slides, DM Sans,
the ©2026 footer).

**Before presenting the Lakeflow deck,** recheck the status chips (GA / Beta / Preview) against the
[release notes](https://docs.databricks.com/aws/en/release-notes/product/): preview features move quickly. They're all
defined in `build_lakeflow_deck.py` (search for `st(`), and the "Status at a glance" slide summarizes them.
