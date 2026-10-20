# 수업 정보 쿼리 (예전 과정 원문 · 표 이름 접두만 ss_)
select_class_info = """
    SELECT * FROM public.ss_members ssm
    INNER JOIN public.ss_members_progress ssmp on ssm.user_id = ssmp.user_id
    WHERE user_name = %s 
    and user_school = %s 
    and user_grade = %s
"""

select_class_progress_info_02 = """
    SELECT * FROM public.ss_members ssm
    INNER JOIN public.ss_members_progress ssmp on ssm.user_id = ssmp.user_id
    WHERE ssm.user_name = %s
    and (subject_name like %s or (subject_id = %s and subject_id != '0') )
"""
