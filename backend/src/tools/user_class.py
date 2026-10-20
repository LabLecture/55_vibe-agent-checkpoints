# 학생(자녀) 수업정보 도구 (예전 과정 원문)
from typing import Annotated

from langchain_core.tools import tool

from src.tools.db import PostgreSqlDB
from src.tools.db_sql import select_class_info


@tool
def user_class_tool(
    user_name:Annotated[str, "학생(자녀)이름, default value is **샘플스**"],
    user_school:Annotated[str, "학교, default value is **샘플학교**"],
    user_grade:Annotated[int, "학년, default value is **7**"]
):
    """학생(자녀)의 **수업정보**를 체크(조회,확인)합니다.
        추가적인 지시사항:
        - 유저 이름이나 학교명이 구체적으로 명시되지 않은 경우(예: '제 딸', '초등학교' 등), 해당 정보는 수집하지 마십시오.
        - 구체적인 이름과 학교명이 제공된 경우에만 user_name과 user_school을 설정하십시오.
        - 일반적인 명칭이 입력된 경우 "안녕하세요 학습지 챗봇입니다. 자녀의 이름과 학교명을 구체적으로 알려주세요."라고 응답하십시오.
    """
    try:
        print(f"user_class_tool_start_user_name: {user_name}, user_school: {user_school}, user_grade: {user_grade}")

        class_datas = PostgreSqlDB().fetch_all(select_class_info, (user_name, user_school, user_grade))

        if class_datas is None:
            return "입력 정보에 부합되는 수업정보가 없습니다.  다시 자녀정보를 입력해주세요."

        # 수업마다 「1. 수업이름」 꼴로 차례 번호를 붙인다
        subjects = "\n".join(f"{i}. {row['subject_name']}" for i, row in enumerate(class_datas, 1))

        return f"학생(자녀)이름:{user_name}\n학교:{user_school}\n학년:{user_grade}\n수업정보:\n{subjects}"
    except Exception as e:
        error_msg = f"Failed to crawl. Error: {repr(e)}"

        return error_msg
