"""학습지 챗봇 그래프의 칸 다섯. 모든 칸은 Command 로 다음 칸을 정한다."""
import json
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from langgraph.types import Command

from src.agents.agents import class_progress_agent, user_class_agent
from src.agents.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP, TEAM_MEMBERS
from src.graph.types import Router, State

# 붙임 1 — coordinator 지시문 원문
COORDINATOR_PROMPT = """# 실행 규칙 (Execution Rules)

- 인사/스몰토크/비윤리적 요청일 경우:
  - 자연스러운 한국어 인사 또는 정중한 거절 메시지로 응답
- 그 외 모든 입력은:
  - 다음 형식으로 Planner에게 위임
    ```
    handoff_to_planner()
    ```
- 코드 블록 없이 **`handoff_to_planner()`** 를 단독 출력하세요."""

# 붙임 2 — planner 지시문 원문
PLANNER_PROMPT = """## Agent Capabilities

- **`user_class`**: 학생(자녀)의 수업 정보를 체크(조회,확인)합니다. (Check (inquiry, confirmation) the class information of the student (child))
 * 필요 정보(required information): 학생 이름(user_name), 학교(user_school), 학년(user_grade)
 * response class information in a markdown format.
- **`class_progress`**: 학생(자녀)의 수업 진도를 체크(조회,확인)합니다. (Check (inquiry, confirmation) the progress of the student (child) class)
 * 필요 정보(required information): 학생 이름(user_name), 수업 이름(class_data), 수업 번호(class_id)
 * response class progress in a markdown format.

# Output Format

Directly output the raw JSON format of `Plan` without "```json".

```ts
interface Step {
  agent_name: string;
  title: string;
  description: string;
  note?: string;
}

interface Plan {
  thought: string;
  title: string;
  steps: Step[];
}
```"""

# 붙임 3 — supervisor 지시문 원문 (<<TEAM_MEMBERS>> 자리에 일꾼 목록을 넣는다)
SUPERVISOR_PROMPT = """You are a supervisor coordinating a team of specialized workers to complete tasks. Your team consists of: <<TEAM_MEMBERS>>.

For each user request, you will:
1. Analyze the request and determine which worker is best suited to handle it next
2. Respond with ONLY a JSON object in the format: {"next": "worker_name"}
3. Review their response and either:
   - Choose the next worker if more work is needed (e.g., {"next": "user_class"})
   - Respond with {"next": "FINISH"} when the task is complete

Always respond with a valid JSON object containing only the 'next' key and a single value: either a worker's name or 'FINISH'.

## Team Members

- **`user_class`**: 학생(자녀)의 수업 정보를 체크(조회,확인)합니다. (Check (inquiry, confirmation) the class information of the student (child))
  * 필요 정보(required information): 학생 이름(user_name), 학교(user_school), 학년(user_grade)
  * response class information in a markdown format.
- **`class_progress`**: 학생(자녀)의 수업 진도를 체크(조회,확인)합니다. (Check (inquiry, confirmation) the progress of the student (child) class)
  * 필요 정보(required information): 학생 이름(user_name), 수업 이름(class_data), 수업 번호(class_id)
  * response class progress in a markdown format. """.replace("<<TEAM_MEMBERS>>", ", ".join(TEAM_MEMBERS))


def coordinator_node(state: State) -> Command[Literal["planner", "__end__"]]:
    llm = get_llm_by_type(AGENT_LLM_MAP["coordinator"])
    content = llm.invoke([SystemMessage(COORDINATOR_PROMPT)] + state["messages"]).content
    # 위임 글자가 있으면 planner 로, 없으면 인사·거절 답을 남기고 끝
    if "handoff_to_planner" in content:
        return Command(goto="planner")
    return Command(
        update={"messages": [AIMessage(content=content, name="coordinator")]},
        goto=END,
    )


def planner_node(state: State) -> Command[Literal["supervisor", "__end__"]]:
    llm = get_llm_by_type(AGENT_LLM_MAP["planner"])
    content = llm.invoke([SystemMessage(PLANNER_PROMPT)] + state["messages"]).content.strip()
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
    goto = llm.invoke([SystemMessage(SUPERVISOR_PROMPT)] + state["messages"])["next"]
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
