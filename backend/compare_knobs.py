"""1-6 RAG 체인의 손잡이(k · 조각 크기 · 틀 · 모델)를 하나씩만 바꿔, 같은 질문 4개의 답을 마크다운 표 파일 하나로 남긴다."""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 서버 · 저장 · 1-4 비교 스크립트의 값과 함수를 그대로 쓴다
from compare_chunks import store_dir
from ingest import STORE_DIR, E5Embeddings, load_pdfs
from main import BASE_URL, NO_ANSWER, TIMEOUT_SEC, TOP_K, format_docs
from search import cell

RETRY_WAIT_SEC = 5  # 재시도 전 대기
FALLBACK_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"  # CLAUDE.md 의 예비 모델
QUESTIONS_DIR = Path("/app/out/questions")
OUT_PATH = Path("/app/out/knob_compare.md")

# 서버 get_chain() 의 틀 글을 글자 그대로 옮긴다
SYSTEM_BASE = (
    "너는 새싹배움 학습지 고객센터 상담원이다\n"
    "아래 규칙을 지켜 답한다.\n"
    f"1. 문서에 답이 없으면 이 문장 그대로만 답한다: {NO_ANSWER}\n"
    "2. 문서에서 직접 나오지 않은 것은 지어내지 않는다.\n"
    "3. 한국어로 답한다.\n"
    "CONTEXT START BLOCK\n"
    "{context}\n"
    "CONTEXT END BLOCK"
)
# 규칙 1~3 과 그 앞 안내 줄만 뺀 틀
SYSTEM_NO_RULES = (
    "너는 새싹배움 학습지 고객센터 상담원이다\n"
    "CONTEXT START BLOCK\n"
    "{context}\n"
    "CONTEXT END BLOCK"
)

# 줄마다 기준에서 한 칸만 바꾼다. size 500 은 기본 저장 폴더(vector_store)
BASE = {"k": TOP_K, "size": 500, "system": SYSTEM_BASE, "model": None}
ROWS = [
    ("기준 1차", "없음", {}),
    ("기준 2차", "없음", {}),
    ("k 1", "k 3 → 1", {"k": 1}),
    ("k 8", "k 3 → 8", {"k": 8}),
    ("크기 200", "저장 폴더 500 → 200", {"size": 200}),
    ("크기 1000", "저장 폴더 500 → 1000", {"size": 1000}),
    ("규칙 뺀 틀", "틀에서 규칙 1~3 뺌", {"system": SYSTEM_NO_RULES}),
    ("예비 모델", f"모델 → {FALLBACK_MODEL}", {"model": FALLBACK_MODEL}),
]


def load_questions() -> list[str]:
    """q1 · q2 · q3 의 질문을 그대로 읽고 넷째 질문을 붙인다."""
    qs = [
        json.loads((QUESTIONS_DIR / f"q{i}.json").read_text(encoding="utf-8"))["question"]
        for i in (1, 2, 3)
    ]
    return qs + ["학부모 앱에서 할 수 있는 일을 모두 알려 주세요"]


def open_stores(embeddings: E5Embeddings) -> dict[int, Chroma]:
    """크기별 저장 폴더를 연다. 기본 폴더는 읽기만, 200 · 1000 은 없을 때만 1-4 방법(겹침 10%)으로 만든다."""
    if not STORE_DIR.exists():
        sys.exit(f"저장 폴더가 없습니다: {STORE_DIR} (먼저 ingest.py 를 실행하세요)")
    stores = {500: Chroma(persist_directory=str(STORE_DIR), embedding_function=embeddings)}
    pages = None
    for size in (200, 1000):
        target = store_dir(size)
        if target.exists():
            stores[size] = Chroma(persist_directory=str(target), embedding_function=embeddings)
            continue
        if pages is None:
            pages = load_pdfs()
        splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=size // 10)
        chunks = splitter.split_documents(pages)
        print(f"{target} 없음 → 새로 만듦 (크기 {size} / 겹침 {size // 10}: 조각 {len(chunks)}개)")
        stores[size] = Chroma.from_documents(
            documents=chunks, embedding=embeddings, persist_directory=str(target)
        )
    return stores


