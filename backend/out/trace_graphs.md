# 3-1 그래프 Langfuse trace (도구 셋 · 고르는 칸)

모델: google/gemma-4-26b-a4b-it · 실행: 2026-10-19 07:31:35 · 고르는 칸 되풀이 한도: 10

태그: 모든 trace 에 `3-1-graph` · 그래프 이름 · 모델 이름

마지막 칸은 Langfuse 화면에서 읽어 사람이 채운다.

| 그래프 | 질문 | 고른 도구(일꾼) 차례 | 2-5 표 차례 | 전체 걸린 초 | 보낸 횟수 | 상태 | trace 이름 | trace 주소 | trace 줄 차례가 표 차례와 같은가 |
|---|---|---|---|---|---|---|---|---|---|
| tool_graph | 내 등급이랑 주문정보 알려줘 | get_grade_info → get_order_info | get_grade_info → get_order_info | 2.5 | 1 | 완료 | tool_graph | https://cloud.langfuse.com/project/cmcyjzieu011fad07chd0ow4c/traces/5f53a6abe56ad1eca50fa642793506b4 | ○(tools 줄 안에 get_grade_info · get_order_info 차례) |
| supervisor_graph | 뉴욕주와 캘리포니아주의 최신 GDP를 검색해서 찾아줘. 그다음 두 값의 평균은 coder 가 파이썬 코드를 실행해서 계산해줘 | researcher → researcher → FINISH | — | 20.1 | 1 | 완료 | supervisor_graph | https://cloud.langfuse.com/project/cmcyjzieu011fad07chd0ow4c/traces/2c62f9a07a41a03ec6e842940cbba368 | ○(supervisor → researcher → supervisor → researcher → supervisor, 첫 researcher 안에 tavily_search 네 번) |

보낸 횟수 합(Tracing 목록에 뜰 trace 수): 2
