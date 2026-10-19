# A2A 환전 에이전트 (LangGraph) 한 바퀴 (카드 읽기 → 메시지 보내기 · 되묻기)

걸린 초: 13.7 · 상태: 완료 · 모델: google/gemma-4-26b-a4b-it

## 카드

| 이름 | 설명 | 판 | 주소 | 입력 | 출력 |
|---|---|---|---|---|---|
| Currency Agent | Helps with exchange rates for currencies | 1.0.0 | http://localhost:10000/ | text, text/plain | text, text/plain |

## 스킬

| id | 이름 | 설명 | 태그 | 예시 |
|---|---|---|---|---|
| convert_currency | Currency Exchange Rates Tool | Helps with exchange values between various currencies | currency conversion, currency exchange | What is exchange rate between USD and GBP? |

Capabilities: {'pushNotifications': True, 'streaming': True}

## 보낸 말

| 대화 | 보낸 말 | task_id | context_id | 작업 상태 차례 | 최종 답 | 걸린 초 |
|---|---|---|---|---|---|---|
| A | How much is 100 USD in KRW? | 088ff409 | 66bf5371 | submitted → working → working → completed | 100 USD is approximately 133,210 KRW. | 3.3 |
| B-1 | How much is 100 USD? | 28893fe7 | eb2e8b21 | submitted → input-required | To provide you with an accurate conversion, could you please let me know which currency you would like to convert the 100 USD into? | 3.2 |
| B-2 | KRW | 28893fe7 | eb2e8b21 | working → working → completed | 100 USD is approximately 133,210 KRW. | 3.6 |

## 도구가 돌려준 환율

서버 로그에서 도구가 부른 주소를 잡아 같은 주소를 한 번 더 부른 값이다.

| 대화 | 도구 주소 | 환율 | 날짜 |
|---|---|---|---|
| A | https://api.frankfurter.dev/v1/latest?from=USD&to=KRW | {'KRW': 1332.1} | 2026-10-16 |
| B-2 | https://api.frankfurter.dev/v1/latest?from=USD&to=KRW | {'KRW': 1332.1} | 2026-10-16 |

## 사람이 확인

| 사람이 확인 | 결과 |
|---|---|
| 대화 A 최종 답의 숫자가 도구가 돌려준 숫자(100 × 환율)와 같은가 | ○ (100 × 1332.1 = 133,210) |
| 대화 B 최종 답의 숫자가 도구가 돌려준 숫자(100 × 환율)와 같은가 | ○ (100 × 1332.1 = 133,210) |
