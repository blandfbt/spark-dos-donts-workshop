# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 07 · Genie Code and custom skills
# MAGIC
# MAGIC **What you'll do:**
# MAGIC 1. Understand the difference between **Genie (SQL agents)** and **Genie Code**
# MAGIC 2. Install the workshop's **skill file** so Genie Code knows the Apex Motorsports Parts domain
# MAGIC 3. Use a **prompt** to ask Genie Code to create a Genie agent for you
# MAGIC 4. Use a second prompt to generate a full sales analysis notebook
# MAGIC
# MAGIC **The idea:** you describe *what* you want (a Genie agent with these tables and business rules). The skill teaches
# MAGIC Genie Code *how* (metric definitions, join paths, API best practices). You never write API code yourself.
# MAGIC
# MAGIC **Before you start:** run **04** (Knowledge Store agent) and **05** (benchmarks). **Compute:** Serverless.

# COMMAND ----------

# DBTITLE 1,⚙️ Configuration
# MAGIC %run ../CONFIG

# COMMAND ----------

# DBTITLE 1,⚙️ Genie helpers
# MAGIC %run ./genie_helpers

# COMMAND ----------

# MAGIC %md
# MAGIC ## Connect and load the primary agent
# MAGIC
# MAGIC Read the Knowledge Store agent id from your `workshop_config` table.

# COMMAND ----------

PRIMARY_SPACE_ID = load_config().get(CFG_KEY_CURATED, "")
if not PRIMARY_SPACE_ID:
    raise RuntimeError("genie_space_id not found in workshop_config. Run notebook 04 first.")
