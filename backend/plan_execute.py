"""계획을 세우고(planner), 한 단계씩 실행하고(agent), 해낸 만큼 보고 다시 계획하는(replan) 그래프를 stream 으로 한 걸음씩 돌려 표로 남긴다."""
import operator
import os
import sys
import time
from pathlib import Path
from typing import Annotated, TypedDict, Union

from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

# 2-2 · 2-3 의 표 도우미를 고치지 않고 가져다 쓴다
from run_agent import TRACE_CHARS, text_of
from run_news import BASE_URL, cell

OUT_PATH = Path("/app/out/plan_execute.md")
ATTEMPTS = 2  # 막히면 한 번만 다시 보낸다
RECURSION_LIMIT = 30  # 되풀이 한도: 계획을 끝없이 다시 세우지 않게 걸음 수를 묶는다
QUESTION = "2024년 호주 오픈 남자 단식 우승자의 고향은 어디야? 검색해서 알려줘"

PLANNER_PROMPT = """For the given objective, come up with a simple step by step plan. This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps."""

REPLANNER_PROMPT = """For the given objective, come up with a simple step by step plan. This plan should involve individual tasks, that if executed correctly will yield the correct answer. Do not add any superfluous steps. The result of the final step should be the final answer. Make sure that each step has all the information needed - do not skip steps.
Your objective was this:
{input}
Your original plan was this:
{plan}
You have currently done the follow steps:
{past_steps}
Update your plan accordingly. If no more steps are needed and you can return to the user, then respond with that. Otherwise, fill out the plan. Only add steps to the plan that still NEED to be done. Do not return previously done steps as part of the plan."""


class State(TypedDict):
    input: str
    plan: list[str]
    # operator.add: (단계, 답) 이 덮어쓰지 않고 뒤에 쌓인다
    past_steps: Annotated[list[tuple], operator.add]
    response: str


class Plan(BaseModel):
    """Plan to follow in future"""

    steps: list[str] = Field(description="different steps to follow, should be in sorted order")


class Response(BaseModel):
    """Response to user."""

    response: str


class Act(BaseModel):
    """Action to perform."""

    action: Union[Response, Plan] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
        "If you need to further use tools to get the answer, use Plan."
    )


def build_graph(llm):
    agent = create_agent(
        model=llm,
        tools=[TavilySearch(max_results=3)],  # 키는 환경 변수 TAVILY_API_KEY 에서 스스로 읽는다
        system_prompt="You are a helpful assistant.",
    )
    # 고르는 칸 그래프와 같이, 이 모델의 도구 호출 길(function_calling)로 구조화된 답을 받는다
    planner = ChatPromptTemplate.from_messages(
        [("system", PLANNER_PROMPT), ("placeholder", "{messages}")]
    ) | llm.with_structured_output(Plan, method="function_calling")
    replanner = ChatPromptTemplate.from_template(REPLANNER_PROMPT) | llm.with_structured_output(
        Act, method="function_calling"
    )

    def plan_step(state: State) -> dict:
        plan = planner.invoke({"messages": [("user", state["input"])]})
        return {"plan": plan.steps}

    def execute_step(state: State) -> dict:
        # 계획을 번호 목록으로 펴고, 첫 단계만 일꾼에게 맡긴다
        plan = state["plan"]
        plan_str = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(plan))
        task = plan[0]
        task_formatted = f"For the following plan:\n{plan_str}\n\nYou are tasked with executing step 1, {task}."
        result = agent.invoke({"messages": [("user", task_formatted)]})
        return {"past_steps": [(task, text_of(result["messages"][-1].content))]}

    def replan_step(state: State) -> dict:
        output = replanner.invoke(state)
        # Response 면 사용자에게 답하고 끝, 아니면 남은 계획으로 갈아 끼운다
        if isinstance(output.action, Response):
            return {"response": output.action.response}
        return {"plan": output.action.steps}

    def should_end(state: State):
        return END if state.get("response") else "agent"

    builder = StateGraph(State)
    builder.add_node("planner", plan_step)
    builder.add_node("agent", execute_step)
    builder.add_node("replan", replan_step)
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "agent")
    builder.add_edge("agent", "replan")
    builder.add_conditional_edges("replan", should_end, ["agent", END])
    return builder.compile()


def run_once(graph, question: str, rows: list) -> None:
    # stream 기본값(updates)은 칸이 끝날 때마다 {칸 이름: 그 칸이 더한 것} 을 준다
    # 받은 목록에 쌓아, 한도에 걸려 멈춰도 그때까지의 걸음이 남게 한다
    stream = graph.stream({"input": question}, {"recursion_limit": RECURSION_LIMIT})
    for step, chunk in enumerate(stream, 1):
        for name, update in chunk.items():
            if not isinstance(update, dict):
                continue
            plan = " / ".join(f"{i + 1}. {s}" for i, s in enumerate(update.get("plan", [])))
            # 일꾼 답은 앞부분만 남긴다 (검색 결과 본문은 표에 들어가지 않는다)
            done = " / ".join(f"{t} → {a[:TRACE_CHARS]}" for t, a in update.get("past_steps", []))
            response = update.get("response", "")[:TRACE_CHARS]
            rows.append((step, name, plan, done, response))
            print(f"STEP {step} · {name} · {plan} · {done} · {response}")


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")
    if not os.environ.get("TAVILY_API_KEY"):
        sys.exit("환경 변수 TAVILY_API_KEY 가 없습니다.")

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)
    graph = build_graph(llm)

    # with_retry 는 stream 을 다시 보내 주지 않으므로 손으로 두 번까지 시도한다
    rows, error, stop, attempt = [], "", "", 0
    start = time.monotonic()
    for attempt in range(1, ATTEMPTS + 1):
        rows = []
        try:
            run_once(graph, QUESTION, rows)
            error = ""
            break
        except GraphRecursionError as e:  # 한도에 걸린 것은 막힘이 아니므로 다시 보내지 않고 걸음을 남긴다
            error = f"{type(e).__name__}: {e}"
            stop = str(rows[-1][0]) if rows else "0"
            print(f"[한도 {RECURSION_LIMIT} 에서 멈춤 · 걸음 {stop}] {error}")
            break
        except Exception as e:  # 막힌 시도의 STEP 줄은 버리고 처음부터 다시
            rows, error = [], f"{type(e).__name__}: {e}"
            print(f"[{attempt}번째 시도 실패] {error}")
    sec = time.monotonic() - start
    status = "한도에서 멈춤" if stop else "호출 실패" if error else "완료"
    print(f"=== ({sec:.1f}초) {status} · 시도 {attempt}번")

    lines = [
        "# Plan-and-Execute 그래프 STEP 확인 (planner · agent · replan)",
        "",
        f"모델: {model} · 한도: {RECURSION_LIMIT} · 시도 횟수: {attempt} · 걸린 초: {sec:.1f} · 상태: {status}",
        "",
        f"질문: {QUESTION}",
        "",
        "```mermaid",
        graph.get_graph(xray=True).draw_mermaid().strip(),
        "```",
        "",
        "| 걸음 | 칸 이름 | 계획 단계 목록 | 해낸 단계와 답 앞부분 | response 앞부분 |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {' | '.join(cell(x) for x in row)} |" for row in rows]
    if stop:
        lines += ["", f"멈춘 걸음: {stop} (이 걸음 다음에 한도에 걸림)"]
    if error:
        lines += ["", f"오류: {cell(error)}"]
    lines += [
        "",
        "| 사람이 확인 | 결과 |",
        "|---|---|",
        "| 다시 세운 계획이 해낸 단계를 보고 바뀌었나 |  |",
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
