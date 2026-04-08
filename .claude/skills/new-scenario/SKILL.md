---
name: new-scenario
description: "Generates .scn scenario files from natural language descriptions using order DSL syntax. Use when: 시나리오 생성, 시나리오 만들어줘, 테스트 케이스 작성, new scenario, 플로우 자동화."
argument-hint: "<자연어 시나리오 설명>"
---

# 시나리오 생성 도우미

사용자의 자연어 요청을 받아 .scn 시나리오 파일을 올바른 DSL 문법으로 생성한다.

**When to Use:** 새 테스트 케이스 작성, 기존 시나리오 변형, 특정 주문/클레임 플로우 자동화
**Not for:** 시나리오 실행 → `run-scenario` | 시나리오 검증 → `validate-scenario`

---

## Execution Steps

1. 먼저 `.claude/skills/scenario-guide/SKILL.md`를 읽고 작성 규칙을 적용한다.

2. $ARGUMENTS의 설명을 분석하여 시나리오를 생성한다.

3. 시나리오 DSL 규칙:
   - 기본 도메인: `https://alpha.zigzag.kr/`
   - 주석: `#`으로 시작, 빈 줄 허용
   - 따옴표 문자열 지원 (shlex.split 기반)

4. 허용 액션:

   | 액션 | 인자 | 설명 |
   |------|------|------|
   | NAVIGATE | url | 페이지 이동 |
   | CLICK | selector | 요소 클릭 |
   | FILL | selector value | 입력 필드 채우기 |
   | WAIT_FOR | selector 또는 ms | 요소/시간 대기 |
   | CHECK | selector | 요소 존재 확인 |
   | PRESS | key | 키 입력 |
   | CHECK_URL | substring | URL 문자열 포함 확인 |
   | CHECK_NOT_URL | substring | URL 문자열 미포함 확인 |
   | WAIT_URL | substring | URL 포함 대기 |
   | CHECK_NEW_ORDER_SHEET | 없음 | 새 주문서 생성 확인 |
   | SAVE_ORDER_DETAIL_ID | 없음 | 현재 주문상세 ID 저장 |
   | CHECK_ORDER_DETAIL_ID_CHANGED | 없음 | 주문상세 ID 변경 확인 |
   | SAVE_ORDER_NUMBER | 없음 | 현재 주문번호 저장 |
   | CHECK_ORDER_NUMBER_CHANGED | 없음 | 주문번호 변경 확인 |
   | EVAL | js_expression | JavaScript 실행 |
   | ENSURE_LOGIN_ZIGZAG_ALPHA | url | 알파 로그인 보장 (인증 필수 URL 사용) |
   | ENSURE_LOGIN_GRAFANA | [url] | Grafana Keycloak-OAuth+OTP 로그인 보장 (GRAFANA_USERNAME/GRAFANA_PASSWORD 환경변수) |
   | CLICK_SNAPSHOT_TEXT | text | 스냅샷 텍스트 클릭 |
   | CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT | text | 스냅샷 텍스트 앞 체크박스 클릭 |
   | SELECT_CART_ITEM_BY_TEXT | text | 장바구니 아이템 선택 |
   | CLICK_ORDER_DETAIL_BY_STATUS | status | 상태별 주문상세 진입 |
   | CLICK_ORDER_DETAIL_WITH_ACTION | action | 액션 가능한 주문상세 진입 |
   | SUBMIT_CANCEL_REQUEST | reason | 취소 요청 제출 |
   | SUBMIT_RETURN_REQUEST | reason | 반품 요청 제출 |
   | SUBMIT_EXCHANGE_REQUEST | reason | 교환 요청 제출 |
   | APPLY_ORDER_STATUS_FILTER | status | 주문 상태 필터 |
   | PRINT_ACTIVE_MODAL | 없음 | 현재 활성 모달 상태 출력 |
   | CHECK_PAYMENT_RESULT | 없음 | 결제 결과 검증 |
   | EXPECT_FAIL | [pattern] | 다음 액션 실패 예상 |
   | READ_OTP | account [var] | OTP 읽기 |
   | DUMP_STATE | tag | 상태 덤프 |

5. 셀렉터 규칙:
   - `@id`, `text=텍스트`, `role=button`, `#id`, `.class`, `[attr]`
   - 접두사 없으면 `@`가 자동 부여됨

6. 안전 정책:
   - `CLICK confirm_payment` 절대 금지
   - 기본은 0원 결제 플로우만 허용
   - 실제 결제 허용은 명시적 승인과 `ALLOW_REAL_PAYMENT=1`이 있는 경우만 예외

7. ENSURE_LOGIN_ZIGZAG_ALPHA target은 반드시 **인증 필수 페이지** 사용 (예: `/checkout/orders`)
   - 공개 페이지(`/catalog/products/...`)를 target으로 사용하면 세션 만료를 감지 못함

8. 기존 시나리오를 참고하여 패턴을 맞춘다.
   - 주문(바로구매): `scenarios/zigzag/alpha_direct_buy_order_normal.scn`
   - 주문(장바구니): `scenarios/zigzag/alpha_cart_order_normal.scn`
   - 교환: `scenarios/zigzag/alpha_claim_exchange.scn`
   - 반품: `scenarios/zigzag/alpha_claim_return.scn`
   - 취소: `scenarios/zigzag/alpha_claim_cancel.scn`
   - 외부 서비스 로그인: `scenarios/aws/sso_login.scn`

9. 카테고리에 맞는 디렉토리에 저장 후 `/validate-scenario`로 검증 권장.
   - Zigzag 주문/클레임: `scenarios/zigzag/`
   - AWS: `scenarios/aws/`
   - 네이버: `scenarios/naver/`
   - Grafana: `scenarios/grafana/`
   - 기타 외부 서비스: `scenarios/<서비스명>/`

10. **시나리오 문서 등록**: 생성한 시나리오를 아래 두 문서에 추가한다.
    - `.claude/skills/list-scenarios/SKILL.md` — 해당 카테고리에 파일명 추가. 기존 카테고리가 없으면 새 섹션 추가
    - `docs/scenarios.md` — Active Scenarios 목록에 번호·경로·목적·핵심 형식으로 추가

---

## 예시

- `/new-scenario 상품 100136725를 장바구니에 담고 주문하는 시나리오`
- `/new-scenario 최근 배송완료 주문의 반품 요청 시나리오`
- `/new-scenario 로그인 후 검색해서 첫 번째 상품 구매하는 시나리오`

---

**Related Skills:**
- [scenario-guide](../scenario-guide/SKILL.md) - 시나리오 작성 가이드
- [run-scenario](../run-scenario/SKILL.md) - 시나리오 실행
- [validate-scenario](../validate-scenario/SKILL.md) - 시나리오 검증
- [list-scenarios](../list-scenarios/SKILL.md) - 시나리오 목록
