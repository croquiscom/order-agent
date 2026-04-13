# QA 시나리오 우선순위 분류 기준 (P0/P1/P2)

> 주문팀 QA시트 자동화에서 시나리오 우선순위를 정량적으로 분류하는 기준표입니다.
> 신규 과제 QA시트 수신 시 각 AC 행에 이 기준으로 태그를 부여합니다.

## 분류 기준

| 등급 | 정의 | 매출 영향 | 우회 가능 여부 | 자동화 정책 |
|------|------|-----------|---------------|-------------|
| **P0** | 장애 시 즉시 매출 손실, 우회 불가 | 분 단위 | 불가 | `.scn` 필수 자동화, 슬랙 알림 연동 |
| **P1** | 장애 시 CS 우회 가능, 수시간 내 복구 | 시간 단위 | CS/수동 처리 | `.scn` 자동화 권장, 리소스 여유 시 |
| **P2** | UX 저하지만 구매/서비스 가능 | 간접적 | 기능 정상 동작 | 수동 QA 유지, 자동화 불요 |

## 도메인별 분류 예시

### 주문 생성

| AC 항목 | 등급 | 사유 |
|---------|------|------|
| PDP에서 구매하기 → 주문서 진입 | P0 | 주문 퍼널 차단 |
| 장바구니 담기 → 장바구니 구매 | P0 | 주문 퍼널 차단 |
| 포인트 전액사용 결제 | P0 | 결제 실패 |
| 주문완료 페이지 노출 | P0 | 결제 성공 확인 불가 |
| 주문 동의 체크박스 | P1 | 결제 전 필수 단계 |
| 주문서 내 상품 정보 노출 | P2 | 정보 미노출이지만 결제 가능 |

### 주문 조회

| AC 항목 | 등급 | 사유 |
|---------|------|------|
| 주문목록 접근 및 조회 | P0 | 유저 주문 확인 불가 |
| 주문상세 진입 | P0 | 클레임 진입점 차단 |
| 배송 추적 조회 | P1 | CS 우회 가능 |
| 배송지연 안내 정보 | P2 | 정보 노출 관련 |

### 클레임 (취소/반품/교환)

| AC 항목 | 등급 | 사유 |
|---------|------|------|
| 취소 요청 제출 | P0 | 유저 취소 불가 시 CS 폭주 |
| 반품 요청 제출 | P0 | 유저 반품 불가 |
| 교환 요청 제출 | P1 | CS 수동 교환 처리 가능 |
| 클레임 사유 선택 | P1 | 제출 플로우 일부 |
| 교환 옵션 선택 (라디오/입력형) | P1 | 교환 플로우 일부 |
| 클레임 완료 화면 노출 | P2 | 결과 확인 관련 |
| 클레임 정보 조회 | P2 | 조회 관련 |

### 장바구니

| AC 항목 | 등급 | 사유 |
|---------|------|------|
| 장바구니 상품 목록 노출 | P0 | 구매 퍼널 차단 |
| 장바구니 선택 구매 | P0 | 구매 퍼널 차단 |
| 옵션변경 버튼 → 모달 노출 | P1 | 재담기로 우회 가능 |
| 옵션 변경 실행 및 반영 | P1 | 재담기로 우회 가능 |
| 옵션변경 토스트 팝업 | P2 | UX 피드백 |
| 모달 내 배송비/뱃지 정보 | P2 | 정보 노출 |
| 30일 경과 상품 옵션변경 미제공 | P2 | 엣지케이스 |

## 옵션변경 과제 (ORDER-11850) QA시트 분류 적용

| QA AC | 내용 | 등급 | 시나리오 |
|-------|------|------|----------|
| AC1 | 옵션변경 버튼 → 모달 노출 | P1 | `alpha_cart_option_change_basic.scn` |
| AC2 | 기존 옵션 프리셋 노출 | P1 | `alpha_cart_option_change_basic.scn` |
| AC3 | 수량/옵션 노출 | P1 | `alpha_cart_option_change_basic.scn` |
| AC4 | 수량 스텝퍼 제한 없음 | P1 | `alpha_cart_option_change_quantity.scn` |
| AC1(변경) | 옵션+수량 변경 가능 | P1 | `alpha_cart_option_change_execute.scn` |
| AC1-1 | 변경 전 버튼 비활성화 | P2 | `alpha_cart_option_change_basic.scn` |
| AC1-2 | 동일옵션 = 수량 추가 | P1 | `alpha_cart_option_change_quantity.scn` |
| AC1-3 | 변경하기 클릭 → 변경 | P1 | `alpha_cart_option_change_execute.scn` |
| AC2(변경) | 다른 옵션 추가 불가 | P2 | 수동 |
| AC3(변경) | 입력형 옵션 수정 | P1 | 상품 ID 확보 후 추가 |
| AC5 | 바로구매 → 변경하기 버튼 | P2 | `alpha_cart_option_change_basic.scn` |
| AC6 | 모달 내 정보 6항목 | P2 | `alpha_cart_option_change_modal_info.scn` |
| AC7 | 토스트 팝업 | P2 | `alpha_cart_option_change_execute.scn` |
| AC8 | 최대구매수량 밸리데이션 | P1 | ORDER-12669 해결 후 추가 |
| AC9 | 최소구매수량 없음 | P2 | `alpha_cart_option_change_quantity.scn` |
| 배송그룹 | 리프레시/이동 | P2 | `alpha_cart_option_change_execute.scn` |
| 가격 | 프로모션 반영 | P1 | `alpha_cart_option_change_execute.scn` |
| 단일옵션 | 얼럿 | P2 | `alpha_cart_option_change_single_option.scn` |
| 30일 | 옵션변경 미제공 | P2 | `alpha_cart_option_change_30day.scn` |

## 시나리오 태그 부여 방법

`.scn` 파일 헤더에 아래 태그를 추가:

```scn
# @title: 장바구니 옵션변경 — 기본 동작 검증
# @tier: regression
# @area: cart, option-change
# @task: ORDER-11850
# @priority: P1
# @lifecycle: active
```

## 태그 기반 실행

```bash
# P0 시나리오만 실행
python3 executor/execute_scenario.py --tag priority=P0 scenarios/zigzag/*.scn

# 특정 과제 시나리오만 실행
python3 executor/execute_scenario.py --tag task=ORDER-11850 scenarios/zigzag/*.scn

# 회귀용만 실행
python3 executor/execute_scenario.py --tag lifecycle=regression scenarios/zigzag/*.scn
```

## 라이프사이클 전환 규칙

```
과제 시작 ─→ @lifecycle: active
                │
과제 QA 완료 ─→ 회귀 가치 있음? ─→ @lifecycle: regression
                │
                └─ 회귀 가치 없음? ─→ @lifecycle: deprecated
                                        │
                            분기별 정리 ─→ 파일 삭제
```

---

*최초 작성: 2026-04-10*
