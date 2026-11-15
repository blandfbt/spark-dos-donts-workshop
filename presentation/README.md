# Presentations

Three talks go with the workshop. All are single self-contained HTML files (fonts, logos and diagrams embedded) with a
matching PDF, built from Python sources that share one style kit.

| deck | length | what it covers |
|---|---|---|
| `spark_at_scale.html` / `.pdf` | 19 slides, 15–20 min | *Spark at scale: Do's & Don'ts.* How Spark runs code at scale (driver and executors, lazy plans, the optimizer, shuffles, joins, data layout, what serverless handles for you), the five categories of do's and don'ts with the timings measured in the workshop, then the workshop and the Genie Code challenge. |
| `lakeflow_data_engineering.html` / `.pdf` | 33 slides, 30–40 min | *Data engineering with Lakeflow.* The Databricks data engineering toolkit end to end: Lakeflow Connect, Auto Loader and Zerobus Ingest; Spark Declarative Pipelines (streaming tables, materialized views, expectations, AUTO CDC, incremental and real-time mode) and the Pipelines Editor; Lakeflow Jobs (triggers, control flow, backfills, repair); Lakeflow Designer; Genie Code and Genie ZeroOps; governance, data quality monitoring, cost, bundles and migration; "when to use what", a reference architecture, and how each piece shows up in the workshop notebooks (including `notebooks/jobs_notebooks`, the lab as a declarative pipeline). Product statuses are as of November 2026. |
| `genie_agents_workshop.html` / `.pdf` | 42 slides, two days | *Genie Agents Workshop + Best Practices.* Day 1: what Genie is and how to build an agent (Section 1 · your first agent, Section 2 · what's new). Day 2: the curation deep dive (Section 3 · curating, Section 4 · benchmarks, monitoring and rollout). An HTML remake of the GM Genie workshop deck (Daria Krasavina, 2026-09-24), updated to November 2026: Genie Agents vs Genie Code vs Genie One, billing, pairing with dashboards, where Genie fits, data and metric-view best practices, the knowledge store (local metadata, prompt matching, joins, measures, fields, filters, suggestions, priority and limits), text and clarification instructions, benchmarks, monitoring, audit logs, rollout, Conversation API, what's new since September, Slack/Teams, mobile, Genie Workbench, docs, and the hands-on lab (`genie/01`–`08`). |

Suggested order: *Spark at scale* before the lab and the do's and don'ts, *Lakeflow* before `notebooks/jobs_notebooks`,
and *Genie Agents* before the `genie/` notebooks. The Lakeflow and Genie decks work on their own too.

| file | what it is |
|---|---|
| `src/build_deck.py` | source of the *Spark at scale* slides, plus the shared style kit (CSS, viewer, SVG helpers, slide templates) |
| `src/build_lakeflow_deck.py` | source of the *Lakeflow* slides; imports the kit from `build_deck.py` |
| `src/build_genie_deck.py` | source of the *Genie Agents* slides; imports the kit and the table / card / status helpers of `build_lakeflow_deck.py` |
| `src/assets/` | DM Sans / DM Mono fonts and the Databricks logos used by both builds |
| `export_pdf.sh` | renders an HTML deck to a PDF with headless Chrome/Chromium/Edge |

## Presenting

Open the HTML file. Use **← / →** (or click the left or right quarter of the screen; clicks in the middle do nothing) to move between slides, **N** to show speaker notes, and **F** for full
screen. A slide number in the URL (`#7`) jumps straight to that slide. Every slide has speaker notes.
In the Genie deck, the section bar at the bottom of the screen jumps to any section and highlights the current one
(it's hidden in the PDF).

## Rebuild and export

```bash
python3 presentation/src/build_deck.py               # -> presentation/spark_at_scale.html
python3 presentation/src/build_lakeflow_deck.py      # -> presentation/lakeflow_data_engineering.html
python3 presentation/src/build_genie_deck.py         # -> presentation/genie_agents_workshop.html
./presentation/export_pdf.sh                          # -> presentation/spark_at_scale.pdf
./presentation/export_pdf.sh presentation/lakeflow_data_engineering.html   # -> ...lakeflow_data_engineering.pdf
./presentation/export_pdf.sh presentation/genie_agents_workshop.html       # -> ...genie_agents_workshop.pdf
```

`export_pdf.sh` finds Chrome, Chromium or Edge automatically. Set `CHROME=/path/to/browser` to choose one.
Styling follows the Databricks corporate slide template (navy title and section slides, oat content slides, DM Sans,
the ©2026 footer).

**Before presenting the Lakeflow deck,** recheck the status chips (GA / Beta / Preview) against the
[release notes](https://docs.databricks.com/aws/en/release-notes/product/): preview features move quickly. They're all
defined in `build_lakeflow_deck.py` (search for `st(`), and the "Status at a glance" slide summarizes them.

**Before presenting the Genie deck,** recheck the status chips and the billing slide against the
[AI/BI and Genie One release notes](https://docs.databricks.com/aws/en/ai-bi/release-notes/2026) and the
[Genie cost docs](https://docs.databricks.com/aws/en/genie/monitor-cost). What changed from the original GM deck:

| slide(s) | original | now | source |
|---|---|---|---|
| Title, notes, footer | "Genie Agents (Spaces)", notes for other presenters, ©2024 | Genie Agents; notes rewritten for Taylor and Brien; ©2026 | — |
| Genie Agents vs Code vs One | three cards | adds renames (spaces → Agents Jul 2026; Assistant → Genie Code; Research Agent → Agent mode) | docs: product name changes |
| Billing | 150 DBUs + 25% off; Genie One/Agents free | same, plus: free applies to human users only (service principals billed), allowance resets monthly, SQL warehouse compute billed separately | docs: Genie costs; Aug 2026 release notes |
| Pair with dashboards | "NEW! top drivers" | Ask Genie GA; explain-this-change via Agent mode; Dashboard Insights Beta | AI/BI release notes 2026 |
| Focused topic | 3–7 tables | aim for ≤ 5; hard limit 50 tables/views/metric views | docs: best practices |
| Example SQL | example SQL, suggested queries | adds parameters, usage guidance, trusted assets | docs: tune quality |
| Knowledge store slides | "NEW!" badges; suggested joins "in the future"; SQL primitives "COMING" | all shipped: prompt matching, join cardinality, suggested joins, measures / fields / filters, knowledge mining from 👍 and downloads; new priority-and-limits slide (200 snippets, 100 instructions) | docs: tune quality |
| General instructions | do/don't | adds the summaries heading; "SQL primitives" → SQL expressions | docs: best practices |
| Benchmarks | what/why; star legend | 500 questions, Chat vs Agent mode (LLM judge + evaluation note), **Run all benchmarks**, parallel runs (Nov 2026), Good / Manual review needed / Bad, one-week result retention | docs: test and monitor; Nov 5 release notes |
| Monitoring, audit logs | monitoring page; alerts | weekly digest, Analyze agent usage, request review, reviewable conversations, custom claim; exact audit `action_name`s | docs: monitor; AI/BI audit events |
| Conversation API | poll every 5–10 s, backoff after 2 min | poll every 1–5 s, back off to 60 s, stop at 10 min; handle 429; Agent mode streams (SSE) | docs: Genie Agents API (updated Nov 5) |
| What's new since September | — | new slide: Ontology GA, Slack/Teams GA, file uploads GA, files in volumes (Preview), MCP connectors (Beta), Flash (Beta), Genie One MCP server GA | AI/BI + product release notes; Ontology GA blog |
| Slack / Teams, mobile | Public Preview | Slack and Teams GA (Nov 9); mobile still Public Preview | Nov 2026 release notes; mobile docs |
| Desktop, Ontology Manager | — | new slide: Genie One desktop app (Beta, macOS and Windows); Ontology Manager (coming soon in Beta) on the what's-new slide | Genie One desktop docs (Nov 10); Genie Ontology GA blog (Nov 11) |
| Monitoring at scale, Genie Code analysis | — | Monitoring slide adds system tables (`system.access.audit` with `service_name = 'aibiGenie'` / `request_params.space_id`, `system.query.history` with `query_source.genie_space_id`) and calls out **Analyze Agent Usage** (Genie Code); benchmark results slide adds **Analyze with Genie** (Genie Code on a run) | Genie Agents monitor docs; audit-log and query-history references |
| Genie Workbench | link | what it does (create, IQ scan, auto-optimize) | GitHub README |
| Hands-on lab | github.com/dariakrasavina/genie-spaces-workshop | this repo's `genie/01`–`08` on the Apex Motorsports lab tables | — |
