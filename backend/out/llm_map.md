# 모델 표 확인

| 칸 | 종류 |
|---|---|
| coordinator | basic |
| planner | basic |
| supervisor | supervisor |
| user_class | basic |
| class_progress | basic |

| 종류 | 질문 | 답 | 걸린 초 |
|---|---|---|---|
| basic | 안녕 | 안녕하세요! 반가워요. 무엇을 도와드릴까요? :) | 1.3 |

| 확인 | 결과 |
|---|---|
| get_llm_by_type("basic") 두 번이 같은 물건 | True |
