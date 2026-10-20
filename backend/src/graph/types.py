"""학습지 챗봇 그래프의 기록지(State)와 supervisor 의 보기(Router)."""
from typing import Literal, TypedDict

from langgraph.graph import MessagesState

from src.config.agents import TEAM_MEMBERS

# supervisor 가 고를 수 있는 보기: 일꾼 이름 + FINISH
OPTIONS = TEAM_MEMBERS + ["FINISH"]


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""

    next: Literal[*OPTIONS]


class State(MessagesState):
    # 일꾼 이름 목록
    TEAM_MEMBERS: list[str]
    # supervisor 가 고른 다음 칸
    next: str
    # planner 가 세운 계획(JSON 글)
    full_plan: str
