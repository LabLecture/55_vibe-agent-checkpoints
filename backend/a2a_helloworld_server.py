"""에이전트 명함(카드)을 내걸고 어떤 말에도 「Hello World」로 답하는 가장 작은 A2A 서버 (모델 없음)."""
import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils import new_agent_text_message

PORT = 9999


class HelloWorldAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        # 받은 말은 보지 않고 늘 같은 메시지 하나로 답한다
        await event_queue.enqueue_event(new_agent_text_message("Hello World"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("cancel 은 지원하지 않습니다")


skill = AgentSkill(
    id="hello_world",
    name="Returns hello world",
    description="just returns hello world",
    tags=["hello world"],
    examples=["hi", "hello world"],
)

agent_card = AgentCard(
    name="Hello World Agent",
    description="Just a hello world agent",
    url=f"http://localhost:{PORT}/",
    version="1.0.0",
    default_input_modes=["text"],
    default_output_modes=["text"],
    capabilities=AgentCapabilities(streaming=True),
    skills=[skill],
)


if __name__ == "__main__":
    # 카드와 실행기를 묶어 /.well-known/agent-card.json 과 JSON-RPC 주소(/)를 내건다
    handler = DefaultRequestHandler(agent_executor=HelloWorldAgentExecutor(), task_store=InMemoryTaskStore())
    app = A2AStarletteApplication(agent_card=agent_card, http_handler=handler)
    uvicorn.run(app.build(), host="0.0.0.0", port=PORT)
