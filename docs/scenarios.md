# Scenarios

> Auto-generated from `.scn` file headers. Do not edit manually.
> Run `python3 -m tools.generate_scenarios_md` to regenerate.

## Smoke (매 배포) (6)

| 시나리오 | 설명 | 영역 | 우선순위 | 페이지 |
|---------|------|------|---------|--------|
| `scenarios/zigzag/alpha_cart_order_normal.scn` | 장바구니 경유 주문 생성 — 스토어배송 | cart, order, payment | P0 | /catalog/products, /checkout/cart, /checkout/order-sheets |
| `scenarios/zigzag/alpha_claim_cancel.scn` | 취소 클레임 요청 완료 | claim, cancel | P0 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_entry_check.scn` | 클레임 3종(취소/반품/교환) 진입 가능 여부 확인 | claim | P1 | /checkout/orders |
| `scenarios/zigzag/alpha_claim_exchange.scn` | 교환 클레임 요청 + 비용 결제 완료 | claim, exchange, payment | P1 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_return.scn` | 반품 클레임 요청 + 비용 결제 완료 | claim, return, payment | P0 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_direct_buy_order_normal.scn` | 바로구매 주문 생성 — 스토어배송 | order, payment | P0 | /catalog/products, /checkout/order-sheets |

## Regression (영향 범위) (33)

| 시나리오 | 설명 | 영역 | 우선순위 | 페이지 |
|---------|------|------|---------|--------|
| `scenarios/zigzag/alpha_cart_checkout_complete_normal.scn` | 장바구니 단건 구매 완료 — 스토어배송 | cart, order, payment, checkout | P0 | /catalog/products, /checkout/cart, /checkout/order-sheets, /checkout/order-complete |
| `scenarios/zigzag/alpha_cart_checkout_complete_zigzin.scn` | 장바구니 단건 구매 완료 — 직진배송 | cart, order, payment, checkout | P0 | /catalog/products, /checkout/cart, /checkout/order-sheets, /checkout/order-complete |
| `scenarios/zigzag/alpha_cart_multi_item_single_order.scn` | 장바구니 다건 중 단건만 주문 | cart, order | P1 | /checkout/cart, /checkout/order-sheets |
| `scenarios/zigzag/alpha_cart_option_change_30day.scn` | 장바구니 옵션변경 — 30일 경과 상품 옵션변경 미제공 검증 | cart, option-change | P2 | /checkout/cart |
| `scenarios/zigzag/alpha_cart_option_change_basic.scn` | 장바구니 옵션변경 — 기본 동작 검증 | cart, option-change | P1 | /catalog/products, /checkout/cart |
| `scenarios/zigzag/alpha_cart_option_change_execute.scn` | 장바구니 옵션변경 — 옵션 변경 실행 및 결과 검증 | cart, option-change | P1 | /catalog/products, /checkout/cart |
| `scenarios/zigzag/alpha_cart_option_change_modal_info.scn` | 장바구니 옵션변경 — 모달 내 정보 항목 검증 | cart, option-change | P2 | /checkout/cart |
| `scenarios/zigzag/alpha_cart_option_change_quantity.scn` | 장바구니 옵션변경 — 수량 변경 및 동일옵션 검증 | cart, option-change | P1 | /checkout/cart |
| `scenarios/zigzag/alpha_cart_option_change_single_option.scn` | 장바구니 옵션변경 — 단일옵션 상품 얼럿 검증 | cart, option-change | P2 | /catalog/products, /checkout/cart |
| `scenarios/zigzag/alpha_cart_order_zigzin.scn` | 장바구니 경유 주문 생성 — 직진배송 | cart, order, payment | P0 | /catalog/products, /checkout/cart, /checkout/order-sheets |
| `scenarios/zigzag/alpha_claim_cancel_by_order.scn` | 지정 주문번호 취소 요청 | claim, cancel | P0 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_cancel_info.scn` | 취소 요청 상세 정보 조회 | claim, cancel | P2 | /checkout/orders, /order-item-requests, /cancel-info |
| `scenarios/zigzag/alpha_claim_cancel_partial.scn` | 다건 주문 부분취소 | claim, cancel, partial | P1 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_cancel_unpaid.scn` | 미입금 주문 취소 | claim, cancel | P1 | /checkout/orders, /cancel |
| `scenarios/zigzag/alpha_claim_completed_view.scn` | 클레임 완료 페이지 확인 | claim | P2 | /checkout/orders, /claim-order-completed |
| `scenarios/zigzag/alpha_claim_exchange_by_order.scn` | 지정 주문번호 교환 요청 + 비용 결제 | claim, exchange, payment | P1 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_exchange_info.scn` | 교환 요청 상세 정보 조회 | claim, exchange | P2 | /checkout/orders, /order-item-requests, /exchange-info |
| `scenarios/zigzag/alpha_claim_exchange_input_option.scn` | 교환 클레임 — 입력형 옵션 상품 | claim, exchange, payment | P1 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_exchange_no_cost.scn` | 추가비용 없는 교환 (동일 옵션 교환) | claim, exchange | P1 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_exchange_policy_1p1.scn` | 1+1 묶음 정책 교환 차단 검증 | claim, exchange, policy | P1 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_exchange_policy_blocked.scn` | 교환 정책 차단 검증 | claim, exchange | P1 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_order_sheet.scn` | 클레임 주문서 진입 확인 (교환 비용 결제) | claim, exchange, payment | P1 | /checkout/orders, /order-sheets |
| `scenarios/zigzag/alpha_claim_return_by_order.scn` | 지정 주문번호 반품 요청 + 비용 결제 | claim, return, payment | P0 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_return_info.scn` | 반품 요청 상세 정보 조회 | claim, return | P2 | /checkout/orders, /order-item-requests, /return-info |
| `scenarios/zigzag/alpha_claim_return_partial.scn` | 다건 주문 부분반품 | claim, return, partial | P1 | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_direct_buy_complete_normal.scn` | 바로구매 주문 완료 — 스토어배송 | order, payment, checkout | P0 | /catalog/products, /checkout/order-sheets, /checkout/order-complete |
| `scenarios/zigzag/alpha_direct_buy_complete_zigzin.scn` | 바로구매 주문 완료 — 직진배송 | order, payment, checkout | P0 | /catalog/products, /checkout/order-sheets, /checkout/order-complete |
| `scenarios/zigzag/alpha_direct_buy_order_zigzin.scn` | 바로구매 주문 생성 — 직진배송 | order, payment | P0 | /catalog/products, /checkout/order-sheets |
| `scenarios/zigzag/alpha_order_confirm.scn` | 구매확정 플로우 | order | P1 | /checkout/orders, /confirm, /confirm-completed |
| `scenarios/zigzag/alpha_order_detail_view.scn` | 주문 상세 페이지 진입 + 주요 섹션 확인 | order | P0 | /checkout/orders |
| `scenarios/zigzag/alpha_relogin_recovery.scn` | 재로그인 복구 검증 | login | P1 | /auth, /checkout/cart |
| `scenarios/zigzag/alpha_return_shipping_tracking.scn` | 반품 수거 추적 페이지 확인 | claim, return, shipping | P1 | /checkout/orders, /return-shipping-tracking |
| `scenarios/zigzag/alpha_shipping_tracking.scn` | 배송 추적 페이지 확인 | order, shipping | P1 | /checkout/orders, /shipping-tracking |

