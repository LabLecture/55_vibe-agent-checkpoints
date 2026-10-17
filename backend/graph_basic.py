"""가장 작은 그래프(START → chatbot → END)에 질문 하나를 넣어 돌리고 결과를 표로 남긴다."""
import os
import sys
import time
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

BASE_URL = "https://openrouter.ai/api/v1"
OUT_PATH = Path("/app/out/graph_basic.md")
QUESTION = "서울의 유명한 맛집 TOP 10 추천해줘"


class State(TypedDict):
    # add_messages: 새 메시지가 덮어쓰지 않고 뒤에 쌓인다
    messages: Annotated[list, add_messages]


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 와 줄바꿈을 바꾼다
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)

    def chatbot(state: State) -> dict:
        # 지금까지의 messages 를 모델에 보내고, 받은 답 하나만 돌려준다
        return {"messages": [llm.invoke(state["messages"])]}

    builder = StateGraph(State)
    builder.add_node("chatbot", chatbot)
    builder.add_edge(START, "chatbot")
    builder.add_edge("chatbot", END)
    graph = builder.compile()

    start = time.monotonic()
    result = graph.invoke({"messages": [("user", QUESTION)]})
    sec = time.monotonic() - start

    messages = result["messages"]
    last = messages[-1].content
    print(f"=== {QUESTION} ({sec:.1f}초) messages {len(messages)}개 -> {last}")

    lines = [
        "# 가장 작은 그래프 실행 확인",
        "",
        f"모델: {model}",
        "",
        "| 질문 | 마지막 메시지 | messages 개수 | 걸린 초 |",
        "|---|---|---|---|",
        f"| {cell(QUESTION)} | {cell(last)} | {len(messages)} | {sec:.1f} |",
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
