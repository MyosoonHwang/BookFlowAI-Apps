# Glue ETL Scripts

Glue Job 6종 (Flex execution · 비용 절감). 각 폴더에 `main.py` 또는 `script.py`.

| Job | 역할 |
|-----|------|
| `raw-pos-mart` | POS raw → Mart |
| `raw-sns-mart` | SNS raw → Mart |
| `raw-aladin-mart` | 알라딘 raw → Mart |
| `raw-event-mart` | 이벤트 raw → Mart |
| `sales-daily-agg` | 일별 판매 집계 |
| `features-build` | Vertex AI Feature 빌드 |

## 배포

GHA 가 `main` 머지 감지 → S3 (`s3://bookflow-glue-scripts-{account}/`) sync → Glue Job 의 `ScriptLocation` 이 자동 참조.

## Glue Catalog 정의

Glue Database + Job IaC 는 `BookFlowAI-Platform/infra/aws/99-glue/glue-catalog.yaml` 참조.
