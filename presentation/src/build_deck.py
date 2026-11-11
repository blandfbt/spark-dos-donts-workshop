"""Build the "Spark at scale" presentation as one self-contained HTML file.

    python3 presentation/src/build_deck.py        # writes presentation/spark_at_scale.html

Fonts, logos and every diagram are embedded, so the HTML works offline and can be shared as a single
file. Styling follows the Databricks corporate Google Slides template: navy title and closing slides,
oat content slides, DM Sans, and the "©2026 Databricks Inc." footer.

Timings quoted on the slides were measured in the workshop's Don't/Do cells (serverless, 100M-row fact table).
Values marked ≈ are projected from a Don't that ran on a slice of the workload.
"""

import base64
import html
import re
import math
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE / "assets"
OUT = HERE.parent / "spark_at_scale.html"

NAVY, TEAL, OAT, OAT2 = "#1B3139", "#1B5162", "#F9F7F4", "#EEEDE9"
LAVA, CORAL, SALMON, PINK, BRICK = "#FF3621", "#FF5F46", "#FF9E94", "#FAC5BD", "#BD2B26"
GREEN, MAROON, YELLOW, SLATE, BLUE = "#00A972", "#98102A", "#FFAB00", "#618794", "#4299E0"
MUTED, LINE = "#5F7281", "#C9D1D5"


# --------------------------------------------------------------------------------------------- assets

# Random base64 runs can look like AWS key or ID prefixes (e.g. "AKIA"/"AIDA" + 16 capitals/digits) to secret scanners.
# Break every such run; decoders ignore the break (CSS line continuation / data-URL whitespace).
_KEY_LIKE = re.compile(r"(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA|APKA|ABIA|ACCA)(?=[A-Z0-9]{16})")


def b64(path, sep="\\\n"):
    return _KEY_LIKE.sub(lambda m: m.group(0)[:2] + sep + m.group(0)[2:], base64.b64encode(path.read_bytes()).decode())


def font_faces():
    faces = [("DM Sans", 400, "normal", "dm-sans-regular.ttf"), ("DM Sans", 500, "normal", "dm-sans-medium.ttf"),
             ("DM Sans", 700, "normal", "dm-sans-bold.ttf"), ("DM Sans", 400, "italic", "dm-sans-italic.ttf"),
             ("DM Mono", 400, "normal", "dm-mono-regular.ttf")]
    return "\n".join(
        f"@font-face{{font-family:'{fam}';font-weight:{w};font-style:{st};"
        f"src:url(\"data:font/ttf;base64,{b64(ASSETS / 'fonts' / f)}\") format('truetype');}}"
        for fam, w, st, f in faces
    )


def logo(name, height, recolor_mark=False):
    svg = (ASSETS / "logos" / name).read_text()
    if recolor_mark:  # white wordmark with the lava mark, as on the template's dark slides
        svg = svg.replace('fill="white"', f'fill="{LAVA}"', 1)
    data = _KEY_LIKE.sub(lambda m: m.group(0)[:2] + "&#10;" + m.group(0)[2:], base64.b64encode(svg.encode()).decode())
    return f'<img alt="Databricks" style="height:{height}px" src="data:image/svg+xml;base64,{data}">'


# --------------------------------------------------------------------------------------------- SVG kit

