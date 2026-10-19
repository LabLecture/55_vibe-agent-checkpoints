# DB 쿼리 확인 (JOIN · GROUP BY)

실행: PostgreSQL MCP (`pg_execute_query`). ㉤ 는 오류 번호를 보려고 db 상자 안 psql(`VERBOSITY=verbose`)로 한 번 더 돌림

| 쿼리 | SQL 원문 | 결과 | 대본 글과 같은가 |
|---|---|---|---|
| ㉠ 턴 2 — 송혜교 · 쌍문초등학교 · 6학년의 수업 (INNER JOIN) | `SELECT p.subject_id, p.subject_name FROM ss_members m INNER JOIN ss_members_progress p ON m.user_id = p.user_id WHERE m.user_name = '송혜교' AND m.user_school = '쌍문초등학교' AND m.user_grade = 6 ORDER BY p.subject_id` | 1 · AI수학 프로그램<br>2 · 창의STEAM 수업<br>3 · 슬기로운 생활 | O(수업 셋 이름 · 순서가 대본 턴 2와 같음) |
| ㉡ 턴 3 — 같은 학생의 수업 1 진도 | `SELECT p.subject_last_mm, p.subject_this_mm FROM ss_members m INNER JOIN ss_members_progress p ON m.user_id = p.user_id WHERE m.user_name = '송혜교' AND m.user_school = '쌍문초등학교' AND m.user_grade = 6 AND p.subject_id = '1'` | 지난달: 나눗셈/원<br>이번달: 분수/들이와무게 에서 [H6] 4.분수(2) | O(지난달 · 이번달 단원 글자가 대본 턴 3과 같음) |
| ㉢ 학생마다 듣는 수업 수 (LEFT JOIN · GROUP BY) | `SELECT m.user_id, m.user_name, COUNT(p.subject_id) AS subject_count FROM ss_members m LEFT JOIN ss_members_progress p ON m.user_id = p.user_id GROUP BY m.user_id, m.user_name ORDER BY m.user_id` | 1 · 송혜교 · 3<br>2 · 장원영 · 1 | -(대본에 없는 쿼리) |
| ㉣ 수업 2개 이상인 학생 (HAVING) | `SELECT m.user_id, m.user_name, COUNT(p.subject_id) AS subject_count FROM ss_members m LEFT JOIN ss_members_progress p ON m.user_id = p.user_id GROUP BY m.user_id, m.user_name HAVING COUNT(p.subject_id) >= 2 ORDER BY m.user_id` | 1 · 송혜교 · 3 | -(대본에 없는 쿼리) |
| ㉤ ㉣ 의 조건을 WHERE 에 | `SELECT m.user_id, m.user_name, COUNT(p.subject_id) AS subject_count FROM ss_members m LEFT JOIN ss_members_progress p ON m.user_id = p.user_id WHERE COUNT(p.subject_id) >= 2 GROUP BY m.user_id, m.user_name ORDER BY m.user_id` | 오류 (MCP): `MCP error -32603: Failed to execute query: Query failed: aggregate functions are not allowed in WHERE`<br>오류 (psql): `ERROR:  42803: aggregate functions are not allowed in WHERE` · `LINE 4: WHERE COUNT(p.subject_id) >= 2` · `LOCATION:  check_agglevels_and_constraints, parse_agg.c:604` | -(오류 번호 42803 · 예전 과정 42883과 다른 번호) |
