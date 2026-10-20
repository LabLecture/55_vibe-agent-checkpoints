"""supervisor 가 일을 맡기는 일꾼 둘. 도구는 아직 없다."""
from langgraph.prebuilt import create_react_agent

from src.agents.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP

user_class_agent = create_react_agent(
    get_llm_by_type(AGENT_LLM_MAP["user_class"]),
    tools=[],
    prompt="학생(자녀)의 수업 정보를 체크(조회,확인)합니다.",
)

class_progress_agent = create_react_agent(
    get_llm_by_type(AGENT_LLM_MAP["class_progress"]),
    tools=[],
    prompt="학생(자녀)의 수업 진도를 체크(조회,확인)합니다.",
)
