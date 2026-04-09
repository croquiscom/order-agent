# UI 변경 감지 기반 회귀 테스트 계획

## 배경

지그재그 E2E 시나리오는 CSS 셀렉터, 텍스트 매칭, URL 패턴에 의존한다.
FE 배포로 화면 구조가 바뀌면 시나리오가 깨지며, 현재는 수동 실행 후에야 인지할 수 있다.

**목표**: FE 배포 시 영향 있는 변경이 감지되면 자동으로 회귀 시나리오를 실행하고, 실패 시 빠르게 원인을 파악·복구한다.

---

## 1. 트리거 전략

### 방안 A: FE 레포 CI 연동 (권장)

zigzag-web 레포의 배포 파이프라인에서 order-agent 회귀를 트리거한다.

```
zigzag-web main 머지 → CI 배포 → alpha 반영 완료 → webhook/dispatch → order-agent 회귀 실행
```

- **구현**: GitHub Actions `repository_dispatch` 또는 배포 후 webhook
- **장점**: 정확한 타이밍, 원인 PR 추적 가능, 불필요한 폴링 없음
- **필요 조건**: FE 레포 CI 수정 권한 또는 FE 팀 협조
- **필터링**: 모든 배포가 아닌, UI 영향 있는 변경만 트리거 (아래 "변경 영향 판별" 참조)

### 방안 B: alpha 환경 버전 폴링 (독립 구현)

alpha.zigzag.kr의 빌드 버전을 주기적으로 확인하고, 변경 시 회귀를 실행한다.

```
크론 (30분 간격) → alpha 버전 확인 → 변경 감지 → order-agent 회귀 실행
```

- **구현**: 크론 스크립트가 `<meta>` 태그, JS 번들 해시, 또는 버전 API 엔드포인트를 폴링
- **장점**: FE 레포 접근 없이 독립 구현, 어떤 경로로든 배포된 변경을 감지
- **필요 조건**: alpha 환경에서 버전 정보를 추출할 수 있는 엔드포인트
- **한계**: 원인 PR 자동 추적 불가, 폴링 간격만큼 지연 발생

### 방안 선택 기준

| 조건 | 선택 |
|------|------|
| FE 레포 CI 수정 가능 | 방안 A |
| FE 레포 접근 불가, alpha 버전 확인 가능 | 방안 B |
| 둘 다 가능 | 방안 A 우선, 방안 B를 보조로 병행 |

---

## 2. 변경 영향 판별

모든 FE 배포가 시나리오에 영향을 주지는 않는다. 트리거 시 불필요한 실행을 줄이기 위해 영향 판별 기준을 둔다.

### 영향 있는 변경 (회귀 실행 필요)

- 주문서/결제 페이지 컴포넌트 변경
- 장바구니 UI 변경
- 클레임(취소/반품/교환) 화면 변경
- 로그인/인증 플로우 변경
- 라우팅 경로 변경 (URL 구조)
- 공통 모달/오버레이/바텀시트 변경

### 영향 없는 변경 (스킵 가능)

- 상품 상세, 검색, 홈 등 주문 플로우 외 페이지
- 스타일만 변경 (레이아웃/구조 변경 없음)
- 백엔드 전용 변경

### 방안 A에서의 필터링

FE 레포 CI에서 변경 파일 경로 기반으로 판별:
```
# 예시: 영향 경로 패턴
src/pages/order/**
src/pages/cart/**
src/pages/claim/**
src/pages/checkout/**
src/components/payment/**
src/components/modal/**
src/routes/**
```

해당 경로에 변경이 있을 때만 dispatch 발행.

---

## 3. 회귀 실행 구성

### 스모크 셋 (빠른 검증, ~5분)

배포 직후 실행. 핵심 플로우만 검증한다.

| # | 시나리오 | 검증 범위 |
|---|---------|----------|
| 1 | `alpha_direct_buy_order_normal.scn` | 바로구매 주문 생성 |
| 2 | `alpha_cart_order_normal.scn` | 장바구니 주문 생성 |
| 3 | `alpha_claim_cancel.scn` | 취소 클레임 |
| 4 | `alpha_claim_return.scn` | 반품 클레임 |
| 5 | `alpha_claim_exchange.scn` | 교환 클레임 |
| 6 | `alpha_claim_entry_check.scn` | 클레임 진입 확인 |

