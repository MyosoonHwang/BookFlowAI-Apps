# BookFlowAI-Apps

BookFlow AI 플랫폼의 **앱 코드** repo. 컨테이너 이미지 + Glue 스크립트 빌드 대상.

## 구조

| 디렉토리 | 내용 | 담당 | 브랜치 |
|---------|------|------|--------|
| `eks-pods/` | 7 Pod + 1 CronJob (V6.2) | 영헌 | `eks-pods` |
| `ecs-sims/` | online-sim · offline-sim · inventory-api | 영헌 + 민지 | `ecs-sims` |
| `publisher/` | EC2 ASG (CodeDeploy Blue/Green) | 영헌 | `publisher` |
| `glue-jobs/` | Glue ETL 스크립트 6종 | 민지 | `glue-jobs` |

## 자매 repo

- [`BookFlowAI-Platform`](https://github.com/MyosoonHwang/BookFlowAI-Platform) — infra (CFN/Bicep/Terraform) + Lambda src + RDS SQL + CI/CD pipeline 정의 + Ansible playbook

## 브랜치 전략

`main` 보호. Task 별 long-lived 브랜치 (`eks-pods`, `ecs-sims`, `publisher`, `glue-jobs`) 에서 작업 후 main 으로 PR.

CodePipeline / GHA 가 main 머지 시 ECR 빌드/푸시 또는 S3 sync 자동 트리거.
