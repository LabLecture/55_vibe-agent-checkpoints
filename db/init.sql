-- 학생 표
CREATE TABLE ss_members (
    user_id varchar(50) NOT NULL,
    user_name varchar(100) NOT NULL,
    user_school varchar(100) NOT NULL,
    user_grade INT NULL
);

-- 학생별 수업 진도 표
CREATE TABLE ss_members_progress (
    user_id varchar(50) NOT NULL,
    subject_id varchar(50) NOT NULL,
    subject_name varchar(50) NOT NULL,
    subject_last_mm varchar(50) NOT NULL,
    subject_this_mm varchar(50) NOT NULL
);

-- 샘플 학생 둘
INSERT INTO ss_members (user_id, user_name, user_school, user_grade) VALUES
    ('1', '송혜교', '쌍문초등학교', 6),
    ('2', '장원영', '미아초등학교', 2);

-- 샘플 진도 넷
INSERT INTO ss_members_progress (user_id, subject_id, subject_name, subject_last_mm, subject_this_mm) VALUES
    ('1', '1', 'AI수학 프로그램', '나눗셈/원', '분수/들이와무게 에서 [H6] 4.분수(2)'),
    ('1', '2', '창의STEAM 수업', 'Level 1 코딩전문가 6 함수', 'Level 2 문제해결자 9 자동화/도식화/유추'),
    ('1', '3', '슬기로운 생활', '4장 독서의 필요성', '3. 추천도서목록'),
    ('2', '3', '슬기로운 생활', '4장 독서의 필요성', '3. 추천도서목록');
