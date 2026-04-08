---
name: scenario-guide
description: "주문 e2e 시나리오 작성 가이드 및 체크리스트. Use when: 시나리오 가이드, 작성 규칙, scenario guide, 시나리오 어떻게."
---

# 시나리오 작성 가이드

.scn 시나리오 파일을 작성하거나 수정할 때 참조하는 규칙과 체크리스트.

**When to Use:** 새 시나리오 작성 전, 기존 시나리오 수정 전, 작성 규칙 확인
**Not for:** 시나리오 생성 → `new-scenario` | 시나리오 검증 → `validate-scenario`

---

## 1. 사전 참조 문서

시나리오 수정/생성/디버깅 **전에 반드시** 아래 문서를 읽을 것:

- `docs/input_interaction_patterns.md` — 클레임 플로우의 입력 UI 패턴, 셀렉터 전략, 결제 패턴, URL 분기 처리, 트러블슈팅
- `docs/exchange_stabilization_plan.md` — 교환 시나리오 안정화 우선순위 및 완료 조건

---

## 2. 기준 시나리오 (레퍼런스)

파생 시나리오를 만들 때 반드시 기준 시나리오의 패턴과 동기화를 유지할 것:

| 유형 | 기준 시나리오 |
|------|--------------|
| 주문 (바로구매) | `alpha_direct_buy_order_normal.scn` |
| 주문 (장바구니) | `alpha_cart_order_normal.scn` |
| 교환 | `alpha_claim_exchange.scn` |
| 반품 | `alpha_claim_return.scn` |
| 취소 | `alpha_claim_cancel.scn` |

- 파생 시나리오에 EVAL을 직접 작성하지 말고, **기준 시나리오의 검증된 EVAL을 복사**하여 사용
- 셀렉터 범위 변경 시 반드시 실제 DOM 구조와 대조 확인

---

## 3. 시나리오 구조 패턴

모든 시나리오는 아래 공통 흐름을 따를 것:

```
# 0) 사전 상태 저장 (baseline) — 결과 검증을 위한 기준점
ENSURE_LOGIN_ALPHA https://alpha.zigzag.kr/checkout/orders
SAVE_ORDER_NUMBER

# 1) 대상 페이지 진입
NAVIGATE <url>
WAIT_FOR <ms>

# 2) 핵심 액션 수행
EVAL / CLICK / SUBMIT_*_REQUEST ...

# 3) 결과 검증
CHECK_URL / CHECK_ORDER_NUMBER_CHANGED / CHECK_PAYMENT_RESULT
DUMP_STATE <tag>
```

작성 규칙:
- `#` 주석으로 **단계별 목적을 명시** — 실패 시 로그에서 위치 파악 용이
- 페이지 전환 후 반드시 `WAIT_FOR`을 넣을 것 — 렌더링 대기 없이 다음 액션 실행하면 요소 탐색 실패
- `ENSURE_LOGIN_ALPHA` target은 반드시 **인증 필수 페이지** 사용 (예: `/checkout/orders`). 공개 페이지 사용 금지

---

## 4. 허용 액션 요약

아래 액션만 사용 가능 (`execute_scenario.py`의 `ALLOWED_ACTIONS`):

| 카테고리 | 액션 |
|---------|------|
| 브라우저 제어 | `NAVIGATE`, `CLICK`, `FILL`, `WAIT_FOR`, `CHECK`, `PRESS` |
| URL 검증 | `CHECK_URL`, `CHECK_NOT_URL`, `WAIT_URL` |
| 주문 검증 | `CHECK_NEW_ORDER_SHEET`, `SAVE_ORDER_DETAIL_ID`, `CHECK_ORDER_DETAIL_ID_CHANGED`, `SAVE_ORDER_NUMBER`, `CHECK_ORDER_NUMBER_CHANGED`, `CHECK_PAYMENT_RESULT` |
| 주문/장바구니 | `CLICK_ORDER_DETAIL_BY_STATUS`, `CLICK_ORDER_DETAIL_WITH_ACTION`, `APPLY_ORDER_STATUS_FILTER`, `SELECT_CART_ITEM_BY_TEXT` |
| 클레임 제출 | `SUBMIT_CANCEL_REQUEST`, `SUBMIT_RETURN_REQUEST`, `SUBMIT_EXCHANGE_REQUEST` |
| 스냅샷 | `CLICK_SNAPSHOT_TEXT`, `CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT` |
| 인증/유틸 | `ENSURE_LOGIN_ALPHA`, `ENSURE_LOGIN_GRAFANA`, `READ_OTP`, `EVAL`, `DUMP_STATE` |
| 디버깅 | `PRINT_ACTIVE_MODAL`, `EXPECT_FAIL` |

