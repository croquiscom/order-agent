# Exchange Stabilization Plan

교환 시나리오 안정화 실행 항목(우선순위 순).

## 1) 환경 안정화 (P0)
- 목표: `request-exchange` 화면에서 정적 리소스/청크 로딩 실패 제거
- 완료조건:
- 동일 계정/동일 주문 기준 5회 연속 실행 시 `Loading chunk ... failed` 미발생
- `EXCHANGE_UI_CHUNK_LOAD` 0건

## 2) 옵션 선택 트랜잭션 고정 (P0)
- 목표: `선택영역 활성화 -> 옵션선택 -> 선택완료 -> 미선택문구 소거`를 단일 트랜잭션으로 보장
- 완료조건:
- `SUBMIT_EXCHANGE_REQUEST` 단계에서 `옵션을선택해주세요` 잔류 0건
- 실패 시 반드시 `EXCHANGE_OPTION_SELECTION_REQUIRED`로 분류

## 3) 탐색 전략 계층화 (P1)
- 목표: 취약한 텍스트 클릭 의존도 축소
- 전략: `data-testid`(가능 시) > role/name > snapshot ref > text fallback
- 완료조건:
- 옵션 선택 관련 클릭 성공률 95% 이상(최근 20회 기준)

## 4) 상태기반 게이팅 강화 (P1)
- 목표: 클릭 성공이 아니라 상태 전이로 성공 판정
- 완료조건:
- 교환 요청 성공은 `/request-exchange` 이탈 + 교환상태 텍스트 확인 동시 충족

## 5) 자동 복구 정책 (P1)
- 목표: 환경/DOM 흔들림 시 재시도 체계 일원화
- 완료조건:
- chunk 오류 감지 시 `request-exchange` 재오픈 후 재시도
- 재시도 초과 시 실패코드 고정(`EXCHANGE_UI_CHUNK_LOAD`/`EXCHANGE_REQUEST_STUCK`)

## 6) 증적 표준화 (P1)
- 목표: 실패 원인 확인 시간을 단축
- 완료조건:
- 실패 시 항상 `screenshot + snapshot + errors + console` 보존
- 옵션 클릭 전/후 증적 2세트 자동 남김

## 7) 시나리오 운영 규칙 (P2)
- 목표: 환경차단과 기능실패를 분리 집계
- 완료조건:
- 리포트에 `failed`/`blocked` 구분
- `EXCHANGE_UI_CHUNK_LOAD`는 blocked로 집계
