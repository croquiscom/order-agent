# Scenarios

> Auto-generated from `.scn` file headers. Do not edit manually.
> Run `python3 -m tools.generate_scenarios_md` to regenerate.

## Smoke (매 배포) (6)

| 시나리오 | 설명 | 영역 | 페이지 |
|---------|------|------|--------|
| `scenarios/zigzag/alpha_cart_order_normal.scn` | 장바구니 경유 주문 생성 — 스토어배송 | cart, order, payment | /catalog/products, /checkout/cart, /checkout/order-sheets |
| `scenarios/zigzag/alpha_claim_cancel.scn` | 취소 클레임 요청 완료 | claim, cancel | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_entry_check.scn` | 클레임 3종(취소/반품/교환) 진입 가능 여부 확인 | claim | /checkout/orders |
| `scenarios/zigzag/alpha_claim_exchange.scn` | 교환 클레임 요청 + 비용 결제 완료 | claim, exchange, payment | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_return.scn` | 반품 클레임 요청 + 비용 결제 완료 | claim, return, payment | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_direct_buy_order_normal.scn` | 바로구매 주문 생성 — 스토어배송 | order, payment | /catalog/products, /checkout/order-sheets |

## Regression (영향 범위) (23)

| 시나리오 | 설명 | 영역 | 페이지 |
|---------|------|------|--------|
| `scenarios/zigzag/alpha_cart_checkout_complete_normal.scn` | 장바구니 단건 구매 완료 — 스토어배송 | cart, order, payment, checkout | /catalog/products, /checkout/cart, /checkout/order-sheets, /checkout/order-complete |
| `scenarios/zigzag/alpha_cart_checkout_complete_zigzin.scn` | 장바구니 단건 구매 완료 — 직진배송 | cart, order, payment, checkout | /catalog/products, /checkout/cart, /checkout/order-sheets, /checkout/order-complete |
| `scenarios/zigzag/alpha_cart_multi_item_single_order.scn` | 장바구니 다건 중 단건만 주문 | cart, order | /checkout/cart, /checkout/order-sheets |
| `scenarios/zigzag/alpha_cart_order_zigzin.scn` | 장바구니 경유 주문 생성 — 직진배송 | cart, order, payment | /catalog/products, /checkout/cart, /checkout/order-sheets |
| `scenarios/zigzag/alpha_claim_cancel_by_order.scn` | 지정 주문번호 취소 요청 | claim, cancel | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_cancel_info.scn` | 취소 요청 상세 정보 조회 | claim, cancel | /checkout/orders, /order-item-requests, /cancel-info |
| `scenarios/zigzag/alpha_claim_cancel_unpaid.scn` | 미입금 주문 취소 | claim, cancel | /checkout/orders, /cancel |
| `scenarios/zigzag/alpha_claim_completed_view.scn` | 클레임 완료 페이지 확인 | claim | /checkout/orders, /claim-order-completed |
| `scenarios/zigzag/alpha_claim_exchange_by_order.scn` | 지정 주문번호 교환 요청 + 비용 결제 | claim, exchange, payment | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_exchange_info.scn` | 교환 요청 상세 정보 조회 | claim, exchange | /checkout/orders, /order-item-requests, /exchange-info |
| `scenarios/zigzag/alpha_claim_exchange_input_option.scn` | 교환 클레임 — 입력형 옵션 상품 | claim, exchange, payment | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_exchange_policy_blocked.scn` | 교환 정책 차단 검증 | claim, exchange | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_order_sheet.scn` | 클레임 주문서 진입 확인 (교환 비용 결제) | claim, exchange, payment | /checkout/orders, /order-sheets |
| `scenarios/zigzag/alpha_claim_return_by_order.scn` | 지정 주문번호 반품 요청 + 비용 결제 | claim, return, payment | /checkout/orders, /claim |
| `scenarios/zigzag/alpha_claim_return_info.scn` | 반품 요청 상세 정보 조회 | claim, return | /checkout/orders, /order-item-requests, /return-info |
| `scenarios/zigzag/alpha_direct_buy_complete_normal.scn` | 바로구매 주문 완료 — 스토어배송 | order, payment, checkout | /catalog/products, /checkout/order-sheets, /checkout/order-complete |
| `scenarios/zigzag/alpha_direct_buy_complete_zigzin.scn` | 바로구매 주문 완료 — 직진배송 | order, payment, checkout | /catalog/products, /checkout/order-sheets, /checkout/order-complete |
| `scenarios/zigzag/alpha_direct_buy_order_zigzin.scn` | 바로구매 주문 생성 — 직진배송 | order, payment | /catalog/products, /checkout/order-sheets |
| `scenarios/zigzag/alpha_order_confirm.scn` | 구매확정 플로우 | order | /checkout/orders, /confirm, /confirm-completed |
| `scenarios/zigzag/alpha_order_detail_view.scn` | 주문 상세 페이지 진입 + 주요 섹션 확인 | order | /checkout/orders |
| `scenarios/zigzag/alpha_relogin_recovery.scn` | 재로그인 복구 검증 | login | /auth, /checkout/cart |
| `scenarios/zigzag/alpha_return_shipping_tracking.scn` | 반품 수거 추적 페이지 확인 | claim, return, shipping | /checkout/orders, /return-shipping-tracking |
| `scenarios/zigzag/alpha_shipping_tracking.scn` | 배송 추적 페이지 확인 | order, shipping | /checkout/orders, /shipping-tracking |

## Full (전체/정기) (10)

| 시나리오 | 설명 | 영역 | 페이지 |
|---------|------|------|--------|
| `scenarios/aws/sso_login.scn` | AWS SSO 로그인 | infra, login | - |
| `scenarios/grafana/login.scn` | Grafana 로그인 (Keycloak-OAuth + OTP) | infra, login | - |
| `scenarios/naver/smoke_naver.scn` | 네이버 검색 스모크 테스트 | naver | - |
| `scenarios/naver/visible_naver.scn` | 네이버 요소 가시성 테스트 | naver | - |
| `scenarios/zigzag/alpha_full_history_regression.scn` | 전체 진행 이력 통합 회귀 | order, cart, payment | /catalog/products, /checkout/cart, /checkout/order-sheets |
| `scenarios/zigzag/alpha_insufficient_points.scn` | 포인트 부족 상태 증적 | payment | /checkout/order-sheets |
| `scenarios/zigzag/alpha_payment_blocked_modal.scn` | 결제 차단 모달 캡처 | payment | /checkout/order-sheets |
| `scenarios/zigzag/alpha_payment_stuck.scn` | 결제 요청 후 고착 여부 판정 | payment | /checkout/order-sheets |
| `scenarios/zigzag/alpha_shipping_defer.scn` | 배송 보류 안내 페이지 확인 | order, shipping | /checkout/orders, /shipping-defer |
| `scenarios/zigzag/alpha_shipping_delay_info.scn` | 배송 지연 안내 페이지 확인 | order, shipping | /checkout/orders, /shipping-schedule-delay-info |

**Total: 39 scenarios**
