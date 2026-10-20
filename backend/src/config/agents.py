"""학습지 챗봇 그래프의 칸마다 쓸 모델 종류를 정한다."""
from typing import Literal

# 모델 종류
LLMType = Literal["basic", "reasoning", "supervisor"]

# 칸 이름 → 모델 종류
AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "basic",
    "planner": "basic",
    "supervisor": "supervisor",
    "user_class": "basic",
    "class_progress": "basic",
}

# supervisor 가 일을 맡기는 일꾼 이름 목록
TEAM_MEMBERS = ["user_class", "class_progress"]
