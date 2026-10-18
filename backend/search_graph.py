"""검색 도구(TavilySearch) 하나를 단 그래프를, 도구 칸과 갈림길을 손으로 짜서 만들고 stream 으로 한 걸음씩 돌려 표로 남긴다."""
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# 2-3 · 2-2 의 표 도우미를 고치지 않고 가져다 쓴다
from run_agent import TRACE_CHARS, text_of
from run_news import BASE_URL, cell

OUT_PATH = Path("/app/out/search_graph.md")
ATTEMPTS = 2  # 막히면 한 번만 다시 보낸다
QUESTION = "한국의 다음 대통령 선거를 검색해서 알려줘"
PREBUILT_MARK = "## 기성품 판"  # 표에서 손 판 부분과 기성품 부분을 가르는 머리말


class State(TypedDict):
    # add_messages: 새 메시지가 덮어쓰지 않고 뒤에 쌓인다
    messages: Annotated[list, add_messages]


class BasicToolNode:
    """마지막 AIMessage 의 도구 쪽지를 하나씩 실행하는 도구 칸 (기성품 ToolNode 대신)"""

    def __init__(self, tools: list) -> None:
        # 도구 이름으로 도구를 찾을 수 있게 사전을 만든다
        self.tools_by_name = {t.name: t for t in tools}

    def __call__(self, inputs: dict) -> dict:
        if messages := inputs.get("messages", []):
            message = messages[-1]
        else:
            raise ValueError("입력에 메시지가 없습니다.")
        outputs = []
        for tool_call in message.tool_calls:
            result = self.tools_by_name[tool_call["name"]].invoke(tool_call["args"])
            # 결과를 한글이 깨지지 않는 json 글로 바꿔, 어느 쪽지의 답인지 이름 · id 를 붙인다
            outputs.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
        return {"messages": outputs}


def route_tools(state: State):
    # 마지막 메시지에 도구 쪽지가 있으면 tools 로, 없으면 끝으로 (기성품 tools_condition 대신)
    if messages := state.get("messages", []):
        ai_message = messages[-1]
    else:
        raise ValueError("갈림길 입력 state 에 메시지가 없습니다.")
    if getattr(ai_message, "tool_calls", None):
        return "tools"
    return END


def build_graph(llm, tool, prebuilt: bool = False):
    # prebuilt=True 면 도구 칸 · 갈림길을 기성품(ToolNode · tools_condition)으로 바꾼 판
    llm_with_tools = llm.bind_tools([tool])

    def chatbot(state: State) -> dict:
        # 지금까지의 messages 를 검색 도구를 쥔 모델에 보내고, 받은 답 하나만 돌려준다
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    builder = StateGraph(State)
    builder.add_node("chatbot", chatbot)
    builder.add_edge(START, "chatbot")
    if prebuilt:
        builder.add_node("tools", ToolNode([tool]))
        builder.add_conditional_edges("chatbot", tools_condition)
    else:
        builder.add_node("tools", BasicToolNode([tool]))
        builder.add_conditional_edges("chatbot", route_tools, {"tools": "tools", END: END})
    builder.add_edge("tools", "chatbot")
    return builder.compile()


def describe(m) -> tuple[str, str, str, str]:
    # 메시지 하나를 (종류, 검색어, 결과 제목, 앞부분) 으로 바꾼다 — 앞부분은 TRACE_CHARS 글자만
    if isinstance(m, AIMessage) and m.tool_calls:
        queries = "; ".join(str(c["args"].get("query", "")) for c in m.tool_calls)
        args = "; ".join(str(c["args"]) for c in m.tool_calls)
        return "도구 쪽지", queries, "", args[:TRACE_CHARS]
    if isinstance(m, ToolMessage):
        content = text_of(m.content)
        try:
            data = json.loads(content)
            results = data.get("results", []) if isinstance(data, dict) else []
        except json.JSONDecodeError:  # json 이 아니면(오류 글 등) 그 글 앞부분만 남긴다
            return "도구 결과", "", "", content[:TRACE_CHARS]
        titles = "; ".join(r.get("title", "") for r in results)
        # 검색 결과 본문 전체는 남기지 않고 첫 결과 앞부분만
        head = results[0].get("content", "") if results else content
        return "도구 결과", str(data.get("query", "")) if isinstance(data, dict) else "", titles, head[:TRACE_CHARS]
    if isinstance(m, AIMessage):
        return "답", "", "", text_of(m.content)[:TRACE_CHARS]
    return type(m).__name__, "", "", text_of(m.content)[:TRACE_CHARS]