## Full (전체/정기) (10)

| 시나리오 | 설명 | 영역 | 우선순위 | 페이지 |
|---------|------|------|---------|--------|
| `scenarios/aws/sso_login.scn` | AWS SSO 로그인 | infra, login | P2 | - |
| `scenarios/grafana/login.scn` | Grafana 로그인 (Keycloak-OAuth + OTP) | infra, login | P2 | - |
| `scenarios/naver/smoke_naver.scn` | 네이버 검색 스모크 테스트 | naver | P2 | - |
| `scenarios/naver/visible_naver.scn` | 네이버 요소 가시성 테스트 | naver | P2 | - |
| `scenarios/zigzag/alpha_full_history_regression.scn` | 전체 진행 이력 통합 회귀 | order, cart, payment | P0 | /catalog/products, /checkout/cart, /checkout/order-sheets |
| `scenarios/zigzag/alpha_insufficient_points.scn` | 포인트 부족 상태 증적 | payment | P1 | /checkout/order-sheets |
| `scenarios/zigzag/alpha_payment_blocked_modal.scn` | 결제 차단 모달 캡처 | payment | P1 | /checkout/order-sheets |
| `scenarios/zigzag/alpha_payment_stuck.scn` | 결제 요청 후 고착 여부 판정 | payment | P1 | /checkout/order-sheets |
| `scenarios/zigzag/alpha_shipping_defer.scn` | 배송 보류 안내 페이지 확인 | order, shipping | P2 | /checkout/orders, /shipping-defer |
| `scenarios/zigzag/alpha_shipping_delay_info.scn` | 배송 지연 안내 페이지 확인 | order, shipping | P2 | /checkout/orders, /shipping-schedule-delay-info |

**Total: 49 scenarios**

---

## 과제별 커버리지

### ORDER-11850 (6개)

P0: 0 | P1: 3 | P2: 3

