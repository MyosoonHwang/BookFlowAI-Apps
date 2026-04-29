"""
pos_etl.py  ·  Glue 4.0 Flex
S3 Raw pos-events/ (GZIP JSON) → S3 Mart pos_events/ (Parquet, partitioned by sale_date)
"""
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType, TimestampType

args = getResolvedOptions(sys.argv, ["JOB_NAME", "RAW_BUCKET", "MART_BUCKET"])
sc   = SparkContext()
glue = GlueContext(sc)
spark = glue.spark_session
job  = Job(glue)
job.init(args["JOB_NAME"], args)

RAW_PATH  = f"s3://{args['RAW_BUCKET']}/pos-events/"
MART_PATH = f"s3://{args['MART_BUCKET']}/pos_events/"

schema = StructType([
    StructField("tx_id",      StringType(),  False),
    StructField("isbn13",     StringType(),  False),
    StructField("qty",        IntegerType(), False),
    StructField("unit_price", LongType(),    False),
    StructField("total_price",LongType(),    False),
    StructField("channel",    StringType(),  False),
    StructField("location_id",IntegerType(), False),
    StructField("ts",         StringType(),  False),
])

df = (
    spark.read
    .option("recursiveFileLookup", "true")
    .option("compression", "gzip")
    .schema(schema)
    .json(RAW_PATH)
    .withColumn("ts_parsed", F.to_timestamp("ts"))
    .withColumn("sale_date",  F.to_date("ts_parsed"))
    .withColumn("sale_hour",  F.hour("ts_parsed"))
    .drop("ts")
    .withColumnRenamed("ts_parsed", "ts")
    .dropDuplicates(["tx_id"])
    .filter(F.col("qty") > 0)
    .filter(F.col("isbn13").rlike(r"^\d{13}$"))
)

(
    df.write
    .mode("overwrite")
    .partitionBy("sale_date")
    .parquet(MART_PATH)
)

job.commit()
