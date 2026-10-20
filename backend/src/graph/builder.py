"""칸 다섯을 이어 학습지 챗봇 그래프를 짓는다."""
from langgraph.graph import START, StateGraph

from src.graph.nodes import (
    class_progress_node,
    coordinator_node,
    planner_node,
    supervisor_node,
    user_class_node,
)
from src.graph.types import State


def build_graph():
    builder = StateGraph(State)
    # 선은 START → coordinator 하나만. 나머지 길은 각 칸의 Command 가 정한다
    builder.add_edge(START, "coordinator")
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("planner", planner_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("user_class", user_class_node)
    builder.add_node("class_progress", class_progress_node)
    return builder.compile()
