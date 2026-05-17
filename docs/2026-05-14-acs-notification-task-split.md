# ACS 알림 연결 작업 분담 가이드

**작성일**: 2026-05-14
**관련 브랜치**: `feat/acs-notification-rebase`

---

## 전체 흐름 한 줄 요약

> AWS EKS에 있는 알림 서버(notification-svc)가 이벤트 발생 시 Azure Logic Apps를 호출하고, Logic Apps가 ACS(Azure Communication Services)를 통해 실제 이메일을 발송하는 구조

```
[EKS 알림 서버] → HTTP 호출 → [Azure Logic Apps] → [ACS Email] → 수신자 이메일
```

---

## 어제 완료된 작업 (참고용)

- 알림 서버가 이메일 수신자 목록을 Logic Apps에 함께 전달하도록 수정
- 이벤트 종류에 따라 수신자를 자동으로 결정하는 로직 추가 (본사 / 물류센터 / 지점)
- 입고 거부(InboundRejected) 알림은 5분치를 모아서 한 번에 발송하는 기능 추가
- 오늘의 모든 결재가 끝났을 때 보내는 알림(DailyPlanFinalized)이 하루에 한 번만 발송되도록 중복 방지

**남은 작업을 A (백엔드 담당) · B (Azure 담당) 2명으로 분담**

---

## 담당자 A — 백엔드 / EKS 담당

### 지금 뭐가 문제인가?

알림 서버가 Logic Apps에 요청을 보낼 때 아래 주소로 호출:
```
POST /workflow/SpikeUrgent
```

그런데 테스트용 mock 서버(azure-logic-apps-mock)에는 저 주소가 없어서 404 에러 발생.
실제로 이메일이 가는지 테스트를 전혀 할 수 없는 상태.

---

### A-1. Mock 서버에 주소 추가하기

**파일 위치**: `mocks/azure-logic-apps-mock/src/main.py`

**할 일**: 2가지

**① WORKFLOW_IDS 딕셔너리에 누락된 이벤트 4개 추가**

```python
# 기존 코드에 아래 4줄 추가 (WORKFLOW_IDS 딕셔너리 안에)
"InboundRejected":     "wf-inbound-rejected-0013",    # 매장 입고 거부
"DailyPlanFinalized":  "wf-daily-plan-finalized-0014", # 오늘 결재 완료
"ApprovalDelayed":     "wf-approval-delayed-0015",     # 결재 지연
"DailyDigest":         "wf-daily-digest-0016",         # 일일 요약
```

**② 새 URL 엔드포인트 함수 추가** (기존 함수 아래에 붙여넣기)

```python
@app.post("/workflow/{event_type}")
async def invoke_by_event_type(event_type: str, request: Request):
    """알림 서버가 /workflow/{이벤트명} 형태로 호출할 때 받아주는 엔드포인트."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    workflow_id = WORKFLOW_IDS.get(event_type, f"wf-unknown-{event_type}")
    run_id = uuid.uuid4().hex
    record = {
        "run_id": run_id,
        "event_type": event_type,
        "workflow_id": workflow_id,
        "received_at": time.time(),
        "body": body,
    }
    _RUNS.setdefault(workflow_id, deque(maxlen=100)).append(record)
    return Response(status_code=202,
        headers={"x-ms-workflow-run-id": run_id})
```

---

### A-2. 불필요한 이메일 발송 막기 (스팸 방지)

**파일 위치**: `eks-pods/notification-svc/src/routes/notification.py`

**문제**: 현재는 주문 승인(OrderApproved), 주문 거절(OrderRejected) 같은 사소한 이벤트도 전부 Logic Apps로 보내서 이메일이 대량 발송됨.

**이메일을 실제로 보내야 하는 이벤트 8종** (이것만 Logic Apps 호출):

| 이벤트 | 언제 발생하나 |
| --- | --- |
| AutoExecutedUrgent | AI가 자동으로 발주를 승인했을 때 (본사 확인 필요) |
| DailyPlanFinalized | 오늘 모든 결재가 완료됐을 때 |
| SpikeUrgent | SNS에서 특정 도서가 갑자기 화제가 됐을 때 |
| ApprovalDelayed | 권역 간 재고 이동 결재가 24시간 넘게 안 됐을 때 |
| InboundRejected | 매장에서 입고를 거부했을 때 (5분 모아서 발송) |
| NewBookRequest | 출판사가 신간 판매 신청을 했을 때 |
| LambdaAlarm | AWS Lambda 함수가 오류 났을 때 |
| DeploymentRollback | 배포가 실패해서 자동 롤백됐을 때 |

**할 일**: `notification.py` 파일 상단에 아래 코드 추가

```python
# 이메일 발송이 필요한 이벤트 목록
_LOGIC_APPS_EVENTS = {
    "AutoExecutedUrgent", "DailyPlanFinalized", "SpikeUrgent",
    "ApprovalDelayed", "InboundRejected", "NewBookRequest",
    "LambdaAlarm", "DeploymentRollback",
}

def _needs_logic_apps(event_type: str) -> bool:
    """이 이벤트가 Logic Apps(이메일) 발송 대상인지 확인."""
    return event_type in _LOGIC_APPS_EVENTS
```

