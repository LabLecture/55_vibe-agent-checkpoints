"""chat 주소로 받은 말 목록을 학습지 챗봇 그래프에 넘기는 서버 몸통."""
import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.service.workflow_service import run_agent_workflow

# uvicorn 은 앱 로그를 INFO 로 내보내지 않으므로 여기서 건다
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TIMEOUT_SEC = 180  # 요청 전체 한도

app = FastAPI()

# 브라우저(localhost:3000)에서 오는 요청을 허용한다
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        # 받은 목록을 {"role", "content"} 사전 목록으로 옮긴다
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        result = await asyncio.wait_for(run_agent_workflow(messages), TIMEOUT_SEC)
        logger.info(f"chat_endpoint, result={result}")
        return {"response": result}
    except Exception as e:
        # 자세한 내용은 서버 로그에만 남기고, 응답에는 예외 이름만 담는다
        logger.exception("chat_endpoint 실패")
        raise HTTPException(status_code=500, detail=type(e).__name__)
