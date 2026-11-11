# Bronze: land the raw lab files exactly as delivered, plus lineage columns.
# Same logic as section 1 of notebooks/01_bronze_to_gold_lab, written as Spark Declarative Pipelines datasets.
#
# Pipeline configuration (set by ../00_create_pipeline_and_job):
#   source_volume  /Volumes/dbx_workshop_dev/shared/raw_files   (read-only raw files)
from pyspark import pipelines as dp
from pyspark.sql import functions as F

LAB_RAW = spark.conf.get("source_volume") + "/lab"


@dp.table(
    name="pipeline_bronze_orders_fact",
    comment="December 2025 order lines exactly as delivered (JSON), with lineage columns",
)
def pipeline_bronze_orders_fact():
    # Auto Loader: only new files are read on each update; the pipeline manages the checkpoint and schema location.
    # JSON columns stay strings (typing happens in silver); fields that don't fit land in _rescued_data.
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .load(f"{LAB_RAW}/orders_json")
        .select("*", F.col("_metadata.file_path").alias("_source_file"), F.current_timestamp().alias("_ingested_at"))
    )


@dp.materialized_view(
    name="pipeline_bronze_dealers_dim",
    comment="Dealer list exactly as delivered (CSV), with lineage columns",
)
def pipeline_bronze_dealers_dim():
    # The dealer list is a small full extract that is replaced on every delivery: a batch read is the right fit.
    return (
        spark.read.option("header", True)  # every column stays a string in bronze
        .csv(f"{LAB_RAW}/dealers_csv")
        .select("*", F.col("_metadata.file_path").alias("_source_file"), F.current_timestamp().alias("_ingested_at"))
    )
