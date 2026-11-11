"""Build the "Data engineering with Lakeflow" presentation as one self-contained HTML file.

    python3 presentation/src/build_lakeflow_deck.py      # writes presentation/lakeflow_data_engineering.html

A 30-40 minute tour of the Databricks data engineering toolkit (Lakeflow Connect, Zerobus Ingest, Auto Loader,
Spark Declarative Pipelines, the Pipelines Editor, Lakeflow Jobs, Lakeflow Designer, Genie Code / ZeroOps, and
the governance and operations around them). Reuses the styling, viewer and SVG kit of build_deck.py so both decks
look the same. Product statuses are as of November 2026 (docs.databricks.com release notes and databricks.com blog).
"""

import html
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_deck as kit  # noqa: E402  (shared styling, logos, SVG kit, slide templates)
from build_deck import (BLUE, BRICK, CORAL, GREEN, LAVA, LINE, MUTED, NAVY, OAT2, SALMON, SLATE, TEAL,  # noqa: E402
                        YELLOW, Svg, bullets, closing_slide, content, font_faces, section_slide, title_slide)

OUT = HERE.parent / "lakeflow_data_engineering.html"
AS_OF = "as of Nov 2026"

EXTRA_CSS = """
.tbl{width:100%;border-collapse:separate;border-spacing:0;font-size:29px;line-height:1.3;margin-top:6px}
.tbl th{text-align:left;font-size:21px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);font-weight:700;
        padding:0 18px 12px;border-bottom:2px solid var(--line)}
.tbl td{padding:15px 18px;border-bottom:1px solid var(--line);vertical-align:top}
.tbl td:first-child{font-weight:700;white-space:nowrap}
.tbl.compact{font-size:26px}.tbl.compact td{padding:13px 18px}
.st{display:inline-block;font-size:18px;font-weight:700;letter-spacing:.5px;padding:3px 12px;border-radius:999px;
    vertical-align:middle;margin-left:10px;white-space:nowrap;color:#fff}
.st.ga{background:#00A972}.st.pp{background:#2272B4}.st.beta{background:#C77C00}.st.prpr{background:#5F7281}
.st.ann{background:#98102A}
.asof{position:absolute;right:90px;bottom:-72px;font-size:19px;color:var(--muted)}
.cards{display:grid;gap:28px}
.cards.c3{grid-template-columns:repeat(3,1fr)}.cards.c2{grid-template-columns:repeat(2,1fr)}.cards.c4{grid-template-columns:repeat(4,1fr)}
.card{background:#fff;border:2px solid var(--line);border-radius:18px;padding:26px 30px}
.card h4{margin:0 0 12px;font-size:34px;color:var(--navy)}
.card p{margin:0;font-size:28px;line-height:1.38;color:#33464e}
.card ul{margin:12px 0 0;padding-left:28px}.card li{font-size:28px;line-height:1.34;margin-bottom:10px}
.card.accent{border-color:var(--teal)}.card.lava{border-color:var(--lava)}.card.green{border-color:var(--green)}
.codebox.lf{margin-top:0;font-size:22px;line-height:1.45;white-space:pre;padding:22px 28px}
.codebox .kw{color:#98102A;font-weight:500}.codebox .fn{color:#1B5162;font-weight:500}.codebox .str{color:#00875A}
.split{display:grid;grid-template-columns:1.05fr .95fr;gap:44px;align-items:start}
.split.wide-left{grid-template-columns:1.25fr .75fr}
.note-s{font-size:22px;color:var(--muted);margin-top:16px;font-style:italic}
ul.dash.sm li{font-size:28px;margin-bottom:12px}
"""


def st(kind, label=None):
    labels = {"ga": "GA", "pp": "Public Preview", "beta": "Beta", "prpr": "Private Preview", "ann": "Announced"}
    return f'<span class="st {kind}">{label or labels[kind]}</span>'


