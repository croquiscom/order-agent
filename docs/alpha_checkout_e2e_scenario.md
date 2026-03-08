# Alpha Checkout E2E Scenario

## 목적
- alpha 환경(`https://alpha.zigzag.kr/`)에서 로그인/구매 플로우를 반복 검증한다.
- 실테스트 중 자주 발생한 이슈(오버레이 클릭 차단, 주문서 URL 검증 누락)를 표준 절차에 반영한다.

## 테스트 계정
- ID: `{{username}}`
- PW: `{{password}}`

## 대상 URL
- 로그인: `https://alpha.zigzag.kr/auth/email-login?redirect=https%3A%2F%2Falpha.zigzag.kr%2Fmy-page`
- 상품: `https://alpha.zigzag.kr/catalog/products/100136725`
- 장바구니: `https://alpha.zigzag.kr/checkout/cart?from=pdp`

## 자동화 시나리오 파일
- PDP 직행 주문 생성 완료(100136725): `services/zigzag/scenarios/alpha_pdp_direct_order_complete_100136725.scn`
- 장바구니 담기 후 결제 완료(100136725): `services/zigzag/scenarios/alpha_cart_add_and_checkout_100136725.scn`
- 주문 생성(바로구매): `services/zigzag/scenarios/alpha_order_creation_100136725.scn`
- 주문 생성(장바구니): `services/zigzag/scenarios/alpha_order_creation_100136725_cart.scn`
- 재로그인 복구: `services/zigzag/scenarios/alpha_relogin_recovery.scn`
- 결제 차단 모달 증적: `services/zigzag/scenarios/alpha_blocking_modal_case.scn`
- 포인트 부족 증적: `services/zigzag/scenarios/alpha_insufficient_points_case.scn`
- 장바구니 다건 타겟 단건 주문: `services/zigzag/scenarios/alpha_cart_multi_item_target_only.scn`
- 결제요청 고착 분류: `services/zigzag/scenarios/alpha_payment_request_stuck_case.scn`
- 취소 요청 완료: `services/zigzag/scenarios/alpha_claim_cancel_case.scn`
- 반품 요청 완료(배송완료 필터): `services/zigzag/scenarios/alpha_claim_return_case.scn`
- 교환 요청 완료(배송완료 필터): `services/zigzag/scenarios/alpha_claim_exchange_case.scn`
  - 범위: 교환 요청 -> 교환비용결제(포인트 전액/0원 결제) -> 교환완료 -> 주문상세 이동
- 클레임 진입 3종(취소/반품/교환): `services/zigzag/scenarios/alpha_claim_entry_case.scn`
- 전체 이력 통합 회귀: `services/zigzag/scenarios/alpha_full_history_regression.scn`

## 실행 방법
```bash
# 1) PDP 직행 주문 생성 완료(100136725)
python3 services/zigzag/scripts/execute_scenario.py \
  services/zigzag/scenarios/alpha_pdp_direct_order_complete_100136725.scn \
  --continue-on-error

# 2) 장바구니 담기 후 결제 완료
python3 services/zigzag/scripts/execute_scenario.py \
  services/zigzag/scenarios/alpha_cart_add_and_checkout_100136725.scn \
  --continue-on-error

# 3) 주문 생성(바로구매)
python3 services/zigzag/scripts/execute_scenario.py \
  services/zigzag/scenarios/alpha_order_creation_100136725.scn \
  --continue-on-error

# 4) 주문 생성(장바구니)
python3 services/zigzag/scripts/execute_scenario.py \
  services/zigzag/scenarios/alpha_order_creation_100136725_cart.scn \
  --continue-on-error

# 5) 전체 진행 이력 통합 회귀
python3 services/zigzag/scripts/execute_scenario.py \
  services/zigzag/scenarios/alpha_full_history_regression.scn \
  --continue-on-error

# 6) 취소 요청 완료
python3 services/zigzag/scripts/execute_scenario.py \
  services/zigzag/scenarios/alpha_claim_cancel_case.scn \
  --continue-on-error
```

## 기대 결과
1. 로그인 후 alpha 상품 페이지 접근 가능
2. 장바구니에서 주문서로 URL 전환 (`/checkout/order-sheets/`)
3. 주문서에서 `포인트 전액사용` 후 `0원 구매하기` 버튼 확인
4. `0원 구매하기` 클릭 후 주문완료 URL(`/checkout/order-completed/`) 확인

## 결제 확정 운영 원칙
- 내부망 실테스트 환경에서는 승인된 테스트 계정으로 결제완료 시나리오를 수행한다.
- 포인트 전액 결제 조건(`0원 구매하기`)이 만족되지 않으면 결제 단계를 진행하지 않는다.