class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []

    def add(self, s):
        self.parts.append(s)
        return self

    def rect(self, x, y, w, h, fill="#fff", stroke=LINE, rx=10, sw=2, dash=None, opacity=1):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" '
                        f'stroke-width="{sw}" opacity="{opacity}"{d}/>')

    def text(self, x, y, s, size=26, color=NAVY, weight=400, anchor="middle", mono=False, italic=False):
        fam = "DM Mono" if mono else "DM Sans"
        st = ' font-style="italic"' if italic else ""
        return self.add(f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{color}" font-weight="{weight}" '
                        f'text-anchor="{anchor}"{st}>{html.escape(s)}</text>')

    def box(self, x, y, w, h, label, sub=None, fill="#fff", stroke=LINE, color=NAVY, size=26, rx=12, mono=False):
        self.rect(x, y, w, h, fill, stroke, rx)
        if sub:
            self.text(x + w / 2, y + h / 2 - 6, label, size, color, 700, mono=mono)
            self.text(x + w / 2, y + h / 2 + size * 0.95, sub, size * 0.72, MUTED)
        else:
            self.text(x + w / 2, y + h / 2 + size * 0.35, label, size, color, 700, mono=mono)
        return self

    def line(self, x1, y1, x2, y2, color=MUTED, sw=3, arrow=True, dash=None, opacity=1):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        m = f' marker-end="url(#ah-{color[1:]})"' if arrow else ""
        return self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" '
                        f'opacity="{opacity}"{m}{d}/>')

    def render(self):
        colors = {NAVY, TEAL, LAVA, CORAL, GREEN, MAROON, SLATE, MUTED, BLUE, YELLOW, BRICK}
        markers = "".join(
            f'<marker id="ah-{c[1:]}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for c in colors)
        return (f'<svg viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" xmlns="http://www.w3.org/2000/svg">'
                f'<defs>{markers}</defs>{"".join(self.parts)}</svg>')


# --------------------------------------------------------------------------------------------- graphics

def g_title_art():
    """Geometric composition in the spirit of the template's title slide."""
    s = Svg(940, 760)
    s.add(f'<circle cx="560" cy="430" r="400" fill="{PINK}"/>')
    c = 250  # grid cell
    x0, y0 = 60, 240
    s.add(f'<polygon points="{x0},{y0 + c} {x0 + c},{y0} {x0 + c},{y0 + c}" fill="{BRICK}"/>')
    s.add(f'<polygon points="{x0 + c},{y0} {x0 + 2 * c - 40},{y0} {x0 + 2 * c + 120},{y0 + c} {x0 + c},{y0 + c}" fill="{CORAL}"/>')
    s.add(f'<polygon points="{x0 + 2 * c - 40},{y0} {x0 + 2 * c + 120},{y0} {x0 + 3 * c},{y0 + c} {x0 + 2 * c + 120},{y0 + c}" fill="{SALMON}"/>')
    s.add(f'<polygon points="{x0},{y0 + c} {x0 + c},{y0 + c} {x0},{y0 + 2 * c}" fill="{LAVA}"/>')
    s.add(f'<path d="M{x0 + c},{y0 + c} h{c} a{c},{c} 0 0 1 -{c},{c} z" fill="{BRICK}"/>')
    s.add(f'<path d="M{x0 + 2 * c},{y0 + c} h{c} v{c} a{c},{c} 0 0 1 -{c},-{c} z" fill="{LAVA}"/>')
    return s.render()


def g_parallelism():
    s = Svg(1700, 420)
    s.text(0, 40, "Summing 100M order lines", 30, NAVY, 700, "start")
    # one process
    s.text(0, 120, "collect() to one Python process", 26, MUTED, 400, "start")
    s.rect(0, 140, 1500, 64, LAVA, LAVA, 8)
    s.text(1520, 184, "≈ 13 min", 34, LAVA, 700, "start")
    s.text(0, 270, "aggregate in Spark, in parallel", 26, MUTED, 400, "start")
    s.rect(0, 290, 4, 64, GREEN, GREEN, 2)
    s.text(24, 334, "1.6 s", 34, GREEN, 700, "start")
    for i in range(48):  # the many cores doing the work
        s.rect(130 + i * 26, 300, 18, 44, "#E3F4EC", GREEN, 3, 1.5)
    s.text(0, 405, "Measured in the workshop on serverless (the collect() time is projected from a 4% slice).", 20, MUTED, 400, "start", italic=True)
    return s.render()


def g_anatomy():
    s = Svg(1720, 600)
    s.box(0, 200, 300, 170, "Your notebook", "Python · Spark Connect client", "#fff", NAVY, NAVY, 28)
    s.text(150, 410, "collect() results land here", 20, LAVA, 500)
    s.line(305, 285, 425, 285, NAVY, 4)
    s.text(365, 268, "plan", 20, MUTED)
    s.rect(430, 160, 330, 250, "#E8EEF0", TEAL, 12)
    s.text(595, 215, "Driver", 32, TEAL, 700)
    for i, t in enumerate(["optimizer (Catalyst)", "scheduler: stages → tasks", "AQE: re-plan at runtime"]):
        s.text(595, 275 + i * 42, t, 22, NAVY)
    s.line(765, 285, 875, 285, TEAL, 4)
    s.text(820, 268, "tasks", 20, MUTED)
    # executors
    s.rect(880, 30, 520, 520, OAT2, LINE, 16)
    s.text(1140, 70, "Executors (many cores, autoscaled)", 22, MUTED, 700)
    for r in range(4):
        for c in range(4):
            x, y = 905 + c * 124, 95 + r * 110
            s.rect(x, y, 110, 92, "#fff", BLUE, 10)
            s.text(x + 55, y + 40, "task", 20, NAVY, 700)
            s.text(x + 55, y + 68, f"part {r * 4 + c + 1}", 17, MUTED)
    s.line(1405, 285, 1500, 285, SLATE, 4)
    s.add(f'<ellipse cx="1610" cy="200" rx="100" ry="26" fill="#fff" stroke="{SLATE}" stroke-width="3"/>')
    s.add(f'<path d="M1510,200 v170 a100,26 0 0 0 200,0 v-170" fill="#fff" stroke="{SLATE}" stroke-width="3"/>')
    s.text(1610, 290, "Delta tables", 22, NAVY, 700)
    s.text(1610, 320, "cloud storage", 18, MUTED)
    return s.render()


def g_lazy():
    s = Svg(1720, 520)
    nodes = [("spark.table", "orders"), ("filter", "2025 only"), ("join", "sdd_dim_part"), ("groupBy", "dealer")]
    for i, (op, sub) in enumerate(nodes):
        x = i * 330
        s.box(x, 60, 280, 120, op, sub, "#fff", SLATE, NAVY, 30, mono=True)
        if i:
            s.line(x - 46, 120, x - 6, 120, SLATE, 3)
    s.text(620, 230, "transformations only build a plan: nothing has run yet", 24, MUTED, 400, italic=True)
    s.line(1325, 120, 1385, 120, LAVA, 4)
    s.box(1390, 50, 320, 140, "write()", "action → the plan runs", "#FFE9E5", LAVA, LAVA, 34, mono=True)
    s.rect(0, 290, 1710, 210, OAT2, OAT2, 14)
    s.text(40, 345, "Transformations (lazy)", 26, TEAL, 700, "start")
    s.text(40, 395, "select · filter · withColumn · join · groupBy · orderBy · union", 26, NAVY, 400, "start", mono=True)
    s.text(40, 450, "Actions (run the whole plan, every time)", 26, LAVA, 700, "start")
    s.text(40, 490, "count · collect · display · toPandas · write · isEmpty", 26, NAVY, 400, "start", mono=True)
    return s.render()


def g_optimizer():
    s = Svg(1720, 520)
    steps = [("Your code", "DataFrame / SQL", "#fff", SLATE),
             ("Logical plan", "what you asked for", "#fff", SLATE),
             ("Optimized plan", "pushdown · pruning", "#E8EEF0", TEAL),
             ("Physical plan", "join strategy · Photon", "#E8EEF0", TEAL),
             ("Execution", "AQE re-plans with real sizes", "#E3F4EC", GREEN)]
    for i, (t, sub, fill, st) in enumerate(steps):
        x = i * 346
        s.box(x, 40, 300, 150, t, sub, fill, st, NAVY, 30)
        if i:
            s.line(x - 42, 115, x - 6, 115, st, 3)
    s.rect(0, 260, 830, 240, "#fff", GREEN, 14)
    s.text(30, 310, "The optimizer can rewrite", 28, GREEN, 700, "start")
    for i, t in enumerate(["filters pushed down to the file scan", "only the columns you use are read",
                           "small tables broadcast instead of shuffled"]):
        s.text(30, 360 + i * 44, "– " + t, 25, NAVY, 400, "start")
    s.rect(880, 260, 830, 240, "#fff", LAVA, 14)
    s.text(910, 310, "…but it can't see inside", 28, LAVA, 700, "start")
    for i, t in enumerate(["Python UDFs and pandas apply()", "lists you collect() and paste back in",
                           "loops that build 300-level-deep plans"]):
        s.text(910, 360 + i * 44, "– " + t, 25, NAVY, 400, "start")
    return s.render()


def g_shuffle():
    s = Svg(1720, 560)
    s.text(0, 34, "Stage 1 · narrow (no data moves)", 24, TEAL, 700, "start")
    s.text(860, 34, "shuffle exchange", 24, LAVA, 700)
    s.text(1720, 34, "Stage 2 · after the shuffle", 24, TEAL, 700, "end")
    keys = [BLUE, YELLOW, GREEN]
    for i in range(4):
        y = 70 + i * 118
        s.rect(0, y, 340, 96, "#fff", SLATE, 10)
        s.text(20, y + 34, f"partition {i + 1}  ·  filter, select", 20, MUTED, 400, "start")
        for k in range(9):
            col = keys[(i + k) % 3]
            s.rect(20 + k * 34, y + 50, 26, 26, col, col, 4)
    for i in range(4):
        for j in range(3):
            s.line(345, 118 + i * 118, 1340, 130 + j * 160, keys[j], 2, arrow=False, opacity=0.45)
    s.rect(640, 230, 440, 110, "#FFE9E5", LAVA, 12)
    s.text(860, 278, "write to disk → network → read", 23, LAVA, 700)
    s.text(860, 312, "rows grouped by hash(key)", 20, NAVY)
    for j in range(3):
        y = 80 + j * 160
        s.rect(1345, y, 375, 110, "#fff", keys[j], 10, 3)
        s.text(1365, y + 40, f"task {j + 1} · aggregate key group {j + 1}", 20, NAVY, 700, "start")
        for k in range(9):
            s.rect(1365 + k * 36, y + 60, 28, 28, keys[j], keys[j], 4)
    return s.render()


def g_joins():
    s = Svg(1720, 470)
    cards = [("Broadcast hash join", GREEN, "small side copied to every executor", "the big side never moves"),
             ("Shuffle join", YELLOW, "both sides re-partitioned by key", "fine for big ⋈ big, costs a shuffle"),
             ("Nested loop / cartesian", LAVA, "no usable equality condition", "every row × every row")]
    for i, (t, col, a, b) in enumerate(cards):
        x = i * 580
        s.rect(x, 0, 550, 470, "#fff", col, 16, 3)
        s.rect(x, 0, 550, 70, col, col, 16)
        s.rect(x, 50, 550, 20, col, col, 0)
        s.text(x + 275, 47, t, 28, "#fff" if col != YELLOW else NAVY, 700)
        cx = x + 275
        if i == 0:
            for k in range(4):
                s.rect(x + 40 + k * 120, 170, 100, 70, BLUE + "33", BLUE, 8)
                s.rect(x + 65 + k * 120, 120, 50, 34, GREEN, GREEN, 6)
                s.line(cx, 105, x + 90 + k * 120, 118, GREEN, 2)
            s.rect(cx - 40, 86, 80, 22, GREEN, GREEN, 6)
        elif i == 1:
            for k in range(3):
                s.rect(x + 50 + k * 160, 110, 120, 50, BLUE + "33", BLUE, 8)
                s.rect(x + 50 + k * 160, 200, 120, 50, YELLOW + "55", YELLOW, 8)
            for k in range(3):
                for m in range(3):
                    s.line(x + 110 + k * 160, 162, x + 110 + m * 160, 198, MUTED, 1.5, arrow=False)
        else:
            for k in range(6):
                for m in range(6):
                    s.line(x + 60 + k * 85, 110, x + 60 + m * 85, 250, LAVA, 1.2, arrow=False, opacity=0.6)
            for k in range(6):
                s.rect(x + 45 + k * 85, 96, 30, 22, BLUE + "33", BLUE, 4)
                s.rect(x + 45 + k * 85, 250, 30, 22, YELLOW + "55", YELLOW, 4)
        s.text(cx, 330, a, 24, NAVY)
        s.text(cx, 372, b, 24, col if col != YELLOW else "#B37800", 700)
    return s.render()


def g_layout():
    s = Svg(1720, 520)
    # column pruning
    s.text(0, 36, "Columns: read only what you use", 28, TEAL, 700, "start")
    for c in range(16):
        used = c in (2, 9)
        s.rect(c * 34, 60, 26, 300, GREEN if used else "#fff", GREEN if used else LINE, 4, 2)
    s.text(0, 400, "2 of 300 columns read from Parquet/Delta", 22, NAVY, 400, "start")
    s.text(0, 434, "toPandas() first = all 300 read and shipped", 22, LAVA, 500, "start")
    # data skipping
    x0 = 620
    s.text(x0, 36, "Files: skip what can't match", 28, TEAL, 700, "start")
    ranges = ["Jan–Feb", "Mar–Apr", "May–Jun", "Jul–Aug", "Sep–Oct", "Nov–Dec"]
    for i, r in enumerate(ranges):
        y = 60 + i * 52
        hit = i == 5
        s.rect(x0, y, 420, 42, "#E3F4EC" if hit else OAT2, GREEN if hit else LINE, 6, 2)
        s.text(x0 + 16, y + 29, f"file {i + 1}  min/max: {r}", 20, NAVY if hit else MUTED, 700 if hit else 400, "start")
    s.text(x0, 400, "WHERE order_date >= '2025-11-01'", 22, NAVY, 400, "start", mono=True)
    s.text(x0, 434, "liquid clustering keeps ranges tight", 22, GREEN, 500, "start")
    # file sizes
    x1 = 1170
    s.text(x1, 36, "Size: fewer, right-sized files", 28, TEAL, 700, "start")
    for r in range(8):
        for c in range(20):
            s.rect(x1 + c * 13, 64 + r * 13, 9, 9, "#FFE9E5", LAVA, 2, 1)
    s.text(x1 + 130, 190, "4,000 tiny files", 20, LAVA, 700)
    for i in range(4):
        s.rect(x1 + 300 + i * 60, 64, 48, 100, "#E3F4EC", GREEN, 6, 2)
    s.text(x1 + 410, 190, "4 files", 20, GREEN, 700)
    s.text(x1, 260, "same rows: 6.7 s vs 1.1 s", 22, NAVY, 400, "start")
    s.text(x1, 400, "OPTIMIZE / predictive optimization", 22, NAVY, 400, "start")
    s.text(x1, 434, "aim for ~100 MB – 1 GB per file", 22, GREEN, 500, "start")
    return s.render()


def g_scoreboard():
    rows = [  # scenario, don't seconds (full size), do seconds, projected?
        ("Partition by date + dealer", 1385, 12.7, True), ("collect() + Python loop", 716, 1.6, True),
        ("One query per dealer", 418, 0.8, True), ("One INSERT per row", 351, 1.2, True),
        ("Python UDF", 120, 1.4, True), ("Read + union per folder", 106, 3.4, True),
        ("coalesce(1) write", 89, 12.5, True), ("withColumn() loop", 83, 1.0, True),
        ("toPandas() wide table", 76, 1.6, True), ("isin(collected list)", 56, 1.9, True),
        ("Window without partitionBy", 41, 7.4, True), ("BETWEEN join, no hint", 33, 1.4, False),
        ("Debug actions per step", 31, 14.4, False), ("inferSchema on CSV", 17.6, 4.3, False),
        ("display() in a job", 15, 0.6, False), ("count() > 0", 11.6, 0.7, False),
        ("4,000 tiny files", 6.7, 1.1, False), ("Full reload vs Auto Loader", 14.4, 8.4, False),
    ]
    s = Svg(1720, 680)
    left, width = 430, 1060
    lo, hi = math.log10(0.5), math.log10(2000)
    X = lambda v: left + (math.log10(v) - lo) / (hi - lo) * width
    for v, lab in [(1, "1 s"), (10, "10 s"), (60, "1 min"), (600, "10 min")]:
        s.line(X(v), 10, X(v), 650, LINE, 1.5, arrow=False, dash="4 6")
        s.text(X(v), 676, lab, 18, MUTED)
    bh = 34
    for i, (name, dont, do, proj) in enumerate(rows):
        y = 14 + i * 35.5
        s.text(left - 16, y + 24, name, 19, NAVY, 400, "end")
        s.rect(left, y + 3, X(dont) - left, bh / 2 - 2, LAVA, LAVA, 3, 0)
        s.rect(left, y + bh / 2 + 1, max(3, X(do) - left), bh / 2 - 2, GREEN, GREEN, 3, 0)
        ratio = dont / do
        s.text(X(dont) + 10, y + 18, f"{'≈ ' if proj else ''}{ratio:,.0f}×", 18, LAVA, 700, "start")
    s.rect(1560, 20, 22, 14, LAVA, LAVA, 3, 0)
    s.text(1592, 33, "Don't", 18, NAVY, 700, "start")
    s.rect(1560, 46, 22, 14, GREEN, GREEN, 3, 0)
    s.text(1592, 59, "Do", 18, NAVY, 700, "start")
    return s.render()


# --------------------------------------------------------------------------------------------- slides

def title_slide(title, author, note):
    return f"""
<section class="slide dark title-slide" data-notes="{html.escape(note)}">
  <div class="lockup">{logo('lockup-primary-white.svg', 46, recolor_mark=True)}</div>
  <h1 class="hero">{title}</h1>
  <div class="author"><span class="rule"></span>{author}</div>
  <div class="art">{g_title_art()}</div>
  <div class="footer">©2026 Databricks Inc. — All rights reserved</div>
</section>"""


def content(title, subtitle, body, note="", cls="", takeaway=None):
    sub = f'<div class="subtitle">{subtitle}</div>' if subtitle else ""
    tk = f'<div class="takeaway">{takeaway}</div>' if takeaway else ""
    return f"""
<section class="slide {cls}" data-notes="{html.escape(note)}">
  <h2 class="title">{title}</h2>{sub}
  <div class="body">{body}</div>{tk}
  <div class="footer">©2026 Databricks Inc. — All rights reserved</div>
  <div class="pagemark">{logo('databricks-symbol-color.svg', 24)}<span class="pageno"></span></div>
</section>"""


def section_slide(kicker, title, items, note):
    lis = "".join(f"<li><span class='num'>{i + 1}</span>{t}</li>" for i, t in enumerate(items))
    return f"""
<section class="slide dark section-slide" data-notes="{html.escape(note)}">
  <div class="kicker">{kicker}</div>
  <h2 class="hero small">{title}</h2>
  <ol class="cats">{lis}</ol>
  <div class="footer">©2026 Databricks Inc. — All rights reserved</div>
  <div class="pagemark">{logo('databricks-symbol-color.svg', 24)}<span class="pageno"></span></div>
</section>"""


def closing_slide(note):
    return f"""
<section class="slide dark closing" data-notes="{html.escape(note)}">
  <div class="center">{logo('lockup-primary-white.svg', 120, recolor_mark=True)}</div>
  <div class="footer">©2026 Databricks Inc. — All rights reserved</div>
</section>"""


def category(principle, why, donts, dos, metrics, note):
    d = "".join(f"<li>{x}</li>" for x in donts)
    o = "".join(f"<li>{x}</li>" for x in dos)
    m = "".join(f'<div class="metric"><div class="m-label">{lab}</div><div class="m-vals"><span class="bad">{bad}</span>'
                f'<span class="arrow">→</span><span class="good">{good}</span></div></div>' for lab, bad, good in metrics)
    body = f"""
    <p class="why">{why}</p>
    <div class="two">
      <div class="col dont"><div class="pill">DON'T</div><ul>{d}</ul></div>
      <div class="col do"><div class="pill">DO</div><ul>{o}</ul></div>
    </div>
    <div class="metrics">{m}</div>"""
    return content(principle, None, body, note, "category")


def bullets(items, cls=""):
    return f'<ul class="dash {cls}">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


SLIDES = [
    title_slide(
        "Spark at scale:<br>Do's &amp; Don'ts", "Spark Do's &amp; Don'ts workshop",
        "Welcome. 15–20 minutes on how Spark actually runs your code, so the do's and don'ts in the workshop "
        "make sense instead of being rules to memorize. Then everyone gets hands-on with the notebook."),

    content("Agenda", "Efficient large-scale computing on Databricks", bullets([
        "How Spark runs your code: driver, executors, lazy plans",
        "Where the time goes: shuffles, joins, data layout",
        "What serverless and Photon do for you, and what they can't",
        "Five ways to leverage the engine, and the anti-patterns to avoid",
        "The workshop and the Genie Code challenge",
    ], "big"), "Three parts: the mental model (most of the time), the five categories of mistakes, and the "
              "workshop. I won't walk through all twenty do's and don'ts; the notebook does that with real timings."),

    content("Anatomy of a Spark application", "On serverless, your notebook is a client and Databricks runs the engine",
            g_anatomy(),
            takeaway="Only what you explicitly ask for comes back to the notebook. <code>collect()</code> and <code>toPandas()</code> ask for everything.",
            note="Your notebook sends a plan. The driver optimizes it, cuts it into stages and tasks, and schedules "
            "tasks on executors — one task per partition. Executors read Delta files directly from cloud storage. "
            "The only data that comes back to your notebook is what you explicitly ask for: that is where "
            "collect() and toPandas() hurt."),

    content("Scale is a parallelism problem", "The same question, answered two ways",
            g_parallelism() + bullets([
                "Spark splits data into <b>partitions</b> and works on all of them at once, on many cores",
                "Efficient code keeps every core busy and <b>moves as little data as possible</b>",
            ], "tight"),
            "This is the whole talk in one picture. Same 100M rows, same sum. One version drags every row into one "
            "Python process; the other lets dozens of cores each sum a slice and send back one number. Everything "
            "else is a variation of this."),

    content("Lazy evaluation", "Transformations describe the work, actions run it",
            g_lazy(),
            takeaway="Five debug <code>count()</code> calls in a pipeline = the pipeline runs five times.",
            note="Nothing runs when you call filter or join; Spark just records it. An action runs the whole plan from "
            "the source tables. Spark doesn't keep intermediate results unless you cache or write them, so five "
            "debug count() calls are five full runs of the pipeline. Laziness is also what lets the optimizer see "
            "the whole job before anything runs."),

    content("From DataFrame code to a physical plan", "The optimizer rewrites what you wrote, if it can see it",
            g_optimizer(),
            takeaway="Write code the optimizer can read: built-in functions, joins and filters, not Python black boxes.",
            note="Catalyst turns your code into a logical plan, optimizes it — pushing filters into the scan, pruning "
            "unused columns — and picks physical operators like the join strategy. On Databricks those run in "
            "Photon, and adaptive query execution re-plans at runtime with real sizes. The catch: the optimizer only "
            "helps with what it can see. A Python UDF or a list you collected is a black box."),

    content("Partitions, stages and the shuffle", "Narrow operations stream; wide operations move data",
            g_shuffle() + bullets([
                "<b>Narrow</b> (filter, select, withColumn): each partition on its own, no data moves",
                "<b>Wide</b> (groupBy, join, orderBy, window): rows with the same key must meet, so they cross the network",
                "One partition = one task = one core: a window with no <code>partitionBy</code> runs on a single core",
            ], "tight"),
            "Inside a stage, tasks stream through their partition. Wherever rows with the same key have to meet, "
            "there is a shuffle: write to disk, send over the network, read back. Shuffles are the expensive part of "
            "most jobs. Fewer, smaller shuffles, and never funnel everything into one partition."),

    content("How Spark joins", "The strategy, not the syntax, decides the cost",
            g_joins(),
            takeaway="Joins on a non-unique key multiply rows. In the workshop, joining orders to an SCD2 history doubled revenue, with no error.",
            note="Three strategies. Broadcast: copy the small side everywhere, the big side doesn't move — AQE does this "
            "automatically. Shuffle join: both sides move, fine when both are big. Nested loop: no equality to hash "
            "on, so every row meets every row; that's the BETWEEN join without the range-join hint. And a correctness "
            "point: if the key isn't unique on the dimension side, rows multiply silently."),

    content("Data layout is performance", "The fastest data is the data you never read",
            g_layout(),
            takeaway="Select the columns you need, filter on clustered columns, keep files right-sized: read less, finish sooner.",
            note="Delta and Parquet are columnar, so selecting 2 of 300 columns reads 2 columns. Each file has min/max "
            "statistics, so a range filter on a clustered column skips most files. And file count matters: 4,000 "
            "tiny files cost more to open than to read. Liquid clustering, OPTIMIZE and predictive optimization keep "
            "the layout healthy."),

    content("What serverless does for you", "…and what is still up to your code", """
    <div class="two even">
      <div class="col plain"><h3 class="good-h">The platform handles</h3>""" + bullets([
                "Adaptive query execution: broadcast decisions, partition sizes, skew",
                "Photon: vectorized, native execution of built-in operators",
                "Compute sizing and autoscaling",
                "Optimized writes, auto compaction, predictive optimization",
            ]) + """</div>
      <div class="col plain"><h3 class="bad-h">Your code still decides</h3>""" + bullets([
                "<b>Where</b> the work runs: executors or one driver process",
                "<b>Whether</b> the optimizer can see your intent",
                "<b>How often</b> the same work is repeated",
                "<b>How</b> data is laid out and keyed",
            ]) + """</div>
    </div>
    <div class="codebox">spark.conf.set("spark.executor.memory", "16g")<span class="cm">   # → [CONFIG_NOT_AVAILABLE] on serverless</span></div>""",
            "Most classic tuning advice is now the platform's job — executor memory, shuffle partitions, broadcast "
            "thresholds. On serverless you can't even set them. What's left is the shape of your code, and that's "
            "exactly what the five categories are about."),

    section_slide("The do's and don'ts", "Five ways to leverage the engine", [
        "Keep the work on the executors", "Let the optimizer see your intent", "Don't do the work twice",
        "Respect the data layout", "Know your keys and your platform",
    ], "Every one of the twenty workshop scenarios falls into one of these five buckets. For each I'll show the "
       "patterns and the measured cost from the workshop run."),

    category("1 · Keep the work on the executors",
             "The driver is one machine. Anything that funnels rows through it loses the parallelism you are paying for.",
             ["<code>collect()</code> / <code>toPandas()</code> on big DataFrames", "a Python loop running one query per key",
              "one <code>INSERT</code> per row", "<code>display()</code> left in production jobs"],
             ["aggregate, filter and <code>limit</code> in Spark, then bring back the small result",
              "one <code>groupBy</code> or join over all keys", "one batch append, or <code>MERGE INTO</code>",
              "one action (the write); row counts from <code>DESCRIBE HISTORY</code>"],
             [("collect() 100M rows (≈ 49 GB on a 15 GB driver)", "≈ 13 min", "1.6 s"), ("query per dealer ×500", "≈ 7 min", "0.8 s"),
              ("INSERT per row ×300", "≈ 6 min", "1.2 s")],
             "The collect number is the one to remember: the 4% slice used 2 GB of driver memory; the full table would "
             "need about 49 GB on a 15 GB driver. That is the out-of-memory crash, predicted rather than reproduced."),

    category("2 · Let the optimizer see your intent",
             "Built-in functions and declarative joins can be optimized and run in Photon. Opaque Python and giant literal lists can't.",
             ["Python UDFs for arithmetic and if/else", "<code>withColumn</code> in a loop over hundreds of columns",
              "<code>isin(&lt;100k collected IDs&gt;)</code>", "<code>BETWEEN</code> joins with no usable equality"],
             ["built-in functions (› pandas UDF › Python UDF)", "<code>withColumns({...})</code> or one <code>select</code>",
              "a left semi join", "the <code>range_join</code> hint, or a bucket key"],
             [("Python UDF", "≈ 120 s", "1.4 s"), ("withColumn() loop", "≈ 83 s", "1.0 s"), ("range join", "33 s", "1.4 s")],
             "The UDF ladder is worth saying out loud: Python UDF about 120 seconds, pandas UDF 20, built-ins 1.4. "
             "Same answer each time. The range-join hint is a one-line change worth 20x here."),

    category("3 · Don't do the work twice",
             "Every action re-runs the plan from the source. Every full reload re-reads all of history.",
             ["<code>count()</code> / <code>display()</code> after every step", "<code>if df.count() &gt; 0</code>",
              "re-reading the whole landing zone each run"],
             ["end the pipeline in one write; <code>cache()</code> only when you truly reuse",
              "<code>if not df.isEmpty()</code>", "Auto Loader or declarative pipelines (incremental)"],
             [("debug actions per step", "31 s", "14 s"), ("count() > 0", "11.6 s", "0.7 s"),
              ("full reload vs Auto Loader", "14 s and growing", "8 s")],
             "These are the quiet ones: each extra action looks harmless in development. The full-reload gap is small "
             "on day one and grows every day, because the full reload reads all history while Auto Loader reads only "
             "new files."),

    category("4 · Respect the data layout",
             "File count, file size and partitioning decide how much work every later read does.",
             ["thousands of tiny files", "<code>inferSchema</code> on CSV and JSON",
              "<code>partitionBy</code> on high-cardinality columns", "<code>coalesce(1)</code> before a big write"],
             ["right-sized files; <code>OPTIMIZE</code> / predictive optimization", "an explicit schema, or Auto Loader schema hints",
              "liquid clustering (<code>CLUSTER BY</code>)", "parallel writes; aggregate first if you need one file"],
             [("partitionBy(date, dealer)", "≈ 23 min", "13 s"), ("coalesce(1) write", "≈ 89 s", "12.5 s"),
              ("inferSchema", "17.6 s", "4.3 s")],
             "Over-partitioning is the biggest number in the whole workshop: a quarter of orders partitioned by date "
             "and dealer is 45,000 folders of tiny files. Liquid clustering on the same two columns writes four files."),

    category("5 · Know your keys and your platform",
             "Keys decide parallelism and correctness. Cluster-era tuning doesn't apply on serverless.",
             ["<code>Window.orderBy(...)</code> with no <code>partitionBy</code>", "joining on a key that isn't unique",
              "<code>spark.conf.set(...)</code> tuning, <code>sparkContext</code>, RDDs"],
             ["<code>Window.partitionBy(key).orderBy(...)</code>", "one row per key: <code>is_current</code> or point-in-time",
              "DataFrame APIs, targeted hints; let AQE tune"],
             [("window without partitionBy", "≈ 41 s", "7.4 s"), ("join on SCD2 history", "+100% revenue", "exact"),
              ("spark.executor.memory", "rejected", "not needed")],
             "Two of these are about correctness, not speed. The SCD2 join doubled revenue without an error. The "
             "global window gets the right answer, on one core. And the config habits simply fail on serverless."),

    content("Same answers, very different costs", "Every Don't/Do pair from the workshop, measured on serverless",
            g_scoreboard() + '<p class="caption">Don\u2019t vs Do, log scale. ≈ marks a Don\u2019t that ran on a slice of the workload and was projected to full size.</p>',
            "Every pair returns the same answer, except the SCD2 join which is left out here because it returns the "
            "wrong one. The gaps run from 2x to over 100x. Note the log scale."),

    content("The workshop", "Clone the repo into your workspace and set one line", """
    <div class="two even">
      <div class="col plain">
        <div class="codebox block"><span class="cm"># CONFIG.py (top of the repo): the only edit</span>
CATALOG       = "dbx_workshop_dev"
SOURCE_SCHEMA = "shared"   <span class="cm"># instructor-built, read-only</span>
USER_SCHEMA   = "jane_doe" <span class="cm"># your own schema</span></div>""" + bullets([
                "Instructor, beforehand: <code>instructor_setup/</code> generates the shared data and creates each participant's schema",
                "<code>01_bronze_to_gold_lab</code>: bronze → silver → gold, SQL and a dashboard, hands-on",
                "<code>02_spark_dos_and_donts</code>: each topic is a <b>why</b>, then a timed <b>Don't</b> and <b>Do</b>; every section can resume after a restart",
            ], "tight") + """</div>
      <div class="col plain genie">
        <h3>🧞 Genie Code challenge</h3>
        <p>A realistic dealer-scorecard job with <b>nine</b> anti-patterns from this deck. It gives the right answer, slowly.</p>""" + bullets([
                "Ask Genie Code to find and fix them",
                "Paste the result; a check cell verifies the output",
                "Reference: ~2 min → <b>6 s</b>",
            ]) + """</div>
    </div>""",
            "The instructor has already generated the data into the shared schema and created a schema for each of you. "
            "You clone the repo, set USER_SCHEMA in CONFIG, and step through the notebooks, then spend the last part on "
            "the Genie Code challenge. Encourage them to question the assistant's answer, not just accept it: the "
            "reference solution deliberately keeps one global window because it runs on 78 rows."),

    closing_slide("Thank you. Questions, then on to the notebook."),
]


# --------------------------------------------------------------------------------------------- page

CSS = """
:root{--navy:#1B3139;--teal:#1B5162;--oat:#F9F7F4;--oat2:#EEEDE9;--lava:#FF3621;--coral:#FF5F46;
      --green:#00A972;--muted:#5F7281;--line:#C9D1D5}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:#20282b;overflow:hidden}
.slide{position:absolute;left:50%;top:50%;width:1920px;height:1080px;transform-origin:center;overflow:hidden;
       background:var(--oat);color:var(--navy);font-family:'DM Sans',Arial,sans-serif;display:none;
       -webkit-print-color-adjust:exact;print-color-adjust:exact}
.slide.active{display:block}
.slide.dark{background:var(--navy);color:#fff}
.footer{position:absolute;left:100px;bottom:42px;font-size:17px;color:#8B9AA1}
.dark .footer{color:#6F8790}
.pagemark{position:absolute;right:100px;bottom:36px;display:flex;align-items:center;gap:26px;font-size:17px;color:#8B9AA1}
.title{position:absolute;left:100px;top:78px;margin:0;font-size:70px;font-weight:400;letter-spacing:-.5px;line-height:1.1}
.subtitle{position:absolute;left:100px;top:168px;font-size:36px;color:var(--teal)}
.body{position:absolute;left:100px;right:100px;top:262px;bottom:110px}
.category .body{top:200px}
code,.mono{font-family:'DM Mono',Consolas,monospace;font-size:.88em;background:var(--oat2);padding:2px 8px;border-radius:6px}
ul.dash{list-style:none;padding:0;margin:26px 0 0}
ul.dash li{position:relative;padding-left:42px;margin:0 0 18px;font-size:34px;line-height:1.3}
ul.dash li:before{content:'–';position:absolute;left:4px;color:var(--teal)}
ul.dash.big li{font-size:40px;margin-bottom:26px}
ul.dash.tight{margin-top:24px}ul.dash.tight li{font-size:31px;margin-bottom:14px}
.caption{font-size:24px;color:var(--muted);font-style:italic;margin:22px 0 0}
/* title slide */
.title-slide .lockup{position:absolute;left:100px;top:70px}
.hero{position:absolute;left:100px;top:330px;margin:0;font-size:104px;font-weight:500;line-height:1.08;letter-spacing:-1px;max-width:900px}
.hero.small{top:250px;font-size:84px;max-width:1720px}
.author{position:absolute;left:100px;bottom:150px;color:var(--coral);font-size:26px;font-weight:700}
.author .rule{display:block;width:72px;height:4px;background:var(--coral);margin-bottom:22px}
.art{position:absolute;right:-40px;bottom:-120px}
/* section slide */
.kicker{position:absolute;left:100px;top:150px;color:var(--coral);font-size:28px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
.cats{position:absolute;left:100px;top:470px;margin:0;padding:0;list-style:none;columns:2;column-gap:120px;width:1700px}
.cats li{font-size:40px;margin:0 0 34px;display:flex;align-items:center;gap:28px;break-inside:avoid}
.cats .num{flex:none;width:64px;height:64px;border-radius:50%;background:var(--coral);color:#fff;display:flex;
           align-items:center;justify-content:center;font-weight:700;font-size:32px}
/* closing */
.closing .center{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
/* columns */
.two{display:grid;grid-template-columns:1fr 1fr;gap:48px;margin-top:10px}
.col{border-radius:18px;padding:30px 36px;background:#fff;border:2px solid var(--line);position:relative}
.col.plain{background:transparent;border:none;padding:0}
.col ul{margin:20px 0 0;padding-left:30px}.col li{font-size:29px;line-height:1.32;margin-bottom:12px}
.col.dont{border-color:var(--lava)}.col.do{border-color:var(--green)}
.pill{display:inline-block;color:#fff;font-weight:700;font-size:22px;padding:6px 18px;border-radius:999px;letter-spacing:1px}
.dont .pill{background:var(--lava)}.do .pill{background:var(--green)}
.why{font-size:30px;color:var(--teal);margin:0 0 28px;max-width:1650px;line-height:1.35}
.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;margin-top:30px}
.metric{background:var(--oat2);border-radius:16px;padding:20px 28px}
.m-label{font-size:22px;color:var(--muted);margin-bottom:6px}
.m-vals{font-size:36px;font-weight:700;display:flex;align-items:baseline;gap:16px;flex-wrap:wrap}
.bad{color:var(--lava)}.good{color:var(--green)}.arrow{color:var(--muted);font-weight:400}
h3{font-size:36px;margin:0 0 6px}.good-h{color:var(--green)}.bad-h{color:var(--lava)}
.codebox{font-family:'DM Mono',Consolas,monospace;background:var(--oat2);border-radius:12px;padding:22px 30px;font-size:25px;
         margin-top:46px;white-space:pre}
.codebox.block{margin-top:0;font-size:22px;line-height:1.5}
.codebox .cm{color:#7d8c93}
.genie{background:#fff !important;border:2px solid var(--teal) !important;border-radius:18px;padding:30px 36px !important}
.genie h3{color:var(--teal)}.genie p{font-size:29px;line-height:1.35;margin:14px 0 0}
.takeaway{position:absolute;left:100px;right:100px;bottom:112px;background:var(--navy);color:#fff;border-radius:14px;
          padding:26px 36px 26px 44px;font-size:32px;line-height:1.3;border-left:10px solid var(--coral)}
.takeaway code{background:rgba(255,255,255,.12);color:#fff}
.category .body{display:flex;flex-direction:column}
.category .why{font-size:32px;margin-bottom:34px}
.category .col li{font-size:31px;margin-bottom:16px}
.category .metrics{margin-top:auto}
.category .m-vals{font-size:38px;flex-wrap:nowrap;white-space:nowrap}.category .m-label{font-size:24px}
/* viewer chrome */
#hud{position:fixed;right:18px;bottom:14px;font:14px 'DM Sans',sans-serif;color:#9fb0b6;user-select:none;transition:opacity .6s}
#hud.idle{opacity:0}
#notes{position:fixed;left:0;right:0;bottom:0;max-height:32vh;overflow:auto;background:rgba(11,32,38,.94);color:#e8eef0;
       font:20px/1.45 'DM Sans',sans-serif;padding:18px 28px;display:none}
#notes.show{display:block}
@media print{
  @page{size:1920px 1080px;margin:0}
  html,body{height:auto;overflow:visible;background:none}
  .slide{display:block !important;position:relative;left:0;top:0;transform:none !important;break-after:page;page-break-after:always}
  #hud,#notes{display:none !important}
}
"""

JS = """
const slides=[...document.querySelectorAll('.slide')];
let cur=Math.max(0,Math.min(slides.length-1,(parseInt(location.hash.slice(1))||1)-1));
slides.forEach((s,i)=>{const p=s.querySelector('.pageno');if(p)p.textContent=i+1;});
const hud=document.getElementById('hud'),notes=document.getElementById('notes');
function fit(){const k=Math.min(innerWidth/1920,innerHeight/1080);slides.forEach(s=>s.style.transform=`translate(-50%,-50%) scale(${k})`);}
function show(i){cur=Math.max(0,Math.min(slides.length-1,i));slides.forEach((s,j)=>s.classList.toggle('active',j===cur));
  history.replaceState(null,'','#'+(cur+1));hud.textContent=`${cur+1} / ${slides.length}  ·  ←/→ navigate · N notes · F fullscreen`;
  notes.textContent=slides[cur].dataset.notes||'';hud.classList.remove('idle');clearTimeout(window._h);
  window._h=setTimeout(()=>hud.classList.add('idle'),2500);}
addEventListener('keydown',e=>{
  if(['ArrowRight','PageDown',' ','Enter'].includes(e.key)){show(cur+1);e.preventDefault();}
  else if(['ArrowLeft','PageUp','Backspace'].includes(e.key)){show(cur-1);e.preventDefault();}
  else if(e.key==='Home')show(0);else if(e.key==='End')show(slides.length-1);
  else if(e.key==='n'||e.key==='N')notes.classList.toggle('show');
  else if(e.key==='f'||e.key==='F'){document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();}
});
addEventListener('click',e=>{if(e.target.closest('#notes'))return;
  // only the outer quarters navigate: left = back, right = forward; clicks in the middle do nothing
  if(e.clientX<innerWidth*0.25)show(cur-1);else if(e.clientX>innerWidth*0.75)show(cur+1);});
addEventListener('resize',fit);fit();show(cur);
"""


def build():
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Spark at scale: Do's &amp; Don'ts</title>
<style>{font_faces()}{CSS}</style></head>
<body>
{''.join(SLIDES)}
<div id="hud"></div><div id="notes"></div>
<script>{JS}</script>
</body></html>"""
    OUT.write_text(page)
    print(f"wrote {OUT} ({len(SLIDES)} slides, {OUT.stat().st_size / 1024:,.0f} KB)")


if __name__ == "__main__":
    build()
