import asyncio
import logging
import os
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

# 저장할 때와 같은 임베딩 클래스와 저장 경로를 그대로 쓴다 (질문 앞에는 "query: " 가 붙는다)
from ingest import STORE_DIR, E5Embeddings

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SEC = 60  # 모델 호출 제한 시간
TOP_K = 3  # 질문마다 찾을 조각 수
NO_ANSWER = "죄송합니다. 해당 질문에 대해서는 답변을 할 수 없습니다. 다른 질문을 해주세요."

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


def format_docs(docs) -> str:
    """찾은 조각의 본문만 빈 줄로 이어 붙인다."""
    return "\n\n".join(doc.page_content for doc in docs)


@lru_cache
def get_chain():
    """문서 찾기 -> 프롬프트 -> 모델 -> 출력 파서 체인을 처음 요청 때 한 번 만든다."""
    # 저장 폴더는 읽기만 한다. 없으면 새로 만들지 않고 실패시킨다
    if not STORE_DIR.exists():
        raise RuntimeError(f"저장 폴더가 없습니다: {STORE_DIR}")
    store = Chroma(persist_directory=str(STORE_DIR), embedding_function=E5Embeddings())
    retriever = store.as_retriever(
        search_type="similarity", search_kwargs={"k": TOP_K}
    )

    # 템플릿 변수는 {context} 와 {question} 둘뿐이다. 거절 문장은 미리 이어 붙인다
    system = (
        "너는 새싹배움 학습지 고객센터 상담원이다\n"
        "아래 규칙을 지켜 답한다.\n"
        f"1. 문서에 답이 없으면 이 문장 그대로만 답한다: {NO_ANSWER}\n"
        "2. 문서에서 직접 나오지 않은 것은 지어내지 않는다.\n"
        "3. 한국어로 답한다.\n"
        "CONTEXT START BLOCK\n"
        "{context}\n"
        "CONTEXT END BLOCK"
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
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
    # 질문 글자 하나를 받아, 찾은 조각은 context 로, 질문은 그대로 question 으로 넘긴다
    return (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )


@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        # 단계별 제한과 별개로 전체 60초를 넘기면 끊는다
        answer = await asyncio.wait_for(
            get_chain().ainvoke(req.question), TIMEOUT_SEC
        )
    except Exception as e:
        # 자세한 내용은 서버 로그에만 남기고, 응답에는 예외 이름만 담는다
        logger.exception("LLM 호출 실패")
        raise HTTPException(status_code=502, detail=type(e).__name__)
    return {"answer": answer}
