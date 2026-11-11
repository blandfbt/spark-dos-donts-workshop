# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Generate the workshop data (instructor, run once before the workshop)
# MAGIC
# MAGIC > **Compute:** serverless, **environment version 5 or later** (Environment side panel).
# MAGIC >
# MAGIC > 🧑‍🏫 **Instructor only.** Participants don't run this notebook: they read the tables it writes.
# MAGIC
# MAGIC **Apex Motorsports Parts** (a fictional company) sells performance parts through 500 dealers and
# MAGIC runs a 20-car test program. This notebook generates everything the Do's & Don'ts workshop needs into the
# MAGIC shared source schema set in `CONFIG` (`dbx_workshop_dev.shared`). Participants read it from there and
# MAGIC write their own tables to their own schema. The instructor setup job normally runs it, followed by
# MAGIC `01_prebuild_shared_gold`.
# MAGIC
# MAGIC ![Workshop data model](../notebooks/images/data_model.png)
# MAGIC
# MAGIC | object | shape | used to show |
# MAGIC |---|---|---|
# MAGIC | `fact_orders` | star-schema fact, ~100M rows, liquid clustered by `order_date` | collect/toPandas, repeated actions, driver loops, UDFs, windows, writes |
# MAGIC | `dim_customer`, `dim_dealer`, `dim_part`, `dim_date` | star-schema dimensions | joins, broadcast |
# MAGIC | `dim_customer_history` | SCD type 2, 1–3 versions per customer | the duplicate-key join explosion |
# MAGIC | `telemetry_wide` | 1M rows × ~300 sensor columns | column pruning, `withColumn` loops |
# MAGIC | `telemetry_readings` + `track_sessions` | 1 Hz car telemetry + session start/end windows | range (non-equi) joins |
# MAGIC | volume `raw_files/orders_csv` | CSV, one quarter of orders | `inferSchema` vs. an explicit schema |
# MAGIC | volume `raw_files/telemetry_small_files` vs `telemetry_compacted` | the same rows as 4,000 tiny vs 4 large Parquet files | the small-files problem |
# MAGIC | volume `raw_files/daily_order_extracts` | one Parquet folder per day | union-in-a-loop vs. one read |
# MAGIC | volume `raw_files/orders_landing` | Parquet landing zone | full re-read vs. incremental Auto Loader |
# MAGIC | volume `raw_files/lab/` | messy December orders (JSON) and dealer list (CSV) | the bronze-to-gold lab |
# MAGIC
# MAGIC Every row is generated on the executors from `spark.range` and seeded random functions, so
# MAGIC nothing is collected on the driver and reruns produce the same data. **Reruns replace** every
# MAGIC table and volume folder written here.

# COMMAND ----------

# DBTITLE 1,⚙️ Instructor mode (writes to the shared source schema)
INSTRUCTOR_SETUP = True

# COMMAND ----------

# MAGIC %run ../CONFIG

# COMMAND ----------

# DBTITLE 1,⚙️ Parameters, schema and volume
from pyspark.sql import functions as F

FACT_ROWS = int(_job_param("fact_rows", "100000000"))  # 100M makes the Don'ts clearly hurt; 20M is a quick smoke test
SCHEMA = SOURCE_SCHEMA  # everything below writes to the shared source schema

