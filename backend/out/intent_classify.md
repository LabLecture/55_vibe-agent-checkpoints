# 의도 분류 확인

모델: google/gemma-4-26b-a4b-it

| 질문 | 모델 답 원문 | 고른 의도 | 걸린 초 | 내가 기대한 의도 | 맞았나 |
|---|---|---|---|---|---|
| 교재는 언제 배송되나요? | GENERAL_INQUIRIES | GENERAL_INQUIRIES | 0.6 | GENERAL_INQUIRIES | O |
| 아이 공부가 어디까지 됐나요? | LEARNING_SUPPORT | LEARNING_SUPPORT | 0.3 | LEARNING_SUPPORT | O |
| 내일 서울 날씨는 어때요? | GENERAL_INQUIRIES | GENERAL_INQUIRIES | 0.7 | None(다섯 밖) | X |
| 초등학교 딸 수업진도를 체크할 수 있나요? | LEARNING_SUPPORT | LEARNING_SUPPORT | 0.6 | LEARNING_SUPPORT | O |
| 쌍문초등학교 6학년 송혜교 | GENERAL_INQUIRIES | GENERAL_INQUIRIES | 0.4 | None(앞 말 없이는 모름) | X |
| 1 | 질문이 제공되지 않았습니다. 분석할 고객의 질문을 입력해 주세요. | None | 0.7 | None(앞 말 없이는 모름) | O |
| 신입채용에 지원하고 싶습니다. | EMPLOYEE_RECRUITMENT | EMPLOYEE_RECRUITMENT | 0.4 | 모호(교사 · 직원 둘 다) | △ |
| 귀사에 입사하고 싶은 지원자 입니다. | EMPLOYEE_RECRUITMENT | EMPLOYEE_RECRUITMENT | 1.1 | 모호(교사 · 직원 둘 다) | △ |
