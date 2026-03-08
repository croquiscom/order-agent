# /new-scenario - 시나리오 생성 도우미

## 목적
사용자의 자연어 요청을 받아 .scn 시나리오 파일을 올바른 DSL 문법으로 생성한다.
시나리오 DSL 문법을 매번 기억하지 않아도 되도록 돕는다.

## 사용 시점
- 새로운 테스트 케이스를 시나리오로 만들 때
- 기존 시나리오를 참고하여 변형 시나리오를 만들 때
- 특정 주문/클레임 플로우를 자동화할 때

## 실행 방법

1. $ARGUMENTS의 설명을 분석하여 시나리오를 생성한다.

2. 시나리오 DSL 규칙:
   - 기본 도메인: `https://alpha.zigzag.kr/`
   - 주석: `#`으로 시작
   - 빈 줄 허용
   - 따옴표 문자열 지원 (shlex.split 기반)

3. 허용 액션:
   | 액션 | 인자 | 설명 |
   |------|------|------|
   | NAVIGATE | url | 페이지 이동 |
   | CLICK | selector | 요소 클릭 |
   | FILL | selector value | 입력 필드 채우기 |
   | WAIT_FOR | selector 또는 ms | 요소 대기 또는 시간 대기 |
   | CHECK | selector | 요소 존재 확인 |
   | PRESS | key | 키 입력 (Enter, Escape 등) |
   | CHECK_URL | substring | 현재 URL에 문자열 포함 확인 |
   | WAIT_URL | substring | URL에 문자열 포함될 때까지 대기 |
   | EVAL | js_expression | JavaScript 실행 |
   | ENSURE_LOGIN_ALPHA | url | 알파 환경 로그인 보장 |
   | CLICK_SNAPSHOT_TEXT | text | 스냅샷에서 텍스트로 클릭 |
   | SUBMIT_CANCEL_REQUEST | reason | 취소 요청 제출 |
   | SUBMIT_RETURN_REQUEST | reason | 반품 요청 제출 |
   | SUBMIT_EXCHANGE_REQUEST | reason | 교환 요청 제출 |
   | APPLY_ORDER_STATUS_FILTER | status | 주문 상태 필터 적용 |
   | DUMP_STATE | tag | 상태 덤프 (디버깅용) |

4. 셀렉터 규칙:
   - `@id` — ID 기반
   - `text=텍스트` — 텍스트 기반
   - `role=button` — ARIA 역할 기반
   - `#id`, `.class`, `[attr]` — CSS 셀렉터
   - 접두사 없으면 `@`가 자동 부여됨

5. 안전 정책:
   - `CLICK confirm_payment` 절대 금지
   - 실제 결제 발생 방지

6. 기존 시나리오(`services/zigzag/scenarios/*.scn`)를 참고하여 패턴을 맞춘다.

7. 생성된 파일을 `services/zigzag/scenarios/`에 저장하고, `/validate-scenario`로 검증을 권장한다.

## 예시
- `/new-scenario 상품 100136725를 장바구니에 담고 주문하는 시나리오`
- `/new-scenario 최근 배송완료 주문의 반품 요청 시나리오`
- `/new-scenario 로그인 후 검색해서 첫 번째 상품 구매하는 시나리오`