def build_chain(retriever, system: str, model: str):
    """서버 get_chain() 과 같은 모양의 체인을 만든다."""
    prompt = ChatPromptTemplate.from_messages([("system", system), ("human", "{question}")])
    llm = ChatOpenAI(
        model=model,
        base_url=BASE_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=TIMEOUT_SEC,
        max_retries=0,
    )
    return (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )


async def ask(chain, question: str) -> dict:
    """막히면 한 번만 다시 보낸다. 그래도 안 되면 오류 원문을 남긴다. 재시도 포함 경과 시간을 잰다."""
    start = time.monotonic()
    error = ""
    for attempt in range(2):
        try:
            answer = await asyncio.wait_for(chain.ainvoke(question), TIMEOUT_SEC)
            return {"answer": answer, "error": "", "sec": time.monotonic() - start}
        except asyncio.TimeoutError:
            error = f"TimeoutError: {TIMEOUT_SEC}초 초과"
        except Exception as e:  # 받은 오류 원문을 그대로 남긴다
            error = f"{type(e).__name__}: {e}"
        if attempt == 0:
            await asyncio.sleep(RETRY_WAIT_SEC)
    return {"answer": "", "error": error, "sec": time.monotonic() - start}


def full(text: str) -> str:
    """답 전문을 표 셀 하나에 넣는다. 줄바꿈은 <br> 로 남긴다."""
    return cell(text.replace("\r\n", "\n").replace("\n", "<br>"))


async def main() -> None:
    if not os.environ.get("OPENROUTER_API_KEY"):
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")
    questions = load_questions()
    stores = open_stores(E5Embeddings())  # 임베딩 모델은 한 번만 올린다

    results = []  # (줄 이름, 질문 번호, 결과)
    for name, _, change in ROWS:
        cfg = {**BASE, **change}
        retriever = stores[cfg["size"]].as_retriever(
            search_type="similarity", search_kwargs={"k": cfg["k"]}
        )
        chain = build_chain(retriever, cfg["system"], cfg["model"] or os.environ["LLM_MODEL"])
        for q_no, q in enumerate(questions, start=1):
            print(f"[{name}] 질문 {q_no} ...", flush=True)
            r = await ask(chain, q)
            # 체인 안 retriever 와 같은 검색을 한 번 더 해 모델이 받은 조각을 센다
            docs = retriever.invoke(q)
            r["chunks"] = len(docs)
            r["chars"] = len(format_docs(docs))
            print(f"  -> {r['sec']:.1f}초 {'오류' if r['error'] else '완료'}", flush=True)
            results.append((name, q_no, r))

    lines = ["# 1-6 RAG 손잡이 견주기", "", "## 줄", ""]
    lines += ["| 줄 | 기준에서 바꾼 칸 |", "|---|---|"]
    lines += [f"| {name} | {cell(desc)} |" for name, desc, _ in ROWS]
    lines += [
        "",
        f"기준: k {TOP_K} · 저장 폴더 vector_store(크기 500) · 서버 틀 · 모델 {os.environ['LLM_MODEL']}",
        "",
        "## 질문",
        "",
    ]
    lines += [f"{i}. {q}" for i, q in enumerate(questions, start=1)]
    lines += [
        "",
        "## 결과 (줄 × 질문)",
        "",
        "| 칸 | 줄 | 질문 | 답 전문 | 걸린 초 | 상태 | 받은 조각 수 | 받은 글자 수 | 문서에 있는 답인가 | 기준과 견주면 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for no, (name, q_no, r) in enumerate(results, start=1):
        body = full(r["error"]) if r["error"] else full(r["answer"])
        state = cell(r["error"]) if r["error"] else "완료"
        lines.append(
            f"| {no} | {name} | {q_no} | {body} | {r['sec']:.1f} | {state} "
            f"| {r['chunks']} | {r['chars']} |  |  |"
        )

    # 기준 1차 · 2차의 답을 질문마다 글자까지 견준다
    first = {q: r for n, q, r in results if n == "기준 1차"}
    second = {q: r for n, q, r in results if n == "기준 2차"}
    lines += ["", "## 기준 두 번 견주기", "", "| 질문 | 글자까지 같은가 |", "|---|---|"]
    for q_no in range(1, len(questions) + 1):
        a, b = first[q_no], second[q_no]
        if a["error"] or b["error"]:
            same = "견줄 수 없음 (오류)"
        else:
            same = "예" if a["answer"] == b["answer"] else "아니오"
        lines.append(f"| {q_no} | {same} |")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
