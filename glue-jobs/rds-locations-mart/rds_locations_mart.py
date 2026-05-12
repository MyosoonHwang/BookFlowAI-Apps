"""
rds_locations_mart · Glue ETL Job
RDS locations (active) → S3 mart/locations_static/ (full overwrite, static master)
Step Functions ETL2
"""
import json
import sys

import boto3
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "MART_BUCKET", "RDS_ENDPOINT", "RDS_PORT", "RDS_DBNAME", "RDS_SECRET_ARN"],
)

sc    = SparkContext()
glue  = GlueContext(sc)
spark = glue.spark_session
job   = Job(glue)
job.init(args["JOB_NAME"], args)

creds = json.loads(
    boto3.client("secretsmanager").get_secret_value(
        SecretId=args["RDS_SECRET_ARN"]
    )["SecretString"]
)

jdbc_url = f"jdbc:postgresql://{args['RDS_ENDPOINT']}:{args['RDS_PORT']}/{args['RDS_DBNAME']}"

df = (
    spark.read.format("jdbc")
    .option("url", jdbc_url)
    .option("dbtable", "(SELECT * FROM locations WHERE active = TRUE) AS t")
    .option("user", creds["username"])
    .option("password", creds["password"])
    .option("driver", "org.postgresql.Driver")
    .load()
)

df = df.select(
    F.col("location_id").cast("int"),
    F.col("location_type").cast("string"),
    F.col("wh_id").cast("int"),
    F.col("size").cast("string"),
    F.col("is_virtual").cast("boolean"),
)

TARGET = f"s3://{args['MART_BUCKET']}/mart/locations_static/"
df.write.mode("overwrite").parquet(TARGET)

print(f"[rds_locations_mart] target={TARGET} rows={df.count()}")
job.commit()
