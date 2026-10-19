# A2A Hello World 한 바퀴 (카드 읽기 → 메시지 보내기)

걸린 초: 1.0 · 상태: 완료

## 카드 주소

| 카드 주소 | 상태 코드 |
|---|---|
| /.well-known/agent.json | 200 |
| /.well-known/agent-card.json | 200 |

## 카드

| 이름 | 설명 | 판 | 주소 | 입력 | 출력 |
|---|---|---|---|---|---|
| Hello World Agent | Just a hello world agent | 1.0.0 | http://localhost:9999/ | text | text |

## 스킬

| id | 이름 | 설명 | 태그 | 예시 |
|---|---|---|---|---|
| hello_world | Returns hello world | just returns hello world | hello world | hi, hello world |

Capabilities: {'streaming': True}

## 메시지

| 보낸 말 | 답 종류(kind) | 답 글 | 걸린 초 |
|---|---|---|---|
| hi | message | Hello World | 1.0 |

## 사람이 확인

| 사람이 확인 | 결과 |
|---|---|
| 카드만 보고 이 에이전트가 무엇을 하는지 말할 수 있나 | ○ (스킬 「Returns hello world」 · 예시 hi 로 무엇을 하는지 보인다) |