def run_once(graph, question: str) -> list[tuple]:
    # stream 기본값(updates)은 칸이 끝날 때마다 {칸 이름: 그 칸이 더한 것} 을 준다
    rows = []
    for step, chunk in enumerate(graph.stream({"messages": [{"role": "user", "content": question}]}), 1):
        for name, update in chunk.items():
            new = update.get("messages", []) if isinstance(update, dict) else []
            if not new:
                continue
            parts = [describe(m) for m in new]
            kind, query, titles, head = (", ".join(p[i] for p in parts if p[i]) for i in range(4))
            rows.append((step, name, kind, query, titles, head))
            print(f"STEP {step} · {name} · {kind} · {query} · {titles} · {head}")
    return rows


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")
    if not os.environ.get("TAVILY_API_KEY"):
        sys.exit("환경 변수 TAVILY_API_KEY 가 없습니다.")

    # 인자 prebuilt 를 주면 기성품 판만 돌려 표 뒤에 덧붙이고, 없으면 손 판으로 표를 새로 쓴다
    prebuilt = sys.argv[1:] == ["prebuilt"]
    hand_part = ""
    if prebuilt:
        if not OUT_PATH.exists():
            sys.exit(f"{OUT_PATH} 가 없습니다. 손 판을 먼저 돌리세요.")
        text = OUT_PATH.read_text(encoding="utf-8")
        # 손 판 부분은 글자 그대로 두고, 전에 덧붙인 기성품 부분만 버린다
        idx = text.find("\n" + PREBUILT_MARK)
        hand_part = text if idx < 0 else text[: idx + 1]

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)
    # TavilySearch 는 키를 환경 변수 TAVILY_API_KEY 에서 스스로 읽는다
    graph = build_graph(llm, TavilySearch(max_results=3), prebuilt)

    # with_retry 는 stream 을 다시 보내 주지 않으므로 손으로 두 번까지 시도한다
    rows, error, attempt = [], "", 0
    start = time.monotonic()
    for attempt in range(1, ATTEMPTS + 1):
        try:
            rows, error = run_once(graph, QUESTION), ""
            break
        except Exception as e:  # 막힌 시도의 STEP 줄은 버리고 처음부터 다시
            rows, error = [], f"{type(e).__name__}: {e}"
            print(f"[{attempt}번째 시도 실패] {error}")
    sec = time.monotonic() - start
    status = "호출 실패" if error else "완료"
    print(f"=== ({sec:.1f}초) {status} · 시도 {attempt}번")

    if prebuilt:
        lines = [
            PREBUILT_MARK + " (ToolNode · tools_condition)",
            "",
            f"모델: {model} · 시도 횟수: {attempt} · 걸린 초: {sec:.1f} · 상태: {status}",
            "",
        ]
    else:
        lines = [
            "# 검색 도구 그래프 STEP 확인 (도구 칸 · 갈림길 손으로 짜기)",
            "",
            f"모델: {model} · 시도 횟수: {attempt} · 걸린 초: {sec:.1f} · 상태: {status}",
            "",
            f"질문: {QUESTION}",
            "",
        ]
    lines += [
        "```mermaid",
        graph.get_graph().draw_mermaid().strip(),
        "```",
        "",
        "| STEP | 칸 이름 | 더한 메시지 종류 | 검색어 | 결과 제목 | 앞부분 | 답이 검색 결과에 있는 말인가 |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [f"| {' | '.join(cell(x) for x in row)} |  |" for row in rows]
    if error:
        lines += ["", f"오류: {cell(error)}"]

    if prebuilt:
        # 손 판 순서는 다시 돌리지 않고 표에 남은 손 판 STEP 줄에서 읽는다
        hand_rows = re.findall(r"^\| (\d+) \| ([^|]+?) \| ([^|]+?) \|", hand_part, re.M)
        hand_order = " → ".join(" ".join(r) for r in hand_rows) or "없음"
        new_order = " → ".join(f"{r[0]} {r[1]} {r[2]}" for r in rows) or "없음"
        lines += ["", "## 두 판 STEP 순서", "", f"손 판: {hand_order} · 기성품 판: {new_order}"]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(hand_part + ("\n" if prebuilt else "") + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
