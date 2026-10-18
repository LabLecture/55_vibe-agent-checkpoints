"""검색 일꾼(researcher) · 코드 일꾼(coder) 과 다음 일꾼을 고르는 칸(supervisor) 을 둔 그래프를 stream(subgraphs=True) 으로 한 걸음씩 돌려 표로 남긴다."""
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command

# 2-2 · 2-3 · 2-5 의 도우미를 고치지 않고 가져다 쓴다
from run_agent import text_of
from run_code import strip_fences
from run_news import BASE_URL, cell
from search_graph import describe

OUT_PATH = Path("/app/out/supervisor_graph.md")
ATTEMPTS = 2  # 막히면 한 번만 다시 보낸다
RECURSION_LIMIT = 10  # 되풀이 한도: 일꾼을 끝없이 오가지 않게 걸음 수를 묶는다
QUESTION = (
    "뉴욕주와 캘리포니아주의 최신 GDP를 검색해서 찾아줘. "
    "그다음 두 값의 평균은 coder 가 파이썬 코드를 실행해서 계산해줘"
)
MEMBERS = ["researcher", "coder"]
OPTIONS = MEMBERS + ["FINISH"]
SUPERVISOR_PROMPT = (
    "You are a supervisor tasked with managing a conversation between the"
    f" following workers: {MEMBERS}. Given the following user request,"
    " respond with the worker to act next. Each worker will perform a"
    " task and respond with their results and status. When finished,"
    " respond with FINISH."
)

# run_code.py 와 같은 설정: __main__ 으로 돌고, globals 하나만 쓴다
repl = PythonREPL(_globals={"__name__": "__main__"}, _locals=None)


@tool
def python_repl_tool(code: str) -> str:
    """Execute python code and return its stdout. Use print(...) to see a value."""
    # PythonREPL 은 예외를 잡아 repr(e) 글자로 돌려준다
    return repl.run(strip_fences(code)) or "(출력 없음)"


class State(TypedDict):
    # add_messages: 새 메시지가 덮어쓰지 않고 뒤에 쌓인다
    messages: Annotated[list, add_messages]
    next: str


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""

    next: Literal["researcher", "coder", "FINISH"]


def build_graph(llm):
    researcher = create_agent(
        model=llm,
        tools=[TavilySearch(max_results=5)],  # 키는 환경 변수 TAVILY_API_KEY 에서 스스로 읽는다
        system_prompt="You are a researcher. DO NOT do any math.",
    )
    coder = create_agent(model=llm, tools=[python_repl_tool])
    # 2-5 에서 이 모델의 도구 호출이 됐던 길(function_calling)로 고른 답을 받는다
    router = llm.with_structured_output(Router, method="function_calling")

    def supervisor(state: State) -> Command[Literal["researcher", "coder", "__end__"]]:
        messages = [{"role": "system", "content": SUPERVISOR_PROMPT}] + state["messages"]
        nxt = router.invoke(messages)["next"]
        # FINISH 면 끝으로, 아니면 고른 일꾼으로 보낸다
        return Command(goto=END if nxt == "FINISH" else nxt, update={"next": nxt})

    def worker(name: str, agent):
        def node(state: State) -> Command[Literal["supervisor"]]:
            result = agent.invoke({"messages": state["messages"]})
            # 에이전트의 마지막 답 하나만 이름표를 단 사람 메시지로 더한다
            answer = HumanMessage(content=text_of(result["messages"][-1].content), name=name)
            return Command(update={"messages": [answer]}, goto="supervisor")

        return node

    builder = StateGraph(State)
    builder.add_node("supervisor", supervisor)
    builder.add_node("researcher", worker("researcher", researcher))
    builder.add_node("coder", worker("coder", coder))
    builder.add_edge(START, "supervisor")
    return builder.compile()


def codes_of(m) -> str:
    # coder 가 python_repl_tool 에 넘긴 코드 원문 (자르지 않는다)
    if isinstance(m, AIMessage) and m.tool_calls:
        return "; ".join(str(c["args"].get("code", "")) for c in m.tool_calls if c["name"] == python_repl_tool.name)
    return ""