그리고 `send()` 함수 안의 Logic Apps 호출 부분을 아래처럼 수정:

```python
# 수정 전 (무조건 Logic Apps 호출)
recipients = get_recipients(req.event_type, req.payload_summary)
ok, err = await _post_logic_apps(...)
new_status = "SENT" if ok else "FAILED"

# 수정 후 (이메일 필요한 이벤트만 Logic Apps 호출)
if _needs_logic_apps(req.event_type):
    recipients = get_recipients(req.event_type, req.payload_summary)
    ok, err = await _post_logic_apps(...)
    new_status = "SENT" if ok else "FAILED"
else:
    ok, err, new_status = True, None, "SKIPPED"  # 나머지는 웹소켓/Redis만 사용
```

---

### A-3. PR 올리기

> A-1, A-2 작업 완료 후 진행

```bash
# 1. 브랜치 이동
git checkout feat/acs-notification-rebase

# 2. 수정한 파일 2개 커밋
git add mocks/azure-logic-apps-mock/src/main.py
git add eks-pods/notification-svc/src/routes/notification.py
git commit -m "fix(mock+notification): /workflow/{event_type} endpoint 추가 + Logic Apps spam 방지"

# 3. GitHub에서 PR 생성
# base(머지 대상): main
# compare(내 브랜치): feat/acs-notification-rebase
# PR 제목: feat(notification): ACS Email 연결 + Mock URL fix + spam 방지
```

> **주의**: `feat/acs-notification` 브랜치는 구버전이라 사용하면 안 됨. 반드시 `feat/acs-notification-rebase` 로 PR 올릴 것.

---

## 담당자 B — Azure Logic Apps 담당

### 지금 뭐가 빠져 있나?

알림 서버(EKS)가 Logic Apps를 호출하는 코드는 완성됐는데, **Azure 쪽 Logic Apps workflow가 아직 없음**. Logic Apps가 없으면 이메일 발송이 실제로 일어나지 않음.

---

### B-1. 이벤트 수신 → 이메일 발송 workflow 만들기

**Azure Portal → Logic Apps → 새 workflow 생성 (Standard)**

**전체 흐름**:

```
① 알림 서버가 HTTP POST로 데이터 전송
      ↓
② Logic Apps가 받아서 이벤트 종류 확인
      ↓
③ 이벤트 종류에 따라 이메일 제목/본문 결정
      ↓
④ ACS Email로 수신자에게 발송
```

**Trigger 설정**: HTTP Request (POST 방식)

Logic Apps가 받는 데이터 형식:
```json
{
  "event_type": "SpikeUrgent",
  "payload": { "title": "채식주의자", "z_score": 4.2 },
  "recipients": [
    { "address": "ms8405493@gmail.com", "displayName": "본사/경영진" }
  ]
}
```

**Switch 분기 설정** (이벤트 종류별 이메일 제목):

| event_type | 이메일 제목 |
| --- | --- |
| AutoExecutedUrgent | 🤖 [특이] AI 자동 승인 {n}건 · 본사 검토 필요 |
| DailyPlanFinalized | ✅ [최종확정] {today} 의사결정 모두 완료 |
| SpikeUrgent | 🔥 [긴급] SNS 급등: "{title}" (z {z_score}) |
| ApprovalDelayed | ⏳ [협의지연] 권역 이동 {n}건 · 24h+ 양쪽 승인 대기 |
| InboundRejected | 📦 [입고거부] {n}건 · 최근 5분 |
| NewBookRequest | 📚 [신간] 출판사 신간 신청 {n}건 · 편입 결정 필요 |
| LambdaAlarm | 🚨 [시스템] Lambda fail: {function_name} |
| DeploymentRollback | 🔄 [배포] CodePipeline rollback: {pipeline_name} |

**ACS Email 액션 설정**:
- **받는 사람(To)**: payload 안의 `recipients` 배열에서 `address` 값 사용
- **보내는 사람(From)**: ACS에서 설정한 발신 도메인 주소
- **제목(Subject)**: 위 테이블 참고
- **본문(Body)**: payload 내용 기반으로 작성 (HTML 권장)

**수신자 그룹 참고**:

| 이벤트 | 누가 받나 |
| --- | --- |
| AutoExecutedUrgent | 본사 (ms8405493@gmail.com) |
| DailyPlanFinalized | 본사 |
| SpikeUrgent | 본사 + 권역 매니저 (rladudgjs0427@gmail.com) |
| ApprovalDelayed | 본사 + 양 권역 매니저 |
| InboundRejected | 본사 + 해당 권역 매니저 |
| NewBookRequest | 본사 |
| LambdaAlarm / DeploymentRollback | DevOps 담당자 |

> 수신자는 알림 서버가 이미 결정해서 payload에 담아서 보내주므로, Logic Apps는 recipients 그대로 사용하면 됨.

