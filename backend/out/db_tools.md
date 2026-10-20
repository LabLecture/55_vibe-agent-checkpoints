# DB 도구 단독 호출 (user_class_tool · class_progress_tool)

실행: `도구.invoke(넣은 값)` 을 하나씩 부름 (모델 · 그래프 없음). ⑤ 는 `docker compose stop db` 뒤 ① 과 같은 값

| 번호 | 도구 | 넣은 값 | 돌려준 글 원문 | 걸린 초 | 섹션 3-3 표와 같은가 |
|---|---|---|---|---|---|
| ① | user_class_tool | {'user_name': '송혜교', 'user_school': '쌍문초등학교', 'user_grade': 6} | 학생(자녀)이름:송혜교<br>학교:쌍문초등학교<br>학년:6<br>수업정보:<br>1. AI수학 프로그램<br>2. 창의STEAM 수업<br>3. 슬기로운 생활 | 0.37 | O(수업 셋 이름 · 차례가 3-3 표와 같다) |
| ② | class_progress_tool | {'user_name': '송혜교', 'class_data': 'AI수학 프로그램', 'class_id': '1'} | <br>        학생(자녀)이름:송혜교<br>        수업진도:{'user_id': '1', 'user_name': '송혜교', 'user_school': '쌍문초등학교', 'user_grade': 6, 'subject_id': '1', 'subject_name': 'AI수학 프로그램', 'subject_last_mm': '나눗셈/원', 'subject_this_mm': '분수/들이와무게 에서 [H6] 4.분수(2)'}<br>         | 0.01 | O(지난달 나눗셈/원 · 이번달 분수/들이와무게 에서 [H6] 4.분수(2) — 3-3 표와 같다) |
| ③ | class_progress_tool | {'user_name': '장원영', 'class_data': '샘플', 'class_id': '1'} | 입력 정보에 부합되는 수업정보가 없습니다.  다시 입력해주세요. | 0.01 | O(장원영은 수업 번호 1 이 없어 없음 글) |
| ④ | user_class_tool | {'user_name': '송혜교', 'user_school': '미아초등학교', 'user_grade': 6} | 학생(자녀)이름:송혜교<br>학교:미아초등학교<br>학년:6<br>수업정보:<br> | 0.01 | O(미아초등학교 송혜교는 표에 없어 「수업정보:」 아래가 빈 글) |
| ⑤ db 상자 멈춤 | user_class_tool | {'user_name': '송혜교', 'user_school': '쌍문초등학교', 'user_grade': 6} | 입력 정보에 부합되는 수업정보가 없습니다.  다시 자녀정보를 입력해주세요. | 3.96 | X(DB 가 꺼졌는데 「수업정보가 없습니다」 글 — 연결 실패를 없음으로 답한다) |
