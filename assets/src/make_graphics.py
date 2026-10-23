"""Generate the workshop diagrams as SVG, then render them to PNG for the notebooks.

    python3 assets/src/make_graphics.py      # needs rsvg-convert (brew install librsvg)

Writes assets/src/*.svg and notebooks/images/*.png.
"""

import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
OUT_PNG = HERE.parent.parent / "notebooks" / "images"

INK = "#1b3139"
MUTED = "#5f7281"
RED = "#d1495b"
RED_BG = "#fbe9eb"
BLUE = "#2e86ab"
BLUE_BG = "#e6f2f7"
GREEN = "#3a7d44"
GREEN_BG = "#e8f3ea"
ORANGE = "#ff3621"
GREY_BG = "#f3f5f6"
LINE = "#c5ced4"
FONT = "Helvetica, Arial, sans-serif"


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts = w, h, []

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill="#fff", stroke=LINE, rx=8, sw=1.5, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=15, color=INK, weight="normal", anchor="middle", italic=False):
        style = ' font-style="italic"' if italic else ""
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.add(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}"{style}>{s}</text>')

    def box(self, x, y, w, h, label, sub=None, fill="#fff", stroke=LINE, color=INK, size=15, rx=8):
        self.rect(x, y, w, h, fill, stroke, rx)
        if sub:
            self.text(x + w / 2, y + h / 2 - 3, label, size, color, "bold")
            self.text(x + w / 2, y + h / 2 + 15, sub, size - 3, MUTED)
        else:
            self.text(x + w / 2, y + h / 2 + size / 3, label, size, color, "bold")

    def arrow(self, x1, y1, x2, y2, color=MUTED, sw=2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        mid = {RED: "r", BLUE: "b", GREEN: "g"}.get(color, "m")
        self.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}" marker-end="url(#a{mid})"{d}/>')

    def panel(self, x, y, w, h, kind, title):
        color, bg = (RED, RED_BG) if kind == "dont" else (GREEN, GREEN_BG)
        self.rect(x, y, w, h, "#fff", color, 12, 2)
        self.rect(x + 16, y - 15, 74 if kind == "dont" else 50, 30, color, color, 15)
        self.text(x + 16 + (37 if kind == "dont" else 25), y + 6, "DON'T" if kind == "dont" else "DO", 15, "#fff", "bold")
        tx = x + (104 if kind == "dont" else 80)
        self.rect(tx, y - 12, len(title) * 8.4 + 12, 24, "#fff", "#fff", 0, 0)
        self.text(tx + 6, y + 6, title, 16, INK, "bold", "start")

    def render(self):
        markers = "".join(
            f'<marker id="a{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
            for k, c in {"r": RED, "b": BLUE, "g": GREEN, "m": MUTED}.items()
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
            f"<defs>{markers}</defs>"
            f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>' + "".join(self.parts) + "</svg>"
        )


def save(name, svg):
    path = HERE / f"{name}.svg"
    path.write_text(svg.render())
    OUT_PNG.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsvg-convert", "-z", "2", "-o", str(OUT_PNG / f"{name}.png"), str(path)], check=True)
    print("wrote", OUT_PNG / f"{name}.png")


# ---------------------------------------------------------------------------------------------

def data_model():
    s = Svg(1000, 470)
    s.text(500, 32, "Apex Motorsports Parts · workshop data", 20, INK, "bold")
    # star schema
    s.rect(20, 55, 560, 395, GREY_BG, LINE, 12)
    s.text(40, 82, "Star schema", 16, MUTED, "bold", "start")
    s.box(215, 210, 170, 76, "fact_orders", "~100M order lines", BLUE_BG, BLUE)
    dims = [(45, 105, "dim_date", "730 days"), (395, 105, "dim_dealer", "500 dealers"),
            (45, 330, "dim_part", "25k parts"), (395, 330, "dim_customer", "2M (current)"),
            (215, 360, "dim_customer_history", "SCD2, 1–3 versions")]
    for x, y, n, sub in dims:
        w = 170
        s.box(x, y, w, 62, n, sub)
        cx, cy = x + w / 2, y + 31
        s.add(f'<line x1="{cx}" y1="{cy + (31 if y < 200 else -31)}" x2="300" y2="{210 if y < 200 else 286}" stroke="{LINE}" stroke-width="2"/>')
    # telemetry
    s.rect(600, 55, 380, 230, GREY_BG, LINE, 12)
    s.text(620, 82, "Test-program telemetry", 16, MUTED, "bold", "start")
    s.box(620, 100, 340, 56, "telemetry_wide", "1M rows × ~300 sensor columns")
    s.box(620, 172, 160, 90, "telemetry_readings", "1 Hz, 43M rows")
    s.box(800, 172, 160, 90, "track_sessions", "start_ts / end_ts")
    s.text(790, 222, "⋈", 18, MUTED)
    # volume
    s.rect(600, 300, 380, 150, "#fff7f5", ORANGE, 12)
    s.text(620, 327, "Volume raw_files/", 16, ORANGE, "bold", "start")
    for i, (n, sub) in enumerate([("orders_csv/", "CSV, one quarter"), ("daily_order_extracts/", "1 folder per day"),
                                  ("telemetry_small_files/", "4,000 tiny files"), ("telemetry_compacted/", "same rows, 4 files"),
                                  ("orders_landing/", "landing zone")]):
        s.text(625, 352 + i * 19, n, 13, INK, "bold", "start")
        s.text(830, 352 + i * 19, sub, 13, MUTED, "start")
    save("data_model", s)


def driver_bottleneck():
    s = Svg(1000, 360)
    s.panel(20, 30, 470, 310, "dont", "collect() / toPandas()")
    s.panel(510, 30, 470, 310, "do", "reduce in Spark first")
    for px, kind in [(20, "dont"), (510, "do")]:
        for i in range(5):
            s.box(px + 30 + i * 86, 70, 76, 50, f"exec {i + 1}", None, fill=BLUE_BG, stroke=BLUE, size=13)
    # don't: fat arrows into driver
    for i in range(5):
        s.add(f'<line x1="{88 + i * 86}" y1="122" x2="{215 + i * 20}" y2="198" stroke="{RED}" stroke-width="6" stroke-linecap="round"/>')
    s.rect(155, 200, 200, 80, RED_BG, RED, 10, 2)
    s.text(255, 228, "driver (1 machine)", 15, RED, "bold")
    s.rect(175, 240, 160, 18, "#fff", RED, 4)
    s.rect(175, 240, 160, 18, RED, RED, 4)
    s.text(255, 254, "memory 100% → OOM", 12, "#fff", "bold")
    s.text(255, 310, "all rows cross the network; Python loops on one core", 13, MUTED, italic=True)
    # do: thin arrows
    for i in range(5):
        s.add(f'<line x1="{578 + i * 86}" y1="122" x2="{705 + i * 20}" y2="198" stroke="{GREEN}" stroke-width="1.5"/>')
    s.text(870, 170, "partial aggregates", 12, MUTED, "normal", "start")
    s.rect(645, 200, 200, 80, GREEN_BG, GREEN, 10, 2)
    s.text(745, 228, "driver", 15, GREEN, "bold")
    s.rect(665, 240, 160, 18, "#fff", GREEN, 4)
    s.rect(665, 240, 12, 18, GREEN, GREEN, 4)
    s.text(745, 274, "1 row back", 12, GREEN)
    s.text(745, 310, "filter · aggregate · limit run on all executors", 13, MUTED, italic=True)
    save("driver_bottleneck", s)


def lazy_evaluation():
    s = Svg(1000, 380)
    s.panel(20, 30, 960, 190, "dont", "5 actions = the same join + aggregation 5 times")
    steps = ["read", "join ×2", "aggregate"]
    actions = ["count()", "display()", "count()", "display()", "write"]
    for r, a in enumerate(actions):
        y = 62 + r * 30
        x = 40
        for st in steps:
            s.rect(x, y, 150, 24, RED_BG, RED, 5, 1)
            s.text(x + 75, y + 17, st, 12, RED)
            x += 160
        s.arrow(x - 8, y + 12, x + 20, y + 12, RED, 1.5)
        s.text(x + 28, y + 17, a, 13, INK, "bold", "start")
    s.text(760, 120, "every action re-runs", 15, RED, "bold", "start")
    s.text(760, 142, "the lineage from the", 15, RED, "bold", "start")
    s.text(760, 164, "source tables", 15, RED, "bold", "start")

    s.panel(20, 250, 960, 110, "do", "one action, then read the small result")
    x = 40
    for st in steps:
        s.rect(x, 290, 150, 30, GREEN_BG, GREEN, 5, 1)
        s.text(x + 75, 310, st, 13, GREEN)
        x += 160
    s.arrow(x - 8, 305, x + 20, 305, GREEN, 1.5)
    s.text(x + 28, 310, "write (once)", 13, INK, "bold", "start")
    s.text(640, 300, "→ row counts: DESCRIBE HISTORY (free)", 13, MUTED, "normal", "start")
    s.text(640, 320, "→ peek: read 10 rows of the output table", 13, MUTED, "normal", "start")
    s.text(640, 340, "→ reuse in-session: df.cache()", 13, MUTED, "normal", "start")
    save("lazy_evaluation", s)


def driver_loop():
    s = Svg(1000, 330)
    s.panel(20, 30, 470, 280, "dont", "for key in keys: spark query")
    s.text(40, 72, "time →", 13, MUTED, "normal", "start")
    for i in range(8):
        y = 85 + i * 19
        s.rect(40 + i * 40, y, 38, 15, RED_BG, RED, 3, 1)
    s.text(460, 104, "query 1: plan + schedule + full scan", 12, RED, "normal", "end")
    s.text(460, 270, "… × 500 dealers, one after another", 13, RED, "bold", "end")
    s.text(255, 295, "each query re-scans the same 100M rows", 13, MUTED, italic=True)
    s.panel(510, 30, 470, 280, "do", "one groupBy(key)")
    s.text(530, 72, "time →", 13, MUTED, "normal", "start")
    for i in range(8):
        s.rect(530, 85 + i * 22, 70, 18, GREEN_BG, GREEN, 3, 1)
    s.text(615, 100, "one scan, all 500 aggregates", 13, GREEN, "bold", "start")
    s.text(615, 120, "in parallel across executors", 13, GREEN, "normal", "start")
    s.text(745, 295, "planned once, data read once", 13, MUTED, italic=True)
    save("driver_loop", s)


def python_udf():
    s = Svg(1000, 330)
    s.panel(20, 30, 590, 280, "dont", "Python UDF")
    s.box(40, 90, 170, 120, "Photon / JVM", "vectorized engine", BLUE_BG, BLUE)
    s.box(420, 90, 170, 120, "Python worker", "one row at a time", RED_BG, RED)
    s.arrow(212, 125, 416, 125, RED, 2.5)
    s.text(314, 116, "serialize rows", 12, RED)
    s.arrow(416, 178, 214, 178, RED, 2.5)
    s.text(314, 197, "deserialize results", 12, RED)
    s.text(315, 250, "opaque to the optimizer · no filter pushdown through it", 13, MUTED, italic=True)
    s.text(315, 272, "pandas UDF: same trip, but in Arrow batches (faster)", 13, MUTED, italic=True)
    s.panel(630, 30, 350, 280, "do", "built-in functions")
    s.box(680, 90, 250, 120, "Photon / JVM", "when · round · regexp · date", GREEN_BG, GREEN)
    s.text(805, 250, "stays native and vectorized", 13, MUTED, italic=True)
    s.text(805, 272, "the optimizer understands it", 13, MUTED, italic=True)
    save("python_udf", s)


def plan_bloat():
    s = Svg(1000, 330)
    s.panel(20, 30, 470, 280, "dont", "withColumn() × 300 in a loop")
    for i in range(6):
        s.rect(40 + i * 12, 60 + i * 12, 430 - i * 24, 225 - i * 24, "#fff" if i % 2 else RED_BG, RED, 6, 1)
    s.text(255, 182, "Project(Project(Project(…)))", 13, RED, "bold")
    s.text(255, 202, "300 levels deep", 13, RED)
    s.text(255, 298, "re-analyzed on every df.columns inside the loop → O(n²)", 12, MUTED, italic=True)
    s.panel(510, 30, 470, 280, "do", "withColumns({...}) / one select")
    s.rect(560, 120, 370, 70, GREEN_BG, GREEN, 8, 1.5)
    s.text(745, 150, "Project([300 expressions])", 14, GREEN, "bold")
    s.text(745, 172, "one level", 13, GREEN)
    s.text(745, 298, "build the expressions in a Python list/dict, apply once", 12, MUTED, italic=True)
    save("plan_bloat", s)


def small_files():
    s = Svg(1000, 320)
    s.panel(20, 30, 470, 270, "dont", "4,000 tiny files")
    for r in range(14):
        for c in range(40):
            s.add(f'<rect x="{42 + c * 10.5}" y="{62 + r * 11}" width="8" height="8" fill="{RED_BG}" stroke="{RED}" stroke-width="0.6"/>')
    s.text(255, 238, "per file: list · open · read footer · schedule", 13, RED, "bold")
    s.text(255, 260, "overhead dominates the actual reading", 13, MUTED, italic=True)
    s.panel(510, 30, 470, 270, "do", "a few right-sized files")
    for i in range(4):
        s.rect(540 + i * 108, 70, 96, 140, GREEN_BG, GREEN, 6, 1.5)
        s.text(588 + i * 108, 146, "~256 MB", 13, GREEN, "bold")
    s.text(745, 238, "same rows · Delta: OPTIMIZE / predictive optimization", 13, GREEN, "bold")
    s.text(745, 260, "aim for 100 MB – 1 GB per file", 13, MUTED, italic=True)
    save("small_files", s)


def incremental_ingest():
    s = Svg(1000, 330)
    s.panel(20, 30, 470, 280, "dont", "full re-read every run")
    s.panel(510, 30, 470, 280, "do", "Auto Loader (incremental)")
    for d in range(6):
        y = 70 + d * 34
        s.text(40, y + 17, f"run {d + 1}", 12, MUTED, "normal", "start")
        s.rect(90, y, 60 + d * 60, 22, RED_BG, RED, 4, 1)
        s.text(560, y + 17, f"run {d + 1}", 12, MUTED, "normal", "start")
        s.rect(610 + d * 50, y, 50, 22, GREEN_BG, GREEN, 4, 1)
    s.text(255, 293, "cost grows with all history", 13, RED, "bold")
    s.text(745, 293, "checkpoint remembers files; only new ones are read", 13, GREEN, "bold")
    save("incremental_ingest", s)


def range_join():
    s = Svg(1000, 340)
    s.panel(20, 30, 470, 290, "dont", "ts BETWEEN start AND end")
    import random
    rnd = random.Random(3)
    rx = [60 + i * 32 for i in range(6)]
    sy = [80 + i * 36 for i in range(6)]
    for x in rx:
        s.box(x - 14, 60, 28, 22, "ts", None, fill=BLUE_BG, stroke=BLUE, size=11, rx=4)
    for i, y in enumerate(sy):
        s.box(340, y - 8, 120, 26, f"session {i + 1}", None, fill=GREY_BG, stroke=LINE, size=12, rx=4)
        for x in rx:
            s.add(f'<line x1="{x}" y1="84" x2="338" y2="{y + 5}" stroke="{RED}" stroke-width="0.8" opacity="0.6"/>')
    s.text(255, 292, "every reading × every session of its car ≈ 15 billion checks", 13, RED, "bold")
    s.panel(510, 30, 470, 290, "do", "hint(\"range_join\", bin size)")
    for b in range(3):
        x = 540 + b * 145
        s.rect(x, 62, 130, 200, GREY_BG, LINE, 8, 1)
        s.text(x + 65, 82, f"bin {b + 1}", 12, MUTED, "bold")
        for i in range(2):
            s.box(x + 10 + i * 58, 96, 50, 22, "ts", None, fill=BLUE_BG, stroke=BLUE, size=11, rx=4)
        s.box(x + 15, 196, 100, 26, f"session {b + 1}", None, fill="#fff", stroke=LINE, size=12, rx=4)
        for i in range(2):
            s.add(f'<line x1="{x + 35 + i * 58}" y1="120" x2="{x + 65}" y2="194" stroke="{GREEN}" stroke-width="1.5"/>')
    s.text(745, 292, "equi-join on the bin, then check BETWEEN only inside it", 13, GREEN, "bold")
    save("range_join", s)


def scd_explosion():
    s = Svg(1000, 300)
    s.panel(20, 30, 470, 250, "dont", "join on customer_id only")
    s.box(40, 70, 130, 50, "order 42", "cust 7 · $100", BLUE_BG, BLUE, 14)
    for i, tier in enumerate(["Bronze (v1)", "Silver (v2)", "Gold (v3)"]):
        y = 60 + i * 52
        s.box(300, y, 170, 40, f"cust 7 · {tier}", None, fill=GREY_BG, stroke=LINE, size=13)
        s.arrow(172, 95, 296, y + 20, RED, 1.5)
    s.text(255, 235, "1 order → 3 rows → revenue counted 3×", 14, RED, "bold")
    s.text(255, 258, "no error; just wrong numbers", 13, MUTED, italic=True)
    s.panel(510, 30, 470, 250, "do", "one row per key on the dimension")
    s.box(530, 70, 130, 50, "order 42", "cust 7 · $100", BLUE_BG, BLUE, 14)
    s.box(790, 112, 170, 40, "cust 7 · Gold (v3)", None, fill=GREEN_BG, stroke=GREEN, size=13)
    s.arrow(662, 95, 786, 132, GREEN, 1.5)
    s.text(745, 205, "WHERE is_current", 14, GREEN, "bold")
    s.text(745, 228, "or: order_date BETWEEN valid_from AND valid_to", 13, GREEN)
    save("scd_explosion", s)


def window_partition():
    s = Svg(1000, 320)
    s.panel(20, 30, 470, 270, "dont", "Window.orderBy(...)")
    for i in range(6):
        s.box(40 + i * 72, 66, 62, 34, f"part {i + 1}", None, fill=BLUE_BG, stroke=BLUE, size=12, rx=5)
        s.add(f'<line x1="{71 + i * 72}" y1="102" x2="{205 + i * 20}" y2="170" stroke="{RED}" stroke-width="2.5"/>')
    s.box(165, 172, 180, 56, "1 task", "sorts all 100M rows", RED_BG, RED)
    s.text(255, 266, "\"No Partition Defined for Window operation!\"", 13, RED, italic=True)
    s.panel(510, 30, 470, 270, "do", "Window.partitionBy(key).orderBy(...)")
    for i in range(6):
        s.box(530 + i * 72, 66, 62, 34, f"part {i + 1}", None, fill=BLUE_BG, stroke=BLUE, size=12, rx=5)
        s.arrow(561 + i * 72, 102, 561 + i * 72, 168, GREEN, 2)
        s.box(530 + i * 72, 172, 62, 56, f"task {i + 1}", None, fill=GREEN_BG, stroke=GREEN, size=12, rx=5)
    s.text(745, 266, "each key's rows sorted independently, in parallel", 13, GREEN, italic=True)
    save("window_partition", s)


def write_layout():
    s = Svg(1000, 330)
    s.panel(20, 30, 470, 280, "dont", "partitionBy(order_date, dealer_id)")
    y = 66
    for d in ["order_date=2025-10-01/", "order_date=2025-10-02/"]:
        s.text(40, y + 12, d, 13, INK, "bold", "start")
        y += 20
        for k in [1, 2, 3]:
            s.text(64, y + 12, f"dealer_id={k}/  part-0.parquet (12 KB)", 12, RED, "normal", "start")
            y += 18
        s.text(64, y + 12, "… 500 dealer folders", 12, MUTED, "normal", "start")
        y += 24
    s.text(40, y + 12, "… × 92 days ≈ 45,000 folders of tiny files", 13, RED, "bold", "start")
    s.panel(510, 30, 470, 280, "do", "CLUSTER BY (order_date, dealer_id)")
    for i in range(6):
        s.rect(540 + (i % 3) * 140, 70 + (i // 3) * 90, 125, 75, GREEN_BG, GREEN, 6, 1.5)
        s.text(602 + (i % 3) * 140, 103 + (i // 3) * 90, "~128–1024 MB", 12, GREEN, "bold")
        s.text(602 + (i % 3) * 140, 121 + (i // 3) * 90, "co-located keys", 11, MUTED)
    s.text(745, 270, "data skipping on both keys · change keys anytime", 13, GREEN, "bold")
    s.text(745, 292, "coalesce(1) instead? one task writes everything", 12, MUTED, italic=True)
    save("write_layout", s)


def medallion_lab():
    s = Svg(1290, 380)
    s.text(645, 30, "The end-to-end lab: endtoend_<layer>_<entity>_<fact|dim>", 18, INK, "bold")
    cols = [
        (20, "Raw files", "volume raw_files/lab/", ["orders_json/ (JSON)", "dealers_csv/ (CSV)"], GREY_BG, MUTED),
        (270, "Bronze", "as delivered + lineage", ["endtoend_bronze_orders_fact", "endtoend_bronze_dealers_dim"], "#f6e7d8", "#a8642a"),
        (520, "Silver", "typed · clean · deduped", ["endtoend_silver_orders_fact", "endtoend_silver_dealers_dim",
                                                   "endtoend_silver_parts_dim", "endtoend_quarantine_orders_fact"], "#eef0f2", "#7d8a96"),
        (770, "Gold", "aggregated for a purpose", ["endtoend_gold_daily_dealer_sales_fact", "endtoend_gold_category_region_fact"], "#fbf3d5", "#b08d1a"),
        (1020, "Serve", "answers and visuals", ["SQL queries", "AI/BI dashboard"], BLUE_BG, BLUE),
    ]
    for x, title, sub, items, fill, stroke in cols:
        s.rect(x, 55, 226, 295, fill, stroke, 12, 2)
        s.text(x + 113, 85, title, 17, stroke, "bold")
        s.text(x + 113, 106, sub, 11.5, MUTED)
        for i, it in enumerate(items):
            s.rect(x + 8, 125 + i * 52, 210, 40, "#fff", stroke, 6, 1)
            s.text(x + 113, 150 + i * 52, it, 9.8 if len(it) > 30 else 11, INK, "bold")
    for x in (270, 520, 770, 1020):
        s.arrow(x - 21, 200, x - 4, 200, MUTED, 2)
    for x, t in [(270, "Auto Loader / spark.read"), (520, "SQL: try_cast, QUALIFY"), (770, "SQL: joins + GROUP BY"),
                 (1020, "SQL, dashboard datasets")]:
        s.text(x - 10, 372, t, 11, MUTED, italic=True)
    save("medallion_lab", s)


if __name__ == "__main__":
    for fn in [data_model, driver_bottleneck, lazy_evaluation, driver_loop, python_udf, plan_bloat, small_files,
               incremental_ingest, range_join, scd_explosion, window_partition, write_layout, medallion_lab]:
        fn()
