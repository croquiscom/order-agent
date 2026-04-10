# OrderAgent

CDP 기반 브라우저 에이전트 프레임워크.
시나리오(DSL)로 웹 브라우저를 제어하여 주문 E2E 테스트, SSO 로그인 등 브라우저 자동화를 수행한다.

---

## 빠른 시작

**Claude Code 사용자**

```
/setup
```

이후 `/list-scenarios`로 시나리오 목록 확인, `/run-scenario`로 실행.

새 시나리오를 추가할 때:

```
/scenario-guide          # 작성 규칙/체크리스트 확인
/new-scenario <설명>     # 가이드를 자동 참조하여 .scn 생성
/validate-scenario       # 문법/안전정책 검증
/run-scenario --dry-run  # 드라이런 후 실제 실행
```

**수동 설정**

```bash
./scripts/setup_env.sh
make doctor
make doctor-json
make doctor-strict
./scripts/doctor.sh
python3 executor/doctor.py --json
```

[수동 설정 가이드](docs/manual-setup-guide.md) 참조.

---

## 아키텍처

```
.scn (시나리오) → Parser → Executor → CDP → Chrome → Logs
```

```
order-agent/
├── core/          # 브라우저 제어 엔진
├── executor/      # 시나리오 실행/생성 엔진
├── scenarios/     # 시나리오 파일 (.scn)
├── scripts/       # 실행 스크립트
├── tests/         # 단위 테스트
├── logs/          # 실행 로그/스크린샷
└── docs/          # 참조 문서
```

---

## 시나리오 DSL

시나리오 파일(`.scn`)은 한 줄에 하나의 액션. 빈 줄과 `#` 주석은 무시된다.

### 기본 액션

| 액션 | 설명 |
|---|---|
| `NAVIGATE <url>` | URL 이동 |
| `CLICK <selector>` | 요소 클릭 |
| `FILL <selector> <value>` | 입력 필드에 값 입력 |
| `WAIT_FOR <selector\|ms>` | 요소 대기 또는 지연 |
| `CHECK <selector>` | 요소 존재 확인 |
| `PRESS <key>` | 키 입력 |
| `CHECK_URL <substring>` | URL 포함 여부 확인 |
| `CHECK_NOT_URL <substring>` | URL 미포함 확인 |
| `WAIT_URL <substring>` | URL 포함 대기 |
| `DUMP_STATE <tag>` | 상태 덤프 |
| `EVAL <javascript>` | JavaScript 실행 |
| `READ_OTP <account> [var]` | OTP 읽기 |
| `EXPECT_FAIL [pattern]` | 다음 액션 실패 예상 |

### 도메인 액션 (Zigzag)

| 액션 | 설명 |
|---|---|
| `ENSURE_LOGIN_ZIGZAG_ALPHA <url>` | alpha 로그인 확인/자동 로그인 |
| `CHECK_NEW_ORDER_SHEET` | 주문서 생성 확인 |
| `SAVE_ORDER_DETAIL_ID` | 주문상세 ID 저장 |
| `CHECK_ORDER_DETAIL_ID_CHANGED` | 주문상세 ID 변경 확인 |
| `SAVE_ORDER_NUMBER` | 주문번호 저장 |
| `CHECK_ORDER_NUMBER_CHANGED` | 주문번호 변경 확인 |
| `CLICK_SNAPSHOT_TEXT <text>` | 퍼지 텍스트 매칭 클릭 |
| `CLICK_PREV_CHECKBOX_FOR_SNAPSHOT_TEXT <text>` | 스냅샷 텍스트 앞 체크박스 클릭 |
| `SELECT_CART_ITEM_BY_TEXT <text>` | 장바구니 아이템 선택 |
| `CLICK_ORDER_DETAIL_BY_STATUS <status>` | 상태별 주문상세 진입 |
| `CLICK_ORDER_DETAIL_WITH_ACTION <action>` | 액션 가능한 주문상세 진입 |
| `APPLY_ORDER_STATUS_FILTER <status>` | 주문 상태 필터 적용 |
| `SUBMIT_CANCEL_REQUEST <reason>` | 취소 요청 |
| `SUBMIT_RETURN_REQUEST <reason>` | 반품 요청 |
| `SUBMIT_EXCHANGE_REQUEST <reason>` | 교환 요청 |
| `PRINT_ACTIVE_MODAL` | 현재 활성 모달 상태 출력 |
| `CHECK_PAYMENT_RESULT` | 결제 결과 검증 |

### 변수 치환

`--var key=value`로 주입한 값을 `{{key}}`로 참조한다.

```
FILL input[name=orderNumber] {{order_number}}
```

### 안전 정책

- 기본 테스트 도메인은 `https://alpha.zigzag.kr/`
- `CLICK confirm_payment`는 기본 차단된다
- 실제 결제는 허용하지 않으며, 예외는 명시적 승인과 `ALLOW_REAL_PAYMENT=1`이 있을 때만 가능하다
- 시나리오 작성 전 [`docs/input_interaction_patterns.md`](docs/input_interaction_patterns.md), [`docs/exchange_stabilization_plan.md`](docs/exchange_stabilization_plan.md) 확인을 권장한다

---

## 시나리오 커버리지 맵

시나리오 추가/변경 시 커버리지 현황을 자동 생성할 수 있다.

```bash
make map           # 터미널 리포트 (카테고리, 티어, 영역, 액션 커버리지)
make map-gaps      # 미커버 액션만 표시
make map-update    # docs/order_flow_map.md 자동 갱신
make map-json      # CI 연동용 JSON 출력
```

전체 플로우 맵과 커버리지 매트릭스는 [`docs/order_flow_map.md`](docs/order_flow_map.md) 참조.

---

## 참조 문서

| 문서 | 설명 |
|---|---|
| [`docs/cli-reference.md`](docs/cli-reference.md) | CLI 옵션, 환경변수, 트러블슈팅 |
| [`docs/manual-setup-guide.md`](docs/manual-setup-guide.md) | 수동 설정 가이드 |
| [`docs/order_flow_map.md`](docs/order_flow_map.md) | 주문 플로우 맵 + 커버리지 매트릭스 (자동 생성) |
| [`docs/scenarios.md`](docs/scenarios.md) | 시나리오 인벤토리 |
| [`docs/input_interaction_patterns.md`](docs/input_interaction_patterns.md) | 클레임 UI 입력 패턴 |
| [`.claude/skills/scenario-guide/SKILL.md`](.claude/skills/scenario-guide/SKILL.md) | 시나리오 작성 가이드 및 체크리스트 |
