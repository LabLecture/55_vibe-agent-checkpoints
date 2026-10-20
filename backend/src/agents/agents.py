"""supervisor 가 일을 맡기는 일꾼 둘. 도구는 아직 없다."""
from langgraph.prebuilt import create_react_agent

from src.agents.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP
from src.prompts.template import apply_prompt_template

user_class_agent = create_react_agent(
    get_llm_by_type(AGENT_LLM_MAP["user_class"]),
    tools=[],
    prompt=lambda state: apply_prompt_template("user_class", state),
)

class_progress_agent = create_react_agent(
    get_llm_by_type(AGENT_LLM_MAP["class_progress"]),
    tools=[],
    prompt=lambda state: apply_prompt_template("class_progress", state),
)