print(f"Primary agent: {genie_ui_room_url(PRIMARY_SPACE_ID)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Genie vs Genie Code
# MAGIC
# MAGIC | | Genie (agent) | Genie Code |
# MAGIC |---|---|---|
# MAGIC | **What it does** | Answers data questions with SQL | Generates and runs notebook code, builds assets |
# MAGIC | **Where it lives** | AI/BI Genie agent (web UI) | Assistant side panel in notebooks and editors |
# MAGIC | **How to teach it** | Knowledge Store: instructions, example SQL, measures | Skill files in `.assistant/skills/` |
# MAGIC | **Best for** | Ad-hoc data questions | Building agents, complex analysis, multi-step workflows |
# MAGIC
# MAGIC **Key insight:** the skill gives Genie Code domain knowledge (what margin % means, which gold table answers what).
# MAGIC The prompt tells it what to build. Together, Genie Code can create an entire Genie agent for you.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Review the skill file
# MAGIC
# MAGIC The skill ships with this repo, next to this notebook:
# MAGIC
# MAGIC ```
# MAGIC <repo>/
# MAGIC   CONFIG
# MAGIC   genie/
# MAGIC     07_genie_code_skills          <-- you are here
# MAGIC     skill/
# MAGIC       apex-motorsports-analytics_genie/
# MAGIC         SKILL.md
# MAGIC ```
# MAGIC
# MAGIC It has two parts:
# MAGIC - **Part 1: Apex Motorsports Parts domain knowledge.** Metrics (net revenue, margin, margin %, revenue per order),
# MAGIC   the gold/silver tables and their grain, join paths, value conventions (regions, tiers, state codes).
# MAGIC - **Part 2: Genie agent best practices.** Instructions, example SQL, benchmarks, and the API details Genie Code
# MAGIC   needs to call the REST API correctly.
# MAGIC
# MAGIC The skill is **generic**: it teaches domain concepts and API patterns, not your catalog or schema.

# COMMAND ----------

import os
import shutil

SKILL_NAME = "apex-motorsports-analytics_genie"
notebook_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
notebook_path = notebook_path[len("/Workspace"):] if notebook_path.startswith("/Workspace/") else notebook_path
notebook_dir = "/".join(notebook_path.split("/")[:-1])   # .../<repo>/genie
repo_dir = "/".join(notebook_path.split("/")[:-2])       # .../<repo>

# The skill ships in genie/skill/ next to this notebook. Depending on how the repo was imported it can also sit at
# the repo root; check both and use whichever exists. /Workspace<path> is the POSIX view of a workspace file.
REL = f"skill/{SKILL_NAME}/SKILL.md"
candidates = [f"{notebook_dir}/{REL}", f"{repo_dir}/genie/{REL}", f"{repo_dir}/{REL}"]
skill_source = next((c for c in dict.fromkeys(candidates) if os.path.exists(f"/Workspace{c}")), None)

if skill_source:
    skill_url = f"{host}/#workspace{skill_source}"
    displayHTML(
        f'<p>\U0001F4C4 <b>Skill file found:</b> '
        f'<a href="{skill_url}" target="_blank" rel="noopener">{skill_source}</a>'
        f'<br/><span style="color:#5a6570">The next cell installs it into your '
        f'<code>.assistant/skills/</code> folder.</span></p>'
    )
else:
    print("Skill file not found. Looked in:")
    for c in dict.fromkeys(candidates):
        print(f"  /Workspace{c}")
    print("\nMake sure the genie/skill/ folder came along with the repo, then re-run this cell.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Install the skill into `.assistant/skills/`
# MAGIC
# MAGIC Genie Code discovers skills in your **`.assistant/skills/`** folder
# MAGIC (`/Workspace/Users/<your_email>/.assistant/skills/`). The **next cell copies the skill there for you** and verifies
# MAGIC it. Only your own home folder is touched. The `_genie` suffix tells Genie Code to load this skill automatically.
# MAGIC
# MAGIC **If you'd rather do it by hand** (or the copy fails on your workspace):
# MAGIC 1. In the workspace file browser, open the `genie/skill/` folder (link above)
# MAGIC 2. Right-click **`apex-motorsports-analytics_genie`** and **Copy**
# MAGIC 3. Navigate to `/Workspace/Users/<your_email>/.assistant/skills/` (create the folders if they don't exist)
# MAGIC 4. Paste

# COMMAND ----------

user_email = w.current_user.me().user_name
dest_dir = f"/Workspace/Users/{user_email}/.assistant/skills/{SKILL_NAME}"
dest_path = f"{dest_dir}/SKILL.md"

if skill_source is None:
    print("No skill source found (see the previous cell): cannot install automatically.")
    print("Follow the manual steps above once the genie/skill/ folder is in your workspace.")
elif os.path.exists(dest_path):
    print(f"Skill already installed: {dest_path}  ({os.path.getsize(dest_path):,} bytes)")
else:
    try:
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copyfile(f"/Workspace{skill_source}", dest_path)
        print(f"Installed skill -> {dest_path}  ({os.path.getsize(dest_path):,} bytes)")
    except Exception as e:
        print(f"Auto-copy failed: {e}")
        print(f"Use the manual steps above to copy the {SKILL_NAME} folder")
        print("into /Workspace/Users/<your_email>/.assistant/skills/.")

print("\nGenie Code loads skills from .assistant/skills/ automatically in a NEW notebook:")
print(f"open one and the {SKILL_NAME} skill will be available to the assistant.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prompt 1: ask Genie Code to create a Genie agent
# MAGIC
# MAGIC This prompt describes *what* you want: a Genie agent with your tables, business rules and example SQL. The skill
# MAGIC teaches Genie Code the details behind the scenes.
# MAGIC
# MAGIC ### How to use
# MAGIC 1. Open a **new, empty notebook**
# MAGIC 2. Open **Genie Code** (the assistant side panel)
# MAGIC 3. Paste the prompt printed below
# MAGIC 4. Review and run what it generates: you get a fully configured Genie agent

# COMMAND ----------

prompt_create_space = f"""
Create a Genie agent called "{GENIE_TITLE_GENIE_CODE}".

IMPORTANT: Create the agent directly. Do NOT generate a notebook with API code.
Use your built-in ability to create and configure a Genie agent.

My tables are in {SOURCE_FQN} (read-only; December 2025 data for Apex Motorsports Parts, a fictional performance-parts seller):
- endtoend_gold_daily_dealer_sales_fact (order_date, region, dealer_id, dealer_name, dealer_tier, orders, units, net_revenue, margin): one row per day and dealer
- endtoend_gold_category_region_fact (region, category, orders, units, net_revenue, margin, margin_pct): one row per region and part category
- endtoend_silver_dealers_dim (dealer_id, dealer_name, region, state, dealer_tier, updated_at): one row per dealer
- endtoend_silver_parts_dim (part_id, part_name, category, list_price, unit_cost): one row per part

The agent should help sales managers answer questions about:
- Net revenue and margin by day, week, region, dealer tier, dealer and state
- Margin % by part category and region
- Average revenue per order
- Top and bottom dealers

Key business rules to include in the agent instructions:
- Margin % = 100 * SUM(margin) / SUM(net_revenue). Never average margin_pct or daily percentages.
- Average revenue per order = SUM(net_revenue) / SUM(orders)
- Dealer state is a two-letter code (TX, CA, MI, ...) in endtoend_silver_dealers_dim; join it on dealer_id
- Part category questions use endtoend_gold_category_region_fact (it has no dates or dealers)
- Weeks start on Monday: CAST(DATE_TRUNC('WEEK', order_date) AS DATE)
- Use exact string match (= 'Midwest') for region, dealer_tier and category
- For integer counts use CAST(... AS BIGINT); round money and rates to 2 decimals

Include 3 sample starter questions and 8-10 example question/SQL pairs covering:
- Simple totals and counts
- The join from daily sales to the dealers dim (state)
- Ratio calculations (margin %, revenue per order)
- Category x region questions
- Weekly and date-range filtering

If an agent with this title already exists, update it instead of creating a duplicate.
"""

print("=" * 70)
print("COPY THIS PROMPT INTO GENIE CODE (assistant side panel)")
print("=" * 70)
print(prompt_create_space)
print("=" * 70)
print(f"\nPrompt length: {len(prompt_create_space):,} chars")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prompt 2: generate a sales analysis notebook
# MAGIC
# MAGIC This prompt asks Genie Code to build a complete analysis notebook using the same domain knowledge from the skill.
# MAGIC Any table it writes goes to **your** schema.
# MAGIC
# MAGIC ### How to use
# MAGIC 1. Open another **new, empty notebook**
# MAGIC 2. Open **Genie Code**
# MAGIC 3. Paste the prompt below and run the generated cells

# COMMAND ----------

prompt_analysis = f"""
Create a December 2025 sales analysis notebook for Apex Motorsports Parts using the tables in {SOURCE_FQN}
(read-only). Use the apex-motorsports-analytics_genie skill for domain context. If you save any table, save it in
{FULL_SCHEMA}, never in {SOURCE_FQN}.

Generate these sections:

1. Setup: show row counts for the 4 tables
2. Revenue: total net revenue, daily trend, weekly trend (Monday-start weeks)
3. Margin: margin % by region and by dealer tier (weighted, SUM / SUM)
4. Dealers: top 10 and bottom 10 dealers by net revenue; net revenue by dealer state
5. Categories: margin % and net revenue by part category, and a region x category heatmap of margin %
6. Executive summary: net revenue, margin %, orders, average revenue per order, best region, best category

Use SQL cells where possible. Join path: endtoend_gold_daily_dealer_sales_fact.dealer_id ->
endtoend_silver_dealers_dim.dealer_id (for state). Margin % is always 100 * SUM(margin) / SUM(net_revenue).
"""

print("=" * 70)
print("COPY THIS PROMPT INTO GENIE CODE (assistant side panel)")
print("=" * 70)
print(prompt_analysis)
print("=" * 70)
print(f"\nPrompt length: {len(prompt_analysis):,} chars")

# COMMAND ----------

# MAGIC %md
# MAGIC ## What you learned
# MAGIC
# MAGIC | Concept | What you did |
# MAGIC |---|---|
# MAGIC | **Skill** | Installed a reusable `.md` file with Apex Motorsports Parts domain knowledge |
# MAGIC | **Prompt 1** | Asked Genie Code to create a Genie agent: it handled the API calls |
# MAGIC | **Prompt 2** | Asked Genie Code to build a full analysis notebook |
# MAGIC
# MAGIC ```
# MAGIC Skill (domain knowledge)      +    Prompt (what you want)       =    Output
# MAGIC apex-motorsports-analytics         "Create an agent for these         Genie agent with
# MAGIC   - margin %, revenue/order          4 tables with these rules"         instructions, samples,
# MAGIC   - grains, join paths                                                  example SQL
# MAGIC   - API best practices
# MAGIC ```
# MAGIC
# MAGIC **Next:** notebook **08**: compare the baseline, metric-view and Knowledge Store agents.
