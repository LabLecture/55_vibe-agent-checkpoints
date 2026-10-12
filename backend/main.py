import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SEC = 60  # 모델 호출 제한 시간
DETAIL_MAX_LEN = 200  # 오류 한 줄의 최대 길이

app = FastAPI()

# 브라우저(localhost:3000)에서 오는 요청을 허용한다
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 역할 한 줄과 질문 칸만 둔 프롬프트 템플릿
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "너는 새싹배움 학습지 고객센터 상담원이다"),
        ("human", "{question}"),
    ]
)


class ChatRequest(BaseModel):
    question: str


def build_chain():
    """프롬프트 -> 모델 -> 출력 파서를 | 로 이은 체인을 만든다."""
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
def chat(req: ChatRequest):
    try:
        # 환경 변수가 빠져도 서버가 죽지 않고 502 로 알리도록 여기서 체인을 만든다
        answer = build_chain().invoke({"question": req.question})
    except Exception as e:
        # 시간 초과 · 모델 오류 · 환경 변수 누락 모두 오류 한 줄로 돌려준다
        detail = f"{type(e).__name__}: {e}"
        detail = " ".join(detail.split())[:DETAIL_MAX_LEN]
        raise HTTPException(status_code=502, detail=detail)
    return {"answer": answer}
