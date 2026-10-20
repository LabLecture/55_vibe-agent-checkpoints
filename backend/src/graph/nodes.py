"""학습지 챗봇 그래프의 칸 다섯. 모든 칸은 Command 로 다음 칸을 정한다."""
import json
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END
from langgraph.types import Command

from src.agents.agents import class_progress_agent, user_class_agent
from src.agents.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP
from src.graph.types import Router, State
from src.prompts.template import apply_prompt_template


def coordinator_node(state: State) -> Command[Literal["planner", "__end__"]]:
    llm = get_llm_by_type(AGENT_LLM_MAP["coordinator"])
    content = llm.invoke(apply_prompt_template("coordinator", state)).content
    # 위임 글자가 있으면 planner 로, 없으면 인사·거절 답을 남기고 끝
    if "handoff_to_planner" in content:
        return Command(goto="planner")
    return Command(
        update={"messages": [AIMessage(content=content, name="coordinator")]},
        goto=END,
    )


def planner_node(state: State) -> Command[Literal["supervisor", "__end__"]]:
    llm = get_llm_by_type(AGENT_LLM_MAP["planner"])
    content = llm.invoke(apply_prompt_template("planner", state)).content.strip()
    # ```json 껍질을 벗긴다
    if content.startswith("```json"):
        content = content.removeprefix("```json").removesuffix("```").strip()
    try:
        json.loads(content)
    except json.JSONDecodeError:
        # 계획이 JSON 이 아니면 끝
        return Command(goto=END)
    return Command(
        update={
            "full_plan": content,
            "messages": [HumanMessage(content=content, name="planner")],
        },
        goto="supervisor",
    )


def supervisor_node(state: State) -> Command[Literal["user_class", "class_progress", "__end__"]]:
    llm = get_llm_by_type(AGENT_LLM_MAP["supervisor"]).with_structured_output(Router, method="json_mode")
    goto = llm.invoke(apply_prompt_template("supervisor", state))["next"]
    return Command(update={"next": goto}, goto=END if goto == "FINISH" else goto)


def user_class_node(state: State) -> Command[Literal["__end__"]]:
    result = user_class_agent.invoke(state)
    # 일꾼이 낸 마지막 AI 답을 일꾼 이름으로 남긴다
    return Command(
        update={"messages": [AIMessage(content=result["messages"][-1].content, name="user_class")]},
        goto=END,
    )


def class_progress_node(state: State) -> Command[Literal["__end__"]]:
    result = class_progress_agent.invoke(state)
    return Command(
        update={"messages": [AIMessage(content=result["messages"][-1].content, name="class_progress")]},
        goto=END,
    )