N_DEALERS = 500
N_PARTS = 25_000
N_CUSTOMERS = 2_000_000
N_CARS = 20
TELEMETRY_DAYS = 60  # 08:00-18:00 at 1 Hz per car and day
SESSIONS_PER_DAY = 6
WIDE_ROWS = 1_000_000
WIDE_SENSOR_GROUPS = [
    "tyre_temp", "tyre_press", "brake_temp", "brake_press", "susp_travel",
    "damper_vel", "aero_load", "oil_temp", "coolant_temp", "exhaust_temp",
]
WIDE_SENSORS_PER_GROUP = 30  # 10 x 30 = 300 sensor columns

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`.raw_files")


def T(name):  # in this notebook, T() means the shared source schema
    return SRC(name)


def save(df, name, cluster_by=None):
    """Replace a workshop table (drop first so clustering/schema changes never conflict)."""
    spark.sql(f"DROP TABLE IF EXISTS {T(name)}")
    writer = df.write.mode("overwrite")
    if cluster_by:
        writer = writer.clusterBy(*cluster_by)
    writer.saveAsTable(T(name))
    print(f"{name:24} {spark.table(T(name)).count():>14,} rows")


def pick(values, rnd):
    """Choose one of values using a uniform random column rnd in [0, 1)."""
    return F.element_at(F.array(*[F.lit(v) for v in values]), (F.floor(rnd * len(values)) + 1).cast("int"))


print(f"Writing to {CATALOG}.{SCHEMA}; fact_orders rows: {FACT_ROWS:,}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Star-schema dimensions

# COMMAND ----------

# DBTITLE 1,Write dim_date, dim_dealer, dim_part
dim_date = (
    spark.sql("SELECT explode(sequence(DATE'2024-01-01', DATE'2025-12-31')) AS order_date")
    .select(
        F.date_format("order_date", "yyyyMMdd").cast("int").alias("date_key"),
        "order_date",
        F.year("order_date").alias("year"),
        F.quarter("order_date").alias("quarter"),
        F.month("order_date").alias("month"),
        F.date_format("order_date", "MMMM").alias("month_name"),
        F.date_format("order_date", "EEEE").alias("day_of_week"),
        F.dayofweek("order_date").isin(1, 7).alias("is_weekend"),
    )
)
save(dim_date, "dim_date")

REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West", "Northwest"]
STATES = ["MI", "OH", "IN", "TX", "CA", "FL", "NC", "GA", "AZ", "WA", "OR", "NY", "PA", "IL", "TN"]
dim_dealer = spark.range(1, N_DEALERS + 1).select(
    F.col("id").cast("int").alias("dealer_id"),
    F.format_string("Apex Dealer %03d", "id").alias("dealer_name"),
    pick(REGIONS, F.rand(11)).alias("region"),
    pick(STATES, F.rand(12)).alias("state"),
    F.when(F.col("id") % 10 == 0, "Platinum").when(F.col("id") % 4 == 0, "Gold").otherwise("Standard").alias("dealer_tier"),
    F.date_add(F.lit("2010-01-01").cast("date"), (F.rand(13) * 5000).cast("int")).alias("opened_date"),
)
save(dim_dealer, "dim_dealer")

CATEGORIES = ["Brakes", "Engine", "Tires", "Suspension", "Electrical", "Aero", "Body", "Fluids", "Exhaust", "Drivetrain"]
dim_part = (
    spark.range(1, N_PARTS + 1)
    .select(
        F.col("id").cast("int").alias("part_id"),
        pick(CATEGORIES, F.rand(21)).alias("category"),
        F.round(5 + F.pow(F.rand(22), 3) * 2000, 2).alias("list_price"),
        F.rand(23).alias("_cost_ratio"),
    )
    .select(
        "part_id",
        F.format_string("%s part %05d", "category", "part_id").alias("part_name"),
        "category",
        "list_price",
        F.round(F.col("list_price") * (0.45 + F.col("_cost_ratio") * 0.3), 2).alias("unit_cost"),
    )
)
save(dim_part, "dim_part")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Customer dimensions (SCD2)
# MAGIC
# MAGIC Every customer has 1–3 versions, and exactly one version per customer has `is_current = true`.
# MAGIC Joining orders to this table on `customer_id` alone multiplies rows. That mistake is one of the
# MAGIC join Don'ts.

# COMMAND ----------

# DBTITLE 1,Write dim_customer_history and dim_customer
SEGMENTS = ["Club racer", "Pro team", "Weekend enthusiast", "Fleet", "Restoration shop"]
customer_history = (
    spark.range(1, N_CUSTOMERS + 1, 1, 64)
    .withColumn("versions", (F.abs(F.xxhash64("id")) % 3 + 1).cast("int"))
    .withColumn("version", F.explode(F.sequence(F.lit(1), F.col("versions"))))
    .select(
        F.col("id").cast("long").alias("customer_id"),
        "version",
        F.format_string("Customer %07d", "id").alias("customer_name"),
        pick(STATES, F.rand(31)).alias("state"),
        pick(SEGMENTS, F.rand(32)).alias("segment"),
        F.element_at(F.array(F.lit("Bronze"), F.lit("Silver"), F.lit("Gold")), F.col("version")).alias("loyalty_tier"),
        F.date_add(F.lit("2023-01-01").cast("date"), (F.col("version") - 1) * 240).alias("valid_from"),
        F.when(F.col("version") == F.col("versions"), F.lit("9999-12-31").cast("date"))
        .otherwise(F.date_add(F.lit("2023-01-01").cast("date"), F.col("version") * 240 - 1))
        .alias("valid_to"),
        (F.col("version") == F.col("versions")).alias("is_current"),
    )
)
save(customer_history, "dim_customer_history")

save(
    spark.table(T("dim_customer_history")).where("is_current").drop("version", "valid_from", "valid_to", "is_current"),
    "dim_customer",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Order fact
# MAGIC
# MAGIC Two years of order lines. The distributions are skewed the way real ones are: 5% of the lines
# MAGIC come from 100 large fleet customers, popular parts and dealers sell far more than the long tail,
# MAGIC and most lines have no discount.

# COMMAND ----------

# DBTITLE 1,Write fact_orders
fact_partitions = max(16, FACT_ROWS // 2_000_000)
parts = spark.table(T("dim_part")).select("part_id", "list_price")
fact_orders = (
    spark.range(0, FACT_ROWS, 1, fact_partitions)
    .select(
        (F.col("id") + 1).alias("order_id"),
        F.timestamp_seconds(
            F.unix_timestamp(F.lit("2024-01-01 00:00:00")) + F.floor(F.rand(41) * 731 * 86400)
        ).alias("order_ts"),
        F.when(F.rand(42) < 0.05, F.floor(F.rand(43) * 100) + 1)
        .otherwise(F.floor(F.rand(44) * N_CUSTOMERS) + 1)
        .cast("long")
        .alias("customer_id"),
        (F.floor(F.pow(F.rand(45), 1.5) * N_DEALERS) + 1).cast("int").alias("dealer_id"),
        (F.floor(F.pow(F.rand(46), 2) * N_PARTS) + 1).cast("int").alias("part_id"),
        (F.floor(F.pow(F.rand(47), 4) * 12) + 1).cast("int").alias("quantity"),
        pick([0.0, 0.0, 0.0, 0.0, 0.05, 0.10, 0.15, 0.20, 0.30], F.rand(48)).alias("discount_pct"),
        pick(["Dealer", "Dealer", "Online", "Phone"], F.rand(49)).alias("channel"),
        F.when(F.rand(50) < 0.1, F.format_string("PROMO-%04d", (F.rand(51) * 500).cast("int"))).alias("promo_code"),
        F.rand(52).alias("_price_noise"),
    )
    .join(F.broadcast(parts), "part_id")
    .select(
        "order_id",
        "order_ts",
        F.to_date("order_ts").alias("order_date"),
        F.date_format("order_ts", "yyyyMMdd").cast("int").alias("date_key"),
        "customer_id",
        "dealer_id",
        "part_id",
        "quantity",
        F.round(F.col("list_price") * (0.9 + F.col("_price_noise") * 0.2), 2).alias("unit_price"),
        "discount_pct",
        "channel",
        "promo_code",
    )
)
save(fact_orders, "fact_orders", cluster_by=["order_date"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Telemetry readings and sessions
# MAGIC
# MAGIC 20 cars run six sessions a day between 08:00 and 18:00. The readings arrive at 1 Hz for the whole
# MAGIC day; `track_sessions` holds the start and end of each session. To label each reading with its
# MAGIC session you need a **range join** (`ts BETWEEN start_ts AND end_ts`).

# COMMAND ----------

# DBTITLE 1,Write telemetry_readings and track_sessions
SESSION_NAMES = ["FP1", "FP2", "FP3", "Qualifying", "Sprint", "Race"]
day_seconds = 10 * 3600
readings = (
    spark.range(0, N_CARS * TELEMETRY_DAYS * day_seconds, 1, 96)
    .select(
        (F.col("id") % N_CARS + 1).cast("int").alias("car_no"),
        (F.col("id") / N_CARS).cast("long").alias("t"),
    )
    .select(
        F.format_string("APX-%02d", "car_no").alias("car_id"),
        F.timestamp_seconds(
            F.unix_timestamp(F.lit("2025-03-01 08:00:00"))
            + (F.col("t") / day_seconds).cast("long") * 86400
            + F.col("t") % day_seconds
        ).alias("ts"),
        F.round(160 + 110 * F.sin(F.col("t") / 37.0 + F.col("car_no")) + F.rand(61) * 6, 1).alias("speed_kph"),
        F.round(9000 + 3000 * F.sin(F.col("t") / 37.0 + F.col("car_no")) + F.rand(62) * 200, 0).cast("int").alias("rpm"),
        F.round(F.greatest(F.lit(0.0), 100 * F.sin(F.col("t") / 37.0 + F.col("car_no") + 0.4)), 1).alias("throttle_pct"),
        F.round(F.greatest(F.lit(0.0), -100 * F.sin(F.col("t") / 37.0 + F.col("car_no") + 0.4)), 1).alias("brake_pct"),
        F.round(95 + 10 * F.sin(F.col("t") / 900.0) + F.rand(63), 1).alias("oil_temp_c"),
    )
)
save(readings, "telemetry_readings")

sessions = (
    spark.range(0, N_CARS * TELEMETRY_DAYS * SESSIONS_PER_DAY)
    .select(
        (F.col("id") % N_CARS + 1).cast("int").alias("car_no"),
        (F.col("id") / N_CARS / SESSIONS_PER_DAY).cast("int").alias("day"),
        ((F.col("id") / N_CARS).cast("int") % SESSIONS_PER_DAY).alias("k"),
    )
    .withColumn(
        "start_ts",
        F.timestamp_seconds(
            F.unix_timestamp(F.lit("2025-03-01 08:00:00"))
            + F.col("day") * 86400
            + F.col("k") * 100 * 60
            + F.floor(F.rand(71) * 20 * 60)
        ),
    )
    .select(
        F.format_string("APX-%02d-D%02d-%s", "car_no", "day", F.element_at(F.array(*[F.lit(s) for s in SESSION_NAMES]), F.col("k") + 1)).alias("session_id"),
        F.format_string("APX-%02d", "car_no").alias("car_id"),
        F.element_at(F.array(*[F.lit(s) for s in SESSION_NAMES]), F.col("k") + 1).alias("session_type"),
        "start_ts",
        F.timestamp_seconds(F.unix_timestamp("start_ts") + 50 * 60 + F.floor(F.rand(72) * 20 * 60)).alias("end_ts"),
    )
)
save(sessions, "track_sessions")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Wide telemetry table

# COMMAND ----------

# DBTITLE 1,Write telemetry_wide
sensor_cols = [f"{g}_{i:03d}" for g in WIDE_SENSOR_GROUPS for i in range(1, WIDE_SENSORS_PER_GROUP + 1)]
sensor_exprs = [
    F.round(
        (40 + (n % 7) * 15)
        + (5 + n % 11) * F.sin(F.col("id") / (50.0 + n))
        + (F.abs(F.xxhash64("id", F.lit(n))) % 1000) / 500.0,
        3,
    ).alias(c)
    for n, c in enumerate(sensor_cols)
]
telemetry_wide = spark.range(0, WIDE_ROWS, 1, 32).select(
    F.format_string("APX-%02d", (F.col("id") % N_CARS + 1).cast("int")).alias("car_id"),
    F.timestamp_seconds(F.unix_timestamp(F.lit("2025-03-01 08:00:00")) + (F.col("id") / N_CARS).cast("long")).alias("ts"),
    ((F.col("id") / N_CARS / 90).cast("int") + 1).alias("lap"),
    *sensor_exprs,
)
save(telemetry_wide, "telemetry_wide")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Raw files in the volume

# COMMAND ----------

# DBTITLE 1,Land raw CSV and Parquet files
def replace_folder(path):
    dbutils.fs.rm(path, True)
    return path


orders = spark.table(T("fact_orders"))
q1_2025 = orders.where("order_date BETWEEN '2025-01-01' AND '2025-03-31'")

# CSV: what a partner system might drop for you (strings everywhere until you give it a schema)
q1_2025.drop("date_key").coalesce(16).write.option("header", True).csv(replace_folder(f"{VOLUME}/orders_csv"))

# One Parquet folder per day, like a daily extract job would produce
(
    q1_2025.repartition("order_date")
    .write.partitionBy("order_date")
    .parquet(replace_folder(f"{VOLUME}/daily_order_extracts"))
)

# The same three days of telemetry as 4,000 tiny files and as 4 well-sized files
three_days = spark.table(T("telemetry_readings")).where("ts < '2025-03-04'")
three_days.repartition(4000).write.parquet(replace_folder(f"{VOLUME}/telemetry_small_files"))
three_days.repartition(4).write.parquet(replace_folder(f"{VOLUME}/telemetry_compacted"))

# Landing zone for the incremental-ingestion scenario: all orders, as an upstream export would deliver them
orders.drop("date_key").write.parquet(replace_folder(f"{VOLUME}/orders_landing"))
dbutils.fs.rm(f"{VOLUME}/_checkpoints", True)

for folder in ["orders_csv", "daily_order_extracts", "telemetry_small_files", "telemetry_compacted", "orders_landing"]:
    files = spark.sql(f"LIST '{VOLUME}/{folder}'").count() if folder != "daily_order_extracts" else None
    print(f"{folder:24} {'' if files is None else f'{files:,} entries'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Raw files for the bronze-to-gold lab
# MAGIC
# MAGIC The lab (`01_bronze_to_gold_lab`) starts from raw files, the way partner systems actually deliver them:
# MAGIC
# MAGIC | folder | content | problems to fix in silver |
# MAGIC |---|---|---|
# MAGIC | `lab/orders_json/` | December 2025 order lines as JSON, ~31 files | ~1% re-sent duplicates (later `sent_at`), 3% US-style timestamps, prices as text (some `$12.50`, some `N/A`), zero/negative quantities, missing dealers, `channel` in mixed case with stray spaces |
# MAGIC | `lab/dealers_csv/` | the dealer reference list as one CSV | duplicate dealers (an older version with a stale tier), regions in mixed case with spaces, some blank names |

# COMMAND ----------

# DBTITLE 1,Land the lab's messy raw files
lab_root = f"{VOLUME}/lab"
december = spark.table(T("fact_orders")).where("order_date >= '2025-12-01'")

lab_orders = (
    december.withColumn("_r", F.rand(81))
    .withColumn("sent_at", F.col("order_ts") + F.expr("INTERVAL 3 MINUTES"))
    .select(
        F.col("order_id").cast("string").alias("order_id"),
        F.when(F.rand(82) < 0.03, F.date_format("order_ts", "MM/dd/yyyy HH:mm:ss"))
        .otherwise(F.date_format("order_ts", "yyyy-MM-dd'T'HH:mm:ss'Z'")).alias("order_ts"),
        F.col("customer_id").cast("string").alias("customer_id"),
        F.when(F.rand(83) < 0.003, F.lit(None)).otherwise(F.col("dealer_id").cast("string")).alias("dealer_id"),
        F.col("part_id").cast("string").alias("part_id"),
        F.when(F.rand(84) < 0.004, F.element_at(F.array(F.lit("0"), F.lit("-1")), (F.floor(F.rand(85) * 2) + 1).cast("int")))
        .otherwise(F.col("quantity").cast("string")).alias("quantity"),
        F.when(F.col("_r") < 0.01, F.format_string("$%.2f", "unit_price"))
        .when(F.col("_r") < 0.012, F.lit("N/A"))
        .otherwise(F.format_string("%.2f", "unit_price")).alias("unit_price"),
        F.col("discount_pct").cast("string").alias("discount_pct"),
        F.when(F.rand(86) < 0.1, F.lower("channel"))
        .when(F.rand(87) < 0.1, F.upper("channel"))
        .when(F.rand(88) < 0.1, F.concat(F.lit(" "), F.col("channel"), F.lit(" ")))
        .otherwise(F.col("channel")).alias("channel"),
        "promo_code",
        F.date_format("sent_at", "yyyy-MM-dd'T'HH:mm:ss'Z'").alias("sent_at"),
        F.to_date("order_ts").alias("_day"),
    )
)
# ~1% of the orders are sent again later by the upstream system (same order_id, later sent_at)
resent = (
    lab_orders.where(F.rand(89) < 0.01)
    .withColumn("sent_at", F.date_format(F.to_timestamp("sent_at", "yyyy-MM-dd'T'HH:mm:ss'Z'") + F.expr("INTERVAL 2 HOURS"),
                                         "yyyy-MM-dd'T'HH:mm:ss'Z'"))
)
(
    lab_orders.unionByName(resent).repartition(31, "_day").drop("_day")
    .write.json(replace_folder(f"{lab_root}/orders_json"))
)

dealer_rows = spark.table(T("dim_dealer"))
current = dealer_rows.select(
    F.col("dealer_id").cast("string").alias("dealer_id"),
    F.when(F.rand(91) < 0.02, F.lit("")).otherwise(F.col("dealer_name")).alias("dealer_name"),
    F.when(F.rand(92) < 0.15, F.lower("region"))
    .when(F.rand(93) < 0.15, F.concat(F.lit("  "), F.upper("region")))
    .otherwise(F.col("region")).alias("region"),
    "state",
    "dealer_tier",
    F.lit("2025-11-15 08:00:00").alias("updated_at"),
)
stale = (
    current.where(F.rand(94) < 0.10)
    .withColumn("dealer_tier", F.lit("Standard"))
    .withColumn("updated_at", F.lit("2024-03-01 08:00:00"))
)
current.unionByName(stale).orderBy(F.rand(95)).coalesce(1).write.option("header", True).csv(
    replace_folder(f"{lab_root}/dealers_csv")
)
dbutils.fs.rm(f"{VOLUME}/_checkpoints/endtoend", True)
print(f"lab orders: {lab_orders.count():,} + {resent.count():,} re-sent · dealers file written")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tag and list what was written

# COMMAND ----------

# DBTITLE 1,Tag the shared objects
# Tag the schema, volume and every generated table, so workshop objects are easy to find and filter
tag_workshop_objects(SCHEMA)

display(
    spark.sql(f"SHOW TABLES IN `{CATALOG}`.`{SCHEMA}`").select("tableName")
)
