from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


@app.post("/chat")
def chat(req: ChatRequest):
    # 아직 LLM을 붙이지 않았으므로 받은 말을 그대로 돌려준다
    return {"answer": req.question}