| 시나리오 | 설명 | 우선순위 | 상태 |
|---------|------|---------|------|
| `scenarios/zigzag/alpha_cart_option_change_30day.scn` | 장바구니 옵션변경 — 30일 경과 상품 옵션변경 미제공 검증 | P2 | active |
| `scenarios/zigzag/alpha_cart_option_change_basic.scn` | 장바구니 옵션변경 — 기본 동작 검증 | P1 | active |
| `scenarios/zigzag/alpha_cart_option_change_execute.scn` | 장바구니 옵션변경 — 옵션 변경 실행 및 결과 검증 | P1 | active |
| `scenarios/zigzag/alpha_cart_option_change_modal_info.scn` | 장바구니 옵션변경 — 모달 내 정보 항목 검증 | P2 | active |
| `scenarios/zigzag/alpha_cart_option_change_quantity.scn` | 장바구니 옵션변경 — 수량 변경 및 동일옵션 검증 | P1 | active |
| `scenarios/zigzag/alpha_cart_option_change_single_option.scn` | 장바구니 옵션변경 — 단일옵션 상품 얼럿 검증 | P2 | active |

---

## 영역별 커버리지

| 영역 | 시나리오 수 | P0 | P1 | P2 |
|------|-----------|----|----|-----|
| cancel | 5 | 2 | 2 | 1 |
| cart | 12 | 5 | 4 | 3 |
| checkout | 4 | 4 | 0 | 0 |
| claim | 20 | 4 | 12 | 4 |
| exchange | 8 | 0 | 7 | 1 |
| infra | 2 | 0 | 0 | 2 |
| login | 3 | 0 | 1 | 2 |
| naver | 2 | 0 | 0 | 2 |
| option-change | 6 | 0 | 3 | 3 |
| order | 15 | 10 | 3 | 2 |
| partial | 2 | 0 | 2 | 0 |
| payment | 18 | 11 | 7 | 0 |
| policy | 1 | 0 | 1 | 0 |
| return | 5 | 2 | 2 | 1 |
| shipping | 4 | 0 | 2 | 2 |

---

## ⚠ 중복 경고

동일한 `@area` + `@pages` 조합을 가진 시나리오가 발견되었습니다.
의도적 중복이 아니면 통합을 검토하세요.

- **cancel|claim** / `/checkout/orders|/claim` (2개)
  - `scenarios/zigzag/alpha_claim_cancel.scn`
  - `scenarios/zigzag/alpha_claim_cancel_by_order.scn`
- **cart|checkout|order|payment** / `/catalog/products|/checkout/cart|/checkout/order-complete|/checkout/order-sheets` (2개)
  - `scenarios/zigzag/alpha_cart_checkout_complete_normal.scn`
  - `scenarios/zigzag/alpha_cart_checkout_complete_zigzin.scn`
- **cart|option-change** / `/catalog/products|/checkout/cart` (3개)
  - `scenarios/zigzag/alpha_cart_option_change_basic.scn`
  - `scenarios/zigzag/alpha_cart_option_change_execute.scn`
  - `scenarios/zigzag/alpha_cart_option_change_single_option.scn`
- **cart|option-change** / `/checkout/cart` (3개)
  - `scenarios/zigzag/alpha_cart_option_change_30day.scn`
  - `scenarios/zigzag/alpha_cart_option_change_modal_info.scn`
  - `scenarios/zigzag/alpha_cart_option_change_quantity.scn`
- **cart|order|payment** / `/catalog/products|/checkout/cart|/checkout/order-sheets` (3개)
  - `scenarios/zigzag/alpha_cart_order_normal.scn`
  - `scenarios/zigzag/alpha_cart_order_zigzin.scn`
  - `scenarios/zigzag/alpha_full_history_regression.scn`
- **checkout|order|payment** / `/catalog/products|/checkout/order-complete|/checkout/order-sheets` (2개)
  - `scenarios/zigzag/alpha_direct_buy_complete_normal.scn`
  - `scenarios/zigzag/alpha_direct_buy_complete_zigzin.scn`
- **claim|exchange** / `/checkout/orders|/claim` (2개)
  - `scenarios/zigzag/alpha_claim_exchange_no_cost.scn`
  - `scenarios/zigzag/alpha_claim_exchange_policy_blocked.scn`
- **claim|exchange|payment** / `/checkout/orders|/claim` (3개)
  - `scenarios/zigzag/alpha_claim_exchange.scn`
  - `scenarios/zigzag/alpha_claim_exchange_by_order.scn`
  - `scenarios/zigzag/alpha_claim_exchange_input_option.scn`
- **claim|payment|return** / `/checkout/orders|/claim` (2개)
  - `scenarios/zigzag/alpha_claim_return.scn`
  - `scenarios/zigzag/alpha_claim_return_by_order.scn`
- **order|payment** / `/catalog/products|/checkout/order-sheets` (2개)
  - `scenarios/zigzag/alpha_direct_buy_order_normal.scn`
  - `scenarios/zigzag/alpha_direct_buy_order_zigzin.scn`
- **payment** / `/checkout/order-sheets` (3개)
  - `scenarios/zigzag/alpha_insufficient_points.scn`
  - `scenarios/zigzag/alpha_payment_blocked_modal.scn`
  - `scenarios/zigzag/alpha_payment_stuck.scn`
