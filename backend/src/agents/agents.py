"""supervisor 가 일을 맡기는 일꾼 둘. 일꾼마다 도구 하나."""
from langgraph.prebuilt import create_react_agent

from src.agents.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP
from src.prompts.template import apply_prompt_template
from src.tools.class_progress import class_progress_tool
from src.tools.user_class import user_class_tool

user_class_agent = create_react_agent(
    get_llm_by_type(AGENT_LLM_MAP["user_class"]),
    tools=[user_class_tool],
    prompt=lambda state: apply_prompt_template("user_class", state),
)

class_progress_agent = create_react_agent(
    get_llm_by_type(AGENT_LLM_MAP["class_progress"]),
    tools=[class_progress_tool],
    prompt=lambda state: apply_prompt_template("class_progress", state),
)
