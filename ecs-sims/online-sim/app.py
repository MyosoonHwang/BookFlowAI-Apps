"""
online-sim: 온라인 POS 판매 시뮬레이터 → Kinesis bookflow-pos-events
채널: ONLINE_APP(70%) / ONLINE_WEB(30%), location_id 1-2

ISBN 풀: BookFlowAI-Platform/seed-data/books.csv 알라딘 1000권 → seed=42 random.sample(1000).
build.sh 가 _shared 모듈을 sim 이미지에 함께 COPY.
"""
import json
import logging
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import boto3

sys.path.insert(0, "/app")
try:
    from _shared.seed_isbns import SEED_ISBNS
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from _shared.seed_isbns import SEED_ISBNS

log = logging.getLogger("online-sim")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

STREAM_NAME = os.environ.get("KINESIS_STREAM_NAME", "bookflow-pos-events")
REGION      = os.environ.get("AWS_REGION", "ap-northeast-1")
INTERVAL    = (10, 30)   # 초

_rng = random.Random(42)
ISBNS = _rng.sample(SEED_ISBNS, min(1000, len(SEED_ISBNS)))

kinesis = boto3.client("kinesis", region_name=REGION)


def make_record() -> dict:
    isbn13    = random.choice(ISBNS)
    qty       = random.randint(1, 3)
    unit_price = random.randint(8000, 35000)
    return {
        "tx_id":      str(uuid.uuid4()),
        "isbn13":     isbn13,
        "qty":        qty,
        "unit_price": unit_price,
        "total_price": qty * unit_price,
        "channel":    random.choices(["ONLINE_APP", "ONLINE_WEB"], weights=[70, 30])[0],
        "location_id": random.randint(1, 2),
        "ts":         datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    log.info("online-sim 시작 stream=%s pool=%d", STREAM_NAME, len(ISBNS))
    while True:
        rec = make_record()
        kinesis.put_record(
            StreamName=STREAM_NAME,
            Data=json.dumps(rec, ensure_ascii=False).encode(),
            PartitionKey=rec["isbn13"],
        )
        log.info("%s isbn=%s qty=%s price=%s",
                 rec["channel"], rec["isbn13"], rec["qty"], rec["total_price"])
        time.sleep(random.uniform(*INTERVAL))


if __name__ == "__main__":
    main()