---

### B-2. 일일 요약 메일 workflow 만들기 (매일 오전 9시)

매일 아침 9시에 "어제 어떻게 됐나"를 정리해서 본사에 보내는 이메일.

**Trigger 설정**: Recurrence — 매일 00:00 UTC (= 한국시간 09:00)

**순서**:

```
① 매일 오전 9시 자동 시작
② 아래 5개 주소에서 데이터 가져오기 (HTTP GET)
   - /dashboard/cascade/funnel?days=1       (의사결정 단계별 현황)
   - /dashboard/pending/summary?days=1      (미결재 건수)
   - /dashboard/sales/30days                (30일 매출)
   - /dashboard/sales/bestsellers?days=1&limit=5  (어제 베스트셀러)
   - /dashboard/forecast/insufficient?limit=5     (재고 부족 도서)
③ 데이터 조합해서 HTML 이메일 본문 작성
④ ACS Email로 발송
   받는 사람: 본사 운영팀 + 경영진 (ms8405493@gmail.com)
   제목: 📊 [일일요약] BookFlow {어제날짜}
```

**이메일 본문 구성**:

```
🎯 핵심 KPI
  - 전사 매출 / 거래 건수 / 객단가(ASP) / 결품률

📦 어제 의사결정 결과
  - 총 {n}건 중 승인 {n} / 거절 {n} / AI 자동실행 {n}

🔥 재고 부족 도서 top 5
🏆 어제 베스트셀러 top 5
📚 신간 편입 {n}건 · 반품 처리 {n}건

⚠️ 오늘 조치 필요한 것
  - 아직 미결재 PENDING: {n}건
  - SNS 급등 중인데 우리 매장 재고 부족: {n}건
```

---

### B-3. 결재 완료 감지 workflow 만들기 (매시간 체크)

오늘의 모든 결재가 완료된 순간 "운송 시작 가능" 알림을 보내는 workflow.

**Trigger 설정**: Recurrence — 매 1시간마다

**순서**:

```
① 1시간마다 자동 실행
② /dashboard/pending/summary?days=1 호출해서 미결재 건수 확인
③ 미결재가 0건인가?
   → 아니면: 그냥 종료
   → 맞으면: 오늘 이미 이 메일 보냈는가? (변수 확인)
              → 이미 보냈으면: 그냥 종료 (중복 방지)
              → 아직 안 보냈으면: ACS Email 발송 + 오늘 발송 완료 표시

별도 workflow: 매일 자정에 "오늘 발송 완료 표시" 초기화
```

> 알림 서버(notification-svc) 쪽에도 이미 Redis로 중복 방지가 되어 있음. Logic Apps에서도 변수로 한 번 더 막아두는 것.

---

### B-4. 진짜 Logic Apps URL로 교체하기 (B-1 완료 후)

B-1 workflow 배포가 끝나면 Azure Portal에서 실제 URL을 복사해서 A 담당자에게 전달.

A 담당자가 아래 파일을 수정:

**파일 위치**: `eks-pods/notification-svc/k8s/configmap.yaml`

```yaml
# 수정 전 (테스트용 mock 주소)
NOTIFICATION_LOGIC_APPS_URL: "http://azure-logic-apps-mock.stubs.svc.cluster.local"

# 수정 후 (Azure Portal에서 복사한 실제 주소)
NOTIFICATION_LOGIC_APPS_URL: "https://prod-XX.koreacentral.logic.azure.com/workflows/{wf_id}/triggers/manual/paths/invoke"
```

수정 후 서버 재시작:

```bash
kubectl apply -f eks-pods/notification-svc/k8s/configmap.yaml
kubectl rollout restart deployment/notification-svc -n bookflow
```

---

## 작업 순서 정리

```
A 담당자                                B 담당자
──────────────────────────             ──────────────────────────
A-1  Mock 서버에 주소 추가
A-2  스팸 방지 필터 추가
A-3  PR 생성 → merge 요청              B-1  이벤트 수신 workflow 생성
                                       B-2  일일 요약 workflow 생성
                                       B-3  결재 완료 감지 workflow 생성
                       ↓
           B-1 배포 완료 후 실제 URL을 A에게 전달
                       ↓
                                       B-4  실제 URL로 configmap 교체
                                            → kubectl apply + 재시작
```

---

## 두 담당자가 함께 결정해야 할 것

1. **수신자 이메일 주소 확정** — 본사 운영팀 / 경영진 / 권역 매니저 / DevOps 각각 누구 이메일로 보낼지
2. **SMS 발송 여부** — SpikeUrgent, LambdaAlarm 2종은 문자도 보낼지 (ACS SMS vs Twilio 중 선택)
3. **일일 요약 발송 시각** — 오전 9시 고정으로 할지, 변경할지
4. **서버 주소** — 이메일 본문 링크를 운영 서버(`bookflow.duckdns.org`) 기준으로 할지, 개발 환경 분기할지
5. **이메일 디자인** — BookFlow 로고나 색상 적용할지, 아니면 텍스트만으로 할지
