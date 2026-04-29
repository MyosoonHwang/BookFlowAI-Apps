# ECS Sims (Fargate)

ECS Cluster `bookflow-ecs` · 3 Service.

| Service | 역할 |
|---------|------|
| `online-sim` | POS 실시간 스트림 시뮬레이터 → Kinesis |
| `offline-sim` | POS 배치 시뮬레이터 → S3 raw |
| `inventory-api` | 재고조회 API · Egress VPC Public · External ALB 뒤 (Fargate) |

## 빌드 → ECR

각 폴더에 `Dockerfile` + 앱 소스. CodePipeline 이 main 머지 감지 → CodeBuild → ECR push → ECS service update.
