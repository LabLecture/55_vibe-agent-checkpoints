# 모델 견주기: 대본 세 턴 한 묶음씩

모델: 확정 google/gemma-4-26b-a4b-it · 예비 nvidia/nemotron-3-super-120b-a12b:free · 셋째 후보 dots-studio/dots-3-note-preview:free

모델마다 새 프로세스(LLM_MODEL 만 다름)로 동시에 돌렸다 · 걸음 한도 5 · 턴 한도 180초 · 다시 보내기 없음

턴 2 · 3 의 앞 챗봇 말은 대본 글이 아니라 그 모델이 앞 턴에 낸 답이다. 확정 모델을 화면에서 돌린 표는 섹션 3-7(backend/out/chat_run.md)

판정: 턴 1 은 도구 시작 줄 없이 답이 있으면 O · 턴 2 는 user_class_tool 시작 줄이 있으면 O · 턴 3 은 class_progress_tool 시작 줄이 있고 답에 대본 턴 3 의 지난달 · 이번달 단원 글이 있으면 O · 그 밖 X

## 요약

진도까지 = 턴 3 O. 초는 실제로 돈 턴만 셈(건너뜀 0.0초는 뺌, 오류 난 턴의 초는 넣음). 같은 확정 모델도 서버만 불렀을 때 턴 3 이 판마다 갈렸다(섹션 3-7 backend/out/chat_api.md)

| 모델 | 돌린 묶음 | 턴 2 O | 턴 3 O (진도까지) | 턴 1 가운데 초 | 턴 2 가운데 초 | 턴 3 가운데 초 | 가장 오래 걸린 초 | 끊기거나 오류 난 턴 |
|---|---|---|---|---|---|---|---|---|
| google/gemma-4-26b-a4b-it | 3 | 3/3 | 2/3 | 4.2 | 6.6 | 5.9 | 10.8 | 0 (건너뜀 0) |
| nvidia/nemotron-3-super-120b-a12b:free | 3 | 0/3 | 0/3 | 0.4 | - | - | 0.6 | 3 (건너뜀 6) |
| dots-studio/dots-3-note-preview:free | 1 | 0/1 | 0/1 | 21.6 | 11.0 | - | 21.6 | 1 (건너뜀 1) |

## 사람이 채울 칸

| 확인 | 결과 |
|---|---|
| 턴 3 X 판 하나의 답이 진도를 지어냈는가 (묶음 · 모델 적기) | 묶음 1 확정 모델: 진도를 지어내지 않았다 (supervisor 가 user_class 를 고르고 진도 도구 시작 줄 없이 「먼저 정확한 수업 정보를 다시 한번 조회해야 합니다 … 잠시만 기다려 주시면」) |
| 이 챗봇에 쓸 모델과 까닭 한 줄 | 확정 모델을 그대로 쓴다 (예비는 세 판 모두 404 로 첫 칸도 못 돌았고, 셋째 후보는 턴 2 에서 supervisor 가 next 를 내지 못해 멈췄다. 확정도 턴 3 은 2/3 이라 화면에서는 「1」 한 번 더가 필요할 수 있다) |

## 묶음별 표

