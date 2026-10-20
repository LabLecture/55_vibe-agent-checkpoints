"""고객 말 목록을 학습지 챗봇 그래프에 넣어 한 번 돌리고 답 글을 돌려준다."""
import logging

from langchain_core.messages import AIMessage

from src.config.agents import TEAM_MEMBERS
from src.graph.builder import build_graph

logger = logging.getLogger(__name__)

# 그래프는 이 파일에서 한 번만 짓는다
graph = build_graph()


async def run_agent_workflow(user_input_messages: list) -> str:
    if not user_input_messages:
        raise ValueError("Input could not be empty")

    logger.info(f"Starting workflow with user input: {user_input_messages}")

    try:
        # {"role", "content"} 사전은 기록지(MessagesState)가 메시지로 바꿔 준다
        result = await graph.ainvoke(
            {"TEAM_MEMBERS": TEAM_MEMBERS, "messages": user_input_messages},
            config={"recursion_limit": 5},  # 재귀 제한을 5로 설정
        )
    except Exception as e:
        # 한도 초과를 포함한 그래프 오류는 예외 이름만 답으로 돌려준다
        return f"An error occurred: {type(e).__name__}"

    # 끝에서부터 거슬러 내용이 있는 첫 AI 답을 고른다
    for message in reversed(result["messages"]):
        if isinstance(message, AIMessage) and message.content:
            return message.content
    return "No response generated."
