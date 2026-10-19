# 3-1 RAG 체인 Langfuse trace (질문 3 × 모델 2)

확정 모델: google/gemma-4-26b-a4b-it · 예비 모델: nvidia/nemotron-3-super-120b-a12b:free · 실행: 2026-10-19 07:23:21

태그: 모든 trace 에 `3-1-rag` · 모델 이름 · 질문 번호(q1~q3)

## 질문

1. 교재는 언제 배송되나요?
2. 아이 공부가 어디까지 됐나요?
3. 내일 서울 날씨는 어때요?

## 결과 (모델 × 질문)

뒤 네 칸은 Langfuse 화면에서 읽어 사람이 채운다.

| 칸 | 모델 | 질문 | 전체 걸린 초 | 보낸 횟수 | 답 앞부분 | trace 이름 | trace 주소 | 모델 줄 초 | 문서 찾기 줄 초 | 들어간 토큰 | 나온 토큰 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | google/gemma-4-26b-a4b-it | 1. 교재는 언제 배송되나요? | 2.1 | 1 | 다음 달 교재는 매달 마지막 주 월요일에 발송됩니다. 보통 이틀 안에 도착하며, 도서 산간 지역은 하루에서 이틀 더 걸릴 수 있습니다. | rag-gemma-4-26b-a4b-it-q1 | https://cloud.langfuse.com/project/cmcyjzieu011fad07chd0ow4c/traces/e14e955e7405446f1cf5d3557d04bf35 |  |  |  |  |
| 2 | google/gemma-4-26b-a4b-it | 2. 아이 공부가 어디까지 됐나요? | 8.3 | 1 | 학부모 앱 「우리 아이」 화면에서는 아이별로 듣고 있는 과목, 이번 주 학습량, 과목별 진도가 한 화면에 나옵니다. 과목 이름을 누르면 단원 목 | rag-gemma-4-26b-a4b-it-q2 | https://cloud.langfuse.com/project/cmcyjzieu011fad07chd0ow4c/traces/4afa318d7bc75b112c2e034cb4d5ea1b | 8.23 | 0.03 | 819 | 80 |
| 3 | google/gemma-4-26b-a4b-it | 3. 내일 서울 날씨는 어때요? | 1.2 | 1 | 죄송합니다. 해당 질문에 대해서는 답변을 할 수 없습니다. 다른 질문을 해주세요. | rag-gemma-4-26b-a4b-it-q3 | https://cloud.langfuse.com/project/cmcyjzieu011fad07chd0ow4c/traces/b0639ab90c3ce32523dd738f10f27e00 |  |  |  |  |
| 4 | nvidia/nemotron-3-super-120b-a12b:free | 1. 교재는 언제 배송되나요? | 3.0 | 1 | 다음 달 교재는 매달 마지막 주 월요일에 발송됩니다. 보통 이틀 안에 도착하며, 도서·산간 지역은 하루에서 이틀 더 걸릴 수 있습니다. | rag-nemotron-3-super-120b-a12b-q1 | https://cloud.langfuse.com/project/cmcyjzieu011fad07chd0ow4c/traces/5e8a75f593bcf48c700ae075c465903e |  |  |  |  |
| 5 | nvidia/nemotron-3-super-120b-a12b:free | 2. 아이 공부가 어디까지 됐나요? | 23.9 | 1 | 학부모 앱 「우리 아이」 화면에서 아이의 학습 현황을 확인할 수 있습니다. 과목 이름을 누르면 단원 목록이 펼쳐지며, 끝낸 단원은 초록색, 지금 | rag-nemotron-3-super-120b-a12b-q2 | https://cloud.langfuse.com/project/cmcyjzieu011fad07chd0ow4c/traces/78a832770b30a7fbe3cb4d0d937d9bc6 | 23.75 | 0.09 | 828 | 86 |
| 6 | nvidia/nemotron-3-super-120b-a12b:free | 3. 내일 서울 날씨는 어때요? | 8.1 | 1 | 죄송합니다. 해당 질문에 대해서는 답변을 할 수 없습니다. 다른 질문을 해주세요. | rag-nemotron-3-super-120b-a12b-q3 | https://cloud.langfuse.com/project/cmcyjzieu011fad07chd0ow4c/traces/8bdbd414257ad4c068a662cd2251ef2f |  |  |  |  |

보낸 횟수 합(Tracing 목록에 뜰 trace 수): 6
