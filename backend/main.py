import asyncio
import logging
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SEC = 60  # 모델 호출 제한 시간

logger = logging.getLogger(__name__)

app = FastAPI()

# 브라우저(localhost:3000)에서 오는 요청을 허용한다
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str


@lru_cache
def get_chain():
    """프롬프트 -> 모델 -> 출력 파서 체인을 처음 요청 때 한 번 만든다."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "너는 새싹배움 학습지 고객센터 상담원이다"),
            ("human", "{question}"),
        ]
    )
    # 모델 이름과 키는 환경 변수로만 읽는다. 자동 재시도는 끈다 (max_retries=0)
    llm = ChatOpenAI(
        model=os.environ["LLM_MODEL"],
        base_url=BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=TIMEOUT_SEC,
        max_retries=0,
    )
    return prompt | llm | StrOutputParser()


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        # 단계별 제한과 별개로 전체 60초를 넘기면 끊는다
        answer = await asyncio.wait_for(
            get_chain().ainvoke({"question": req.question}), TIMEOUT_SEC
        )
    except Exception as e:
        # 자세한 내용은 서버 로그에만 남기고, 응답에는 예외 이름만 담는다
        logger.exception("LLM 호출 실패")
        raise HTTPException(status_code=502, detail=type(e).__name__)
    return {"answer": answer}
