# /analyze-failure - 시나리오 실패 분석

## 목적
시나리오 실행 실패 시 로그, 스크린샷, 에러 메시지를 종합 분석하여 원인과 해결 방안을 제시한다.
수동으로 로그를 열고, 스크린샷을 찾고, 시나리오 파일을 대조하는 번거로움을 제거한다.

## 사용 시점
- 시나리오 실행이 실패했을 때
- 특정 라인에서 반복 실패하는 원인을 파악할 때
- 클레임(취소/반품/교환) 처리 실패의 근본 원인을 분석할 때

## 실행 방법

1. **실패 로그 식별**
   - $ARGUMENTS에 로그 파일명이 있으면 해당 파일 분석
   - 없으면 `logs/order-agent-exec_*.log` 중 가장 최근 파일에서 FAILED가 포함된 것을 찾는다

2. **로그에서 실패 정보 추출**
   - FAILED 라인의 line_no, 액션, 에러 메시지
   - 에러 직전/직후 컨텍스트 (전후 5줄)
   - AgentBrowserError의 stderr 내용

3. **관련 스크린샷 수집**
   - `failed_line_{line_no}_*.png` — 실패 시점 화면
   - `diag_*.png` — 동일 타임스탬프 진단 캡처
   - 스크린샷을 Read 도구로 읽어 시각적으로 분석

4. **원본 시나리오 대조**
   - 로그에서 실행된 .scn 파일 경로 추출
   - 실패한 라인 번호의 원본 커맨드 확인
   - 전후 커맨드의 흐름 분석

5. **실패 패턴 분류**
   - `Element not found` — 셀렉터 변경 또는 페이지 미로딩
   - `blocked by another element` — 오버레이/모달 가림
   - `timeout expired` — 페이지 로딩 지연
   - `execution context was destroyed` — 페이지 전환 경합
   - `reason_option_not_found` — 클레임 사유 UI 변경
   - `CANCEL/RETURN/EXCHANGE_REQUEST_STUCK` — 제출 후 페이지 미전환
   - `upstream error` / `502` — 서버 에러

6. **분석 결과 보고**
   - 실패 원인 요약
   - 해결 방안 제시 (셀렉터 수정, 대기 시간 조정, 시나리오 수정 등)
   - 필요 시 수정된 시나리오 라인 제안

## 예시
- `/analyze-failure` — 가장 최근 실패 분석
- `/analyze-failure order-agent-exec_20260306_214920.log` — 특정 로그 분석
- `/analyze-failure failed_line_18` — 18번 라인 실패만 분석
