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

1. $ARGUMENTS의 설명을 분석하여 시나리오를 생성한다.

2. 시나리오 DSL 규칙:
   - 기본 도메인: `https://alpha.zigzag.kr/`
   - 주석: `#`으로 시작, 빈 줄 허용
   - 따옴표 문자열 지원 (shlex.split 기반)

3. 허용 액션:

   | 액션 | 인자 | 설명 |
   |------|------|------|
   | NAVIGATE | url | 페이지 이동 |
   | CLICK | selector | 요소 클릭 |
   | FILL | selector value | 입력 필드 채우기 |
   | WAIT_FOR | selector 또는 ms | 요소/시간 대기 |
   | CHECK | selector | 요소 존재 확인 |
   | PRESS | key | 키 입력 |
   | CHECK_URL | substring | URL 문자열 포함 확인 |
   | WAIT_URL | substring | URL 포함 대기 |
   | EVAL | js_expression | JavaScript 실행 |
   | ENSURE_LOGIN_ALPHA | url | 알파 로그인 보장 (인증 필수 URL 사용) |
   | CLICK_SNAPSHOT_TEXT | text | 스냅샷 텍스트 클릭 |
   | SUBMIT_CANCEL_REQUEST | reason | 취소 요청 제출 |
   | SUBMIT_RETURN_REQUEST | reason | 반품 요청 제출 |
   | SUBMIT_EXCHANGE_REQUEST | reason | 교환 요청 제출 |
   | APPLY_ORDER_STATUS_FILTER | status | 주문 상태 필터 |
   | DUMP_STATE | tag | 상태 덤프 |

4. 셀렉터 규칙:
   - `@id`, `text=텍스트`, `role=button`, `#id`, `.class`, `[attr]`
   - 접두사 없으면 `@`가 자동 부여됨

5. 안전 정책: `CLICK confirm_payment` 절대 금지

6. ENSURE_LOGIN_ALPHA target은 반드시 **인증 필수 페이지** 사용 (예: `/checkout/orders`)
   - 공개 페이지(`/catalog/products/...`)를 target으로 사용하면 세션 만료를 감지 못함

7. 기존 시나리오(`services/zigzag/scenarios/*.scn`)를 참고하여 패턴을 맞춘다.

8. `services/zigzag/scenarios/`에 저장 후 `/validate-scenario`로 검증 권장.

---

## 예시

- `/new-scenario 상품 100136725를 장바구니에 담고 주문하는 시나리오`
- `/new-scenario 최근 배송완료 주문의 반품 요청 시나리오`
- `/new-scenario 로그인 후 검색해서 첫 번째 상품 구매하는 시나리오`

---

**Related Skills:**
- [run-scenario](../run-scenario/SKILL.md) - 시나리오 실행
- [validate-scenario](../validate-scenario/SKILL.md) - 시나리오 검증
- [list-scenarios](../list-scenarios/SKILL.md) - 시나리오 목록
