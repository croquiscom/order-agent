# QA시트 → 시나리오 자동화 변환 프로세스

> 주문팀 과제별 QA시트를 `.scn` 시나리오로 변환하는 표준 워크플로우입니다.

## 프로세스 개요

```
QA시트 수신 → P0/P1/P2 분류 → P0·P1 시나리오 생성 → dry-run 검증 → 태그 부여 → QA Gate 실행
```

---

## Step 1: QA시트 입수

과제 QA시트(Google Sheets)를 CSV로 다운로드합니다.

```bash
# Claude Code에서 CSV 읽기
# (Google Sheets → 파일 → 다운로드 → CSV)
```

## Step 2: P0/P1/P2 분류

`docs/qa_priority_classification.md`의 기준에 따라 각 AC 행에 등급을 부여합니다.

| 등급 | 기준 | 자동화 정책 |
|------|------|------------|
| **P0** | 즉시 매출 손실, 우회 불가 | `.scn` 필수 |
| **P1** | CS 우회 가능, 수시간 복구 | `.scn` 권장 |
| **P2** | UX 저하, 기능 정상 | 수동 유지 |

**판단 기준:** "이 기능이 장애나면 매출에 분 단위로 영향이 있는가?"

## Step 3: 시나리오 생성

### 방법 A: `/new-scenario` 스킬 사용 (권장)

```
/new-scenario 장바구니에서 옵션변경 버튼 클릭 → 모달 노출 → 다른 옵션 선택 → 변경하기
```

스킬이 시나리오 가이드를 자동 로딩하고 `.scn` 파일을 생성합니다.

### 방법 B: 기존 시나리오 복제 후 수정

```bash
# 유사 시나리오 찾기
python3 executor/execute_scenario.py --dry-run --tag area=cart scenarios/zigzag/*.scn

# 복제 후 수정
cp scenarios/zigzag/alpha_cart_order_normal.scn scenarios/zigzag/alpha_cart_new_feature.scn
```

### 방법 C: Claude Code에 QA시트 전달

```
이 QA시트를 시나리오로 변환해줘
(CSV 내용 붙여넣기 또는 파일 경로 전달)
```

## Step 4: 필수 태그 부여

모든 시나리오에 아래 메타 태그를 반드시 포함합니다.

```scn
# @title: 기능명 — 검증 내용 요약
# @tier: smoke | regression
# @area: cart, order, claim, payment, ...
# @task: ORDER-XXXXX
# @priority: P0 | P1 | P2
# @lifecycle: active
```

| 태그 | 필수 | 설명 |
|------|------|------|
| `@title` | O | 시나리오 제목 |
| `@tier` | O | smoke(매 배포) / regression(주기적) |
| `@area` | O | 도메인 영역 (쉼표 구분) |
| `@task` | O | JIRA 티켓 번호 |
| `@priority` | O | P0/P1/P2 |
| `@lifecycle` | O | active/regression/deprecated |
| `@description` | - | 상세 설명 |

## Step 5: dry-run 검증

```bash
# 문법/안전정책 검증
python3 executor/execute_scenario.py --dry-run scenarios/zigzag/alpha_new_feature.scn

# 해당 과제 시나리오만 일괄 검증
python3 executor/execute_scenario.py --dry-run --tag task=ORDER-XXXXX scenarios/zigzag/*.scn
```

## Step 6: 실행

### 개별 실행

```bash
# 특정 시나리오
python3 executor/execute_scenario.py scenarios/zigzag/alpha_new_feature.scn

# 특정 과제만
python3 executor/execute_scenario.py --tag task=ORDER-XXXXX scenarios/zigzag/*.scn
```

### QA Gate (P0 자동 실행 + 슬랙 알림)

```bash
# P0만 실행, 실패 시 슬랙 알림
./scripts/run_qa_gate.sh

# 특정 과제 P1까지 포함
./scripts/run_qa_gate.sh --tag task=ORDER-XXXXX --tag priority=P1

# dry-run 모드
./scripts/run_qa_gate.sh --dry-run
```

### 회귀 테스트

```bash
# P0 smoke 테스트 (매 배포)
python3 scripts/run_regression.py --tier smoke --tag priority=P0

# 전체 회귀 (주 1회)
python3 scripts/run_regression.py --tier regression --slack
```

## Step 7: 과제 완료 후 라이프사이클 전환

```bash
# 회귀 가치 있는 시나리오: @lifecycle: regression 으로 변경
# 회귀 가치 없는 시나리오: @lifecycle: deprecated 으로 변경
# 분기별 정리 시 deprecated 파일 삭제
```

---

## 슬랙 알림 설정

```bash
# .env 파일에 웹훅 URL 추가
echo 'ORDER_QA_SLACK_WEBHOOK=https://hooks.slack.com/services/T.../B.../xxx' >> .env

# 또는 환경변수로 직접 설정
export ORDER_QA_SLACK_WEBHOOK="https://hooks.slack.com/services/T.../B.../xxx"
```

알림 내용:
- 실행 결과 (PASS/FAIL)
- 실패 시나리오 목록 + 에러 메시지
- Tier/Area/Tag 필터 정보
- 실행 시간

---

## 자동화 불가 항목 관리

아래 유형은 수동 QA로 유지합니다.

| 유형 | 사유 | 대안 |
|------|------|------|
| 시각적 검증 (레이아웃, 색상) | DOM으로 판단 불가 | 스크린샷 비교 (향후) |
| UX 판단 (사용성, 직관성) | 자동화 불가 | 수동 유지 |
| 특수 상품 상태 (품절, 프로모션 종료) | 테스트 환경 제어 불가 | 상품 상태 API 확보 시 |
| 외부 연동 (PG 결제, 배송사 API) | 안전 정책 제한 | 모킹 또는 수동 |

---

## 자주 쓰는 명령어 요약

```bash
# 과제별 시나리오 확인
python3 executor/execute_scenario.py --dry-run --tag task=ORDER-XXXXX scenarios/zigzag/*.scn

# P0만 실행
python3 executor/execute_scenario.py --tag priority=P0 scenarios/zigzag/*.scn

# QA Gate (P0 + 실패 알림)
./scripts/run_qa_gate.sh

# 전체 회귀 + 슬랙 알림
python3 scripts/run_regression.py --tier regression --slack

# 특정 영역만 실행
python3 scripts/run_regression.py --tier regression --area cart --tag priority=P1
```

---

*최초 작성: 2026-04-10*
