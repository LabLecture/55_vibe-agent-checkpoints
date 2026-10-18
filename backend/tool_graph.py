"""주문 · 등급 · 배송 도구 셋을 단 그래프를 StateGraph 로 짓고, 질문마다 고른 도구와 답을 표로 남긴다."""
import os
import sys
import time
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


@tool
def get_order_info():
    """주문한 상품 정보 조회"""
    return ["스트라이프 셔츠 12,000원", "트레이닝 바지 35,000원"]


@tool
def get_shipping_info(product: str):
    """주문한 상품에 대한 배송 정보 조회"""
    return "배송준비중"


@tool
def get_grade_info():
    """유저의 등급 조회"""
    return "VIP"


TOOLS = [get_order_info, get_shipping_info, get_grade_info]

BASE_URL = "https://openrouter.ai/api/v1"
OUT_PATH = Path("/app/out/tool_graph.md")
HEAD = 80  # 마지막 답 앞부분으로 보여 줄 글자 수

QUESTIONS = [
    "주문 조회해줘",
    "내 등급 조회",
    "스트라이프 셔츠 주문한거 언제와",
    "내 등급이랑 주문정보 알려줘",
    "한국의 수도가 어디야",
]


class State(TypedDict):
    # add_messages: 새 메시지가 덮어쓰지 않고 뒤에 쌓인다
    messages: Annotated[list, add_messages]


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 와 줄바꿈을 바꾼다
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def build_graph(llm):
    llm_with_tools = llm.bind_tools(TOOLS)

    def chatbot(state: State) -> dict:
        # 지금까지의 messages 를 도구 셋을 쥔 모델에 보내고, 받은 답 하나만 돌려준다
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    builder = StateGraph(State)
    builder.add_node("chatbot", chatbot)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_edge(START, "chatbot")
    # 도구 쪽지가 있으면 tools 로, 없으면 끝으로
    builder.add_conditional_edges("chatbot", tools_condition)
    builder.add_edge("tools", "chatbot")
    return builder.compile()


def read_messages(messages: list) -> tuple[str, str, str, str, int]:
    # messages 를 차례대로 읽어 (고른 도구 순서, 인자, 도구 결과, 마지막 답, 모델 호출 수) 를 만든다
    names, args, results, last, calls = [], [], [], "", 0
    for m in messages:
        if isinstance(m, AIMessage):
            calls += 1
            last = m.content if isinstance(m.content, str) else str(m.content)
            for c in m.tool_calls:
                names.append(c["name"])
                args.append(f"{c['name']} {c['args']}")
        elif isinstance(m, ToolMessage):
            results.append(f"{m.name}: {m.content}")
    return " → ".join(names) or "없음", "; ".join(args), "; ".join(results), last[:HEAD], calls


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)
    graph = build_graph(llm)
    runner = graph.with_retry(stop_after_attempt=2)  # 막히면 한 번만 다시 보낸다

    lines = [
        "# 도구 셋 그래프 확인",
        "",
        f"모델: {model}",
        "",
        "```mermaid",
        graph.get_graph().draw_mermaid().strip(),
        "```",
        "",
        "| 질문 | 고른 도구 순서 | 인자 | 도구 결과 | 마지막 답 앞부분 | 모델 호출 수 | 걸린 초 | 고른 도구가 질문에 맞는가 |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for q in QUESTIONS:
        start = time.monotonic()
        try:
            out = runner.invoke({"messages": [("user", q)]})
            names, args, results, last, calls = read_messages(out["messages"])
        except Exception as e:  # 두 번 다 막히면 오류 원문을 남기고 다음 질문으로
            names, args, results, last, calls = "호출 실패", "", "", f"{type(e).__name__}: {e}", 0
        sec = time.monotonic() - start

        print(f"=== {q} ({sec:.1f}초) {names} · {args} · {results} · 호출 {calls}번 · {last}")
        lines.append(
            f"| {cell(q)} | {cell(names)} | {cell(args)} | {cell(results)} "
            f"| {cell(last)} | {calls} | {sec:.1f} |  |"
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
