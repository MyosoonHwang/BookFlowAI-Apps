import sys
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'github_sha', 's3_bucket'])
print(f"raw-pos-mart job: SHA={args.get('github_sha')}, bucket={args.get('s3_bucket')}")
