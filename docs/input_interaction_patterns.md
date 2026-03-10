# 입력 인터랙션 패턴 가이드

> 지그재그 커머스 플랫폼의 클레임(교환/반품/취소) 플로우에서 발견되는 다양한 입력 UI 패턴과
> `execute_scenario.py` 자동화 처리 방식을 정리한 참조 문서입니다.

## 목차
1. [옵션 선택 패턴](#1-옵션-선택-패턴)
2. [사유 선택 패턴](#2-사유-선택-패턴)
3. [텍스트 입력 패턴](#3-텍스트-입력-패턴)
4. [체크박스/라디오 패턴](#4-체크박스라디오-패턴)
5. [결제 관련 패턴](#5-결제-관련-패턴)
6. [트러블슈팅](#6-트러블슈팅)

---

## 1. 옵션 선택 패턴

교환 시 새로운 옵션을 선택해야 하는 UI. 상품 유형에 따라 4가지 패턴이 존재합니다.

### 1-0. 단일 옵션 (옵션 선택 불필요)

| 항목 | 설명 |
|---|---|
| **적용 상품** | 옵션이 1개뿐인 상품 (Free 사이즈, 단일 색상 등) |
| **UI 구조** | "교환 옵션을 선택해 주세요" 트리거가 존재하지만 선택 가능한 옵션이 동일 1건 |
| **자동화 처리** | `_needs_option_selection()` → False → 옵션 선택 단계 전체 스킵 → 사유 선택/제출로 직행 |
| **교환비용** | 동일 옵션 교환이므로 교환비용 결제 시트가 발생하지 않을 수 있음 |
| **주의사항** | `detect_js`에서 입력형 옵션으로 오분류되지 않도록 `hasInput` 기반 판별 필수 — SVG div 개수만으로 판별 금지 |

### 1-1. 라디오 버튼형 (기본)

| 항목 | 설명 |
|---|---|
| **적용 상품** | 복수 옵션 상품 (색상만, 사이즈만 등) |
| **UI 구조** | 옵션 트리거 클릭 → 모달/바텀시트 → `[role="radio"]` 또는 `<input type="radio">` 목록 → "선택완료" 버튼 |
| **DOM 탐지** | `[role="dialog"]`, `dialog`, `[aria-modal="true"]` 내부 라디오 요소 |
| **자동화 처리** | `_open_option_modal_layered()` → `_pick_option_in_modal_layered()` → `_click_option_done_layered()` |
| **주의사항** | 품절(`품절`/`매진`) 옵션은 자동 스킵됨 |

### 1-2. 입력형 옵션 (Input-Type)

| 항목 | 설명 |
|---|---|
| **적용 상품** | 커스텀 텍스트 입력이 필요한 상품 (이니셜 각인, 문구 입력 등) |
| **UI 구조** | 옵션 트리거("교환 옵션을 선택해 주세요") 클릭 → **인라인 확장** → 텍스트 `<input>` + SVG chevron 드롭다운(색상/사이즈) → `.list-container` 목록 → "선택완료" 버튼 |
| **입력형 판별** | `input[type="text"]` placeholder에 "입력해주세요" 포함 (`hasInput=true` 필수). SVG 드롭다운 헤더 개수는 보조 정보 |
| **자동화 처리** | `_handle_input_type_option()`: (0) 옵션 피커 트리거 오픈 → (1) 텍스트 필드 채우기 → (2) 드롭다운 순차 열기/선택 → (3) 선택완료 |
| **옵션 피커 트리거** | "교환옵션을선택해주세요" 텍스트의 div (h=40~48, w=542). 클릭 시 색상/사이즈 드롭다운이 **인라인 확장**됨 |
| **토글 방지** | 피커가 이미 열려있으면(색상/사이즈 div 존재) 재클릭하지 않음 — 토글로 닫히는 것 방지 |
| **드롭다운 탐지 조건** | `<div>` + SVG 자식 + 텍스트 1~6자 + 너비>100px, 높이 30~80px + top>60px |
| **제외 필터** | 페이지 타이틀(`주문교환`, `주문반품` 등), 비옵션 영역(`배송메모`, `사유선택`, `사진첨부` 등) |
| **cascade 동작** | 색상 선택 → 사이즈 드롭다운 자동 열림 → 사이즈 선택 → cascade 종료 |
| **fallback** | `.list-container` 미출현 시 native `<select>` 요소 fallback 시도 |

### 1-3. 다단계 옵션 (Multi-Level)

| 항목 | 설명 |
|---|---|
| **적용 상품** | 색상 + 사이즈 등 2단계 이상 옵션이 있는 상품 |
| **UI 구조** | 모달 내 1차 옵션 선택 → 2차 옵션 자동 표시 → "선택완료" |
| **자동화 처리** | `_ensure_exchange_product_selected()` 내부 루프가 `max_option_levels=6`까지 반복 |
| **주의사항** | 각 레벨에서 `_needs_option_selection()` 재확인 후 진행 |

---

## 2. 사유 선택 패턴

### 2-1. 드롭다운 선택

| 항목 | 설명 |
|---|---|
| **UI 구조** | "사유를 선택해주세요" 드롭다운 → 사유 목록 → 선택 |
| **자동화 처리** | `_ensure_claim_reason_selected()` — 드롭다운 열기 → 첫 번째 유효 사유 선택 |
| **`__ASK__` 모드** | `SUBMIT_*_REQUEST "__ASK__"` 시 자동으로 첫 번째 사유 선택 |

### 2-2. 상세 사유 텍스트

| 항목 | 설명 |
|---|---|
| **UI 구조** | `<textarea>` placeholder "자세히 적어주시면..." |
| **자동화 처리** | `_fill_default_required_inputs("test")` — 빈 필수 입력 필드에 "test" 자동 입력 |

---

## 3. 텍스트 입력 패턴

| 패턴 | 탐지 기준 | 자동화 처리 |
|---|---|---|
| 필수 텍스트 입력 | placeholder에 "입력해주세요" 포함 | snapshot 노드에서 ref 찾아 `agent-browser fill @ref "test"` |
| 상세 사유 텍스트 | `<textarea>` 또는 `contenteditable` | `_fill_default_required_inputs()` |
| 옵션 커스텀 텍스트 | 입력형 옵션 모달 내 `<input type="text">` | `_handle_input_type_option()` 내부에서 처리 |

---

## 4. 체크박스/라디오 패턴

| 패턴 | UI 위치 | 자동화 처리 |
|---|---|---|
| 교환 안내사항 확인 | 페이지 하단 `<label>` + `<input type="checkbox">` | `check_notice_js` — label 클릭 → checked 확인 → fallback으로 직접 설정 |
| 수거 방법 선택 | `[role="radio"]` 또는 `<input type="radio">` | `pickup_select_js` — 첫 번째 활성 라디오 선택, fallback으로 "수거해주세요" 텍스트 클릭 |
| 옵션 항목 선택 | 모달 내 `[role="radio"]` / `[role="option"]` | `_pick_option_in_modal_layered()` |

---

## 5. 결제 관련 패턴

| 패턴 | 탐지 기준 | 자동화 처리 |
|---|---|---|
| 포인트 전액사용 | URL에 `/order-sheets/exchange` + "포인트 전액사용" 버튼 존재 | `_apply_full_points_on_exchange_cost_sheet()` |
| 0원 결제 | "0원 결제하기" 또는 "0원 구매하기" 텍스트 버튼 | URL 조건 분기 EVAL로 `/order-sheets/exchange`일 때만 클릭 |
| 추가비용 없는 교환 | SUBMIT 후 `/order-sheets/exchange`를 거치지 않음 | URL 분기로 결제 단계 전체 스킵 → 완료/주문상세 페이지로 직행 |
| 유료 결제 차단 | 결제 금액 > 0 + 포인트 부족 | `CLAIM_NOT_AVAILABLE` 리포트 후 안전 종결 |

---

## 6. 트러블슈팅

### 페이지 타이틀/비옵션 영역 오인식
- **증상**: 드롭다운 탐지가 "주문교환", "배송메모" 같은 비옵션 요소를 매칭
- **원인**: 타이틀 div에 뒤로가기 SVG, 배송메모에 chevron SVG가 있어 드롭다운 헤더 탐지 조건 충족
- **해결**: `excluded` 배열로 명시 제외 (`주문교환`, `배송메모`, `사유선택`, `사진첨부` 등) + `r.top < 60` 위치 필터

### 단일 옵션 상품의 입력형 오분류
- **증상**: 옵션 1개인 일반 상품이 `input_type:inputs=false,dropdowns=1`로 감지되어 입력형 경로 진입
- **원인**: `detect_js` 조건이 `hasInput || headers.length > 0`이라 SVG div 1개만 있어도 입력형으로 판별
- **해결**: 판별 조건을 `hasInput` 기반으로 변경 — 텍스트 입력 필드가 없으면 입력형이 아님

### 옵션 피커 토글로 인한 닫힘
- **증상**: 옵션 피커가 열렸다가 바로 닫힘 → 색상/사이즈 드롭다운을 찾지 못함
- **원인**: `_open_option_modal_layered()`가 먼저 피커를 열고, `_handle_input_type_option()` step 0이 다시 클릭하여 토글 닫힘
- **해결**: step 0에서 색상/사이즈 드롭다운 존재 여부를 먼저 확인 — 이미 열려있으면 클릭 스킵

### `.list-container` 미출현
- **증상**: 드롭다운 헤더 클릭 후 옵션 목록이 나타나지 않음
- **원인**: 잘못된 요소 클릭, 또는 다른 DOM 구조 사용
- **해결**: native `<select>` fallback, snapshot 기반 재탐색

### 옵션 선택 무한 루프
- **증상**: 같은 드롭다운을 반복 클릭하며 진전 없음
- **원인**: 제외 필터 미적용, 또는 선택 후 상태 변화 미감지
- **해결**: `_needs_option_selection()` 재확인으로 조기 탈출, `max_option_levels=6` 상한

### React 이벤트 미전달
- **증상**: DOM 클릭 이벤트가 React 상태를 업데이트하지 않음
- **원인**: React synthetic event 시스템과 native event 불일치
- **해결**: `PointerEvent` + `elementFromPoint` 패턴 사용 (`_ptr_click_js`)

---

## 관련 코드 참조

| 함수/변수 | 위치 | 역할 |
|---|---|---|
| `_handle_input_type_option()` | `execute_scenario.py` | 입력형 옵션 모달 처리 |
| `_ensure_exchange_product_selected()` | `execute_scenario.py` | 교환 옵션 선택 보장 (모든 유형) |
| `_open_option_modal_layered()` | `execute_scenario.py` | 옵션 모달 열기 (다단계 fallback) |
| `_pick_option_in_modal_layered()` | `execute_scenario.py` | 모달 내 옵션 항목 선택 |
| `_click_option_done_layered()` | `execute_scenario.py` | "선택완료" 버튼 클릭 |
| `_ensure_claim_reason_selected()` | `execute_scenario.py` | 클레임 사유 선택 |
| `_fill_default_required_inputs()` | `execute_scenario.py` | 필수 입력 필드 자동 채우기 |

---

*최종 업데이트: 2026-03-10*
