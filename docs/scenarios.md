# Scenario Inventory

시나리오 목록은 이 문서에서 관리한다.

## Active Scenarios

1. `services/zigzag/scenarios/alpha_pdp_direct_order_complete_100136725.scn`
- 목적: PDP 바로구매 경로로 주문완료(`/checkout/order-completed/`)까지 검증
- 핵심: `CLICK_SNAPSHOT_TEXT "포인트 전액사용"` + `0원` 결제 버튼 검증

2. `services/zigzag/scenarios/alpha_order_creation_100136725.scn`
- 목적: 바로구매 주문 생성 플로우(기준 orderNumber 대비 변경 확인)
- 핵심: 로그인 보장, 신규 order-sheet 검증, 포인트 전액/결제, `CHECK_ORDER_NUMBER_CHANGED`

3. `services/zigzag/scenarios/alpha_order_creation_100136725_cart.scn`
- 목적: 장바구니 경유 주문 생성 플로우(기준 orderNumber 대비 변경 확인)
- 핵심: cart -> order-sheet 전환, 포인트 전액/결제, `CHECK_ORDER_NUMBER_CHANGED`

4. `services/zigzag/scenarios/alpha_cart_add_and_checkout_100136725.scn`
- 목적: PDP에서 장바구니 담기 후 장바구니에서 구매 완료까지 검증
- 핵심: 기존 장바구니는 유지하고 타겟 상품만 선택(`SELECT_CART_ITEM_BY_TEXT`), 포인트 전액/결제, `order-completed` 확인
- 최신 실브라우저 성공: 2026-03-06, `order-completed/138266936863171343`

5. `services/zigzag/scenarios/alpha_full_history_regression.scn`
- 목적: alpha 회귀 및 증적 수집(상태 덤프 중심)

6. `services/zigzag/scenarios/alpha_relogin_recovery.scn`
- 목적: 로그인 세션 만료 시 `ENSURE_LOGIN_ALPHA` 복구 동작 검증

7. `services/zigzag/scenarios/alpha_blocking_modal_case.scn`
- 목적: 결제 클릭 이후 차단 모달/알림 메시지 증적 수집

8. `services/zigzag/scenarios/alpha_insufficient_points_case.scn`
- 목적: 포인트 전액사용 불가/0원 미충족 상태 증적 수집

9. `services/zigzag/scenarios/alpha_cart_multi_item_target_only.scn`
- 목적: 장바구니 다건 상태에서 타겟 상품만 선택 후 주문서 전환 검증

10. `services/zigzag/scenarios/alpha_payment_request_stuck_case.scn`
- 목적: 결제 후 `PAYMENT_REQUEST_STUCK` 분류 검증 (`CHECK_PAYMENT_RESULT`)

11. `services/zigzag/scenarios/alpha_claim_cancel_case.scn`
- 목적: 주문배송 목록 -> 주문상세 -> 취소요청 화면 -> 취소 요청 완료까지 검증
- 핵심: 필터 모달 없이 주문배송목록에서 `결제완료/주문확인중` 상태 주문을 직접 탐색 + `CLICK_ORDER_DETAIL_WITH_ACTION 취소` + `SUBMIT_CANCEL_REQUEST "옵션을 잘못 선택했어요"` + 취소 상태 텍스트 검증

12. `services/zigzag/scenarios/alpha_claim_entry_case.scn`
- 목적: 주문상세에서 클레임 3종(취소/반품/교환) 진입 가능 여부 및 증적 수집

13. `services/zigzag/scenarios/alpha_claim_return_case.scn`
- 목적: 주문배송 목록의 배송완료 필터 적용 후 반품 요청 완료까지 검증
- 핵심: `APPLY_ORDER_STATUS_FILTER 배송완료` -> `CLICK_ORDER_DETAIL_WITH_ACTION 반품` -> `SUBMIT_RETURN_REQUEST "사이즈가 맞지 않아요"` -> 반품 상태 텍스트 검증

14. `services/zigzag/scenarios/alpha_claim_exchange_case.scn`
- 목적: 주문배송 목록의 배송완료 필터 적용 후 교환 요청 -> 교환비용 결제 -> 완료 -> 주문상세 이동까지 검증
- 핵심: `APPLY_ORDER_STATUS_FILTER 배송완료` -> `CLICK_ORDER_DETAIL_WITH_ACTION 교환` -> `SUBMIT_EXCHANGE_REQUEST "사이즈가 맞지 않아요"` -> `포인트 전액사용` + `0원 결제하기` -> `/claim-order-completed` -> 주문상세 이동
- 최신 개선: 다단계 옵션(2단계 이상 포함)에서 `옵션 미선택 문구`가 사라질 때까지 단계별로 `첫 활성 옵션` 반복 선택, `색상/사이즈` 타이틀 클릭 제외, container 네이밍 영역 우선 탐색