def run_once(graph, question: str, limit: int, rows: list, picks: list) -> None:
    # subgraphs=True 면 (어느 그래프인가, {칸 이름: 그 칸이 더한 것}) 짝으로 준다 — 바깥은 빈 튜플
    # 받은 목록에 쌓아, 한도에 걸려 멈춰도 그때까지의 걸음이 남게 한다
    stream = graph.stream(
        {"messages": [{"role": "user", "content": question}]},
        {"recursion_limit": limit},  # config 는 일꾼 안 에이전트에도 이어진다
        subgraphs=True,
    )
    for step, (ns, chunk) in enumerate(stream, 1):
        where = f"일꾼 안 ({ns[0].split(':')[0]})" if ns else "바깥"
        for name, update in chunk.items():
            if not isinstance(update, dict):
                continue
            if "next" in update:  # 고르는 칸은 messages 대신 고른 일꾼만 더한다
                picks.append(update["next"])
                rows.append((step, where, name, f"고름 → {update['next']}", "", "", ""))
                print(f"STEP {step} · {where} · {name} · 고름 → {update['next']}")
            new = update.get("messages", [])
            if not new:
                continue
            kinds, queries, codes, heads = [], [], [], []
            for m in new:
                kind, query, _, head = describe(m)
                if isinstance(m, HumanMessage):
                    kind = f"사람 메시지 ({m.name})" if m.name else "사람 메시지"
                kinds.append(kind)
                queries.append(query)
                codes.append(codes_of(m))
                heads.append(head)
            row = (step, where, name) + tuple(", ".join(x for x in col if x) for col in (kinds, queries, codes, heads))
            rows.append(row)
            print(f"STEP {' · '.join(str(x) for x in row)}")


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")
    if not os.environ.get("TAVILY_API_KEY"):
        sys.exit("환경 변수 TAVILY_API_KEY 가 없습니다.")

    # 인자 limit N 을 주면 한도 N 으로 돌려 표 뒤에 덧붙이고, 없으면 한도 RECURSION_LIMIT 로 표를 새로 쓴다
    append = len(sys.argv) == 3 and sys.argv[1] == "limit"
    limit = int(sys.argv[2]) if append else RECURSION_LIMIT
    if append and not OUT_PATH.exists():
        sys.exit(f"{OUT_PATH} 가 없습니다. 인자 없이 먼저 돌리세요.")

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)
    graph = build_graph(llm)

    # with_retry 는 stream 을 다시 보내 주지 않으므로 손으로 두 번까지 시도한다
    rows, picks, error, stop, attempt = [], [], "", "", 0
    start = time.monotonic()
    for attempt in range(1, ATTEMPTS + 1):
        rows, picks = [], []
        try:
            run_once(graph, QUESTION, limit, rows, picks)
            error = ""
            break
        except GraphRecursionError as e:  # 한도에 걸린 것은 막힘이 아니므로 다시 보내지 않고 걸음을 남긴다
            error = f"{type(e).__name__}: {e}"
            stop = str(rows[-1][0]) if rows else "0"
            print(f"[한도 {limit} 에서 멈춤 · 걸음 {stop}] {error}")
            break
        except Exception as e:  # 막힌 시도의 STEP 줄은 버리고 처음부터 다시
            rows, picks, error = [], [], f"{type(e).__name__}: {e}"
            print(f"[{attempt}번째 시도 실패] {error}")
    sec = time.monotonic() - start
    status = "한도에서 멈춤" if stop else "호출 실패" if error else "완료"
    print(f"=== ({sec:.1f}초) {status} · 시도 {attempt}번")

    calls = Counter(p for p in picks if p != "FINISH")
    repeats = sum(1 for a, b in zip(picks, picks[1:]) if a == b and a != "FINISH")
    meta = f"모델: {model} · 한도: {limit} · 시도 횟수: {attempt} · 걸린 초: {sec:.1f} · 상태: {status}"
    if append:
        lines = [f"## 되풀이 한도 {limit}", "", meta, ""]
    else:
        lines = [
            "# supervisor 그래프 STEP 확인 (researcher · coder)",
            "",
            meta,
            "",
            f"질문: {QUESTION}",
            "",
            "```mermaid",
            graph.get_graph().draw_mermaid().strip(),
            "```",
            "",
        ]
    lines += [
        "| 걸음 | 그래프 | 칸 이름 | 더한 것 종류 | 검색어 | 실행한 코드 | 앞부분 |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [f"| {' | '.join(cell(x) for x in row)} |" for row in rows]
    if stop:
        lines += ["", f"멈춘 걸음: {stop} (이 걸음 다음에 한도에 걸림)"]
    if error:
        lines += ["", f"오류: {cell(error)}"]
    lines += [
        "",
        "### 요약" if append else "## 요약",
        "",
        f"- 고른 차례: {' → '.join(picks) or '없음'}",
        f"- 일꾼마다 부른 수: " + ", ".join(f"{w} {calls[w]}번" for w in MEMBERS),
        f"- 같은 일꾼을 잇달아 부른 수: {repeats}",
        f"- 걸린 초: {sec:.1f}",
        "",
        "| 사람이 확인 | 결과 |",
        "|---|---|",
        "| 평균이 researcher 답의 두 값으로 계산됐나 |  |",
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # 덧붙일 때는 앞 줄을 글자 그대로 두고 뒤에만 더한다
    before = OUT_PATH.read_text(encoding="utf-8") + "\n" if append else ""
    OUT_PATH.write_text(before + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
