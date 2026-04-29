"""
event_etl.py  ·  Glue 4.0 Flex
S3 Raw events/ (JSON, 4종 이벤트 타입) → S3 Mart calendar_events/ (Parquet, partitioned by event_type)
이벤트 타입: book_fair, holiday, publisher_promo, author_signing
"""
import sys
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F

args  = getResolvedOptions(sys.argv, ["JOB_NAME", "RAW_BUCKET", "MART_BUCKET"])
sc    = SparkContext()
glue  = GlueContext(sc)
spark = glue.spark_session
job   = Job(glue)
job.init(args["JOB_NAME"], args)

RAW_PATH  = f"s3://{args['RAW_BUCKET']}/events/"
MART_PATH = f"s3://{args['MART_BUCKET']}/calendar_events/"

EVENT_TYPES = ["book_fair", "holiday", "publisher_promo", "author_signing"]

frames = []
for etype in EVENT_TYPES:
    try:
        df_e = (
            spark.read
            .option("recursiveFileLookup", "true")
            .json(f"{RAW_PATH}{etype}/")
            .withColumn("event_type", F.lit(etype))
        )
        frames.append(df_e)
    except Exception:
        pass

if not frames:
    job.commit()
    sys.exit(0)

from functools import reduce
from pyspark.sql import DataFrame

df_all = reduce(DataFrame.unionByName, frames, reduce(lambda a, b: a.unionByName(b, allowMissingColumns=True), frames))

df_clean = (
    df_all
    .select(
        F.col("event_id"),
        F.col("event_type"),
        F.col("title"),
        F.col("start_date"),
        F.col("end_date"),
        F.col("location").alias("event_location"),
        F.col("isbn13_list"),
        F.col("synced_at"),
    )
    .dropDuplicates(["event_id"])
)

df_clean.write.mode("overwrite").partitionBy("event_type").parquet(MART_PATH)

job.commit()
