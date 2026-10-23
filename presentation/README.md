# Spark at scale: Do's & Don'ts (presentation)

A 19-slide, 15–20 minute talk that goes with the workshop. It spends most of its time on *how* Spark
runs code at scale (driver and executors, lazy plans, the optimizer, shuffles, joins, data layout,
what serverless handles for you). Then it covers the five categories of do's and don'ts with the
timings measured in the workshop, and ends with the workshop and the Genie Code challenge.

| file | what it is |
|---|---|
| `spark_at_scale.html` | the deck: one self-contained file (fonts, logos and diagrams embedded); open it in any browser and share it as is |
| `spark_at_scale.pdf` | the same deck as a PDF, one 16:9 page per slide |
| `export_pdf.sh` | regenerates the PDF with headless Chrome/Chromium/Edge |
| `src/build_deck.py` | source of the slides, diagrams and styling; rebuilds the HTML |
| `src/assets/` | DM Sans / DM Mono fonts and the Databricks logos used by the build |

## Presenting

Open `spark_at_scale.html`. Use **← / →** (or click) to move between slides, **N** to show speaker notes,
and **F** for full screen. A slide number in the URL (`#7`) jumps straight to that slide.

## Rebuild and export

```bash
python3 presentation/src/build_deck.py     # edit slides in build_deck.py, then rebuild the HTML
./presentation/export_pdf.sh               # writes presentation/spark_at_scale.pdf
```

`export_pdf.sh` finds Chrome, Chromium or Edge automatically. Set `CHROME=/path/to/browser` to choose one.
Styling follows the Databricks corporate slide template (navy title and closing slides, oat content
slides, DM Sans, the ©2026 footer).
