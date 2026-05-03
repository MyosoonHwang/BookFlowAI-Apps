"""
offline-sim: 오프라인(매장) POS 판매 시뮬레이터 → Kinesis bookflow-pos-events
채널: OFFLINE, location_id 3-14 (지점)

ISBN 풀: BookFlowAI-Platform/seed-data/books.csv 알라딘 1000권 → seed=42 random.sample(1000).
build.sh 가 _shared 모듈을 sim 이미지에 함께 COPY (sibling _shared/seed_isbns.py).
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

# _shared 모듈 import (Dockerfile 이 ../​_shared/seed_isbns.py 을 /app/_shared/ 로 COPY)
sys.path.insert(0, "/app")
try:
    from _shared.seed_isbns import SEED_ISBNS
except ImportError:
    # 로컬 dev 시 sibling 폴더 에서
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from _shared.seed_isbns import SEED_ISBNS

log = logging.getLogger("offline-sim")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

STREAM_NAME = os.environ.get("KINESIS_STREAM_NAME", "bookflow-pos-events")
REGION      = os.environ.get("AWS_REGION", "ap-northeast-1")
INTERVAL    = (30, 90)   # 초

BRANCH_IDS = list(range(3, 15))   # location_id 3~14: 오프라인 지점

# 결정성: 동일 시드로 매 빌드 동일 1000 ISBN 풀 → 단위테스트가 row ID 참조 가능
_rng = random.Random(42)
ISBNS = _rng.sample(SEED_ISBNS, min(1000, len(SEED_ISBNS)))

kinesis = boto3.client("kinesis", region_name=REGION)


def make_record() -> dict:
    isbn13     = random.choice(ISBNS)
    qty        = random.randint(1, 5)
    unit_price = random.randint(8000, 35000)
    return {
        "tx_id":      str(uuid.uuid4()),
        "isbn13":     isbn13,
        "qty":        qty,
        "unit_price": unit_price,
        "total_price": qty * unit_price,
        "channel":    "OFFLINE",
        "location_id": random.choice(BRANCH_IDS),
        "ts":         datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    log.info("offline-sim 시작 stream=%s pool=%d", STREAM_NAME, len(ISBNS))
    while True:
        rec = make_record()
        kinesis.put_record(
            StreamName=STREAM_NAME,
            Data=json.dumps(rec, ensure_ascii=False).encode(),
            PartitionKey=rec["isbn13"],
        )
        log.info("OFFLINE loc=%s isbn=%s qty=%s price=%s",
                 rec["location_id"], rec["isbn13"], rec["qty"], rec["total_price"])
        time.sleep(random.uniform(*INTERVAL))


if __name__ == "__main__":
    main()
