# Publisher EC2 (CodeDeploy Blue/Green)

EC2 ASG (Ubuntu 24 · t3.micro × 2) · Egress VPC Public · External ALB 뒤.

## 빌드 → CodeDeploy

GHA + OIDC → S3 artifact 업로드 → CodeDeploy Blue/Green deployment.

## 파일 (예정)

```
publisher/
├── appspec.yml          # CodeDeploy hooks
├── scripts/             # before-install, after-install, validate-service
└── src/                 # 앱 소스
```