## 최근 실테스트 결과 반영
- 주문서 할인 영역에는 `마일리지 전액사용`과 `포인트 전액사용`이 모두 존재할 수 있음.
- `포인트 전액사용`은 텍스트 클릭 대신 snapshot ref 기반(`CLICK_SNAPSHOT_TEXT`)으로 정확히 클릭하도록 보강함.
- `0원 구매하기`가 보이지 않으면 결제 단계를 실패 처리하도록 게이트를 추가함.
- 장바구니 시나리오는 기존 장바구니는 유지하고, 타겟 상품만 선택해 주문하도록 보강함.
- 2026-03-06 실브라우저 기준 `alpha_cart_add_and_checkout_100136725.scn` 주문완료 확인:
  `https://alpha.zigzag.kr/checkout/order-completed/138266936863171343`

## 실테스트 기반 개선 반영사항
- 오버레이에 의해 `CLICK` 차단될 때 `ESC` 후 자동 재시도
- 실패 시 자동 스크린샷 저장(`logs/failed_line_*.png`)
- URL 전환 검증용 `CHECK_URL` 액션 지원
- URL 전환 대기용 `WAIT_URL` 액션 지원
- 상태 덤프용 `DUMP_STATE` 액션 지원 (`logs/diag_<tag>_*.txt`, `.png`)
- `PRESS` 액션 지원(모달/레이어 해제 용도)
- `CLICK_SNAPSHOT_TEXT` 액션 지원(snapshot ref 기반 안정 클릭)
- `SELECT_CART_ITEM_BY_TEXT` 액션 지원(장바구니 타겟 상품 체크박스 선택)
- `CLICK_ORDER_DETAIL_BY_STATUS` 액션 지원(주문상세 목록에서 상태 기준 우선 선택)
- `CLICK_ORDER_DETAIL_WITH_ACTION` 액션 지원(주문상세 목록에서 특정 액션 버튼이 보이는 주문 자동 선택)
- `SUBMIT_CANCEL_REQUEST` 액션 지원(취소사유 선택/안내체크/취소요청 제출)
- `SUBMIT_RETURN_REQUEST` 액션 지원(반품사유 선택/안내체크/반품요청 제출)
- `SUBMIT_EXCHANGE_REQUEST` 액션 지원(교환사유 선택/수거방법/안내체크/교환요청 제출)
- `CHECK_PAYMENT_RESULT` 액션 지원(주문서 잔류 근거와 메시지 후보 출력)
- 주문번호 추적 별칭 액션 지원: `SAVE_ORDER_NUMBER`, `CHECK_ORDER_NUMBER_CHANGED`
- `agent-browser` 호출 타임아웃/재시도 지원(`ORDER_AGENT_AGENT_BROWSER_TIMEOUT_SEC`, 기본 20초)
- 교환 옵션 선택 안정화:
  - 다단계 옵션(2단계 이상)에서 `옵션 미선택` 문구가 사라질 때까지 단계 반복 선택
  - 각 단계는 `첫 활성 옵션`만 선택
  - `색상/사이즈` 타이틀 요소는 선택 후보에서 제외
  - `container` 네이밍 영역(class/id/name/data-testid/style 포함) 우선 스코프
- 클레임 공통 입력 안정화:
  - 사유 불일치 시 첫 선택지 fallback
  - 필수 입력 필드가 비어 있으면 기본값 `test` 자동 입력

## 실패 케이스 분류

1. `STAYED_ON_ORDER_SHEET`
- 결제 시도 후에도 `/checkout/order-sheets/`에 머무는 경우

2. `PAYMENT_REQUEST_STUCK`
- `/api/payment/v1/request/...`로 진입했지만 `/checkout/order-completed/`로 전환되지 않는 경우
- 최근 관측(2026-03-06): chunk load 실패/403 다수와 함께 발생

3. `NO_COMPLETION_REDIRECT`
- 위 2개 조건 외 케이스에서 완료 URL 미도달

4. `ENV_UPSTREAM_UNHEALTHY`
- `no healthy upstream`/`bad gateway`가 복구 재시도 이후에도 지속되는 환경 장애

5. `RETURN_REQUEST_STUCK`
- 반품 요청 제출 후에도 `/request-return`에서 이탈하지 못하는 경우

6. `RETURN_REQUEST_BLOCKED_1P1`
- 1+1 상품 반품 정책(전체 옵션 동시 반품)으로 요청이 차단되는 경우

7. `EXCHANGE_REQUEST_STUCK`
- 교환 요청 제출 후에도 `/request-exchange`에 머무르는 경우

8. `EXCHANGE_REQUEST_BLOCKED_1P1`
- 1+1 상품 교환 정책(전체 옵션 동시 교환)으로 요청이 차단되는 경우

9. `EXCHANGE_OPTION_SELECTION_REQUIRED`
- 교환 요청 단계에서 필수 교환 옵션이 미선택으로 남아 제출이 막히는 경우

10. `EXCHANGE_UI_CHUNK_LOAD`
- 교환 옵션 UI가 chunk load 오류(정적 리소스 로딩 실패)로 깨져 제출이 막히는 경우
