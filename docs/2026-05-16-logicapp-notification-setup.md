# Logic App 알림 시스템 설정 — BookFlow 운송 이메일

## 개요

BookFlow 4단계 상태머신(PENDING → APPROVED → IN_TRANSIT → EXECUTED)과 연동된
Azure Logic Apps 이메일 알림 시스템 구성 및 수동 테스트 절차.

- **이벤트 발생 경로**: 대시보드 버튼 클릭 → intervention-svc → notification-svc → Logic App → ACS 이메일
- **수신자 결정**: `notification-svc/src/recipients.py`에서 `location_id` 기반 개별 담당자 조회

---

## Logic App 워크플로 목록

| Logic App 이름 | 트리거 | 발송 대상 | 이벤트 / 스케줄 |
|---|---|---|---|
| `la-bookflowmj-stock-depart` | HTTP (SAS URL) | 도착지 담당자 1명 | `StockDepartPending` |
| `la-bookflowmj-stock-arrival` | HTTP (SAS URL) | 출발지 담당자 1명 | `StockArrivalPending` |
| `la-bookflowmj-notification` | HTTP (SAS URL) | HQ + WH | `SpikeUrgent`, `DailyPlanFinalized`, `NegotiationDelay` |
| `la-bookflowmj-approval-request` | HTTP (SAS URL) | HQ + WH + Branch | `ForecastCompleted`, `OrderPending` |
| `la-bookflowmj-daily-digest` | Recurrence (매일 09:00 KST) | HQ | 스케줄 |
| `la-bookflowmj-secret-rotation` | Recurrence (매일 02:00 KST) | 운영팀 (HQ) | 스케줄 |

**리소스 그룹**: `rg-bookflow` / **위치**: `japanwest`

### 각 Logic App 역할 상세