def table(headers, rows, cls=""):
    th = "".join(f"<th>{h}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="tbl {cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


def cards(items, cols=3):
    out = []
    for it in items:
        title, body, extra = it[0], it[1], (it[2] if len(it) > 2 else "")
        inner = bullets_card(body) if isinstance(body, list) else f"<p>{body}</p>"
        out.append(f'<div class="card {extra}"><h4>{title}</h4>{inner}</div>')
    return f'<div class="cards c{cols}">' + "".join(out) + "</div>"


def bullets_card(items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


KEYWORDS = ["CREATE OR REFRESH STREAMING TABLE", "CREATE OR REFRESH MATERIALIZED VIEW", "CREATE FLOW", "AUTO CDC INTO",
            "STORED AS SCD TYPE 1", "STORED AS SCD TYPE 2", "SEQUENCE BY", "KEYS", "CONSTRAINT", "EXPECT",
            "ON VIOLATION DROP ROW", "GROUP BY ALL", "AS SELECT", "FROM STREAM", "FROM", "JOIN", "USING", "SELECT",
            "from", "import", "def", "return"]
_TOKEN = re.compile(
    r'(?P<str>"[^"\n]*"|\'[^\'\n]*\')'
    r'|(?P<cm>(?:(?<=\s)|^)#[^\n]*|--[^\n]*)'
    r'|(?P<fn>@dp\.[a-z_]+|dp\.[a-z_]+(?=\())'
    r'|(?P<kw>\b(?:' + "|".join(re.escape(k) for k in sorted(KEYWORDS, key=len, reverse=True)) + r')\b)', re.M)


def code(src):
    """Small highlighter for the code boxes: strings, comments, dp.* calls and keywords, in one pass."""
    out, pos = [], 0
    for m in _TOKEN.finditer(src):
        out.append(html.escape(src[pos:m.start()]))
        cls = {"str": "str", "cm": "cm", "fn": "fn", "kw": "kw"}[m.lastgroup]
        out.append(f'<span class="{cls}">{html.escape(m.group(0))}</span>')
        pos = m.end()
    out.append(html.escape(src[pos:]))
    return f'<div class="codebox lf">{"".join(out)}</div>'


def with_asof(body):
    return f'<div class="asof">Status {AS_OF}</div>' + body


# --------------------------------------------------------------------------------------------- graphics

def g_fragmented():
    s = Svg(1720, 580)
    s.text(380, 34, "Stitched together", 30, LAVA, 700)
    s.text(1310, 34, "One platform", 30, GREEN, 700)
    tools = [("SaaS ingestion tool", 70), ("CDC tool", 150), ("Custom scripts", 230), ("Spark / Glue / EMR jobs", 310),
             ("Airflow", 390), ("Observability SaaS", 470)]
    for label, y in tools:
        s.box(60, y, 300, 62, label, None, "#FFF4F2", SALMON, NAVY, 21, 10)
    for label, y in [("Data quality tool", 150), ("Catalog / lineage", 310), ("Secrets / creds", 470)]:
        s.box(420, y, 290, 62, label, None, "#FFF4F2", SALMON, NAVY, 21, 10)
    for y in (180, 340):
        s.line(360, y, 420, y, SALMON, 2, False, "5 5")
        s.line(360, y + 80, 420, y - 0, SALMON, 2, False, "5 5")
    s.text(385, 568, "separate identity, lineage, monitoring and billing per tool", 20, MUTED, 400, "middle", italic=True)
    s.line(760, 280, 880, 280, MUTED, 3)
    # unified
    s.rect(900, 70, 800, 450, "#fff", TEAL, 18, 3)
    s.text(1300, 116, "Lakeflow", 30, TEAL, 700)
    cols = [("Ingest", "Connect · Auto Loader · Zerobus"), ("Transform", "Declarative Pipelines"),
            ("Orchestrate", "Lakeflow Jobs")]
    for i, (h, sub) in enumerate(cols):
        x = 930 + i * 255
        s.rect(x, 145, 235, 150, OAT2, LINE, 12)
        s.text(x + 117, 205, h, 28, NAVY, 700)
        for j, part in enumerate(sub.split(" · ")):
            s.text(x + 117, 240 + j * 22, part, 17, MUTED)
    s.box(930, 315, 740, 64, "Lakeflow Designer (no-code) · Genie Code / ZeroOps (agents)", None, "#EAF4F7", TEAL, TEAL, 21, 12)
    s.box(930, 395, 740, 64, "Unity Catalog: access · lineage · quality · audit", None, NAVY, NAVY, "#fff", 22, 12)
    s.box(930, 470, 740, 36, "Serverless compute · one bill in system tables", None, "#E3F4EC", GREEN, NAVY, 18, 10)
    return s.render()


def g_lakeflow_map():
    s = Svg(1720, 600)
    # sources
    s.text(110, 30, "Sources", 24, MUTED, 700)
    for i, lab in enumerate(["SaaS apps", "Databases", "Cloud files", "Event streams", "Apps & devices"]):
        s.box(0, 50 + i * 100, 220, 72, lab, None, "#fff", LINE, NAVY, 21, 10)
    # ingest
    s.rect(270, 40, 360, 490, "#fff", TEAL, 16, 3)
    s.text(450, 80, "INGEST", 22, TEAL, 700)
    s.box(295, 100, 310, 110, "Lakeflow Connect", "100+ managed connectors", OAT2, LINE, NAVY, 25)
    s.box(295, 225, 310, 110, "Auto Loader", "incremental files", OAT2, LINE, NAVY, 25)
    s.box(295, 350, 310, 110, "Zerobus Ingest", "push events, no bus", OAT2, LINE, NAVY, 25)
    s.text(450, 505, "or any Spark source (Kafka, Kinesis…)", 17, MUTED)
    # transform
    s.rect(670, 40, 420, 490, "#fff", TEAL, 16, 3)
    s.text(880, 80, "TRANSFORM", 22, TEAL, 700)
    s.rect(695, 100, 370, 170, OAT2, LINE, 12)
    s.text(880, 160, "Spark Declarative", 27, NAVY, 700)
    s.text(880, 196, "Pipelines", 27, NAVY, 700)
    s.text(880, 240, "streaming tables · MVs · AUTO CDC", 18, MUTED)
    s.box(695, 290, 370, 80, "Pipelines Editor", "multi-file IDE", "#EAF4F7", TEAL, TEAL, 23)
    s.box(695, 390, 370, 110, "Lakeflow Designer", "visual, no-code → SDP", "#FFF4F2", SALMON, BRICK, 24)
    # orchestrate
    s.rect(1130, 40, 330, 490, "#fff", TEAL, 16, 3)
    s.text(1295, 80, "ORCHESTRATE", 22, TEAL, 700)
    s.box(1155, 100, 280, 170, "Lakeflow Jobs", "triggers · control flow", OAT2, LINE, NAVY, 27)
    for i, lab in enumerate(["schedule", "file arrival", "table update", "continuous"]):
        s.text(1295, 305 + i * 40, lab, 20, MUTED)
    s.text(1295, 480, "+ backfills · repair runs", 19, MUTED)
    # consumers
    s.text(1600, 30, "Consumers", 24, MUTED, 700)
    for i, lab in enumerate(["BI & dashboards", "Genie agents", "ML & AI", "Apps / Lakebase", "Sharing"]):
        s.box(1500, 50 + i * 100, 220, 72, lab, None, "#fff", LINE, NAVY, 21, 10)
    for x1, x2 in [(220, 270), (630, 670), (1090, 1130), (1460, 1500)]:
        s.line(x1, 286, x2, 286, MUTED, 3)
    s.box(270, 545, 1190, 52, "Unity Catalog · serverless · Genie Code & ZeroOps across every step", None, NAVY, NAVY, "#fff", 22, 12)
    return s.render()


def g_ingest_decision():
    s = Svg(1720, 560)
    s.rect(0, 225, 300, 110, NAVY, NAVY, 12)
    s.text(150, 272, "Where does the", 26, "#fff", 700)
    s.text(150, 306, "data come from?", 26, "#fff", 700)
    rows = [
        ("A SaaS app or database", "Lakeflow Connect", "managed connector: auth, schema, incremental state handled", GREEN),
        ("Files landing in cloud storage", "Auto Loader", "streaming table on cloud_files / read_files; file events", BLUE),
        ("Your apps or devices emit events", "Zerobus Ingest", "push straight into a Delta table; no message bus to run", CORAL),
        ("An existing Kafka / Kinesis / Event Hubs", "Streaming source in SDP", "Structured Streaming; managed Kafka connector is Beta", SLATE),
    ]
    for i, (q, tool, why, c) in enumerate(rows):
        y = 20 + i * 135
        s.line(300, 280, 380, y + 52, MUTED, 2.5)
        s.box(380, y, 470, 104, q, None, "#fff", LINE, NAVY, 23, 12)
        s.line(850, y + 52, 920, y + 52, c, 3)
        s.rect(920, y, 790, 104, "#fff", c, 12, 3)
        s.text(950, y + 45, tool, 28, c, 700, "start")
        s.text(950, y + 82, why, 20, MUTED, 400, "start")
    return s.render()


def g_zerobus():
    s = Svg(1720, 330)
    s.text(0, 30, "Classic event path", 24, LAVA, 700, "start")
    xs = [(0, "Producers"), (290, "Kafka cluster"), (580, "Stream job"), (870, "Delta table")]
    for x, lab in xs:
        s.box(x, 50, 240, 80, lab, None, "#FFF4F2" if lab != "Delta table" else "#fff", SALMON if lab != "Delta table" else LINE, NAVY, 23)
    for x, _ in xs[:-1]:
        s.line(x + 240, 90, x + 290, 90, SALMON, 3)
    s.text(1140, 98, "a bus + a job to size, patch, monitor and secure", 21, MUTED, 400, "start", italic=True)
    s.text(0, 205, "Zerobus Ingest", 24, GREEN, 700, "start")
    s.box(0, 225, 240, 80, "Producers", None, "#E3F4EC", GREEN, NAVY, 23)
    s.box(290, 225, 530, 80, "Zerobus (serverless) · gRPC · REST · SDKs", None, "#E3F4EC", GREEN, NAVY, 21)
    s.box(870, 225, 240, 80, "Delta table", "UC-governed", "#fff", LINE, NAVY, 23)
    s.line(240, 265, 290, 265, GREEN, 3)
    s.line(820, 265, 870, 265, GREEN, 3)
    s.text(1140, 273, "seconds to the table, nothing in between", 21, GREEN, 500, "start")
    return s.render()


def g_declarative():
    s = Svg(1720, 470)
    s.text(380, 34, "Imperative: you write the how", 26, LAVA, 700)
    steps = ["read new files since checkpoint X", "parse + cast; route bad rows", "MERGE into silver by key, latest wins",
             "recompute gold for touched days", "order the jobs; retry; backfill"]
    for i, t in enumerate(steps):
        s.box(40, 60 + i * 78, 680, 62, t, None, "#FFF4F2", SALMON, NAVY, 22, 10)
    s.text(1290, 34, "Declarative: you write the what", 26, GREEN, 700)
    nodes = [(880, 110, "bronze_orders", "streaming table"), (1160, 110, "silver_orders", "AUTO CDC"),
             (1440, 110, "gold_daily_sales", "materialized view")]
    for x, y, a, b in nodes:
        s.box(x, y, 250, 110, a, b, "#E3F4EC", GREEN, NAVY, 23, 12, mono=True)
    s.line(1130, 165, 1160, 165, GREEN, 3)
    s.line(1410, 165, 1440, 165, GREEN, 3)
    s.rect(880, 270, 810, 170, "#fff", LINE, 14, 2)
    s.text(1285, 312, "The engine works out", 24, NAVY, 700)
    for i, t in enumerate(["dependency order and parallelism", "what is new since last run (incremental)",
                           "checkpoints, retries, schema evolution", "compute sizing (serverless)"]):
        s.text(910 + (i % 2) * 400, 360 + (i // 2) * 44, "✓ " + t, 21, MUTED, 400, "start")
    return s.render()


def g_pipeline_lab():
    s = Svg(1720, 470)
    s.box(0, 170, 250, 120, "raw_files/lab", "JSON + CSV (shared)", "#fff", LINE, NAVY, 23, 12, mono=True)
    s.box(320, 70, 340, 120, "bronze_orders", "ST · Auto Loader", "#FFF0E0", YELLOW, NAVY, 24, 12, mono=True)
    s.box(320, 280, 340, 120, "bronze_dealers", "MV · batch CSV", "#FFF0E0", YELLOW, NAVY, 24, 12, mono=True)
    s.box(740, 10, 360, 100, "silver_orders_valid", "ST · expectations", "#EEF2F4", SLATE, NAVY, 22, 12, mono=True)
    s.box(740, 130, 360, 100, "silver_orders", "AUTO CDC · latest wins", "#EEF2F4", SLATE, NAVY, 22, 12, mono=True)
    s.box(740, 250, 360, 90, "quarantine_orders", "ST · failed rules", "#FFF4F2", SALMON, BRICK, 22, 12, mono=True)
    s.box(740, 360, 360, 100, "silver_dealers / parts", "MVs", "#EEF2F4", SLATE, NAVY, 22, 12, mono=True)
    s.box(1190, 120, 340, 110, "gold_daily_sales", "materialized view", "#FFF6D6", YELLOW, NAVY, 24, 12, mono=True)
    s.box(1190, 290, 340, 110, "gold_category_region", "materialized view", "#FFF6D6", YELLOW, NAVY, 24, 12, mono=True)
    s.line(250, 210, 320, 130, MUTED, 2.5)
    s.line(250, 250, 320, 340, MUTED, 2.5)
    s.line(660, 120, 740, 60, MUTED, 2.5)
    s.line(660, 140, 740, 295, LAVA, 2.5, True, "6 5")
    s.line(920, 110, 920, 130, MUTED, 2.5)
    s.line(660, 340, 740, 410, MUTED, 2.5)
    s.line(1100, 180, 1190, 175, MUTED, 2.5)
    s.line(1100, 190, 1190, 335, MUTED, 2.5)
    s.line(1100, 410, 1190, 200, MUTED, 2.5)
    s.line(1100, 420, 1190, 355, MUTED, 2.5)
    s.text(1360, 445, "all written as pipeline_* tables in dbx_workshop_dev.<user_schema>", 19, MUTED, 400, "middle", italic=True)
    return s.render()


def g_scd():
    s = Svg(1720, 300)
    s.text(0, 30, "Change feed (arrives out of order)", 23, NAVY, 700, "start")
    feed = [("D042", "Gold", "11-15 08:00"), ("D042", "Platinum", "11-20 09:30"), ("D042", "Gold", "11-18 10:00")]
    for i, (k, v, t) in enumerate(feed):
        y = 50 + i * 70
        s.box(0, y, 500, 56, f"{k} · {v} · {t}", None, "#fff", LINE, NAVY, 21, 10, mono=True)
    s.line(520, 155, 600, 155, MUTED, 3)
    s.text(620, 30, "SCD type 1: latest wins", 23, GREEN, 700, "start")
    s.box(620, 50, 460, 56, "D042 · Platinum", None, "#E3F4EC", GREEN, NAVY, 21, 10, mono=True)
    s.text(620, 150, "SEQUENCE BY handles", 20, MUTED, 400, "start")
    s.text(620, 178, "late and out-of-order rows", 20, MUTED, 400, "start")
    s.text(1120, 30, "SCD type 2: full history", 23, TEAL, 700, "start")
    hist = [("D042 · Gold", "11-15 → 11-18"), ("D042 · Gold", "11-18 → 11-20"), ("D042 · Platinum", "11-20 → (current)")]
    for i, (a, b) in enumerate(hist):
        y = 50 + i * 70
        s.box(1120, y, 600, 56, f"{a}   {b}", None, "#EAF4F7", TEAL, NAVY, 20, 10, mono=True)
    s.text(1120, 285, "__START_AT / __END_AT columns maintained for you", 19, MUTED, 400, "start", italic=True)
    return s.render()


def g_jobs():
    s = Svg(1720, 500)
    s.text(140, 30, "Triggers", 24, MUTED, 700)
    for i, lab in enumerate(["Schedule (cron)", "File arrival", "Table update", "Continuous", "API / manual"]):
        s.box(0, 50 + i * 86, 280, 66, lab, None, "#fff", LINE, NAVY, 21, 10)
    s.text(140, 495, "+ SQL condition (Beta)", 18, MUTED)
    s.line(280, 250, 340, 250, MUTED, 3)
    s.rect(340, 40, 1060, 440, "#fff", TEAL, 18, 3)
    s.text(870, 80, "Job: a DAG of tasks", 24, TEAL, 700)
    s.box(380, 200, 220, 90, "Pipeline", "SDP update", "#E3F4EC", GREEN, NAVY, 23)
    s.box(660, 110, 230, 90, "If / else", "row count > 0?", OAT2, LINE, NAVY, 23)
    s.box(660, 290, 230, 90, "SQL / dbt", "checks, models", OAT2, LINE, NAVY, 23)
    s.box(950, 110, 230, 90, "For each", "per region", OAT2, LINE, NAVY, 23)
    s.box(950, 290, 230, 90, "Notebook", "publish / ML", OAT2, LINE, NAVY, 23)
    s.box(1210, 200, 160, 90, "Run job", "child", OAT2, LINE, NAVY, 22)
    s.line(600, 230, 660, 160, MUTED, 2.5)
    s.line(600, 260, 660, 330, MUTED, 2.5)
    s.line(890, 155, 950, 155, MUTED, 2.5)
    s.line(890, 335, 950, 335, MUTED, 2.5)
    s.line(1180, 160, 1210, 230, MUTED, 2.5)
    s.line(1180, 330, 1210, 260, MUTED, 2.5)
    s.text(870, 440, "task values · parameters · retries · timeouts · serverless or classic per task", 19, MUTED)
    s.line(1400, 250, 1450, 250, MUTED, 3)
    s.text(1580, 30, "Operate", 24, MUTED, 700)
    for i, lab in enumerate(["Notifications", "Repair & rerun", "Backfill runs", "Timeline / Gantt", "System tables"]):
        s.box(1450, 50 + i * 86, 270, 66, lab, None, "#fff", LINE, NAVY, 21, 10)
    return s.render()


def g_ref_arch():
    s = Svg(1720, 610)
    # sources
    srcs = [("Dealer CRM (Salesforce)", 40), ("ERP orders (SQL Server)", 130), ("Partner files (S3 / ADLS)", 220),
            ("Car telemetry (devices)", 310), ("Clickstream (Kafka)", 400)]
    s.text(150, 22, "Apex Motorsports sources", 21, MUTED, 700)
    for lab, y in srcs:
        s.box(0, y, 300, 70, lab, None, "#fff", LINE, NAVY, 19, 10)
    ing = [("Lakeflow Connect", 85, GREEN), ("Auto Loader", 220, BLUE), ("Zerobus Ingest", 310, CORAL), ("SDP Kafka source", 400, SLATE)]
    for lab, y, c in ing:
        s.box(370, y, 260, 70, lab, None, "#fff", c, c, 21, 10)
    for (lab, y), t in zip(srcs, [85, 85, 220, 310, 400]):
        s.line(300, y + 35, 370, t + 35, LINE, 2)
    # pipeline
    s.rect(690, 40, 640, 450, "#fff", TEAL, 16, 3)
    s.text(1010, 76, "Spark Declarative Pipelines (serverless)", 21, TEAL, 700)
    s.box(715, 100, 180, 360, "Bronze", "streaming tables", "#FFF0E0", YELLOW, NAVY, 25)
    s.box(920, 100, 180, 360, "Silver", "quality · CDC", "#EEF2F4", SLATE, NAVY, 25)
    s.box(1125, 100, 180, 360, "Gold", "materialized views", "#FFF6D6", YELLOW, NAVY, 25)
    s.line(895, 280, 920, 280, MUTED, 2.5)
    s.line(1100, 280, 1125, 280, MUTED, 2.5)
    for lab, y, c in ing:
        s.line(630, y + 35, 715, 280, LINE, 2)
    # consumers
    cons = [("AI/BI dashboards", 60), ("Genie agents", 150), ("Real-time apps · Lakebase", 240), ("ML features & models", 330),
            ("Delta Sharing to partners", 420)]
    for lab, y in cons:
        s.box(1400, y, 320, 70, lab, None, "#fff", LINE, NAVY, 19, 10)
        s.line(1330, 280, 1400, y + 35, LINE, 2)
    s.box(0, 500, 1720, 46, "Lakeflow Jobs: table-update trigger → pipeline → quality gate (if/else) → refresh dashboards → notify", None,
          OAT2, LINE, NAVY, 20, 10)
    s.box(0, 556, 1720, 46, "Unity Catalog: permissions · lineage · data quality monitoring · system tables · bundles in Git", None,
          NAVY, NAVY, "#fff", 20, 10)
    return s.render()


# --------------------------------------------------------------------------------------------- slides

SDP_SQL = """CREATE OR REFRESH STREAMING TABLE pipeline_silver_orders_valid (
  CONSTRAINT known_dealer      EXPECT (dealer_id IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT positive_quantity EXPECT (quantity > 0)          ON VIOLATION DROP ROW
) AS SELECT try_cast(order_id AS BIGINT) AS order_id, ...
FROM STREAM(pipeline_bronze_orders_fact);

CREATE OR REFRESH STREAMING TABLE pipeline_silver_orders_fact;
CREATE FLOW pipeline_silver_orders_dedupe AS AUTO CDC INTO pipeline_silver_orders_fact
FROM STREAM(pipeline_silver_orders_valid)
KEYS (order_id) SEQUENCE BY sent_at STORED AS SCD TYPE 1;

CREATE OR REFRESH MATERIALIZED VIEW pipeline_gold_daily_dealer_sales_fact
AS SELECT to_date(o.order_ts) AS order_date, d.region, ..., sum(o.net_revenue) AS net_revenue
FROM pipeline_silver_orders_fact o JOIN pipeline_silver_dealers_dim d USING (dealer_id) GROUP BY ALL;"""

SDP_PY = """from pyspark import pipelines as dp

dp.create_streaming_table("pipeline_silver_orders_fact")
dp.create_auto_cdc_flow(
    target="pipeline_silver_orders_fact",
    source="pipeline_silver_orders_valid",
    keys=["order_id"], sequence_by="sent_at",
    stored_as_scd_type=1)   # 2 keeps full history"""

SLIDES = [
    title_slide(
        "Data engineering<br>with Lakeflow", "Spark Do's &amp; Don'ts workshop · companion talk",
        "Welcome. The first talk was about how Spark runs your code. This one is about the toolkit around it: how "
        "data gets in, how it's transformed, how it runs in production, and how it's governed. 30 to 40 minutes, then "
        "the workshop notebooks, including a declarative-pipeline version of the bronze-to-gold lab."),

    content("Agenda", "The Databricks data engineering toolkit, end to end", bullets([
        "Why one platform: what Lakeflow replaces",
        "<b>Ingest</b>: Lakeflow Connect, Auto Loader, Zerobus Ingest",
        "<b>Transform</b>: Spark Declarative Pipelines, the Pipelines Editor, real-time mode",
        "<b>Orchestrate</b>: Lakeflow Jobs",
        "<b>Build without code, build with agents</b>: Lakeflow Designer, Genie Code, Genie ZeroOps",
        "<b>Operate</b>: governance, quality, cost, CI/CD; when to use what",
    ], "big"),
        "Six parts. I'll spend the most time on declarative pipelines and jobs, because that's what you'll use in the "
        "workshop. Statuses on the slides are as of November 2026; preview features change quickly, so check the "
        "release notes before you commit to one."),

    content("The job hasn't changed. The stack has.", "Get data from sources to consumers, reliably and on time",
            g_fragmented(),
            takeaway="Every extra tool is another identity, another lineage gap, another bill and another on-call rotation.",
            note="The data engineering job is the same as ever: land data, clean it, shape it, run it on time. What "
            "changes is how many tools you stitch together to do it. Each one has its own auth, its own monitoring, and "
            "none of them share lineage. Lakeflow puts ingestion, transformation and orchestration on one platform, "
            "governed by Unity Catalog and running on serverless compute."),

    content("Lakeflow at a glance", "Ingest · transform · orchestrate, on Unity Catalog",
            g_lakeflow_map(),
            "Here's the map we'll walk through. Three ways in: managed connectors, Auto Loader for files, Zerobus for "
            "events. One transformation engine: Spark Declarative Pipelines, which you author in the Pipelines Editor, "
            "or visually in Designer. Jobs orchestrates everything. Unity Catalog and serverless sit under all of it, "
            "and Genie Code and ZeroOps work across every step. Lakeflow itself went GA in June 2025; Connect, "
            "Declarative Pipelines (formerly DLT) and Jobs (formerly Workflows) all live under that name."),

    section_slide("Part 1", "Ingest", ["Lakeflow Connect", "Auto Loader", "Zerobus Ingest", "Picking the right one"],
                  "First, getting data in. Three tools, each for a different kind of source."),

    content("Three ways in, one question", "Pick the ingestion tool by where the data comes from",
            g_ingest_decision(),
            takeaway="All four land in Unity Catalog Delta tables, so everything downstream looks the same.",
            note="The decision is mostly about the source. A SaaS application or an operational database: use a managed "
            "connector, don't write API pagination code. Files arriving in cloud storage: Auto Loader. Your own "
            "applications or devices emitting events: Zerobus, which writes straight into a table. If you already "
            "run Kafka, read it from a declarative pipeline; there's also a managed Kafka connector in Beta."),

    content("Lakeflow Connect", "Managed connectors for SaaS apps, databases and file sources", with_asof("""
    <div class="split wide-left"><div>""" + bullets([
        "<b>100+ managed connectors</b>: Salesforce, Workday, ServiceNow, SharePoint, SQL Server, Oracle, NetSuite, Google Analytics, Confluence, HubSpot…",
        "Incremental by default: each run lands only what changed, into UC streaming tables",
        "Databases: log-based <b>CDC</b>, or <b>query-based</b> capture on a cursor column (no gateway, no staging) " + st("ga"),
        "<b>Community connectors</b>: open source, built on the Spark Python Data Source API " + st("beta"),
        "Runs on serverless; free tier of <b>100 DBUs per day</b> for managed connectors",
    ], "sm") + """</div><div>""" + cards([
        ("Managed", "UI, API or bundle; Databricks maintains the connector, schema handling and state.", "green"),
        ("Standard", "<code>read_files</code>, Kafka, Kinesis, JDBC from SQL or Spark: full control, your code.", ""),
        ("Federation", "Query in place with Lakehouse Federation when you don't need a copy.", ""),
    ], 1) + "</div></div>"),
            "Lakeflow Connect is the 'don't build it yourself' option. The connector handles auth, API limits, schema "
            "changes and incremental state, and lands data in streaming tables you can build on. For databases you "
            "choose log-based CDC, or query-based capture, which just needs a monotonically increasing column and "
            "skips the gateway; note it captures the latest state per run, not every intermediate change. Community "
            "connectors fill the long tail and are Beta, with no Databricks SLA. And when you need a custom read, "
            "the standard Spark and SQL sources are always there."),

    content("Auto Loader", "Incremental, exactly-once file ingestion from cloud storage", with_asof("""
    <div class="split"><div>""" + code("""(spark.readStream.format("cloudFiles")
   .option("cloudFiles.format", "json")
   .option("cloudFiles.schemaLocation", ckpt)
   .option("cloudFiles.useManagedFileEvents", "true")
   .load("/Volumes/.../raw_files/lab/orders_json")
   .writeStream.option("checkpointLocation", ckpt)
   .trigger(availableNow=True)
   .toTable("bronze_orders"))

-- or in SQL / a pipeline
SELECT * FROM STREAM read_files('/Volumes/...', format => 'json')""") + """</div><div>""" + bullets([
        "Remembers which files it processed: rerun it and only new files are read",
        "Schema inference and <b>evolution</b>; bad fields go to <code>_rescued_data</code>, nothing silently lost",
        "<b>Managed file events</b> " + st("ga") + " : no directory listing at scale",
        "<code>availableNow</code> = batch semantics with streaming bookkeeping",
    ], "sm") + "</div></div>"),
            "You've already used Auto Loader in the lab: step 1b, and section 6c of the do's and don'ts, where a full "
            "reload re-read everything and Auto Loader picked up one new file. The checkpoint is the point: rerun it and "
            "it reads only what's new. Schema evolution and the rescued-data column mean an upstream change doesn't "
            "silently drop data. With Unity Catalog file events, GA since December 2025, it no longer lists the "
            "directory to find new files, which matters once you have millions of them. In a pipeline, read_files with "
            "STREAM is the same thing in SQL."),

    content("Zerobus Ingest", "Push events straight into Delta tables, without running a message bus", with_asof(
        g_zerobus() + """<div class="two even" style="margin-top:26px"><div class="col plain">""" + bullets([
            "Serverless, part of Lakeflow Connect " + st("ga", "GA Feb 2026"),
            "Advertised: under 5 s to the table, up to 100 MB/s per connection, 10+ GB/s per table",
            "Writes into tables or <b>streaming tables</b> " + st("ga"),
        ], "sm") + """</div><div class="col plain">""" + bullets([
            "gRPC and REST APIs, SDKs (Python, Java, Rust, Go, TypeScript) " + st("ga"),
            "OpenTelemetry, MQTT and Kafka-compatible producer APIs: check status per interface",
            "Keep Kafka when many consumers need the same stream",
        ], "sm") + "</div></div>"),
            "Zerobus is for when you own the producer: application events, device telemetry, logs. Instead of standing "
            "up Kafka just to get events into the lakehouse, producers write directly to a Unity Catalog table through "
            "an SDK or API. The numbers are Databricks' advertised figures. Interfaces are at different stages: gRPC, "
            "REST and the SDKs are GA, OpenTelemetry and the Kafka-compatible API were later, so check the docs for "
            "the one you need. It doesn't replace a bus with many independent consumers. For Apex Motorsports, this is "
            "the car telemetry path."),

    section_slide("Part 2", "Transform", ["Spark Declarative Pipelines", "Tables, flows and expectations", "AUTO CDC",
                                          "Incremental and real-time", "The Pipelines Editor"],
                  "Next, the transformation engine: Spark Declarative Pipelines, which most of the rest of the platform builds on."),

    content("Spark Declarative Pipelines", "Declare the tables you want; the engine works out how to keep them up to date",
            g_declarative(),
            takeaway="Formerly Delta Live Tables. Same idea, now part of Apache Spark itself.",
            note="With imperative code you write every step: track what's new, merge by key, recompute the affected "
            "aggregates, order the jobs, handle retries. With a declarative pipeline you define the tables and the "
            "queries that produce them. The engine builds the dependency graph, runs things in the right order and in "
            "parallel, processes only what's new, and manages checkpoints and retries. This used to be called Delta "
            "Live Tables; the declarative core was contributed to Apache Spark and ships in Spark 4.1."),

    content("Three building blocks", "Choosing between a streaming table, a materialized view and a view",
            table(["", "What it is", "Use it for", "Workshop example"], [
                ["Streaming table", "Append-only, processes each input row once (incremental)",
                 "Ingestion, append-only facts, CDC targets", "<code>pipeline_bronze_orders_fact</code>"],
                ["Materialized view", "The result of a query, kept up to date; refreshed incrementally when possible",
                 "Joins, aggregates, gold tables", "<code>pipeline_gold_daily_dealer_sales_fact</code>"],
                ["View", "Not stored; computed when read", "Intermediate logic you don't need to keep", "an intermediate cleaning step"],
                ["Flow", "A query that writes into a target: append, AUTO CDC, update",
                 "Many sources into one table; backfills", "<code>pipeline_silver_orders_dedupe</code>"],
            ]) + '<p class="note-s">Streaming tables and materialized views also work outside a pipeline: create them in Databricks SQL or a notebook.</p>',
            "Most of the design work is picking the right object. Streaming tables for anything that only grows: they "
            "read each input row once. Materialized views for anything derived, joins and aggregations: they're "
            "recomputed, incrementally when the engine can. Views for logic you don't need to store. Flows are how "
            "data gets into a target, and you can have several flows into one table, which is how you merge sources or "
            "backfill. These objects aren't pipeline-only: you can create them straight from the SQL editor."),

    content("The bronze-to-gold lab, declaratively", "The same tables you built by hand, as one pipeline",
            g_pipeline_lab() + bullets([
                "<b>Bronze</b>: Auto Loader streaming table for orders (Python file); dealers as a batch materialized view",
                "<b>Silver</b>: expectations drop bad rows, a quarantine table keeps them with a reason, <b>AUTO CDC</b> keeps the latest re-sent order",
                "<b>Gold</b>: materialized views · all in <code>notebooks/jobs_notebooks/pipeline</code>",
            ], "sm"),
            "This is the lab as a pipeline: one Python file and two SQL files. Bronze reads the raw JSON with Auto "
            "Loader; the dealer list is a small full extract, so a batch materialized view fits. Silver types the rows "
            "and checks them with expectations, an AUTO CDC flow keeps the latest version of each re-sent order, and a "
            "separate streaming table quarantines the rejects with a reason. Gold is materialized views. The workshop's "
            "jobs_notebooks folder has this exact pipeline; one notebook creates it and a job that runs it, in your own schema."),

    content("What the code looks like", "Silver and gold from the workshop pipeline, in SQL",
            code(SDP_SQL),
            takeaway="No checkpoint paths, no QUALIFY de-duplication, no ordering of steps: the engine derives all three.",
            note="Here's the silver and gold code. The expectations are constraints on the table. The de-duplication is "
            "an AUTO CDC flow keyed on order_id and sequenced by sent_at, which is what the lab's QUALIFY row_number did, "
            "but incremental. Gold reads silver with a normal join. Notice what's missing compared with the notebook: "
            "checkpoints, merge logic, and any statement of which step runs first."),

    content("Data quality with expectations", "Declare what valid data looks like, and what to do when it isn't", """
    <div class="split"><div>""" + table(["Action", "Bad rows", "Use when"], [
        ["<code>EXPECT</code>", "kept; counted in metrics", "you want visibility first"],
        ["<code>… DROP ROW</code>", "dropped; counted", "bad rows must not flow on"],
        ["<code>… FAIL UPDATE</code>", "the update stops", "bad data means a broken source"],
    ], "compact") + """<p class="note-s">Quarantine pattern: a second flow selects the rows that fail the rule into
    their own table, as the lab's <code>endtoend_quarantine_orders_fact</code> does.</p></div><div>""" + bullets([
        "Results land in the pipeline <b>event log</b>: pass/fail counts per rule, per update",
        "Delta <code>CHECK</code> constraints still guard writes from anywhere else",
        "Expectations are a Databricks extension (not in open-source SDP)",
        "Across tables: <b>data quality monitoring</b> watches freshness and completeness (part 5)",
    ], "sm") + "</div></div>",
            "Expectations are rules on a table with an action. Warn and keep the row, drop it, or fail the update. Every "
            "update records pass and fail counts in the event log, so you can chart quality over time. For "
            "auditing, the quarantine pattern sends the failing rows to their own table, which is what the lab did by "
            "hand. This is one of the features Databricks adds on top of the open-source framework."),

    content("AUTO CDC", "Apply a change feed correctly, with SCD type 1 or type 2, in a few lines",
            g_scd() + """<div class="split" style="margin-top:22px"><div>""" + code(SDP_PY) + """</div><div>""" + bullets([
        "Handles <b>out-of-order</b> and late changes with <code>sequence_by</code>",
        "Deletes via <code>apply_as_deletes</code>; <code>AUTO CDC FROM SNAPSHOT</code> for full snapshots",
        "Formerly <code>APPLY CHANGES</code>; SQL form on the previous slide",
    ], "sm") + "</div></div>",
            "Hand-written MERGE logic for change data is where pipelines quietly go wrong: out-of-order events, late "
            "updates, deletes. AUTO CDC takes the key and a sequencing column and gets it right, as type 1 (latest wins) "
            "or type 2 (full history with start and end columns). In the workshop pipeline, AUTO CDC type 1 keeps the "
            "latest version of each re-sent order line, replacing the lab's QUALIFY ROW_NUMBER de-duplication, and it "
            "does it incrementally. If your source only gives "
            "snapshots, the FROM SNAPSHOT variant derives the changes for you."),

    content("Incremental by default, real-time when you need it", "How much work each update does, and how fast", with_asof(
        cards([
            ("Incremental MVs", ["Serverless pipelines refresh materialized views incrementally when the query allows",
                                 "Falls back to a full recompute only when it must"], "green"),
            ("Incremental Replace Where", ["Batch semantics (replace a slice) without recomputing everything " + st("ga"),
                                           "Good fit for daily re-processing"], ""),
            ("Real-Time Mode", ["Structured Streaming " + st("ga", "GA Mar 2026"),
                                "Declarative pipelines " + st("ga", "GA Oct 2026"),
                                "Millisecond-scale latency, classic and serverless"], "lava"),
        ], 3) + bullets([
            "Same code, different trigger: <b>triggered</b> (batch-like, cheapest) → <b>continuous</b> (seconds) → <b>real-time mode</b> (ms)",
            "Declarative APIs (append, AUTO CDC, Replace Where, MVs) are also available from notebooks and the SQL editor",
        ], "sm")),
            "Two levers. First, how much work an update does: on serverless, materialized views refresh incrementally "
            "where the query allows it, and Replace Where now does too, so batch-style reprocessing doesn't mean a full "
            "rebuild. Second, how fast: the same pipeline code can run triggered, continuously, or in real-time mode, "
            "which went GA for Structured Streaming in March and for declarative pipelines at the end of October, with "
            "latencies in milliseconds. Most pipelines should be triggered; pay for latency only where the business needs it."),

    content("Lakeflow Pipelines Editor", "A multi-file IDE built for pipelines", with_asof("""
    <div class="split"><div>""" + bullets([
        "Pipeline as a <b>folder of Python and SQL files</b>, in a Git folder " + st("ga", "GA May 2026"),
        "Live <b>pipeline graph</b> and data previews next to the code",
        "<b>Run one file or one table</b>: dry runs and selective refresh while you iterate",
        "Issues panel and execution insights per table",
        "<b>Genie Code</b> in the editor: create, change and debug the pipeline",
    ], "sm") + """</div><div>""" + cards([
        ("Typical loop", ["Write a table in a new file", "Run just that table; check preview and expectations",
                          "Commit from the Git folder", "Deploy with a bundle to test, then prod"], "accent"),
    ], 1) + "</div></div>"),
            "The editor is where you'll build pipelines day to day. A pipeline is a folder of files, so it fits Git and "
            "code review. You see the graph and sample data next to the code, and you can run just the table you're "
            "working on instead of the whole pipeline. Genie Code is built in, which is how a lot of pipelines get "
            "started now: describe the table, review what it writes."),

    section_slide("Part 3", "Orchestrate", ["Lakeflow Jobs", "Triggers", "Control flow and operations"],
                  "Third, running all of this in production with Lakeflow Jobs."),

    content("Lakeflow Jobs", "One orchestrator for pipelines, notebooks, SQL, dbt, dashboards and ML",
            g_jobs(),
            "A job is a graph of tasks: pipelines, notebooks, SQL, dbt, Python, dashboard refreshes, and more. You add "
            "control flow, if/else, for each and run-job for modular child jobs, and pass values between tasks. Each "
            "task can run on serverless or classic compute. On the left, what starts it; on the right, what you get to "
            "operate it. It was called Workflows before Lakeflow, and it's included with the platform, with no separate "
            "orchestrator to run."),

    content("Triggers: run when the data is ready", "Event-driven beats a cron guess", with_asof(
        table(["Trigger", "Starts a run when…", "Notes"], [
            ["Schedule", "a cron time is reached", "the default; pair with a condition below"],
            ["File arrival", "new files land in a UC volume or external location", "no polling code"],
            ["Table update", "monitored tables change (any / all of them)", "updated tables passed to tasks " + st("ga")],
            ["Continuous", "the previous run ends", "always-on streaming jobs"],
            ["SQL condition", "a query on a SQL warehouse returns rows or a new value", st("beta")],
            ["Multiple triggers", "up to five per job, e.g. table update + nightly safety run", st("beta")],
        ], "compact")),
            "Schedules are guesses about when upstream data will be ready. File-arrival and table-update triggers react "
            "to the data itself, and a table-update trigger hands the list of changed tables to the job, so a for-each "
            "task can process just those. SQL conditions, in Beta, gate a run on a query, for example 'yesterday's "
            "orders have landed'. Multiple triggers per job, also Beta, let you combine an event trigger with a safety-net schedule."),

    content("Control flow and day-2 operations", "What makes a job production-ready", with_asof(cards([
        ("Control flow", ["<b>If / else</b> on task values or results", "<b>For each</b> over a list, with concurrency",
                          "<b>Run job</b> for reusable child jobs", "Job and task parameters, task values"], ""),
        ("Recovery", ["Retries and timeouts per task", "<b>Repair run</b>: rerun failed tasks only",
                      "<b>Backfill</b>: one job over a date range, up to 100 runs", "Partial runs while debugging"], "green"),
        ("Visibility", ["Notifications: email, Slack, webhooks", "Duration alerts for late runs",
                        "Timeline view of the critical path", "<code>system.lakeflow</code> tables for runs and cost"], "accent"),
    ], 3) + bullets([
        "Outside Databricks: an open operator framework for external systems (REST, Snowflake, Slack, PagerDuty) " + st("ann"),
        "Coming from Airflow or ADF? The concepts map one-to-one: DAG → job, operator → task, sensor → trigger",
    ], "sm")),
            "The production features are what decide whether teams keep an external orchestrator. Repair runs rerun only "
            "what failed. Backfills run the same job across a date range, which used to be the main reason to keep "
            "Airflow. Timeline views and the system tables show where the time and money go. For things outside "
            "Databricks, the June announcement added an operator framework; check its status before you plan on it."),

    section_slide("Part 4", "Without code, and with agents", ["Lakeflow Designer", "Genie Code", "Genie ZeroOps"],
                  "Fourth: two ways to build that aren't writing pipeline code by hand."),

    content("Lakeflow Designer", "Visual, AI-assisted data prep that produces real pipelines", with_asof("""
    <div class="split"><div>""" + bullets([
        "Drag-and-drop canvas or plain-English prompts " + st("ga", "GA Jun 2026"),
        "Runs on Spark Declarative Pipelines; outputs are UC tables or <b>materialized views</b>",
        "Generated code visible per operator; files live in Git folders",
        "Parameterized sources and outputs: one flow, test and prod schedules",
        "October 2026: Prepare, Unique and <b>Guardrails</b> (quality) operators; multi-join; file outputs",
    ], "sm") + """</div><div>""" + cards([
        ("Who it's for", "Analysts and domain experts who'd otherwise use a desktop prep tool, and the engineers who "
                         "review and productionize their flows.", "lava"),
        ("Where it stops", "Complex ETL with custom logic still belongs in code; Designer has Python and SQL "
                           "operators for the gaps.", ""),
    ], 1) + "</div></div>"),
            "Designer is for the people who today build data prep in desktop tools and email spreadsheets around. "
            "They build flows on a canvas or by describing them; underneath it's a declarative pipeline governed by "
            "Unity Catalog, with the generated code visible and in Git. Engineers can review it like any other code. "
            "It's not meant to replace pipelines with complex logic, and it's honest about that with code operators "
            "for the gaps."),

    content("Agents across the lifecycle", "Genie Code builds; Genie ZeroOps keeps it running", with_asof(cards([
        ("Genie Code " + st("ga"), ["Creates ingestion connectors, Python and SQL pipelines, and jobs with triggers",
                                    "Grounded in Unity Catalog: knows your schemas, lineage and permissions",
                                    "Writes <b>declarative</b> pipelines, so the engine validates dependencies before anything runs",
                                    "You used it in the workshop: the scorecard challenge"], "accent"),
        ("Genie ZeroOps " + st("prpr"), ["Background agent for jobs, pipelines and tables",
                                        "Detects failures and quality anomalies; root cause through lineage",
                                        "Proposes a fix, tests it in a sandbox, opens it for review",
                                        "Nothing reaches production without human approval"], "lava"),
    ], 2)),
            "Two agents with different jobs. Genie Code is the coding agent: it builds connectors, pipelines and jobs, "
            "and because it sits on Unity Catalog it knows your tables. It tends to write declarative pipelines, which "
            "is a good thing: the engine checks the graph before anything runs. Genie ZeroOps, announced at Data + AI "
            "Summit and in private preview, watches production, finds the root cause through lineage, and proposes a "
            "tested fix for a human to approve."),

    section_slide("Part 5", "Operate", ["Governance and quality", "Cost and compute", "CI/CD and migration",
                                        "When to use what"],
                  "Last part: what's around the pipelines once they're in production."),

    content("Governed and observable by default", "Unity Catalog sees every table, pipeline and job", with_asof(cards([
        ("Lineage", ["Table and column lineage from source to dashboard, captured automatically",
                     "Jobs and pipelines linked to the tables they write"], ""),
        ("Data quality monitoring", ["Anomaly detection on <b>freshness</b> and <b>completeness</b>, per schema " + st("ga", "GA Oct 2026"),
                                     "Learns each table's normal pattern; no rules to write"], "green"),
        ("Cost and runs", ["<code>system.billing</code>, <code>system.lakeflow</code> tables",
                           "Serverless: <b>performance-optimized</b> or <b>standard</b> mode per job",
                           "Tag jobs and pipelines to attribute cost"], "accent"),
    ], 3) + bullets([
        "Same permissions model for connectors, pipelines, tables and agents: grant once in Unity Catalog",
    ], "sm")),
            "Because everything runs on Unity Catalog, governance comes for free: lineage from the source system through "
            "the pipeline to the dashboard, without instrumenting anything. Data quality monitoring, GA at the end of "
            "October, learns when each table normally updates and how many rows it gets, and flags late or incomplete "
            "tables. And the system tables give you runs and cost by job, pipeline and tag; serverless standard mode is "
            "the cheaper option for jobs that don't need the fastest start."),

    content("CI/CD and migration", "Treat pipelines and jobs as code", with_asof("""
    <div class="split"><div>""" + code("""# databricks.yml: one bundle, many targets
resources:
  pipelines:
    lab_pipeline:
      catalog: dbx_workshop_dev
      schema: ${var.user_schema}
      libraries: [{glob: {include: pipeline/**}}]
  jobs:
    lab_job:
      tasks: [{task_key: refresh,
               pipeline_task: {pipeline_id: ${resources.pipelines.lab_pipeline.id}}}]

$ databricks bundle deploy -t prod""") + """</div><div>""" + bullets([
        "<b>Declarative Automation Bundles</b> (formerly Databricks Asset Bundles, renamed Mar 2026): YAML or Python",
        "Git folders for development; CLI, REST, SDKs and Terraform for automation",
        "<b>Lakebridge</b>: free tooling to assess and convert legacy ETL and SQL",
        "This workshop ships as a bundle: <code>databricks.yml</code> + <code>resources/jobs.yml</code>",
    ], "sm") + "</div></div>"),
            "Pipelines and jobs should be deployed like code. Bundles, renamed this March to Declarative Automation "
            "Bundles, describe pipelines, jobs and their settings in YAML or Python, with one target per environment. "
            "The rename doesn't change the CLI. Lakebridge is the migration toolkit for legacy ETL and SQL. And this "
            "workshop itself is a bundle: the instructor's setup job is defined in resources/jobs.yml."),

    content("When to use what", "A cheat sheet for the common choices",
            table(["You need to…", "Use", "Instead of"], [
                ["Copy a SaaS app or database into the lakehouse", "Lakeflow Connect", "custom API / CDC scripts, a separate ingestion tool"],
                ["Pick up files as they land", "Auto Loader (in a pipeline)", "full reloads, listing folders yourself"],
                ["Get app or device events into tables", "Zerobus Ingest", "a Kafka cluster used only as a pipe"],
                ["Build medallion tables, batch or streaming", "Spark Declarative Pipelines", "notebooks with hand-rolled MERGE and checkpoints"],
                ["Apply CDC or keep SCD2 history", "AUTO CDC", "MERGE with ROW_NUMBER de-duplication"],
                ["Run things in order, on events", "Lakeflow Jobs + triggers", "an external orchestrator, cron guesses"],
                ["Let analysts prep data themselves", "Lakeflow Designer", "desktop prep tools and file hand-offs"],
                ["One-off exploration or a custom step", "a notebook (as a job task)", "forcing it into a pipeline"],
            ], "compact"),
            "If you remember one slide, make it this one. The pattern: prefer the managed, declarative option, and drop "
            "to code where you need control. Notebooks are still the right tool for exploration and for custom steps; "
            "they just run as a task in a job rather than being the pipeline."),

    content("Reference architecture", "Apex Motorsports Parts, end to end on Lakeflow",
            g_ref_arch(),
            "Putting it together for our fictional company. Dealer CRM and the ERP come in through managed connectors, "
            "partner files through Auto Loader, car telemetry through Zerobus, clickstream from an existing Kafka. One "
            "set of declarative pipelines builds bronze, silver and gold. A job, triggered by table updates, runs the "
            "pipeline, checks quality, refreshes dashboards and notifies the team. Unity Catalog governs all of it, and "
            "the gold tables feed dashboards, the Genie agents you'll build later, apps and partners."),

    content("Where this shows up in the workshop", "Everything on these slides you can try today", cards([
        ("01 · bronze-to-gold lab", ["Auto Loader into bronze", "QUALIFY de-duplication, CHECK constraints, quarantine",
                                     "Gold tables and a dashboard, by hand"], ""),
        ("jobs_notebooks", ["The same lab as a <b>declarative pipeline</b>: Auto Loader, expectations, AUTO CDC, quarantine, MVs",
                            "One notebook creates the pipeline and a <b>Lakeflow job</b> in your schema"], "green"),
        ("02 · do's and don'ts", ["6c: full reload vs Auto Loader", "9: liquid clustering and file layout",
                                  "11: Genie Code optimizes a slow job"], ""),
        ("genie/", ["Genie agents and metric views on the gold tables the pipeline produces"], "accent"),
    ], 2),
            "Here's how the talk maps onto the notebooks. The lab builds the medallion by hand, which is the best way to "
            "see what a declarative pipeline does for you. Then the jobs_notebooks folder runs the same logic as a "
            "pipeline and a job, so you can compare the two side by side. Notebook 02 has the Auto Loader comparison, and "
            "the Genie notebooks show what you can build on the gold layer."),

    content("Status at a glance", "What's GA, what's preview, as of November 2026", table(["Capability", "Status", "Since"], [
        ["Lakeflow Connect managed connectors · query-based capture", st("ga"), "connector-by-connector; many SaaS ones still Beta"],
        ["Community connectors · managed Kafka connector", st("beta"), "2026"],
        ["Zerobus Ingest (gRPC, REST, SDKs)", st("ga"), "Feb 2026"],
        ["Auto Loader with managed file events", st("ga"), "Dec 2025"],
        ["Pipelines Editor", st("ga"), "May 2026"],
        ["Real-time mode in declarative pipelines", st("ga"), "Oct 2026 (Structured Streaming: Mar 2026)"],
        ["Lakeflow Designer", st("ga"), "Jun 2026"],
        ["Jobs: SQL-condition triggers · multiple triggers", st("beta"), "2026"],
        ["Data quality monitoring (freshness, completeness)", st("ga"), "Oct 2026"],
        ["Genie ZeroOps", st("prpr"), "announced Jun 2026"],
    ], "compact"),
            "A summary to photograph. Previews move fast, so treat this as a snapshot and check the release notes. "
            "Note that Lakeflow Connect's status is per connector: the platform is GA, but many newer SaaS connectors "
            "are Beta."),

    closing_slide("Thank you. Questions, then on to the notebooks: start with jobs_notebooks to see the lab as a pipeline."),
]


def build():
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data engineering with Lakeflow</title>
<style>{font_faces()}{kit.CSS}{EXTRA_CSS}</style></head>
<body>
{''.join(SLIDES)}
<div id="hud"></div><div id="notes"></div>
<script>{kit.JS}</script>
</body></html>"""
    OUT.write_text(page)
    print(f"wrote {OUT} ({len(SLIDES)} slides, {OUT.stat().st_size / 1024:,.0f} KB)")


if __name__ == "__main__":
    build()