실행 명령:
```bash
python3 executor/execute_scenario.py \
  --continue-on-error \
  --stop-on-scenario-fail \
  scenarios/zigzag/alpha_direct_buy_order_normal.scn \
  scenarios/zigzag/alpha_cart_order_normal.scn \
  scenarios/zigzag/alpha_claim_cancel.scn \
  scenarios/zigzag/alpha_claim_return.scn \
  scenarios/zigzag/alpha_claim_exchange.scn \
  scenarios/zigzag/alpha_claim_entry_check.scn
```

### 풀 회귀 (전체 검증, ~15분)

스모크에서 실패가 없으면 생략 가능. 필요 시 수동 또는 주 1회 정기 실행.

```bash
python3 executor/execute_scenario.py \
  --continue-on-error \
  scenarios/zigzag/alpha_full_history_regression.scn
```

---

## 4. 실패 시 대응 프로세스

```
실패 감지
  │
  ├─ 1. 자동 진단
  │     - /analyze-failure 로 실패 패턴 분류
  │     - 실패 스크린샷 + 로그 수집
  │
  ├─ 2. 원인 분류
  │     ┌─ SELECTOR_NOT_FOUND → 화면 구조 변경 → 셀렉터 업데이트
  │     ├─ SELECTOR_AMBIGUOUS → 새 요소 추가 → 셀렉터 구체화
  │     ├─ URL_MISMATCH → 라우팅 변경 → URL 패턴 업데이트
  │     ├─ TIMING_ISSUE → 렌더링 지연 → WAIT_FOR 추가/조정
  │     └─ SELF_HEALED → fuzzy match 성공 → .scn 파일 영구 패치
  │
  ├─ 3. 시나리오 수정
  │     - 기준 시나리오(exchange/return/cancel.scn) 먼저 수정
  │     - 파생 시나리오 동기화
  │     - docs/input_interaction_patterns.md 반영
  │
  └─ 4. 재실행 검증
        - 수정된 시나리오로 스모크 셋 재실행
        - 통과 확인 후 커밋
```

---

## 5. 실패 알림

### Slack 알림 (최소 구현)

회귀 실행 결과를 Slack 채널로 전송한다.

```
✅ 성공 시: "[order-agent] 회귀 통과 (6/6) — alpha 배포 반영 확인"
❌ 실패 시: "[order-agent] 회귀 실패 (4/6) — 실패: alpha_claim_exchange.scn, alpha_claim_return.scn"
           + 실패 스크린샷 첨부
           + 트리거 원인 PR 링크 (방안 A인 경우)
```

---

## 6. 중장기 개선

### Self-Heal → 자동 패치 제안

현재 fuzzy match self-heal은 실행 중 임시 복구만 한다.
self-heal 이력을 축적하여 `.scn` 파일 패치를 자동 제안하도록 확장한다.

```
[self-heal 감지] alpha_claim_exchange.scn:15
  기존: CLICK text=교환 신청
  매칭: CLICK text=교환 요청하기  (유사도 78%)
  → .scn 파일 패치를 제안합니다. 적용하시겠습니까?
```

### 셀렉터 안정성 등급 개선

| 등급 | 유형 | 내성 | 목표 비율 |
|------|------|------|----------|
| A | `data-testid` | 최고 | 40%+ |
| B | `role=` / ARIA | 높음 | 30%+ |
| C | CSS 속성 | 중간 | 20% |
| D | `text=` | 낮음 | 10% 이하 |

FE 팀에 주문 플로우 핵심 요소에 `data-testid` 추가를 요청한다.

### DOM 스냅샷 diff

실패 시 접근성 트리 텍스트 덤프를 저장하고, 이전 성공 시 덤프와 diff하여 변경점을 시각화한다.

---

## 7. 구현 우선순위

| 순서 | 작업 | 소요 | 효과 |
|------|------|------|------|
| 1 | 스모크 셋 정의 + 실행 스크립트 | 반나절 | 수동이라도 빠른 검증 가능 |
| 2 | 트리거 방식 결정 (A or B) | 조사 1일 | 자동화 기반 확보 |
| 3 | 트리거 → 회귀 실행 파이프라인 | 1~2일 | 배포 시 자동 검증 |
| 4 | Slack 실패 알림 | 반나절 | 실패 즉시 인지 |
| 5 | self-heal → .scn 패치 제안 | 2~3일 | 복구 시간 단축 |
| 6 | 셀렉터 등급 개선 + data-testid | 지속 | 근본적 내성 확보 |

---

## 미결 사항

- [ ] FE 레포(zigzag-web) CI 수정 권한 확인 → 방안 A/B 결정
- [ ] alpha 환경 버전 확인 엔드포인트 존재 여부 확인
- [ ] Slack 알림 채널 및 webhook URL 결정
- [ ] FE 팀에 data-testid 추가 협의 시점
