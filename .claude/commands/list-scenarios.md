# /list-scenarios - 시나리오 목록 조회

## 목적
사용 가능한 테스트 시나리오를 한글 설명과 함께 번호 목록으로 보여준다.
사용자가 번호를 선택하면 `/run-scenario`로 해당 시나리오를 실행한다.

## 실행 방법

1. `services/*/scenarios/*.scn` 파일을 모두 탐색한다.

2. 각 파일의 첫 번째 `#` 주석 줄에서 한글 설명을 추출한다.

3. 아래 카테고리별로 그룹핑하여 번호를 매긴 목록을 출력한다:

### 지그재그 (Zigzag)

**주문 생성 — 스토어배송 (normal)**
| # | 시나리오 | 설명 |
|---|---------|------|
| 1 | alpha_direct_buy_order_normal | 스토어배송 바로구매 주문 생성 (주문번호 변경 검증) |
| 2 | alpha_direct_buy_complete_normal | 스토어배송 바로구매 주문 완료 (주문완료 페이지 도달) |
| 3 | alpha_cart_checkout_complete_normal | 스토어배송 장바구니 담기 → 구매 완료 |
| 4 | alpha_cart_order_normal | 스토어배송 장바구니 경유 주문 생성 (주문번호 변경 검증) |

**주문 생성 — 직진배송 (zigzin)**
| # | 시나리오 | 설명 |
|---|---------|------|
| 5 | alpha_direct_buy_order_zigzin | 직진배송 바로구매 주문 생성 (주문번호 변경 검증) |
| 6 | alpha_direct_buy_complete_zigzin | 직진배송 바로구매 주문 완료 (주문완료 페이지 도달) |
| 7 | alpha_cart_checkout_complete_zigzin | 직진배송 장바구니 담기 → 구매 완료 |
| 8 | alpha_cart_order_zigzin | 직진배송 장바구니 경유 주문 생성 (주문번호 변경 검증) |

**장바구니 기타**
| # | 시나리오 | 설명 |
|---|---------|------|
| 9 | alpha_cart_multi_item_single_order | 장바구니 다건 중 타겟 단건 주문 |

**클레임 (성공)**
| # | 시나리오 | 설명 |
|---|---------|------|
| 10 | alpha_claim_cancel | 취소 요청 완료 (자동 탐색) |
| 11 | alpha_claim_cancel_by_order | 지정 주문번호 취소 (`--var order_number=주문번호`) |
| 12 | alpha_claim_return | 반품 요청 + 비용 결제 완료 (자동 탐색) |
| 13 | alpha_claim_return_by_order | 지정 주문번호 반품 (`--var order_number=주문번호`) |
| 14 | alpha_claim_exchange | 교환 요청 + 비용 결제 완료 (자동 탐색) |
| 15 | alpha_claim_exchange_by_order | 지정 주문번호 교환 (`--var order_number=주문번호`) |
| 16 | alpha_claim_entry_check | 클레임 3종 진입 가능 여부 확인 |

**클레임 (실패/정책 차단)**
| # | 시나리오 | 설명 |
|---|---------|------|
| 17 | alpha_claim_exchange_policy_blocked | 협찬 프로모션 교환 정책 차단 검증 |

**결제/포인트 예외**
| # | 시나리오 | 설명 |
|---|---------|------|
| 18 | alpha_payment_blocked_modal | 결제 차단 모달 캡처 |
| 19 | alpha_insufficient_points | 포인트 부족 상태 증적 |
| 20 | alpha_payment_stuck | 결제 요청 후 고착 여부 판정 |

**기타**
| # | 시나리오 | 설명 |
|---|---------|------|
| 21 | alpha_relogin_recovery | 재로그인 복구 검증 |
| 22 | alpha_full_history_regression | 전체 이력 통합 회귀 테스트 |

### 네이버 (Naver)
| # | 시나리오 | 설명 |
|---|---------|------|
| 23 | smoke_naver | 네이버 스모크 테스트 |
| 24 | visible_naver | 네이버 가시성 테스트 |

4. 목록 출력 후 사용자에게 안내한다:
   ```
   번호를 입력하면 해당 시나리오를 실행합니다.
   여러 개를 선택하려면 쉼표로 구분하세요 (예: 1,6)
   ```

5. 사용자가 번호를 입력하면:
   - 해당 번호의 `.scn` 파일 경로를 조합한다
   - `/run-scenario <파일경로>` 스킬을 호출하여 실행한다
   - 여러 번호인 경우 순차 실행한다

6. 새로운 `.scn` 파일이 추가된 경우:
   - 위 목록에 없는 파일이 발견되면 "기타" 카테고리에 자동 추가하여 보여준다
   - 파일의 첫 `#` 주석에서 설명을 추출한다

## 예시
- `/list-scenarios` — 전체 목록 표시 후 선택 대기