---

## 5. 셀렉터 우선순위

안정성 높은 순서로 사용할 것:

1. **`role=button`, `role=textbox`** — ARIA role 셀렉터, UI 변경에 강함
2. **`button[type=submit]`, `input[name=...]`** — CSS 속성 셀렉터
3. **`#fixed-id`** — 고정 ID가 있을 때만
4. **`text=...`** — 최후 수단. 짧은 텍스트는 다른 요소에 매칭 위험

금지:
- 동적 ID (`#awsui-input-0` 등) — 렌더링마다 변경됨
- `text=로그인`처럼 짧은 텍스트 — 여러 요소에 매칭 가능

참고: 접두사(`@`, `#`, `.`, `[`, `/`, `xpath=`, `text=`, `role=`) 없으면 `@`가 자동 부여됨

---

## 6. 안전 정책

- **`CLICK confirm_payment` 차단** — 실제 결제 방지. `ALLOW_REAL_PAYMENT=1` 없이는 실행 불가
- **0원 결제만 허용** — 포인트 전액사용 → 0원 결제 패턴이 기본
- **포인트 부족 시** — `CLAIM_NOT_AVAILABLE` 리포트 후 안전 종결
- **0원 결제 버튼 탐색** — `button` 태그를 별도 쿼리로 우선 탐색 → 없을 때만 `[role=button],div,a,span` fallback. 혼합 셀렉터 사용 금지 (래퍼 div 오매칭)

---

## 7. 클레임 시나리오 특이사항

- 교환/반품은 **기존 배송완료 주문 필요** → `--var ORDER_NO=<주문번호>`로 전달. 사전 주문 생성 불필요
- `SUBMIT_EXCHANGE_REQUEST "__ASK__"` — 자동으로 첫 번째 사유 선택
- URL 분기: 추가비용 없는 교환은 `/order-sheets/exchange`를 거치지 않음 → EVAL에서 URL 체크 후 스킵 로직 필수
- 옵션 선택은 4가지 패턴(단일/라디오/입력형/다단계) — `docs/input_interaction_patterns.md` 참조

---

## 8. 변경 시 동기화 체크리스트

새 액션을 추가하거나 기존 액션을 변경하면 **반드시** 함께 수정:

- [ ] `executor/execute_scenario.py` — `ALLOWED_ACTIONS`, 검증, CLI 변환
- [ ] `executor/generate_scenario_claude.py` — 시스템 프롬프트, 액션 검증
- [ ] `scenarios/*/*.scn` — 관련 시나리오
- [ ] `tests/*` — 파싱/변환/실행 테스트
- [ ] `claude.md` 섹션 4 — 시나리오 DSL 문서

---

## 9. 검증 및 디버깅

- **드라이런 먼저**: `--dry-run`으로 파싱/안전정책 검증 후 실제 실행
- **로그 확인**: `logs/order-agent-exec_*.log`에서 FAILED 라인 검색
- **스크린샷 확인**: `logs/*.png`로 최종/실패 화면 확인
- **오버레이 간섭**: 클릭이 모달에 가리면 자동 ESC + 1회 재시도
- **`CLICK text=...` 실패**: `find text <value> click` fallback이 1회 자동 수행됨

---

**Related Skills:**
- [new-scenario](../new-scenario/SKILL.md) — 시나리오 생성
- [validate-scenario](../validate-scenario/SKILL.md) — 시나리오 검증
- [run-scenario](../run-scenario/SKILL.md) — 시나리오 실행
- [list-scenarios](../list-scenarios/SKILL.md) — 시나리오 목록
- [analyze-failure](../analyze-failure/SKILL.md) — 실패 분석
