"""채팅 그래프와 갈림길 그래프를 StateGraph 로 짓고, stream 으로 칸마다 한 걸음씩 돌려 표로 남긴다."""
import os
import random
import sys
import time
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

BASE_URL = "https://openrouter.ai/api/v1"
OUT_PATH = Path("/app/out/graph_steps.md")
QUESTION = "서울의 유명한 맛집 TOP 10 추천해줘"
MOOD_INPUT = {"graph_state": "Hi, this is Intel"}
MOOD_RUNS = 5
HEAD = 80  # 앞부분으로 보여 줄 글자 수


class ChatState(TypedDict):
    # add_messages: 새 메시지가 덮어쓰지 않고 뒤에 쌓인다
    messages: Annotated[list, add_messages]


class MoodState(TypedDict):
    # 여섯 칸 가운데 지금은 graph_state 만 쓴다
    graph_state: str
    goal: str
    todo: list
    current_job: str
    total_time: int
    time_spend: int


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 와 줄바꿈을 바꾼다
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def node_1(state: MoodState) -> dict:
    return {"graph_state": state["graph_state"] + " I am"}


def node_2(state: MoodState) -> dict:
    return {"graph_state": state["graph_state"] + " happy!"}


def node_3(state: MoodState) -> dict:
    return {"graph_state": state["graph_state"] + " sad!"}


def decide_mood(state: MoodState) -> Literal["node_2", "node_3"]:
    # 반반으로 다음 칸을 고른다
    return "node_2" if random.random() < 0.5 else "node_3"


def build_mood_graph():
    builder = StateGraph(MoodState)
    builder.add_node("node_1", node_1)
    builder.add_node("node_2", node_2)
    builder.add_node("node_3", node_3)
    builder.add_edge(START, "node_1")
    builder.add_conditional_edges("node_1", decide_mood)
    builder.add_edge("node_2", END)
    builder.add_edge("node_3", END)
    return builder.compile()


def build_chat_graph(llm):
    def chatbot(state: ChatState) -> dict:
        # 지금까지의 messages 를 모델에 보내고, 받은 답 하나만 돌려준다
        return {"messages": [llm.invoke(state["messages"])]}

    builder = StateGraph(ChatState)
    builder.add_node("chatbot", chatbot)
    builder.add_edge(START, "chatbot")
    builder.add_edge("chatbot", END)
    return builder.compile()


def main() -> None:
    model = os.environ.get("LLM_MODEL")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not model:
        sys.exit("환경 변수 LLM_MODEL 이 없습니다.")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    llm = ChatOpenAI(model=model, base_url=BASE_URL, api_key=api_key, max_retries=0)

    # 채팅 그래프: stream 기본값(updates)은 칸이 끝날 때마다 {칸 이름: 돌려준 것} 을 준다
    chat = build_chat_graph(llm)
    chat_input = {"messages": [("user", QUESTION)]}
    count = len(chat_input["messages"])
    steps, last = [], ""
    start = time.monotonic()
    for step, chunk in enumerate(chat.stream(chat_input), 1):
        for name, update in chunk.items():
            new = update["messages"]
            count += len(new)
            last = new[-1].content
            steps.append(name)
            print(f"[채팅] STEP {step} · {name} · {cell(last)[:HEAD]}")
    chat_sec = time.monotonic() - start

    # 갈림길 그래프: 다섯 번 돌려 어느 길로 갔는지 본다
    mood = build_mood_graph()
    mood_rows = []
    for run in range(1, MOOD_RUNS + 1):
        path, state = [], MOOD_INPUT["graph_state"]
        start = time.monotonic()
        for step, chunk in enumerate(mood.stream(MOOD_INPUT), 1):
            for name, update in chunk.items():
                state = update["graph_state"]
                path.append(name)
                print(f"[갈림길 {run}] STEP {step} · {name} · {state[:HEAD]}")
        mood_rows.append((run, path, state, time.monotonic() - start))

    lines = [
        "# 그래프 STEP 확인",
        "",
        f"모델: {model}",
        "",
        "## 채팅 그래프",
        "",
        "```mermaid",
        chat.get_graph().draw_mermaid().strip(),
        "```",
        "",
        "| 번째 | STEP 순서 | messages 개수 | 마지막 답 앞부분 | 걸린 초 | STEP 순서가 그림의 선 위에 있는가 |",
        "|---|---|---|---|---|---|",
        f"| 1 | {' → '.join(steps)} | {count} | {cell(last)[:HEAD]} | {chat_sec:.1f} |  |",
        "",
        "## 갈림길 그래프",
        "",
        "```mermaid",
        mood.get_graph().draw_mermaid().strip(),
        "```",
        "",
        "| 번째 | STEP 순서 | 마지막 graph_state | 걸린 초 | STEP 순서가 그림의 선 위에 있는가 |",
        "|---|---|---|---|---|",
    ]
    for run, path, state, sec in mood_rows:
        lines.append(f"| {run} | {' → '.join(path)} | {cell(state)} | {sec:.3f} |  |")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