**`la-bookflowmj-stock-depart`** — 내부 재고 운송 시작 알림
- 대시보드에서 출고 버튼 클릭 시 발동. 도착지 담당자 1명에게 "몇 권의 어떤 책이 어디서 출발했다"는 메일을 보냄.
- 수신자는 그룹 전체가 아닌 `target_location_id`로 개별 담당자만 조회 (예: 부산 서면점 담당자만 수신).
- 이메일 색상: 파란색 (#1a73e8).

**`la-bookflowmj-stock-arrival`** — 내부 재고 운송 완료 알림
- 도착지에서 수령 확인 버튼 클릭 시 발동. 출발지 담당자 1명에게 "책이 도착지에 수령 완료됐다"는 확인 메일을 보냄.
- 수신자는 `source_location_id`로 출발지 담당자만 조회 (예: 영남 거점창고 담당자만 수신).
- 이메일 색상: 초록색 (#188038).

**`la-bookflowmj-notification`** — 긴급 운영 알림 (HQ + WH)
- 긴급발주(`SpikeUrgent`), 수요계획 확정(`DailyPlanFinalized`), 협상 지연(`NegotiationDelay`) 발생 시 본사와 물류센터에 알림.
- 이벤트 종류는 다르지만 수신자가 HQ+WH로 동일하여 단일 Logic App으로 통합.

**`la-bookflowmj-approval-request`** — 발주 승인 요청 알림 (HQ + WH + Branch 전체)
- 수요예측 완료(`ForecastCompleted`)나 개별 발주 승인 요청(`OrderPending`) 시 전 레벨에 알림.
- 내부적으로 `Switch_EventType`으로 이벤트 종류를 분기하여 이메일 내용을 다르게 구성.
- `la-bookflowmj-forecast-completed`(삭제됨)의 역할을 흡수한 통합 워크플로.

**`la-bookflowmj-daily-digest`** — 일일 운영 현황 요약 메일 (HQ, 스케줄)
- 매일 09:00 KST에 자동 실행. notification-svc를 호출하지 않고 Logic App 자체가 직접 대시보드 API에서 데이터를 가져와 HQ에 발송.
- 내부 분기: 반려 건수>0이면 HQ 전용으로 긴급 알림, 없으면 정기 digest 발송.

**`la-bookflowmj-secret-rotation`** — Key Vault 시크릿 만료 점검 (HQ, 스케줄)
- 매일 02:00 KST에 자동 실행. Azure Key Vault에서 만료일이 설정된 시크릿 목록을 조회하여 이름·만료일·남은 일수를 표로 정리해 HQ에 발송.
- 시크릿 값은 메일에 포함되지 않음.

---

## Logic App 간 주요 차이점

### approval-request vs notification

| 항목 | `approval-request` | `notification` |
|---|---|---|
| 이벤트 | `ForecastCompleted`, `OrderPending` | `SpikeUrgent`, `DailyPlanFinalized`, `NegotiationDelay` |
| 수신자 | HQ + WH + Branch (승인요청이므로 전 레벨) | HQ + WH (긴급 운영 알림) |
| 내부 분기 | Switch_EventType으로 이벤트별 메일 내용 분기 | 단일 액션 |

### daily-digest vs secret-rotation

두 워크플로 모두 **Recurrence 트리거** (HTTP SAS URL 없음).

| 항목 | `daily-digest` | `secret-rotation` |
|---|---|---|
| 스케줄 | 매일 09:00 KST (UTC 00:00) | 매일 02:00 KST (UTC 17:00 전일) |
| 수신자 | HQ (경영진 digest) | 운영팀 (HQ) |
| 데이터 소스 | Dashboard API funnel 쿼리 | Key Vault `/secrets` API |
| 내부 분기 | rejected>0 이면 HQ만, 아니면 digest 수신자 전체 | 만료일 있는 시크릿만 필터 후 테이블 이메일 |

---

## 작동 흐름

### StockDepartPending (출고 버튼 클릭)

```
대시보드 출고 버튼
  └─ POST /intervention/orders/{order_id}/dispatch
       └─ intervention-svc
            ├─ pending_orders.status: APPROVED → IN_TRANSIT
            ├─ inventory-svc: source 재고 차감
            ├─ OrderDispatched 이벤트 (Redis pub)
            └─ notify_publish("StockDepartPending", details)
                 └─ notification-svc POST /notification/send
                      ├─ get_recipients() → target_location_id 조회
                      │    └─ NOTIFICATION_CONTACT_LOCATION_CONTACTS_JSON 파싱
                      │         → 해당 지점·물류센터 담당자 이메일 1개
                      └─ POST la-bookflowmj-stock-depart (SAS URL)
                           └─ ACS 이메일 발송 → 도착지 담당자 수신
```

**이메일 제목**: `[운송시작] N권 『도서명』 — 출발지 출발`

### StockArrivalPending (수령 확인 버튼 클릭)

```
대시보드 수령 버튼
  └─ POST /intervention/orders/{order_id}/receive
       └─ intervention-svc
            ├─ pending_orders.status: IN_TRANSIT → EXECUTED
            ├─ inventory-svc: target 재고 증가
            ├─ OrderExecuted 이벤트 (Redis pub)
            └─ notify_publish("StockArrivalPending", details)
                 └─ notification-svc POST /notification/send
                      ├─ get_recipients() → source_location_id 조회
                      │    └─ NOTIFICATION_CONTACT_LOCATION_CONTACTS_JSON 파싱
                      │         → 해당 출발지 담당자 이메일 1개
                      └─ POST la-bookflowmj-stock-arrival (SAS URL)
                           └─ ACS 이메일 발송 → 출발지 담당자 수신
```

**이메일 제목**: `[운송완료] N권 『도서명』 — 도착지 수령 완료`

---

## 수신자 결정 로직 (recipients.py)

```python
# StockDepartPending: 도착지 담당자 1명만
def _stock_depart_recipients(payload):
    return _location_recipient(payload.get("target_location_id"), payload.get("target_location"))

# StockArrivalPending: 출발지 담당자 1명만
def _stock_arrival_recipients(payload):
    return _location_recipient(payload.get("source_location_id"), payload.get("source_location"))

# location_id → email 조회 (NOTIFICATION_CONTACT_LOCATION_CONTACTS_JSON)
def _location_recipient(location_id, display_name):
    contacts = _location_contacts()          # JSON 파싱
    email = contacts.get(int(location_id))   # location_id로 직접 조회
    return [{"address": email, "displayName": display_name}]
```

### 담당자 이메일 매핑 (K8s ConfigMap)

| location_id | 지점명 | 이메일 |
|---|---|---|
| 1 | 강남점 | ms8405493@gmail.com |
| 2 | 광화문점 | ms8405493@gmail.com |
| 3 | 잠실점 | ms8405493@gmail.com |
| 4 | 홍대점 | ms8405493@gmail.com |
| 5 | 신촌점 | ms8405493@gmail.com |
| 6 | 용산점 | ms8405493@gmail.com |
| 7 | 부산 서면점 | ms8405493@gmail.com |
| 8 | 대구 동성점 | ms8405493@gmail.com |
| 9 | 울산 삼산점 | ms8405493@gmail.com |
| 10 | 대구 교대점 | ms8405493@gmail.com |
| 11 | 부산 센텀점 | ms8405493@gmail.com |
| 12 | 포항 양덕점 | ms8405493@gmail.com |
| 13 | 수도권 온라인 | ms8405493@gmail.com |
| 14 | 영남 온라인 | ms8405493@gmail.com |
| 15 | 수도권 거점창고 (WH) | rladudgjs0427@gmail.com |
| 16 | 영남 거점창고 (WH) | rladudgjs0427@gmail.com |

### 그룹 이메일 매핑

| 그룹 | 이메일 | env 키 |
|---|---|---|
| 본사/경영진 (HQ) | woohek00@gmail.com | `NOTIFICATION_CONTACT_HQ_EMAILS` |
| 물류센터 (WH) | rladudgjs0427@gmail.com | `NOTIFICATION_CONTACT_WH_EMAILS` |
| 지점 전체 (Branch) | ms8405493@gmail.com | `NOTIFICATION_CONTACT_BRANCH_EMAILS` |

---

## 2026-05-17 수정 사항

### 변경 파일 (BookFlowAI-Apps)

#### `eks-pods/notification-svc/src/recipients.py`
수신자 라우팅 로직 수정.
- `StockDepartPending` / `StockArrivalPending`: 기존에는 HQ+WH+Branch 전 그룹에 이메일을 보냈음. 개별 지점·물류센터 담당자 1명만 받도록 변경 (`target/source_location_id` 기반).
- `SpikeUrgent` (긴급발주): 기존 HQ+WH → **HQ 단독**으로 변경.
- `DeliveryCompleted`: Logic App 삭제에 따라 매핑 제거.

#### `eks-pods/notification-svc/src/settings.py`
환경변수 설정 필드 변경.
- `contact_location_contacts_json` 추가 → 16개 지점·물류센터 이메일 JSON을 `NOTIFICATION_CONTACT_LOCATION_CONTACTS_JSON` 환경변수에서 읽음.
- `logic_apps_forecast_completed_url`, `logic_apps_delivery_completed_url` 필드 **제거** (해당 Logic App 삭제에 따라).
- 이메일 주석 수정 (woohek00 / rladudgjs0427 / ms8405493 기준으로 업데이트).

#### `eks-pods/notification-svc/src/routes/notification.py`
이벤트 → Logic App URL 라우팅 테이블 수정.
- `DeliveryCompleted` → `delivery_completed` 항목 제거.
- `url_map`에서 `forecast_completed`, `delivery_completed` 키 제거.
- 주석 업데이트 (현재 활성 워크플로 기준).

#### `eks-pods/notification-svc/k8s/configmap.yaml`
K8s 환경변수 설정 파일.
- `NOTIFICATION_CONTACT_LOCATION_CONTACTS_JSON` 추가: location_id 1~14 → `ms8405493@gmail.com` (지점), 15~16 → `rladudgjs0427@gmail.com` (거점창고).
- 이메일 주소 전면 수정: HQ `woohek00@gmail.com`, WH `rladudgjs0427@gmail.com`, Branch `ms8405493@gmail.com`.

#### `eks-pods/intervention-svc/src/routes/orders.py`
재고 운송 상세 정보 반환 수정.
- `_fetch_stock_details()` 함수에서 `source_location_id`, `target_location_id` 컬럼 추가 반환.
- notification-svc가 이 값을 받아야 per-location 개별 담당자 조회가 가능하기 때문.

### Logic App 변경 (Azure, BookFlowAI-Platform)

- `la-bookflowmj-stock-arrival`, `la-bookflowmj-stock-depart` 삭제 후 재생성
  - 이메일 제목: `isbn13` 직접 표시 → `『도서명』` 형식으로 변경
  - trigger schema에 `source_location_id`, `target_location_id` 필드 추가
  - UTF-8 charset 명시 (`Content-Type: application/json; charset=utf-8`)
- `la-bookflowmj-forecast-completed` **삭제** — `ForecastCompleted` 이벤트는 이미 `approval-request`로 라우팅되어 있어 사용되지 않던 레거시 워크플로
- `la-bookflowmj-delivery-completed` **삭제** — `DeliveryCompleted` 이벤트가 현재 사용되지 않음
- `la-bookflowmj-secret-rotation` `digestRecipients` 수정: 기존 3개 그룹 → **HQ (`woohek00@gmail.com`) 단독**으로 변경

### 코드 변경 적용 방법

> **중요**: K8s `kubectl set env`로는 SAS URL 같은 환경변수 값만 즉시 반영 가능.
> Python 코드(`.py`) 또는 ConfigMap(`.yaml`) 변경은 **CodeBuild → ECR → K8s 롤링 업데이트** 과정을 거쳐야 적용됨.

| 변경 종류 | 반영 방법 |
|---|---|
| SAS URL 교체 | `kubectl set env deployment/notification-svc -n bookflow NOTIFICATION_LOGIC_APPS_XXX_URL="..."` → 즉시 반영 |
| 이메일 주소 변경 (ConfigMap) | git push → CodeBuild 빌드 → 파드 재시작 후 반영 |
| Python 코드 변경 (`.py`) | git push → CodeBuild 빌드 → 파드 재시작 후 반영 |

SAS URL은 `kubectl set env`로 deployment에 주입 (Secret 미사용):
```
NOTIFICATION_LOGIC_APPS_STOCK_DEPART_URL
NOTIFICATION_LOGIC_APPS_STOCK_ARRIVAL_URL
```

---

## K8s 설정

### ConfigMap 주요 키 (notification-svc-env)

```yaml
NOTIFICATION_CONTACT_HQ_EMAILS: "woohek00@gmail.com"
NOTIFICATION_CONTACT_WH_EMAILS: "rladudgjs0427@gmail.com"
NOTIFICATION_CONTACT_BRANCH_EMAILS: "ms8405493@gmail.com"
NOTIFICATION_CONTACT_LOCATION_CONTACTS_JSON: '{"1":"ms8405493@gmail.com",...,"14":"ms8405493@gmail.com","15":"rladudgjs0427@gmail.com","16":"rladudgjs0427@gmail.com"}'
AUTH_MODE: "jwt"
```

### SAS URL 갱신 방법 (Logic App 재배포 후)

```bash
# SAS URL 재발급
az rest --method POST \
  --uri "https://management.azure.com/subscriptions/e98a94bb-7532-4e49-8a36-bc42e30d5a81/resourceGroups/rg-bookflow/providers/Microsoft.Logic/workflows/la-bookflowmj-stock-depart/triggers/manual/listCallbackUrl?api-version=2016-06-01" \
  --query value -o tsv

# K8s에 주입
kubectl set env deployment/notification-svc -n bookflow \
  NOTIFICATION_LOGIC_APPS_STOCK_DEPART_URL="<SAS_URL>" \
  NOTIFICATION_LOGIC_APPS_STOCK_ARRIVAL_URL="<SAS_URL>"
```

---

## 수동 테스트 방법 (대시보드 없이)

### 사전 준비

```bash
# port-forward (두 창 또는 백그라운드)
kubectl port-forward -n bookflow svc/intervention-svc 18090:80 &
kubectl port-forward -n bookflow svc/notification-svc 18092:80 &
```

### 1. 테스트용 주문 DB 직접 삽입

```bash
kubectl exec -n bookflow <intervention-svc-pod> -- python3 -c "
import os, psycopg
from datetime import date, timedelta
conn = psycopg.connect(
  host=os.environ['INTERVENTION_RDS_HOST'], port=5432,
  dbname='bookflow', user=os.environ['INTERVENTION_RDS_USER'],
  password=os.environ['INTERVENTION_RDS_PASSWORD']
)
cur = conn.cursor()
cur.execute('''
  INSERT INTO pending_orders
    (order_id, order_type, isbn13, source_location_id, target_location_id,
     qty, status, expected_arrival_at)
  VALUES (gen_random_uuid(), 'STOCK_TRANSFER', '9788925588735', 16, 7, 5, 'APPROVED', %s)
  RETURNING order_id
''', (date.today() + timedelta(days=1),))
print('order_id:', cur.fetchone()[0])
conn.commit()
conn.close()
"
# → order_id 복사
```

> isbn13 `9788925588735` = 프로젝트 헤일메리 (영남 거점창고 재고 보유)
> source_location_id=16 (영남 거점창고, WH), target_location_id=7 (부산 서면점, STORE)

### 2. Dispatch — 출발지 출고 버튼 (APPROVED → IN_TRANSIT)

```bash
ORDER_ID="<위에서 복사한 order_id>"
curl -s -X POST "http://localhost:18090/intervention/orders/${ORDER_ID}/dispatch" \
  -H "Authorization: Bearer mock-token-hq-admin" \
  -H "Content-Type: application/json" \
  -d "{}"
# 예상: {"order_id":"...","status":"IN_TRANSIT"}
# 이메일: 부산서면점 담당자(ms8405493@gmail.com) — "[운송시작] 5권 『프로젝트 헤일메리』 — 영남 거점창고 출발"
```

### 3. Receive — 도착지 수령 버튼 (IN_TRANSIT → EXECUTED)

```bash
curl -s -X POST "http://localhost:18090/intervention/orders/${ORDER_ID}/receive" \
  -H "Authorization: Bearer mock-token-hq-admin" \
  -H "Content-Type: application/json" \
  -d "{}"
# 예상: {"order_id":"...","status":"EXECUTED"}
# 이메일: 영남거점창고 담당자(rladudgjs0427@gmail.com) — "[운송완료] 5권 『프로젝트 헤일메리』 — 부산 서면점 수령 완료"
```

### 4. Logic App 실행 확인

```bash
# stock-depart 최근 실행 상태
az rest --method GET \
  --uri "https://management.azure.com/subscriptions/e98a94bb-7532-4e49-8a36-bc42e30d5a81/resourceGroups/rg-bookflow/providers/Microsoft.Logic/workflows/la-bookflowmj-stock-depart/runs?api-version=2016-06-01&\$top=1" \
  --query "value[0].{status:properties.status,time:properties.startTime}" -o json

# stock-arrival 최근 실행 상태
az rest --method GET \
  --uri "https://management.azure.com/subscriptions/e98a94bb-7532-4e49-8a36-bc42e30d5a81/resourceGroups/rg-bookflow/providers/Microsoft.Logic/workflows/la-bookflowmj-stock-arrival/runs?api-version=2016-06-01&\$top=1" \
  --query "value[0].{status:properties.status,time:properties.startTime}" -o json
```

### 5. notification-svc 직접 호출 (이메일 단독 테스트)

상태머신 없이 이메일만 테스트할 때:

```bash
curl -s -X POST "http://localhost:18092/notification/send" \
  -H "Authorization: Bearer mock-token-hq-admin" \
  -H "Content-Type: application/json" \
  --data '{
    "event_type": "StockDepartPending",
    "severity": "INFO",
    "payload_summary": {
      "order_id": "test-manual-001",
      "isbn13": "9788925588735",
      "title": "프로젝트 헤일메리",
      "source_location": "영남 거점창고",
      "source_location_type": "WH",
      "source_location_id": 16,
      "target_location": "부산 서면점",
      "target_location_type": "STORE_OFFLINE",
      "target_location_id": 7,
      "qty": 5,
      "dispatched_at": "2026-05-17T19:00:00",
      "expected_arrival": "2026-05-18"
    }
  }'
# source_location_id, target_location_id 필드 필수 (per-location 라우팅 기준)
```

---

## 트러블슈팅

### "Need atleast one valid To, CC or BCC recipient"

Logic App 내 `recipients` 배열이 빈 배열(`[]`)로 전달된 경우.

원인: `NOTIFICATION_CONTACT_LOCATION_CONTACTS_JSON` 환경변수 미설정 또는 `target/source_location_id` 필드 누락.

확인:
```bash
kubectl exec -n bookflow <notification-svc-pod> -- python3 -c "
import sys; sys.path.insert(0, '/app')
from src.settings import settings
from src.recipients import _location_contacts
print(len(_location_contacts()), 'locations loaded')
"
```

### AUTH_MODE 설정 확인

```bash
kubectl exec -n bookflow <pod> -- env | grep AUTH_MODE
# 테스트 시: AUTH_MODE=mock 이어야 함
# 운영 시: AUTH_MODE=jwt (configmap의 AUTH_MODE: "jwt" 적용)
```

AUTH_MODE가 jwt로 덮어씌워진 경우 임시 override:
```bash
kubectl set env deployment/notification-svc -n bookflow AUTH_MODE=mock
```
