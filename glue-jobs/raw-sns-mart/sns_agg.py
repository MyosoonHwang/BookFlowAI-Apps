"""
sns_agg.py  ·  Glue 4.0 Flex
S3 Raw sns/ (JSON) → S3 Mart sns_mentions/ (Parquet, partitioned by mention_date)
is_spike_seed 플래그: mention_count ≥ 10인 경우 True
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

RAW_PATH  = f"s3://{args['RAW_BUCKET']}/sns/"
MART_PATH = f"s3://{args['MART_BUCKET']}/sns_mentions/"

SPIKE_THRESHOLD = 10

df = (
    spark.read
    .option("recursiveFileLookup", "true")
    .json(RAW_PATH)
    .select(
        F.col("mention_id"),
        F.col("isbn13"),
        F.col("platform"),
        F.col("mention_count").cast("int"),
        F.col("sentiment_score").cast("double"),
        F.col("collected_at"),
    )
    .filter(F.col("isbn13").rlike(r"^\d{13}$"))
    .withColumn("mention_date",  F.to_date("collected_at"))
    .withColumn("is_spike_seed", F.col("mention_count") >= SPIKE_THRESHOLD)
    .dropDuplicates(["mention_id"])
)

df.write.mode("overwrite").partitionBy("mention_date").parquet(MART_PATH)

job.commit()
