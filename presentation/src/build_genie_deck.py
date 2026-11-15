"""Build the "Genie Agents Workshop + Best Practices" presentation as one self-contained HTML file.

    python3 presentation/src/build_genie_deck.py      # writes presentation/genie_agents_workshop.html

An HTML remake of the GM Genie workshop deck ("GM: [Genie] Workshop + Best Practices - 2026.09.24", Daria
Krasavina), updated for Genie Agents as of November 2026 (docs.databricks.com Genie Agents pages, the AI/BI and
Genie One release notes for 2026, and databricks.com blog posts). It reuses the styling, viewer and SVG kit of
build_deck.py and the table / card / status helpers of build_lakeflow_deck.py, so all three decks look the same.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_deck as kit  # noqa: E402  (shared styling, logos, SVG kit, slide templates)
from build_deck import (BLUE, BRICK, CORAL, GREEN, LAVA, LINE, MUTED, NAVY, OAT2, SALMON, SLATE, TEAL,  # noqa: E402
                        YELLOW, Svg, bullets, closing_slide, content, font_faces, section_slide, title_slide)
from build_lakeflow_deck import EXTRA_CSS, cards, code, st, table, with_asof  # noqa: E402

OUT = HERE.parent / "genie_agents_workshop.html"
ASSETS_IMG = HERE / "assets" / "images"

GENIE_CSS = """
.chat{background:#fff;border:2px solid var(--line);border-radius:18px;padding:26px 32px;font-size:28px;line-height:1.4}
.chat .q{color:var(--navy);font-weight:700;margin-bottom:14px}
.chat .a{display:inline-block;background:var(--oat2);border-radius:14px;padding:10px 20px;margin-bottom:14px}
.chat .doubt{color:var(--lava);font-style:italic}
.who{font-size:20px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:10px}
.big-num{font-size:84px;font-weight:700;line-height:1;color:var(--navy)}
.big-num.green{color:var(--green)}.big-num.lava{color:var(--lava)}
.card .kick{font-size:19px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:10px}
.links{columns:2;column-gap:70px;font-size:27px;line-height:1.35;margin:0;padding:0;list-style:none}
.links li{break-inside:avoid;margin:0 0 20px}
.links a{color:var(--navy);font-weight:700;text-decoration:none}
.links .url{display:block;font-family:'DM Mono',monospace;font-size:18px;color:var(--teal)}
.pattern{display:grid;grid-template-columns:repeat(4,1fr);gap:22px}
.pattern .card h4{font-size:30px}.pattern .card .num{color:var(--coral);font-weight:700;font-size:26px}
.quote{background:#fff;border-left:10px solid var(--coral);border-radius:12px;padding:24px 34px;font-size:28px;line-height:1.45;margin-top:30px}
.quote b{color:var(--teal)}
.do-dont{display:grid;grid-template-columns:1fr 1fr;gap:40px}
.do-dont .col li{font-size:27px;margin-bottom:12px}
.do-dont .col li b{display:block}
"""


# --------------------------------------------------------------------------------------------- graphics

def g_platform():
    """The Data Intelligence Platform layers, as in the corporate deck, with Genie highlighted."""
    s = Svg(1720, 640)
    rows = [
        ("Agentic Work", "Data-smart coworkers for every employee", [("Genie", "AI coworker connected to all your data", True)], CORAL),
        ("Agentic Apps", "Deploy agents at scale to transform work", [("Apps", "custom apps", False), ("AI/BI", "dashboards + Genie Agents", True)], SALMON),
        ("Agentic Dev", "Develop and deploy agents, apps and models", [("Agent Bricks", "build · deploy · optimize · govern", False), ("Genie Code", "agent for data practitioners", True)], SLATE),
        ("Agentic Data", "Unified, real-time data foundation", [("Lakeflow", "ingest · streaming · ETL", False), ("Lakehouse", "SQL data warehousing", False), ("Lakebase", "serverless Postgres", False)], TEAL),
    ]
    y = 20
    for name, sub, items, color in rows:
        s.rect(0, y, 1300, 118, "#fff", LINE, 14)
        s.rect(0, y, 14, 118, color, color, 6)
        s.text(40, y + 52, name, 30, NAVY, 700, "start")
        s.text(40, y + 88, sub, 20, MUTED, 400, "start")
        x = 520
        w = (1280 - 520 - 16 * (len(items) - 1)) / len(items)
        for label, desc, hot in items:
            s.box(x, y + 14, w, 90, label, desc, "#FFF1EE" if hot else OAT2, LAVA if hot else LINE, NAVY, 26, 12)
            x += w + 16
        y += 134
    # governance column
    s.rect(1330, 20, 390, 520, NAVY, NAVY, 16)
    s.text(1525, 80, "Unity Catalog", 32, "#fff", 700)
    s.text(1525, 118, "unified governance", 22, "#9FB4BC", 400)
    for i, t in enumerate(["Access · Semantics", "Genie Ontology", "Observability", "Unity AI Gateway", "Cost management"]):
        s.rect(1360, 150 + i * 74, 330, 58, "#244550", "#244550", 10)
        s.text(1525, 188 + i * 74, t, 23, "#fff", 500)
    s.rect(0, 566, 1720, 60, OAT2, LINE, 12)
    s.text(860, 605, "Open format data lake · any cloud · any model · any data", 24, NAVY, 500)
    return s.render()


def g_tailor():
    s = Svg(1720, 420)
    steps = [("1", "Leverage platform metadata", "Pick a focused topic. Genie reads table and column comments, keys and usage from Unity Catalog", TEAL),
             ("2", "Add agent-level semantics", "Knowledge store: SQL expressions, joins, example SQL, local descriptions, a few text instructions", CORAL),
             ("3", "Iterate on evidence", "Benchmarks score accuracy; the Monitoring tab and feedback show what users actually ask", GREEN)]
    for i, (n, title, body, color) in enumerate(steps):
        x = i * 590
        s.rect(x, 20, 540, 380, "#fff", color, 18, 3)
        s.add(f'<circle cx="{x + 70}" cy="90" r="38" fill="{color}"/>')
        s.text(x + 70, 102, n, 36, "#fff", 700)
        s.text(x + 130, 102, title, 29, NAVY, 700, "start")
        words, line, yy = body.split(), "", 175
        for w in words:
            if len(line) + len(w) > 34:
                s.text(x + 40, yy, line.strip(), 25, "#33464E", 400, "start")
                line, yy = "", yy + 40
            line += w + " "
        s.text(x + 40, yy, line.strip(), 25, "#33464E", 400, "start")
        if i < 2:
            s.line(x + 548, 210, x + 584, 210, MUTED, 4)
    return s.render()


def g_dashboard():
    s = Svg(1000, 560)
    s.rect(0, 0, 1000, 560, "#fff", LINE, 16)
    s.rect(0, 0, 1000, 56, OAT2, LINE, 16)
    s.text(30, 37, "Fleet parts sales · December", 22, NAVY, 700, "start")
    s.rect(820, 12, 160, 34, NAVY, NAVY, 17)
    s.text(900, 35, "✦ Ask Genie", 19, "#fff", 700)
    for i, (lab, val) in enumerate([("Net revenue", "$41.2M"), ("Orders", "4.2M"), ("Margin", "31.4%")]):
        s.rect(30 + i * 200, 80, 180, 100, OAT2, OAT2, 12)
        s.text(50 + i * 200, 115, lab, 17, MUTED, 400, "start")
        s.text(50 + i * 200, 158, val, 34, NAVY, 700, "start")
    pts = [(40, 470), (110, 440), (180, 452), (250, 410), (320, 420), (390, 360), (460, 300), (530, 315)]
    s.add('<polyline fill="none" stroke="#1B5162" stroke-width="5" points="' + " ".join(f"{x},{y}" for x, y in pts) + '"/>')
    s.add(f'<circle cx="460" cy="300" r="14" fill="none" stroke="{LAVA}" stroke-width="4"/>')
    s.rect(330, 214, 270, 64, "#fff", LAVA, 10, 2)
    s.text(465, 244, "Explain this change", 19, LAVA, 700)
    s.text(465, 268, "top drivers (Agent mode)", 16, MUTED, 400)
    s.text(40, 520, "right-click a point · or select a chart and ask a follow-up", 17, MUTED, 400, "start", italic=True)
    s.rect(640, 70, 340, 470, "#F7FAFB", TEAL, 14, 2)
    s.text(660, 105, "Genie", 22, TEAL, 700, "start")
    s.rect(660, 125, 300, 70, "#fff", LINE, 10)
    s.text(675, 152, "Why did revenue jump", 18, NAVY, 400, "start")
    s.text(675, 178, "in week 3?", 18, NAVY, 400, "start")
    s.rect(660, 210, 300, 150, OAT2, OAT2, 10)
    for i, t in enumerate(["Top drivers", "1  Region: Midwest  +38%", "2  Tier: Platinum  +21%", "3  Brakes category  +12%"]):
        s.text(675, 240 + i * 34, t, 17 if i else 18, NAVY, 700 if i == 0 else 400, "start")
    s.rect(660, 380, 300, 140, "#fff", LINE, 10, 1.5, "6 5")
    s.text(810, 425, "Key Insights", 19, MUTED, 700)
    s.text(810, 455, "(Dashboard Insights, Beta)", 16, MUTED, 400)
    s.text(810, 485, "trends · outliers · drivers", 16, MUTED, 400)
    return s.render()


def g_where_fits():
    s = Svg(1720, 640)
    s.line(200, 560, 1680, 560, NAVY, 3)
    s.line(200, 560, 200, 40, NAVY, 3)
    s.text(940, 620, "Open exploration  →", 24, MUTED, 500)
    s.text(185, 290, "Determinism", 24, MUTED, 500, "end")
    s.text(185, 322, "of results ↑", 24, MUTED, 500, "end")
    items = [
        (225, 420, 480, "Question in the UC sample-data tab", "quick look at one table", OAT2, LINE),
        (725, 370, 370, "Genie Agent on tables", "explore a complex data model", "#E6F2F7", BLUE),
        (500, 170, 430, "Genie Agent on metric views", "governed KPIs, flexible grouping", "#E3F4EC", GREEN),
        (1110, 90, 420, "AI/BI dashboard", "the same KPIs and grouping, every time", "#FFF1EE", LAVA),
        (1150, 400, 420, "Genie One", "across agents, dashboards and apps", "#F3EEF9", SLATE),
    ]
    for x, y, w, t, sub, fill, stroke in items:
        s.box(x, y, w, 100, t, sub, fill, stroke, NAVY, 23, 14)
    s.text(1680, 40, "Setup effort grows with curation; so does trust", 21, MUTED, 400, "end", italic=True)
    return s.render()


def g_tables_vs_mv():
    s = Svg(1720, 300)
    s.box(0, 40, 300, 110, "lab_gold_daily…", "table", "#fff", LINE, NAVY, 24, 12, mono=True)
    s.box(0, 170, 300, 110, "lab_silver_dealers…", "table", "#fff", LINE, NAVY, 24, 12, mono=True)
    s.line(310, 160, 480, 160, MUTED, 4)
    s.box(490, 70, 520, 180, "genie_mv_dealer_sales", "metric view: measures + dimensions, join pinned", "#E3F4EC", GREEN, NAVY, 26, 14, mono=True)
    s.line(1020, 160, 1180, 160, MUTED, 4)
    s.box(1190, 40, 530, 110, "SELECT region, MEASURE(margin_percent)", "what Genie writes", OAT2, LINE, NAVY, 21, 12, mono=True)
    s.box(1190, 170, 530, 110, "same formula everywhere", "dashboards · Genie · SQL · notebooks", "#fff", GREEN, NAVY, 24, 12)
    return s.render()


def g_hide_columns():
    s = Svg(820, 470)
    s.rect(0, 0, 820, 470, "#fff", LINE, 14)
    s.text(28, 44, "Configure › Sources › lab_gold_daily_dealer_sales_fact", 19, MUTED, 500, "start")
    rows = [("order_date", "Day of the order (Dec 2025)", "date, day", False), ("dealer_tier", "Platinum / Gold / Standard", "tier, level", False),
            ("net_revenue", "Revenue after discount, USD", "sales, revenue", False), ("margin", "net_revenue − cost, USD", "profit", False),
            ("_ingested_at", "load timestamp", "", True)]
    s.text(28, 92, "COLUMN", 15, MUTED, 700, "start")
    s.text(250, 92, "DESCRIPTION (agent-local)", 15, MUTED, 700, "start")
    s.text(590, 92, "SYNONYMS", 15, MUTED, 700, "start")
    for i, (c, d, syn, hidden) in enumerate(rows):
        y = 112 + i * 66
        s.rect(16, y, 788, 56, "#F4F5F6" if hidden else "#fff", LINE, 8, 1.5)
        col = "#A0AAB0" if hidden else NAVY
        s.text(30, y + 36, c, 19, col, 700, "start", mono=True)
        s.text(250, y + 36, d, 18, col, 400, "start")
        s.text(590, y + 36, syn, 18, TEAL if not hidden else col, 500, "start")
        s.text(780, y + 37, "⊘" if hidden else "◉", 22, LAVA if hidden else GREEN, 700, "end")
    s.text(28, 455, "eye icon hides a column from Genie; UC metadata is unchanged", 16, MUTED, 400, "start", italic=True)
    return s.render()


def g_joins():
    s = Svg(820, 420)
    s.box(0, 40, 330, 120, "lab_gold_daily…", "many", "#fff", NAVY, NAVY, 24, 12, mono=True)
    s.box(490, 40, 330, 120, "lab_silver_dealers…", "one", "#fff", NAVY, NAVY, 24, 12, mono=True)
    s.line(340, 100, 480, 100, TEAL, 4)
    s.text(410, 84, "many → one", 18, TEAL, 700)
    s.rect(0, 200, 820, 200, OAT2, OAT2, 14)
    s.text(30, 245, "Join condition", 18, MUTED, 700, "start")
    s.text(30, 285, "daily.dealer_id = dealers.dealer_id", 22, NAVY, 400, "start", mono=True)
    s.text(30, 335, "Sources of joins", 18, MUTED, 700, "start")
    s.text(30, 372, "UC PK/FK (saved automatically) · defined here · suggested from conversations", 18, NAVY, 400, "start")
    return s.render()


def g_expression(kind, name, sql, syn, use):
    s = Svg(820, 420)
    s.rect(0, 0, 820, 420, "#fff", LINE, 14)
    s.rect(24, 22, 150, 40, TEAL, TEAL, 20)
    s.text(99, 49, kind, 19, "#fff", 700)
    for i, (lab, val, mono) in enumerate([("Name", name, False), ("SQL", sql, True), ("Synonyms", syn, False), ("Instructions", use, False)]):
        y = 88 + i * 80
        s.text(30, y + 16, lab, 16, MUTED, 700, "start")
        s.rect(24, y + 26, 772, 44, OAT2 if mono else "#fff", LINE, 8, 1.5)
        s.text(40, y + 55, val, 19 if mono else 20, NAVY, 400, "start", mono=mono)
    return s.render()


def g_bench_states():
    s = Svg(1720, 300)
    states = [("★", "Good", "result matches the ground-truth SQL (Chat) or the evaluation note (Agent)", GREEN),
              ("★", "Manual review needed", "no SQL answer, or no confident match: an author decides Good or Bad", YELLOW),
              ("★", "Bad", "query error, empty result, extra columns, a different value", LAVA),
              ("⊙", "Run unsuccessful", "the evaluation itself didn't complete: check the question and ground truth", SLATE)]
    for i, (icon, t, sub, color) in enumerate(states):
        x = 3 + i * 429
        s.rect(x, 20, 400, 260, "#fff", color, 16, 3)
        s.text(x + 50, 95, icon, 52, color, 700)
        s.text(x + 90, 90, t, 27, NAVY, 700, "start")
        words, line, yy = sub.split(), "", 150
        for w in words:
            if len(line) + len(w) > 30:
                s.text(x + 30, yy, line.strip(), 22, "#33464E", 400, "start")
                line, yy = "", yy + 34
            line += w + " "
        s.text(x + 30, yy, line.strip(), 22, "#33464E", 400, "start")
    return s.render()


def g_loop():
    s = Svg(1720, 290)
    steps = [("Monitoring tab", "questions · 👍 / 👎 · reviews"), ("Triage", "data? context? ambiguity?"),
             ("Fix the knowledge store", "expression › example › text"), ("Add to benchmarks", "the question + variations"),
             ("Run all benchmarks", "check for regressions")]
    for i, (t, sub) in enumerate(steps):
        x = i * 350
        s.box(x, 40, 310, 150, t, sub, "#fff" if i % 2 else OAT2, TEAL if i in (0, 4) else LINE, NAVY, 25, 14)
        if i < 4:
            s.line(x + 314, 115, x + 344, 115, MUTED, 4)
    s.add(f'<path d="M1550,196 C1550,236 160,236 160,196" fill="none" stroke="{CORAL}" stroke-width="4" stroke-dasharray="10 8" marker-end="url(#ah-{CORAL[1:]})"/>')
    s.text(860, 278, "repeat: feedback never changes the agent on its own; authors review first", 20, CORAL, 500)
    return s.render()


def g_polling():
    s = Svg(1720, 300)
    s.line(60, 150, 1660, 150, NAVY, 3)
    s.text(60, 120, "POST message", 20, NAVY, 700, "start")
    s.add(f'<circle cx="60" cy="150" r="10" fill="{NAVY}"/>')
    x, delay, labels = 60, 2, []
    while x < 1500:
        x += delay * 22
        s.add(f'<circle cx="{x}" cy="150" r="7" fill="{TEAL}"/>')
        labels.append((x, delay))
        delay = min(60, int(delay * 1.6) + 1)
    for x2, d in labels[:6]:
        s.text(x2, 190, f"{d}s", 17, MUTED, 500)
    s.text(1660, 120, "stop at 10 min", 20, LAVA, 700, "end")
    s.add(f'<line x1="1660" y1="132" x2="1660" y2="168" stroke="{LAVA}" stroke-width="4"/>')
    s.text(60, 250, "GET message status: start every 1–5 s, back off exponentially to 60 s, stop on COMPLETED · FAILED · CANCELLED", 22, NAVY, 400, "start")
    return s.render()


def g_slack():
    s = Svg(820, 470)
    s.rect(0, 0, 820, 470, "#fff", LINE, 14)
    s.rect(0, 0, 820, 52, "#3F0E40", "#3F0E40", 14)
    s.text(26, 34, "# fleet-parts-analytics", 21, "#fff", 700, "start")
    s.rect(26, 80, 46, 46, SLATE, SLATE, 10)
    s.text(90, 98, "Dana (Fleet ops)", 19, NAVY, 700, "start")
    s.text(90, 126, "@Genie which region grew margin most in December?", 20, NAVY, 400, "start")
    s.rect(26, 160, 46, 46, LAVA, LAVA, 10)
    s.text(49, 192, "✦", 24, "#fff", 700)
    s.text(90, 178, "Genie", 19, NAVY, 700, "start")
    s.rect(90, 192, 700, 200, OAT2, OAT2, 12)
    s.text(110, 232, "The Midwest: margin 33.1% (+2.4 pts vs November).", 20, NAVY, 400, "start")
    for i, (r, v) in enumerate([("Midwest", 300), ("West", 250), ("Northeast", 210), ("South", 180)]):
        s.rect(110, 252 + i * 32, v, 22, TEAL if i == 0 else SLATE, "none", 4, 0)
        s.text(120 + v, 270 + i * 32, r, 16, MUTED, 500, "start")
    s.text(110, 425, "answers from Genie One or a pinned Genie Agent · your Unity Catalog permissions", 16, MUTED, 400, "start", italic=True)
    return s.render()


def g_lab():
    s = Svg(1720, 560)
    nbs = [("01", "create_genie_spaces", "baseline agent: tables only"), ("02", "metric_views", "governed KPIs + an agent on them"),
           ("03", "knowledge_store", "expressions, joins, examples, synonyms"), ("04", "genie_evals_benchmarks", "benchmark suites, run, fix"),
           ("05", "genie_code_skills", "build an agent with Genie Code"), ("06", "compare_genie_spaces", "baseline vs metric view vs curated"),
           ("07", "monitoring_observability", "feedback, audit logs, query history"), ("08", "cicd_genie_spaces", "promote dev → prod as code")]
    for i, (n, name, sub) in enumerate(nbs):
        col, row = i % 4, i // 4
        x, y = col * 432, 20 + row * 190
        s.rect(x, y, 408, 160, "#fff", TEAL if i in (2, 3) else LINE, 14, 2)
        s.text(x + 26, y + 56, n, 40, CORAL, 700, "start")
        s.text(x + 92, y + 52, name, 20, NAVY, 700, "start", mono=True)
        s.text(x + 26, y + 112, sub, 21, MUTED, 400, "start")
    s.rect(0, 420, 1720, 120, OAT2, OAT2, 14)
    s.text(30, 466, "Data (read-only): dbx_workshop_dev.shared · lab_gold_daily_dealer_sales_fact, lab_gold_category_region_fact,", 21, NAVY, 400, "start")
    s.text(30, 502, "lab_silver_dealers_dim, lab_silver_parts_dim  ·  yours: genie_mv_dealer_sales, genie_mv_category_sales, genie_workshop_config", 21, NAVY, 400, "start")
    return s.render()


# --------------------------------------------------------------------------------------------- slides

def split(left, right, cls=""):
    return f'<div class="split {cls}"><div>{left}</div><div>{right}</div></div>'


SLIDES = [
    title_slide(
        "Genie Agents<br>Workshop +<br>Best Practices", "Presenters: Taylor Isbell, Brien Blandford-Levy",
        "Welcome. Over the next hour we'll cover how Genie Agents work, where they fit next to dashboards, Genie Code and "
        "Genie One, and the best practices for curating an agent people trust. Then you'll build three agents yourself "
        "in the hands-on lab. Introduce Taylor and Brien, and say this deck reflects the product as of November 2026."),

    content("Agenda", "Two days: slides first, then the hands-on lab", split(
        "<h3>Day 1 · What is Genie, and how to build an agent</h3>" + bullets([
            "<b>Section 1</b> · Building your first Genie Agent: what Genie is; Genie Agents vs Genie Code vs Genie One; "
            "billing; pairing with dashboards",
            "<b>Section 2</b> · What's new with Genie: Ontology and the Ontology Manager, Slack and Teams, mobile and desktop, Genie Workbench",
            "<b>Lab</b> · <code>genie/01_create_genie_spaces</code>: build a baseline agent (UI and code), query it, "
            "give feedback",
        ], "sm"),
        "<h3>Day 2 · Deep dive: curating agents</h3>" + bullets([
            "<b>Section 3</b> · Curating an agent people trust: clean data, tables vs metric views, the knowledge store, "
            "instructions",
            "<b>Section 4</b> · Benchmarks, monitoring and rollout",
            "<b>Lab</b> · <code>genie/02</code> to <code>08</code>: metric views, knowledge store, benchmarks, Genie Code, "
            "compare three agents, monitoring, CI/CD",
        ], "sm")),
        "Day 1 is the orientation: what Genie is, what changed recently, and building a first agent end to end. Day 2 "
        "is the curation deep dive: the knowledge store, metric views, benchmarks and running an agent in production. "
        "The lab follows the notebooks in genie/ of the workshop repo. Use the section bar at the bottom of the screen "
        "to jump between sections."),

    section_slide("Day 1 · Section 1", "Building your first Genie Agent", [
        "Where Genie fits in the platform", "Genie Agents, Code and One", "Talk with your data, and trust it",
        "Pair Genie with dashboards",
    ], "Section 1 goes with the first block of the lab: what a Genie Agent is, where it fits next to Genie Code, Genie "
       "One and dashboards, and why trust is the bar it has to clear. Then we build the baseline agent on tables."),

    content("Genie in the Data Intelligence Platform", "Genie is the heart of the agentic work layer", g_platform(),
            "Genie sits at the agentic work layer, grounded by Unity Catalog. Today is about Genie Agents, and how they "
            "relate to Genie One and Genie Code. Note for presenters: the layer names come from the corporate platform "
            "deck; use the current corporate slide if it has changed. Genie Ontology, the shared business-context "
            "layer in Unity Catalog, went GA on November 11, 2026."),

    content("Genie Agents vs Genie Code vs Genie One", "Three products, one Genie", with_asof(cards([
        ("Genie Agents", ["<b>For data teams and domain experts</b>", "Curated, domain-specific agents: trusted data, metrics and business rules",
                          "Formerly <i>Genie spaces</i> (renamed July 2026)", "Chat or <b>Agent mode</b> (multi-step research)"], "accent"),
        ("Genie Code " + st("ga"), ["<b>For technical users and builders</b>", "Generates and runs code; builds pipelines, dashboards and agents",
                                    "Works in notebooks, SQL, MLflow; skills and scheduled tasks", "Formerly Databricks Assistant"], ""),
        ("Genie One", ["<b>For business users</b>", "One place to ask questions, search assets, explore dashboards, run apps",
                       "Answers draw on Genie Agents and Genie Ontology", "Slack, Teams, mobile, MCP"], "lava"),
    ])), "The question we get most. Genie Agents are what you build in this workshop: a curated, domain-specific "
         "agent. Genie One is the business user's front door across workspaces; it uses your agents. Genie Code is the "
         "agent for practitioners: it can even build a Genie Agent for you, which you'll see in notebook 05. Renames: "
         "Genie spaces became Genie Agents on July 9, 2026, and Research Agent became Agent mode in February."),

    content("What changed with billing", "Pay-as-you-go since July 8, 2026, with promotions on top", with_asof(cards([
        ("Genie One &amp; Genie Agents", '<div class="kick">for human users</div><div class="big-num green">Free</div>'
                                         "<p>through January 31, 2027 (promotion extended in August). Service-principal usage is billed.</p>", "green"),
        ("Genie Code", '<div class="kick">every user, every month</div><div class="big-num">150 DBUs</div>'
                       "<p>free allowance, resets on the 1st (≈ $10.50 in US East). Above it: <b>25% off</b> through Jan 31, 2027.</p>", "accent"),
        ("Still billed as usual", '<div class="kick">not covered by the above</div><div class="big-num lava">SQL</div>'
                                  "<p>The SQL warehouse that runs Genie's queries, and other compute, bill as normal.</p>", "lava"),
    ])), "July 8 moved Genie to pay-as-you-go: no more per-user query-per-minute caps, a monthly free allowance, and "
         "metering above it. Since then a promotion makes Genie One and Genie Agents free for human users through "
         "January 31, 2027. Genie Code keeps the 150 DBU allowance with 25% off overage. Two caveats: service principals "
         "don't get the allowance or the promotion, and the warehouse compute behind Genie's queries is billed normally. "
         "Source: Genie cost docs and the August 2026 release notes. Confirm your contract's terms with your account team."),

    content("Genie Agents: talk with your data", "Answer ad hoc structured-data questions in plain language", cards([
        ("Conversational analytics", "Ask in natural language; get SQL, a table, a chart and a summary in seconds", "accent"),
        ("Tailored to your business", "Grounded in Unity Catalog metadata, Genie Ontology and the context you curate", ""),
        ("Governed and secure", "Every query runs with the user's Unity Catalog permissions, row filters and masks", "green"),
        ("Accessible anywhere", "Dashboards, Genie One, Slack and Teams, mobile, embedding, the Conversation API and MCP", "lava"),
    ], 2), "What makes Genie different is context: it knows your schemas, comments, keys and relationships from "
           "Unity Catalog, and learns from the business context in Genie Ontology. Answers respect each user's "
           "permissions, so the same agent can serve people with different access."),

    content("Tailor a Genie Agent to your data and business", "Context in three layers", g_tailor(),
            "First, Genie learns from what's already in the platform. Second, authors enrich it in the agent's knowledge "
            "store. Third, authors measure accuracy with benchmarks and watch real usage in the Monitoring tab. Most of "
            "today is about doing the second and third well."),

    content("The trust challenge", "Natural-language analytics is only useful if people believe the answers", split(
        '<div class="chat"><div class="who">Sarah · marketing lead</div><div class="q">“What was our click-through rate last quarter?”</div>'
        '<div class="a">Genie: <b>8.5%</b></div><div class="doubt">“Wait, I remember celebrating when we hit 6% last quarter…”</div></div>'
        '<p class="note-s">Different campaigns? A standard calendar instead of the fiscal one? Sarah can\'t tell what went wrong, only that something feels off.</p>',
        "<h3>The real question</h3>" + bullets([
            "Not <i>can</i> Genie generate SQL, but do users trust the result enough to decide with it",
            "Without systematic evaluation, doubt compounds",
            "Users quietly go back to analysts, and the self-service investment sits unused",
        ], "sm")),
        "Keep this story in mind for the whole session. Every best practice that follows exists to prevent this moment, "
        "or to catch it before users do. Benchmarks are how you prove accuracy, not just hope for it."),

    content("AI/BI: native analytics with real-world intelligence", "Governed by Unity Catalog, powered by Databricks SQL", cards([
        ("Dashboards", "Fast, secure visual insights for the whole organization: the same KPIs, the same way, every time", "accent"),
        ("Genie Agents", "Accurate answers from AI for the ad hoc questions dashboards don't anticipate", "lava"),
    ], 2) + '<p class="note-s" style="margin-top:34px">Use both: dashboards answer the known questions, Genie the next one.</p>',
            "AI/BI is two capabilities: dashboards and Genie. They're complements: dashboards for deterministic, "
            "repeatable views; Genie for the questions that come after."),

    content("Pair Genie with dashboards", "Dashboards guide users; Genie answers the follow-ups", with_asof(split(
        g_dashboard(),
        bullets([
            "<b>Guide business users</b>: the dashboard shows which data and KPIs exist",
            "<b>Ask Genie</b> on published dashboards " + st("ga") + ": select a chart and ask a follow-up; link your curated agent",
            "<b>Explain this change</b>: right-click a change for its top drivers, run by Agent mode",
            "<b>Dashboard Insights</b> " + st("beta") + ": Genie scans the page for trends, outliers and drivers",
        ], "sm"), "wide-left")),
        "Pair every agent with a dashboard as you roll out: it tells users what domain the agent covers. Ask Genie on "
        "dashboards has been GA since July 2026 and is on by default for published dashboards; authors can link an "
        "existing Genie Agent so follow-ups use your curated context. Explain-this-change works on time series and, "
        "since April, pivot cells, bars, pies and heatmaps. Dashboard Insights is Beta, admin opt-in."),

    content("Where Genie fits in data exploration", "Pick by how deterministic the answer must be", g_where_fits(),
            "Quick question about one table: ask in the UC sample-data tab. Exploring a complex model: a Genie Agent on "
            "tables. Governed KPIs with flexible grouping: a Genie Agent on metric views. Fixed KPIs every time: a "
            "dashboard. Genie One spans all of them for business users."),

    section_slide("Day 1 · Section 2", "What's new with Genie", [
        "New since September", "Genie One in Slack and Teams", "Genie One mobile and desktop", "Genie Workbench",
    ], "Section 2 closes Day 1 with a quick tour of what has shipped since September and where Genie now shows up. "
       "Then the Day 1 lab: build the baseline agent in genie/01_create_genie_spaces."),

    content("What's new since September", "Genie Agents and Genie One, September–November 2026", with_asof(table(["Capability", "Status", "Since"], [
        ["Genie Ontology: shared business context, OntoRank, Ontology snippets", st("ga"), "Nov 11"],
        ["Ontology Manager: explore, curate and govern the Ontology (graph and domain views)", st("beta", "Beta soon"), "Nov 11"],
        ["Genie One in Slack and Microsoft Teams", st("ga"), "Nov 9"],
        ["Benchmarks run questions in parallel · custom identity claims in monitoring", st("ga", "Released"), "Nov 5"],
        ["Analyze unstructured files in UC volumes, with page-level citations", st("pp"), "Nov 2"],
        ["Guided agent creation · faster file retrieval (Beta)", st("ga", "Released"), "Oct 29"],
        ["Conversation file uploads", st("ga"), "Oct 16"],
        ["Flash (speed-first) · upgraded Agent mode models", st("beta"), "Oct 15"],
        ["External tools through MCP connectors in Genie Agents", st("beta"), "Oct 8"],
        ["Genie One MCP server <code>system.ai.genie_one_mcp</code> (Beta endpoint retires Nov 30)", st("ga"), "Sep 25"],
    ], "compact")),
        "A snapshot of the release notes since the original deck. Highlights: Genie Ontology GA, with the Ontology "
        "Manager announced alongside it (coming soon in Beta): the visual interface where teams explore entities and "
        "relationships, spot gaps, review what agents learned and promote it into governed Unity Catalog Pages. Slack and Teams GA, "
        "file uploads GA, and unstructured files in volumes in Public Preview, so agents can cite documents next to "
        "tables. If you use the old Genie MCP endpoint, /api/2.0/mcp/genie, migrate to the Unity Gateway service "
        "before November 30. Releases roll out over a week or more, so a workspace may lag."),

    content("Genie One in Slack and Microsoft Teams", "Genie where work already happens", with_asof(split(
        bullets([
            "<b>Generally available</b> since November 9, 2026",
            "Slack: DM Genie or mention <code>@Genie</code> in a channel or group DM",
            "Teams: chat with the app or mention <code>@Databricks Genie</code>",
            "Answers from Genie One, or a <b>pinned Genie Agent</b>",
            "Governed: each user sees only what they're authorized to access",
        ], "sm"), g_slack())),
        "Slack and Teams went GA on November 9. Admins can pin a specific Genie Agent so the channel uses your curated "
        "context. Responses are governed per user, so the same channel can serve people with different access."),

    content("Genie One mobile app", "Databricks Genie on iOS and Android", with_asof(cards([
        ("Get it " + st("pp"), ["Search <b>Databricks Genie</b> in the App Store or Google Play", "iPhone, iPad and Android devices", "Public Preview since June 15, 2026"], "accent"),
        ("What it does", ["Ask data questions, mobile dashboards, dashboard chat", "Databricks Apps and scheduled tasks", "Switch workspaces"], ""),
        ("Good to know", ["Push notifications for scheduled tasks: iOS only", "MCP connections carry over from the web; configure them there", "Org credentials and network rules still apply"], "lava"),
    ])), "Mobile is still Public Preview. It's the same governed Genie, with your organization's sign-in and network "
         "configuration."),

    content("Genie One desktop app", "Genie One for macOS and Windows, without a browser", with_asof(split(
        bullets([
            st("beta") + " A native app for <b>macOS</b> and <b>Windows</b>; installers in the docs",
            "Same Genie One as the web: data questions, threads and documents, Genie Agents, UC tables, Databricks Apps",
            "Sign in with <b>Log in</b> (account › workspace) or <b>Enter workspace link</b>; it remembers your workspace",
            "Back / Forward / Reload title bar · updates itself · on macOS a <b>dock badge</b> for unread threads",
            "No admin switch for the app: manage it like any other client (e.g. MDM)",
        ], "sm"),
        f'<figure class="shot"><img alt="Genie One desktop app on macOS, with the unread badge on its dock icon" '
        f'src="data:image/png;base64,{kit.b64(ASSETS_IMG / "genie_one_desktop.png", "&#10;")}">'
        '<figcaption>Genie One desktop on macOS: note the unread badge on the dock icon. '
        'Screenshot: Databricks docs</figcaption></figure>', "shot-split")),
        "New since September: the Genie One desktop app, in Beta for macOS and Windows. It's the same Genie One as the "
        "browser, with desktop conveniences: window navigation, automatic updates, and on macOS a dock badge for "
        "unread threads, visible in the screenshot. Links to Genie One pages open in the app; anything else in the "
        "workspace, or outside it, opens in the default browser. There's no admin control specific to the app; access "
        "is governed like any other client, so organizations that need to restrict it use their device management. "
        "Source: Genie One desktop docs, updated November 10, 2026; the screenshot is from that page."),

    content("Genie Workbench", "Create, score and optimize Genie Agents (open source Databricks App)", split(
        bullets([
            "<b>Create</b> agents from business requirements and UC data sources",
            "<b>Score</b> an agent's quality with an instant rule-based IQ scan",
            "<b>Auto-optimize</b> with a benchmark-driven pipeline (Genie Space Optimizer)",
            "Track scan history, sessions and optimization state",
            "Install from a notebook in a Git folder (serverless, environment 5)",
        ], "sm"),
        '<div class="card accent"><div class="kick">github</div><h4>databricks-solutions/<br>databricks-genie-workbench</h4>'
        "<p>Field-built, not a supported product. Deploys as a Databricks App with Lakebase for state.</p></div>"),
        "Workbench is a field-built Databricks App, actively maintained. It's useful for scoring a set of agents and "
        "for benchmark-driven optimization. Position it as a solutions accelerator, not a product feature."),

    section_slide("Day 2 · Section 3", "Curating an agent people trust", [
        "Start with clean, focused data", "Tables or metric views", "The knowledge store", "Instructions, last",
    ], "Now how to build agents well. The order matters: data first, then structured context in the knowledge "
       "store, then text instructions only for what's left."),

    content("Start with clean, well-curated data", "Table metadata is the most effective context", cards([
        ("Choose focused datasets", "A small, non-conflicting set of UC tables; remove columns users won't analyze", "accent"),
        ("Use curated data", "Gold tables, pre-aggregated views or metric views: fewer joins, simpler math, fewer tokens", ""),
        ("Comments and synonyms", "Describe every column with example values and the words business users say", ""),
        ("Define relationships", "Primary and foreign keys in Unity Catalog, or pre-join into views", "green"),
    ], 2), "Clean data avoids wrong answers and long thinking times while the model infers. Remove irrelevant columns, "
           "redundant identifiers and non-analytical fields. Add comments with descriptions, example values and synonyms "
           "('sales' vs 'orders'). Define PK/FKs so Genie doesn't have to guess relationships. Tip from the docs: review "
           "AI-generated descriptions before you rely on them."),

    content("Choose between tables and metric views", "They serve different purposes in Genie", split(
        "<h3 class='good-h'>Metric views</h3>" + bullets([
            "Business metrics governed in Unity Catalog, defined once, reused everywhere",
            "Deterministic by design; generated queries are simple to read",
            "Group by any dimension: suits Genie's ad hoc nature",
            "<span class='bad'>Trade-offs:</span> you maintain the YAML; limited to the dimensions you add; KPIs not in the view can still be guessed",
        ], "sm"),
        "<h3>Tables</h3>" + bullets([
            "Simple to start and expand: add tables to an agent",
            "Good for complex data models: Genie joins as needed",
            "Needs the best practices: descriptions, PK/FK, expressions",
            "<span class='bad'>Trade-offs:</span> metrics live in instructions, examples and functions in one agent; less reusable and less deterministic",
        ], "sm")) + g_tables_vs_mv(),
            "Metric views move logic left into Unity Catalog: the formula for margin percent lives in one place and "
            "every consumer uses it. Tables are faster to start with and better for exploration. In the lab you'll build "
            "both and compare them on the same questions (notebooks 02 and 06)."),

    content("Select a focused topic and data", "Curate in Unity Catalog, start small", with_asof(split(
        bullets([
            "<b>Aim for five or fewer tables</b>: the narrower, the better",
            "Hard limit: <b>50</b> tables, views or metric views per agent",
            "One audience and one purpose per agent",
            "Hide confusing or unused columns",
            "Pre-join complex relationships into views or metric views",
        ], "sm"),
        bullets([
            "<b>Think like the business</b>: include only fields users analyze",
            "<b>Document everything</b>: table and column descriptions",
            "<b>Have a domain expert build it</b>: an SQL-proficient analyst",
            "<b>Start with the smallest setup</b>, expand from feedback",
        ], "sm"))),
        "The current docs still say aim for five or fewer tables, with a hard limit of 50. The original deck said 3 to "
        "7; the spirit is the same. If you need more, pre-join into views or metric views."),

    content("Example SQL queries", "Teach complete question-answering patterns", with_asof(split(
        bullets([
            "A business question paired with its SQL; Genie reuses it or learns the pattern",
            "<b>Parameters</b> (<code>:region</code>, typed String / Date / Decimal / …) make one example cover many questions",
            "<b>Usage guidance</b>: say when the example applies",
            "<b>Trusted assets</b>: parameterized examples and UC SQL functions return verified answers",
            "Use them for complex, multi-part or ambiguous prompts",
        ], "sm"),
        code("-- Question: What is net revenue for dealers in :state?\n"
             "SELECT ROUND(SUM(s.net_revenue), 2) AS net_revenue\n"
             "FROM lab_gold_daily_dealer_sales_fact s\n"
             "JOIN lab_silver_dealers_dim d USING (dealer_id)\n"
             "WHERE d.state = :state"))),
        "Example SQL is the script for your most important questions. Parameters turn one example into a family of "
        "questions, and parameterized examples and UC functions become trusted assets: the answer is marked as verified. "
        "Genie also suggests popular queries from your workspace's history for authors to review and save."),

    content("Knowledge store: local data prep", "Fix metadata inside the agent, without UC permissions", split(
        bullets([
            "<b>Hide columns</b> that confuse Genie: no new view needed",
            "<b>Edit table and column descriptions locally</b>; Reset restores UC",
            "<b>Column synonyms</b> for cryptic names",
            "<b>Prompt matching</b>: format assistance and entity matching (value dictionaries) for string columns",
            "Changes stay in the agent; Unity Catalog metadata is untouched",
        ], "sm"), g_hide_columns()),
        "The knowledge store is the agent's own curated layer. Hiding columns is ideal when you can't create views. "
        "Local descriptions let people without ALTER on the table still add context. Synonyms explain cryptic names. "
        "Prompt matching samples values so Genie maps 'platinum dealers' to dealer_tier = 'Platinum'; entity matching "
        "stores up to 1,024 distinct values for up to 120 string columns. Path: Configure, Sources, select a table."),

    content("Knowledge store: joins", "Table relationships Genie doesn't have to guess", split(
        bullets([
            "<b>UC primary / foreign keys</b> are saved as joins automatically",
            "<b>Define joins in the agent</b> when you can't add keys, or relationships are complex",
            "Set the <b>relationship type</b>: many-to-one, one-to-many, one-to-one",
            "<b>Suggested joins</b>: Genie proposes joins it learns from conversations",
            "Self-joins and multiple joins get aliases automatically",
        ], "sm"), g_joins()),
        "Before, users without ALTER TABLE couldn't define PK/FK relationships. Now they define them in the agent: "
        "Configure, Examples, Add, Joins. The cardinality matters: it tells Genie a join won't multiply rows. Suggested "
        "joins, once a roadmap item, now come from conversations and from authors' thumbs-up."),

    content("Knowledge store: measures", "Exactly how to calculate a KPI", split(
        bullets([
            "Aggregations that summarize data: total revenue, average order value, active customers, YoY growth",
            "Name, SQL, synonyms and usage instructions",
            "Genie retrieves the relevant ones per prompt",
            "More knowledge in fewer tokens than example SQL or text",
        ], "sm"),
        g_expression("Measure", "margin_percent", "ROUND(100 * SUM(margin) / SUM(net_revenue), 2)", "margin %, margin rate",
                     "Never average daily margin percents")),
        "Measures, filters and fields are the SQL expressions of the knowledge store: the 'SQL primitives' the original "
        "deck listed as coming are now here. Think of example SQL as a script for common questions, and expressions as "
        "the bullet points: reusable definitions Genie combines. Structured input fields remind authors to give a name, "
        "the SQL and synonyms."),

    content("Knowledge store: fields (dimensions)", "Row-level attributes to slice, filter and categorize", split(
        bullets([
            "<code>CASE WHEN …</code>: categorize with if/then/else logic",
            "<code>CONCAT(a, '-', b)</code>: build a label",
            "<code>DATE_TRUNC('WEEK', order_date)</code>: date parts and buckets",
            "<code>DATEDIFF(…)</code>: days between two dates",
            "<code>COALESCE(col, 'Unknown')</code>: null handling",
        ], "sm"),
        g_expression("Field", "order_size_band", "CASE WHEN net_revenue >= 5000 THEN 'Large' …", "deal size, order band",
                     "Use for questions about large / medium / small orders")),
        "Fields, also called dimensions, are per-row: mileage buckets, repair-order types, performance tiers. In the "
        "API they're instructions.sql_snippets.expressions. Same structure as a measure: name, SQL, synonyms, "
        "instructions."),

    content("Knowledge store: filters", "Named conditions business users say out loud", split(
        bullets([
            "Boolean conditions: <i>large orders</i>, <i>active dealers</i>, <i>last fiscal quarter</i>",
            "One definition instead of every author re-typing the WHERE clause",
            "Pair with synonyms: 'big deals' → the same filter",
        ], "sm"),
        g_expression("Filter", "platinum_dealers", "dealer_tier = 'Platinum'", "top-tier dealers, platinum",
                     "Apply when users ask about premium or top dealers")),
        "Filters are the third expression type. They're especially useful for business definitions of time: a fiscal "
        "quarter is a filter, not a paragraph of text instructions."),

    content("Knowledge store: suggestions from usage", "Genie mines knowledge from feedback and metadata", split(
        bullets([
            "When an author gives a 👍 or downloads results, Genie may <b>suggest new SQL expressions and joins</b>",
            "Genie also analyzes Unity Catalog metadata for suggestions",
            "Suggestions persist until an author <b>reviews and saves</b> them in the knowledge store",
            "Nothing changes in the agent without an author's approval",
        ], "sm"),
        '<div class="card accent"><div class="kick">suggested · from your 👍</div><h4>Measure: avg_revenue_per_order</h4>'
        "<p><code>SUM(net_revenue) / NULLIF(SUM(orders), 0)</code></p>"
        '<p style="margin-top:16px"><b>Save</b> · Edit · Dismiss</p></div>'),
        "In the original deck this was 'coming': auto-suggested instructions that populate as users talk to Genie. It "
        "shipped as knowledge mining: persistent suggestions from thumbs-up and result downloads (February 2026). "
        "Authors review and save; suggestions never auto-apply."),

    content("The knowledge store, in priority order", "Limits and what counts toward them", with_asof(split(
        table(["Use", "For", "Why"], [
            ["1 · SQL expressions", "metrics, filters, dimensions", "structured, reliable, cheap in tokens"],
            ["2 · Example SQL", "complex, multi-part, ambiguous", "full patterns Genie can reuse"],
            ["3 · Text instructions", "what SQL can't say", "global context, formatting, clarification"],
        ], "compact"),
        bullets([
            "<b>200 knowledge-store snippets</b> per agent: table descriptions, joins, SQL expressions",
            "<b>100 instructions</b>: each example SQL, each SQL function, and the text block count one each",
            "Column descriptions, synonyms and prompt matching don't count",
        ], "sm"))),
        "This is the single most useful slide to photograph. The docs are explicit: SQL expressions first because "
        "structured SQL definitions are more reliable and maintainable than text; example SQL for complex prompts; text "
        "instructions as a last resort. The limits: 200 snippets and 100 instructions per agent."),

    content("Finally, general instructions", "Only when metadata, expressions or examples can't do it", '<div class="do-dont">'
            '<div class="col do"><div class="pill">DO</div><ul>'
            "<li><b>Teach when to ask for clarification</b>when a prompt is missing context</li>"
            "<li><b>Add formatting rules</b>rounding, language, number of rows</li>"
            "<li><b>Be concise and direct</b>“When the user… make sure to…”, “Always include…”</li>"
            "<li><b>Organize as a list</b>easier for collaborators and for Genie</li>"
            "<li><b>Summaries</b>under the heading “Instructions you must follow when providing summaries”</li>"
            "</ul></div>"
            '<div class="col dont"><div class="pill">DON\'T</div><ul>'
            "<li><b>Overload the text</b>it isn't filtered per prompt; it uses context in every question</li>"
            "<li><b>Write conflicting rules</b>text says round to 2, examples must too</li>"
            "<li><b>Enumerate column values</b>use prompt matching and value dictionaries</li>"
            "<li><b>Put SQL logic in text</b>use SQL expressions and example SQL</li>"
            "</ul></div></div>",
            "Text instructions are the last resort. They're applied to every prompt, so too many crowd out context, "
            "especially in long conversations. Keep them short and as a list. New since the original deck: summary "
            "behavior is controlled only by text instructions, under that exact heading. The 'SQL primitives coming' "
            "note is obsolete: use SQL expressions."),

    content("Clarification questions: a four-part pattern", "Place it at the end of the general instructions", '<div class="pattern">'
            + "".join(f'<div class="card"><div class="num">{n}</div><h4>{t}</h4><p>{b}</p></div>' for n, t, b in [
                ("01", "Trigger condition", "the topic or scenario: “When users ask about X…”"),
                ("02", "Missing details", "what must be present: “…but don't include Y…”"),
                ("03", "Required action", "“…you must ask a clarification question first”"),
                ("04", "Example question", "the exact wording: “Please specify…”")])
            + '</div><div class="quote">“When users ask about <b>sales performance breakdown</b> [01] but don\'t include <b>time range, '
              'sales channel or KPIs</b> [02], you <b>must ask a clarification question first</b> [03]. For example: '
              '<b>‘Please specify the time range and sales channel you are looking for.’</b> [04]”</div>',
            "Vague rules like 'ask clarification questions when asked about sales' don't work. All four parts, and put "
            "them at the end of the general instructions, which is the current docs' recommendation."),

    section_slide("Day 2 · Section 4", "Benchmarks, monitoring and rollout", [
        "Benchmarks", "Monitoring and feedback", "Staged rollout", "Conversation API",
    ], "Building the agent is half the job. Now: how you know it's right, and how you keep it right after launch."),

    content("Genie benchmarks: what and why", "Curated test questions with gold-standard answers", with_asof(split(
        bullets([
            "Questions plus a <b>SQL answer</b> (or <b>Generate SQL</b>) and an optional <b>evaluation note</b>",
            "Up to <b>500</b> benchmark questions per agent",
            "<b>Chat mode</b> compares result sets with your SQL; <b>Agent mode</b> uses an LLM judge with the evaluation note",
            "<b>Run all benchmarks</b> or <b>Run selected</b>; questions now run in parallel (Nov 2026)",
            "Add any chat answer with <b>⋮ › Add as benchmark</b>",
        ], "sm"),
        cards([("Why", ["validate answers automatically", "catch regressions after every change", "show stakeholders measured accuracy before rollout"], "green")], 1))),
        "Benchmarks are how you replace hope with numbers. Add the 10 to 20 questions the business cares most about, "
        "with ground-truth SQL, then add phrasing variations. Run them after every change to the agent. New this fall: "
        "questions run in parallel, so a run finishes much faster. The button in the UI reads Run all benchmarks; the "
        "docs call it Run benchmarks."),

    content("Reading benchmark results", "Evaluations tab › select a run", with_asof(g_bench_states() + bullets([
        "Resolve <b>Manual review needed</b> by comparing model output with ground truth, then marking Good or Bad",
        "Per-question result data stays for <b>one week</b>; the generated and ground-truth SQL remain",
        "<b>Analyze with Genie</b>: from a run, launch <b>Genie Code</b> to analyze it; it groups the failures, separates "
        "context gaps from questionable ground truth, and suggests instruction or context fixes for you to review and save",
    ], "sm")),
        "Good means the result matched. Manual review needed means the scorer couldn't decide: no SQL answer, or no "
        "confident match; it doesn't mean wrong. Bad means a definite mismatch. A run can also be unsuccessful or "
        "paused, which is about the run, not the answer. Accuracy shows once the review items are resolved. Then use "
        "Analyze with Genie on the run: Genie Code reads the expected answers, the generated output and the agent's "
        "context, and proposes fixes. Nothing is saved until you accept it."),

    content("The Monitoring tab", "In the agent for one agent; in system tables for all of them", with_asof(split(
        "<h3>In the Monitoring tab</h3>" + bullets([
            "Every question and response; filter by time, rating, user or status",
            "<b>Weekly digest</b>: message volume, active users, 👍 / 👎",
            "<b>Analyze Agent Usage</b> launches <b>Genie Code</b> over the last six months of messages, feedback and "
            "issues; answers cite the conversations",
            "<b>Request review</b> and reviewable conversations; needs <b>CAN MANAGE</b>",
            "Feedback never changes the agent by itself: authors review first",
        ], "sm"),
        "<h3>At scale: system tables</h3>" + table(["What", "Table · key"], [
            ["Questions, 👍 / 👎, review requests, API errors",
             "<code>system.access.audit</code><br><code>service_name = 'aibiGenie'</code> · <code>request_params.space_id</code>"],
            ["Genie's SQL: status, duration, warehouse",
             "<code>system.query.history</code><br><code>query_source.genie_space_id</code>"],
        ], "compact") + '<div class="codebox block mini">SELECT query_source.genie_space_id AS agent,\n'
        '       count(*) AS statements,\n'
        "       count_if(execution_status = 'FAILED') AS failed\n"
        'FROM system.query.history\n'
        'WHERE query_source.genie_space_id IS NOT NULL\n'
        'GROUP BY ALL</div>'
        '<p class="note-s">One row per agent across the account; aggregate per agent and day before joining the two '
        'tables. Lab: <code>genie/07_monitoring_observability</code>.</p>')),
        "The Monitoring tab is the author's view of one agent: what people ask, how Genie behaved, and the feedback. "
        "Analyze Agent Usage, in the weekly digest, hands the last six months of messages, feedback and issues to Genie "
        "Code and gives you a summary with citations back to the conversations. To see every agent at once, use system "
        "tables: audit logs (service aibiGenie, keyed by request_params.space_id) for questions, ratings, review "
        "requests and API errors, and query history (query_source.genie_space_id) for the SQL Genie ran. There's no "
        "message-level join between them, so aggregate per agent and day first. Query history lands within about an "
        "hour. Lab notebook 07 builds these queries."),

    content("Manage feedback: audit logs and alerts", "Know about a 👎 before the user escalates", split(
        bullets([
            "<b>Audit logs</b> in <code>system.access.audit</code>, service <code>aibiGenie</code>",
            "<b>Databricks SQL alerts</b> on those events email the team: review requests, 👎 spikes",
            "<b>Continuous improvement</b>: add the question to benchmarks, improve context, rerun",
        ], "sm"),
        table(["Event", "action_name"], [
            ["Message (UI)", "<code>createConversationMessage</code>"],
            ["Message (API)", "<code>genieCreateConversationMessage</code>"],
            ["Rating 👍 / 👎", "<code>updateConversationMessageFeedback</code>"],
            ["Review request", "<code>createConversationMessageComment</code>"],
        ], "compact")) + g_loop(),
        "Audit events let you build alerts. Note the action names: ratings are updateConversationMessageFeedback, and "
        "review requests are createConversationMessageComment. Notebook 07 in the lab queries these and query history."),

    content("Genie rollout plan", "Three stages, then repeat the last one", cards([
        ("1 · Self-validation", ["Identify 10–20 key business questions and teach Genie to answer them", "Benchmark them; test ad hoc questions yourself"], "accent"),
        ("2 · Staged rollout", ["A small group of trusted users first, then expand", "Guide users: pair with a dashboard, sample questions, a short guide", "Promote dev → prod with Declarative Automation Bundles"], ""),
        ("3 · Ongoing iteration", ["Monitoring tab and audit logs for prompts and feedback", "Add to benchmarks, improve context, rerun benchmarks, repeat"], "green"),
    ]), "First, self-validation: data teams test the agent themselves. Second, a staged rollout to trusted users, "
        "with guidance on what to ask. Testers should add clarifications in chat when an answer is wrong and upvote the "
        "final query when it's right. Third, iterate forever. Business users must be members of the agent's workspace. "
        "Notebook 08 shows promotion between environments as code."),

    content("Conversation API best practices", "When you embed Genie in your own app", with_asof(split(
        bullets([
            "<b>Queue requests</b>: the API doesn't retry for you; handle <code>429</code> with backoff",
            "<b>Poll adaptively</b>: start every 1–5 s, back off to 60 s, stop after 10 min",
            "<b>Stop on a final status</b>: COMPLETED, FAILED or CANCELLED",
        ], "sm"),
        bullets([
            "<b>New conversation per user session</b>; keep it for that session's follow-ups",
            "<b>Agent mode</b> streams responses (Server-Sent Events) instead of polling",
            "One backend poller per message, shared by all clients",
        ], "sm")) + g_polling()),
        "The polling guidance changed: the current API guide says poll every 1 to 5 seconds initially, back off "
        "exponentially to a minute, and stop after 10 minutes. The original deck said 5 to 10 seconds with backoff "
        "after two minutes. There's no published per-workspace questions-per-minute number any more; plan for 429s "
        "and confirm capacity with the account team for high-volume apps. Use one backend poller per message."),

    content("Relevant documentation", "Bookmark these", '<ul class="links">' + "".join(
        f'<li><a href="{u}">{t}</a><span class="url">{u.replace("https://", "")}</span></li>' for t, u in [
            ("Curate an effective Genie Agent", "https://docs.databricks.com/aws/en/genie-agents/best-practices"),
            ("Tune Genie Agent quality (knowledge store)", "https://docs.databricks.com/aws/en/genie-agents/tune-quality"),
            ("Test and monitor a Genie Agent", "https://docs.databricks.com/aws/en/genie-agents/monitor"),
            ("Use the Genie Agents API", "https://docs.databricks.com/aws/en/genie-agents/conversation-api"),
            ("Genie One desktop app (Beta)", "https://learn.microsoft.com/en-us/azure/databricks/genie-one/desktop"),
            ("Embed a Genie Agent in an external app", "https://docs.databricks.com/aws/en/genie-agents/embed"),
            ("Genie costs", "https://docs.databricks.com/aws/en/genie/monitor-cost"),
            ("Genie app in Microsoft Teams", "https://docs.databricks.com/aws/en/integrations/msft-teams"),
            ("Genie audit events", "https://docs.databricks.com/aws/en/ai-bi/admin/audit"),
            ("AI/BI and Genie One release notes 2026", "https://docs.databricks.com/aws/en/ai-bi/release-notes/2026"),
            ("Blog: Genie One, Genie Agents and Genie Ontology", "https://www.databricks.com/blog/introducing-genie-one-genie-ontology-and-genie-agents"),
            ("Blog: Production-ready Genie spaces, and trust", "https://www.databricks.com/blog/how-build-production-ready-genie-spaces-and-build-trust-along-way"),
            ("Genie Workbench", "https://github.com/databricks-solutions/databricks-genie-workbench"),
        ]) + "</ul>",
            "All links are current docs pages. The workshop notebooks live in the repo linked on the next slide."),

    content("Hands-on lab", "genie/ in the workshop repo · Apex Motorsports Parts data", g_lab()
            + '<p class="note-s">Repo: github.com/blandfbt/spark-dos-donts-workshop (genie/) · based on github.com/dariakrasavina/genie-agents-workshop</p>',
            "Everyone builds three agents on the same data and proves with benchmarks that curation is what earns trust: "
            "a tables-only baseline (01), a metric-view agent (02) and a knowledge-store agent (03). The data is the gold "
            "layer of the bronze-to-gold lab, prebuilt read-only in dbx_workshop_dev.shared; everything you create goes "
            "to your own schema. Set USER_SCHEMA in CONFIG first. In 04, click Run all benchmarks for each agent."),

    closing_slide("Thank you. Questions, then on to the lab: open genie/01_create_genie_spaces."),
]


# Section selector: one button per section slide, grouped by day; the current section is highlighted.
SHOT_CSS = """
.split.shot-split{grid-template-columns:1.15fr .85fr;align-items:start}
figure.shot{margin:0;display:flex;flex-direction:column;align-items:center}
figure.shot img{height:600px;width:auto;border-radius:14px;box-shadow:0 10px 30px rgba(27,49,57,.18);border:1px solid #DCE0E2}
.codebox.block.mini{font-size:18px;line-height:1.45;margin-top:18px;padding:16px 22px}
figure.shot figcaption{font-size:19px;color:#5F7281;font-style:italic;margin-top:14px;text-align:center}
"""

SECTION_CSS = """
#sections{position:fixed;left:50%;bottom:10px;transform:translateX(-50%);display:flex;align-items:center;gap:6px;
  padding:6px 8px;background:rgba(11,32,38,.82);border-radius:999px;font:13px 'DM Sans',sans-serif;z-index:5;
  user-select:none;opacity:.55;transition:opacity .3s}
#sections:hover,#sections.show{opacity:1}
#sections .day{white-space:nowrap;color:#8fa3aa;font-weight:700;letter-spacing:1px;text-transform:uppercase;font-size:11px;padding:0 4px 0 8px}
#sections button{white-space:nowrap;border:0;border-radius:999px;background:transparent;color:#dfe7ea;font:inherit;padding:5px 12px;cursor:pointer}
#sections button:hover{background:rgba(255,255,255,.12)}
#sections button.on{background:#FF5F46;color:#fff;font-weight:700}
@media print{#sections{display:none !important}}
"""

SECTION_JS = """
(()=>{const nav=document.getElementById('sections');
 const SHORT={1:'Your first agent',2:\"What's new\",3:'Curating',4:'Benchmarks & rollout'};
 const secs=slides.map((s,i)=>({i,s})).filter(o=>o.s.classList.contains('section-slide')).map(o=>{
   const k=o.s.querySelector('.kicker').textContent, t=o.s.querySelector('h2').textContent;
   const m=k.match(/(Day \\d+)\\s*·\\s*Section (\\d+)/);return {i:o.i,day:m?m[1]:'',n:m?m[2]:k,t};});
 let lastDay='';secs.forEach(x=>{if(x.day!==lastDay){const d=document.createElement('span');d.className='day';
   d.textContent=x.day;nav.appendChild(d);lastDay=x.day;}
   const b=document.createElement('button');b.textContent=x.n+' · '+(SHORT[x.n]||x.t);b.title='Section '+x.n+': '+x.t;
   b.addEventListener('click',e=>{e.stopPropagation();show(x.i);});x.b=b;nav.appendChild(b);});
 nav.addEventListener('click',e=>e.stopPropagation());
 const orig=show;show=function(i){orig(i);let c=null;secs.forEach(x=>{if(x.i<=cur)c=x;});
   secs.forEach(x=>x.b.classList.toggle('on',x===c));nav.classList.add('show');clearTimeout(window._sx);
   window._sx=setTimeout(()=>nav.classList.remove('show'),2500);};
 show(cur);})();
"""


def build():
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Genie Agents Workshop + Best Practices</title>
<style>{font_faces()}{kit.CSS}{EXTRA_CSS}{GENIE_CSS}{SHOT_CSS}{SECTION_CSS}</style></head>
<body>
{''.join(SLIDES)}
<div id="hud"></div><div id="notes"></div>
<nav id="sections" aria-label="Sections"></nav>
<script>{kit.JS}</script>
<script>{SECTION_JS}</script>
</body></html>"""
    OUT.write_text(page)
    print(f"wrote {OUT} ({len(SLIDES)} slides, {OUT.stat().st_size / 1024:,.0f} KB)")


if __name__ == "__main__":
    build()
