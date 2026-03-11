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

**수동 설정**

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
| `ENSURE_LOGIN_ALPHA` | alpha 로그인 확인/자동 로그인 |
| `CHECK_NEW_ORDER_SHEET` | 주문서 생성 확인 |
| `CLICK_SNAPSHOT_TEXT <text>` | 퍼지 텍스트 매칭 클릭 |
| `SUBMIT_CANCEL_REQUEST <reason>` | 취소 요청 |
| `SUBMIT_RETURN_REQUEST <reason>` | 반품 요청 |
| `SUBMIT_EXCHANGE_REQUEST <reason>` | 교환 요청 |

### 변수 치환

`--var key=value`로 주입한 값을 `{{key}}`로 참조한다.

```
FILL input[name=orderNumber] {{order_number}}
```

---

## 참조 문서

| 문서 | 설명 |
|---|---|
| [`docs/cli-reference.md`](docs/cli-reference.md) | CLI 옵션, 환경변수, 트러블슈팅 |
| [`docs/manual-setup-guide.md`](docs/manual-setup-guide.md) | 수동 설정 가이드 |
| [`docs/scenarios.md`](docs/scenarios.md) | 시나리오 인벤토리 |
| [`docs/input_interaction_patterns.md`](docs/input_interaction_patterns.md) | 클레임 UI 입력 패턴 |