| 묶음 | 모델 | 턴 | 고객 말 | 지나간 칸 | 도구 시작 줄 | 답 앞 80자 | 걸린 초 | 판정 |
|---|---|---|---|---|---|---|---|---|
| 1 | google/gemma-4-26b-a4b-it | 1 | 초등학교 딸 수업진도를 체크할 수 있나요? | coordinator → planner → supervisor → user_class | (없음) | 네, 물론이죠! 자녀분의 수업 진도를 확인해 드릴 수 있습니다.  자녀분의 수업 정보를 확인하려면 아래 정보를 알려주세요: - 이름 - 학교 - | 4.2 | O |
| 1 | google/gemma-4-26b-a4b-it | 2 | 쌍문초등학교 6학년 송혜교 | coordinator → planner → supervisor → user_class | user_class_tool_start_user_name: 송혜교, user_school: 쌍문초등학교, user_grade: 6 | 송혜교님은 총 3개의 수업을 듣고 있어요:  1. AI수학 프로그램 2. 창의STEAM 수업 3. 슬기로운 생활  어떤 수업의 진도를 확인해 드 | 5.8 | O |
| 1 | google/gemma-4-26b-a4b-it | 3 | 1 | coordinator → planner → supervisor → user_class | (없음) | 죄송합니다. 수업의 상세 진도를 확인하기 위해서는 먼저 정확한 수업 정보를 다시 한번 조회해야 합니다.  잠시만 기다려 주시면, 송혜교 학생의  | 6.4 | X |
| 1 | nvidia/nemotron-3-super-120b-a12b:free | 1 | 초등학교 딸 수업진도를 체크할 수 있나요? | - | (없음) | (답 없음) | 0.6 | X |
| 1 | nvidia/nemotron-3-super-120b-a12b:free | 2 | 쌍문초등학교 6학년 송혜교 | - | (없음) | (답 없음) | 0.0 | X |
| 1 | nvidia/nemotron-3-super-120b-a12b:free | 3 | 1 | - | (없음) | (답 없음) | 0.0 | X |
| 1 | dots-studio/dots-3-note-preview:free | 1 | 초등학교 딸 수업진도를 체크할 수 있나요? | coordinator → planner → supervisor → user_class | (없음) |   안녕하세요! 학습지 챗봇입니다.   자녀의 수업 진도를 확인해 드리고 싶으시군요? 😊  그런데 확인을 위해 아래 정보가 필요해요: - 자녀의 | 21.6 | O |
| 1 | dots-studio/dots-3-note-preview:free | 2 | 쌍문초등학교 6학년 송혜교 | coordinator → planner | (없음) | (답 없음) | 11.0 | X |
| 1 | dots-studio/dots-3-note-preview:free | 3 | 1 | - | (없음) | (답 없음) | 0.0 | X |
| 2 | google/gemma-4-26b-a4b-it | 1 | 초등학교 딸 수업진도를 체크할 수 있나요? | coordinator → planner → supervisor → user_class | (없음) | 네, 물론이죠! 자녀분의 수업 진도를 확인해 드릴 수 있습니다.  다만, 정확한 정보를 찾기 위해서는 자녀분의 정보가 필요해요. 아래 정보를 알 | 10.8 | O |
| 2 | google/gemma-4-26b-a4b-it | 2 | 쌍문초등학교 6학년 송혜교 | coordinator → planner → supervisor → user_class | user_class_tool_start_user_name: 송혜교, user_school: 쌍문초등학교, user_grade: 6 | 송혜교님은 총 3개의 수업을 듣고 있어요:  1. AI수학 프로그램 2. 창의STEAM 수업 3. 슬기로운 생활  어떤 수업의 진도를 확인할까요 | 7.6 | O |
| 2 | google/gemma-4-26b-a4b-it | 3 | 1 | coordinator → planner → supervisor → class_progress | class_progress_tool_start_user_name: 송혜교, class_data: AI수학 프로그램, class_id: 1 | 네, 송혜교 학생의 수업 진도를 확인해 드릴게요.  송혜교 학생은 AI수학 프로그램 수업에서 지난달엔 나눗셈/원을 마쳤고, 이번달엔 분수/들이와 | 5.6 | O |
| 2 | nvidia/nemotron-3-super-120b-a12b:free | 1 | 초등학교 딸 수업진도를 체크할 수 있나요? | - | (없음) | (답 없음) | 0.4 | X |
| 2 | nvidia/nemotron-3-super-120b-a12b:free | 2 | 쌍문초등학교 6학년 송혜교 | - | (없음) | (답 없음) | 0.0 | X |
| 2 | nvidia/nemotron-3-super-120b-a12b:free | 3 | 1 | - | (없음) | (답 없음) | 0.0 | X |
| 3 | google/gemma-4-26b-a4b-it | 1 | 초등학교 딸 수업진도를 체크할 수 있나요? | coordinator → planner → supervisor → user_class | (없음) | 안녕하세요! 자녀분의 수업 진도를 확인해 드릴 수 있습니다. 😊  자녀분의 수업 정보를 정확하게 확인하기 위해 아래 정보를 알려주세요:  - 이 | 3.5 | O |
| 3 | google/gemma-4-26b-a4b-it | 2 | 쌍문초등학교 6학년 송혜교 | coordinator → planner → supervisor → user_class | user_class_tool_start_user_name: 송혜교, user_school: 쌍문초등학교, user_grade: 6 | 송혜교님은 총 3개의 수업을 듣고 있어요:  1. AI수학 프로그램 2. 창의STEAM 수업 3. 슬기로운 생활  어떤 수업의 진도를 확인해 드 | 6.6 | O |
| 3 | google/gemma-4-26b-a4b-it | 3 | 1 | coordinator → planner → supervisor → class_progress | class_progress_tool_start_user_name: 송혜교, class_data: AI수학 프로그램, class_id: 1 | 네. 고객님 자녀분 송혜교님은 AI수학 프로그램 수업에서 지난달엔 나눗셈/원 단원을 마쳤고, 이번달엔 분수/들이와무게 에서 [H6] 4.분수(2 | 5.9 | O |
| 3 | nvidia/nemotron-3-super-120b-a12b:free | 1 | 초등학교 딸 수업진도를 체크할 수 있나요? | - | (없음) | (답 없음) | 0.2 | X |
| 3 | nvidia/nemotron-3-super-120b-a12b:free | 2 | 쌍문초등학교 6학년 송혜교 | - | (없음) | (답 없음) | 0.0 | X |
| 3 | nvidia/nemotron-3-super-120b-a12b:free | 3 | 1 | - | (없음) | (답 없음) | 0.0 | X |

## 상태 원문 (완료가 아닌 턴)

- nvidia/nemotron-3-super-120b-a12b:free · 턴 1: 오류: OpenAIModelNotFoundError('Error code: 404 - {\'error\': {\'message\': \'Provider returned error\', \'code\': 404, \'metadata\': {\'raw\': \'{"status":404,"title":"Not Found","detail":"Function \\\'****\\\': Not found for account \\\'****\\\'"}\', \'provider_name\': \'Nvidia\', \'is_byok\': False}}, \'user_id\': \'****\'}')
- nvidia/nemotron-3-super-120b-a12b:free · 턴 2: 건너뜀: 턴 1 답 없음
- nvidia/nemotron-3-super-120b-a12b:free · 턴 3: 건너뜀: 턴 2 답 없음
- dots-studio/dots-3-note-preview:free · 턴 2: 오류: KeyError('next')
- dots-studio/dots-3-note-preview:free · 턴 3: 건너뜀: 턴 2 답 없음
- 묶음 2 · nvidia/nemotron-3-super-120b-a12b:free · 턴 1: 오류: OpenAIModelNotFoundError('Error code: 404 - {\'error\': {\'message\': \'Provider returned error\', \'code\': 404, \'metadata\': {\'raw\': \'{"status":404,"title":"Not Found","detail":"Function \\\'****\\\': Not found for account \\\'****\\\'"}\', \'provider_name\': \'Nvidia\', \'is_byok\': False}}, \'user_id\': \'****\'}')
- 묶음 2 · nvidia/nemotron-3-super-120b-a12b:free · 턴 2: 건너뜀: 턴 1 답 없음
- 묶음 2 · nvidia/nemotron-3-super-120b-a12b:free · 턴 3: 건너뜀: 턴 2 답 없음
- 묶음 3 · nvidia/nemotron-3-super-120b-a12b:free · 턴 1: 오류: OpenAIModelNotFoundError('Error code: 404 - {\'error\': {\'message\': \'Provider returned error\', \'code\': 404, \'metadata\': {\'raw\': \'{"status":404,"title":"Not Found","detail":"Function \\\'****\\\': Not found for account \\\'****\\\'"}\', \'provider_name\': \'Nvidia\', \'is_byok\': False}}, \'user_id\': \'****\'}')
- 묶음 3 · nvidia/nemotron-3-super-120b-a12b:free · 턴 2: 건너뜀: 턴 1 답 없음
- 묶음 3 · nvidia/nemotron-3-super-120b-a12b:free · 턴 3: 건너뜀: 턴 2 답 없음

## 답 전문

### google/gemma-4-26b-a4b-it · 턴 1

~~~text
네, 물론이죠! 자녀분의 수업 진도를 확인해 드릴 수 있습니다.

자녀분의 수업 정보를 확인하려면 아래 정보를 알려주세요:
- 이름
- 학교
- 학년

알려주시면 바로 확인해서 도와드릴게요!
~~~

### google/gemma-4-26b-a4b-it · 턴 2

~~~text
송혜교님은 총 3개의 수업을 듣고 있어요:

1. AI수학 프로그램
2. 창의STEAM 수업
3. 슬기로운 생활

어떤 수업의 진도를 확인해 드릴까요?
~~~

### google/gemma-4-26b-a4b-it · 턴 3

~~~text
죄송합니다. 수업의 상세 진도를 확인하기 위해서는 먼저 정확한 수업 정보를 다시 한번 조회해야 합니다.

잠시만 기다려 주시면, 송혜교 학생의 **AI수학 프로그램** 진도를 바로 확인해 드릴게요!
~~~

### nvidia/nemotron-3-super-120b-a12b:free · 턴 1

~~~text
(답 없음)
~~~

### nvidia/nemotron-3-super-120b-a12b:free · 턴 2

~~~text
(답 없음)
~~~

### nvidia/nemotron-3-super-120b-a12b:free · 턴 3

~~~text
(답 없음)
~~~

### dots-studio/dots-3-note-preview:free · 턴 1

~~~text


안녕하세요! 학습지 챗봇입니다. 

자녀의 수업 진도를 확인해 드리고 싶으시군요? 😊

그런데 확인을 위해 아래 정보가 필요해요:
- 자녀의 **이름**
- **학교** 이름
- **학년**

구체적인 정보를 알려주시면 바로 수업 정보를 조회해 드릴게요!
~~~

### dots-studio/dots-3-note-preview:free · 턴 2

~~~text
(답 없음)
~~~

### dots-studio/dots-3-note-preview:free · 턴 3

~~~text
(답 없음)
~~~
### 묶음 2 · google/gemma-4-26b-a4b-it · 턴 1

~~~text
네, 물론이죠! 자녀분의 수업 진도를 확인해 드릴 수 있습니다.

다만, 정확한 정보를 찾기 위해서는 자녀분의 정보가 필요해요. 아래 정보를 알려주시면 바로 확인해 드릴게요!

자녀분의 수업 정보를 확인하려면 아래 정보를 알려주세요:
- 이름
- 학교
- 학년

알려주시면 바로 도와드릴게요!
~~~

### 묶음 2 · google/gemma-4-26b-a4b-it · 턴 2

~~~text
송혜교님은 총 3개의 수업을 듣고 있어요:

1. AI수학 프로그램
2. 창의STEAM 수업
3. 슬기로운 생활

어떤 수업의 진도를 확인할까요?
~~~

### 묶음 2 · google/gemma-4-26b-a4b-it · 턴 3

~~~text
네, 송혜교 학생의 수업 진도를 확인해 드릴게요.

송혜교 학생은 AI수학 프로그램 수업에서 지난달엔 나눗셈/원을 마쳤고, 이번달엔 분수/들이와무게 에서 [H6] 4.분수(2) 단원을 진행하고 있습니다.

최근 한달간 학습한 내용에 대해 AI가 분석하여 개인별 맞춤 결과를 제공하는데, 해당 페이지 링크를 제공해 드릴까요?
~~~

### 묶음 2 · nvidia/nemotron-3-super-120b-a12b:free · 턴 1

~~~text
(답 없음)
~~~

### 묶음 2 · nvidia/nemotron-3-super-120b-a12b:free · 턴 2

~~~text
(답 없음)
~~~

### 묶음 2 · nvidia/nemotron-3-super-120b-a12b:free · 턴 3

~~~text
(답 없음)
~~~

### 묶음 3 · google/gemma-4-26b-a4b-it · 턴 1

~~~text
안녕하세요! 자녀분의 수업 진도를 확인해 드릴 수 있습니다. 😊

자녀분의 수업 정보를 정확하게 확인하기 위해 아래 정보를 알려주세요:

- 이름
- 학교
- 학년

알려주시면 바로 확인해서 도와드릴게요!
~~~

### 묶음 3 · google/gemma-4-26b-a4b-it · 턴 2

~~~text
송혜교님은 총 3개의 수업을 듣고 있어요:

1. AI수학 프로그램
2. 창의STEAM 수업
3. 슬기로운 생활

어떤 수업의 진도를 확인해 드릴까요?
~~~

### 묶음 3 · google/gemma-4-26b-a4b-it · 턴 3

~~~text
네. 고객님 자녀분 송혜교님은 AI수학 프로그램 수업에서 지난달엔 나눗셈/원 단원을 마쳤고, 이번달엔 분수/들이와무게 에서 [H6] 4.분수(2) 단원을 진행하고 있습니다.

최근 한달간 학습한 내용에 대해 AI가 분석하여 개인별 맞춤 결과를 제공하는데, 해당 페이지 링크를 제공해 드릴까요?
~~~

### 묶음 3 · nvidia/nemotron-3-super-120b-a12b:free · 턴 1

~~~text
(답 없음)
~~~

### 묶음 3 · nvidia/nemotron-3-super-120b-a12b:free · 턴 2

~~~text
(답 없음)
~~~

### 묶음 3 · nvidia/nemotron-3-super-120b-a12b:free · 턴 3

~~~text
(답 없음)
~~~
