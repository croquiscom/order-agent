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

교환 시 새로운 옵션을 선택해야 하는 UI. 상품 유형에 따라 3가지 패턴이 존재합니다.

### 1-1. 라디오 버튼형 (기본)

| 항목 | 설명 |
|---|---|
| **적용 상품** | 단일 옵션 상품 (색상만, 사이즈만 등) |
| **UI 구조** | 옵션 트리거 클릭 → 모달/바텀시트 → `[role="radio"]` 또는 `<input type="radio">` 목록 → "선택완료" 버튼 |
| **DOM 탐지** | `[role="dialog"]`, `dialog`, `[aria-modal="true"]` 내부 라디오 요소 |
| **자동화 처리** | `_open_option_modal_layered()` → `_pick_option_in_modal_layered()` → `_click_option_done_layered()` |
| **주의사항** | 품절(`품절`/`매진`) 옵션은 자동 스킵됨 |

### 1-2. 입력형 옵션 (Input-Type)

| 항목 | 설명 |
|---|---|
| **적용 상품** | 커스텀 텍스트 입력이 필요한 상품 (이니셜 각인, 문구 입력 등) |
| **UI 구조** | 옵션 트리거 클릭 → 인라인/모달 확장 → 텍스트 `<input>` + SVG chevron 드롭다운(색상/사이즈) → `.list-container` 목록 → "선택완료" 버튼 |
| **DOM 탐지** | `input[type="text"]` placeholder에 "입력해주세요" 포함, 또는 SVG chevron을 가진 짧은 텍스트 div 헤더 |
| **자동화 처리** | `_handle_input_type_option()` — 텍스트 필드 채우기 → 드롭다운 순차 열기/선택 → 선택완료 |
| **드롭다운 탐지 조건** | `<div>` + SVG 자식 + 텍스트 1~6자 + 너비>100px, 높이 30~80px |
| **제외 필터** | 페이지 타이틀(`주문교환`, `주문반품` 등), 상단 60px 이내 요소, 이미 열린 드롭다운(`.list-container` 형제 존재) |
| **cascade 동작** | 색상 선택 → 사이즈 드롭다운 자동 열림 → 사이즈 선택 → cascade 종료 |
| **fallback** | `.list-container` 미출현 시 native `<select>` 요소 fallback 시도 |
| **주의사항** | 페이지 타이틀과 드롭다운 헤더의 DOM 구조가 유사하므로 제외 필터가 핵심 |

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
| 0원 결제 | "0원 결제하기" 또는 "0원 구매하기" 텍스트 버튼 | 시나리오에서 `CLICK "text=0원 결제하기"` |
| 유료 결제 차단 | 결제 금액 > 0 + 포인트 부족 | `CLAIM_NOT_AVAILABLE` 리포트 후 안전 종결 |

---

## 6. 트러블슈팅

### 페이지 타이틀 오인식
- **증상**: 드롭다운 탐지가 "주문교환" 같은 페이지 타이틀을 매칭
- **원인**: 타이틀 div에 뒤로가기 SVG 아이콘이 있어 드롭다운 헤더 탐지 조건 충족
- **해결**: `pageTitles` 배열로 명시 제외 + `r.top < 60` 위치 필터

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