15. `services/naver/scenarios/smoke_naver.scn`
- 목적: 네이버 검색 스모크

16. `services/naver/scenarios/visible_naver.scn`
- 목적: 네이버 가시성 대기 포함 스모크

## 운영 원칙

- 시나리오 파일 추가/삭제 시 이 문서를 먼저 갱신한다.
- README에는 대표 실행 예시만 유지하고, 전체 목록은 본 문서를 단일 소스로 사용한다.
- 실결제 검증 시나리오는 반드시 `order-completed` 도달 조건을 포함한다.
- 교환 시나리오 안정화 작업/운영 기준은 `docs/exchange_stabilization_plan.md`를 단일 소스로 관리한다.
- 클레임(취소/반품/교환)에서 선택형 필드는 기본적으로 `첫 활성 옵션`을 사용한다.
- 클레임(취소/반품/교환)에서 입력형 필수 필드가 비어 있으면 기본값 `test`를 입력한다.
- 옵션 선택 스코프는 `container` 네이밍(class/id/name/data-testid/style 포함) 영역을 우선 사용한다.
- 클레임 사유는 시나리오에서 `SUBMIT_*_REQUEST "__ASK__"`로 지정하면 런타임에 실제 전체 선택지를 번호로 선택한다.
- 비대화 실행에서는 `ORDER_AGENT_REASON_INDEX`(1-based) 또는 `ORDER_AGENT_REASON_TEXT`를 반드시 지정해야 하며, 미지정 시 `ASK_REASON_REQUIRED`로 실패한다.

## Failure Codes

- `STAYED_ON_ORDER_SHEET`
  - 의미: 결제 시도 후에도 주문서(`/checkout/order-sheets/`)에 잔류
  - 대표 원인: 동의/포인트/버튼 상태 불충족, 차단 모달

- `PAYMENT_REQUEST_STUCK`
  - 의미: 결제 요청 URL(`/api/payment/v1/request/...`)로 이동했으나 완료 페이지로 미전환
  - 대표 원인: 결제 리다이렉트 장애, chunk 로딩 실패, 내부망 리소스 차단

- `NO_COMPLETION_REDIRECT`
  - 의미: 주문서 잔류도 아니고 결제요청 고착도 아닌 상태에서 완료 URL 미도달
  - 대표 원인: 예외 라우팅/중간 페이지 이탈

- `ENV_UPSTREAM_UNHEALTHY`
  - 의미: 페이지가 `no healthy upstream`/`bad gateway` 상태로 복구 재시도 후에도 지속
  - 대표 원인: 내부망/게이트웨이 일시 장애

- `RETURN_REQUEST_STUCK`
  - 의미: 반품 요청 제출 후에도 `/request-return`에서 이탈하지 못한 경우
  - 대표 원인: 수거방법/필수항목 미선택, 확인 모달 미처리

- `RETURN_REQUEST_BLOCKED_1P1`
  - 의미: 1+1 상품 정책으로 부분 반품이 차단된 경우
  - 대표 원인: 세트 옵션 일부만 반품 요청

- `EXCHANGE_REQUEST_STUCK`
  - 의미: 교환 요청 제출 후에도 `/request-exchange`에서 이탈하지 못한 경우
  - 대표 원인: 수거방법/필수항목 미선택, 확인 모달 미처리

- `EXCHANGE_REQUEST_BLOCKED_1P1`
  - 의미: 1+1 상품 정책으로 부분 교환이 차단된 경우
  - 대표 원인: 세트 옵션 일부만 교환 요청

- `EXCHANGE_OPTION_SELECTION_REQUIRED`
  - 의미: 교환 요청 단계에서 필수 교환 옵션이 미선택 상태로 남아 제출 불가
  - 대표 원인: 옵션 선택 UI 미노출/미선택

- `EXCHANGE_UI_CHUNK_LOAD`
  - 의미: 교환 옵션 선택 UI 로딩이 chunk load 오류로 깨져 제출 불가
  - 대표 원인: 내부망 리소스 로딩 실패(정적 chunk 403/로드 실패)
  - 집계 기준: `blocked` (환경 차단)
