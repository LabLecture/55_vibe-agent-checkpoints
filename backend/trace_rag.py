"""1-6 RAG 체인(get_chain)에 Langfuse CallbackHandler 를 꽂아 질문 3개를 확정 · 예비 모델로 돌리고, trace 주소를 표로 남긴다."""
import os
import sys
import time
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

from langfuse import get_client
from langfuse.langchain import CallbackHandler

# 판에 따라 propagate_attributes 가 없을 수 있다. 없으면 run_name · langfuse_tags 만 쓴다
try:
    from langfuse import propagate_attributes
except ImportError:
    propagate_attributes = None

# 서버 체인과 1-6 질문 · 표 도우미를 고치지 않고 가져다 쓴다
import main
from search import QUESTIONS, cell

FALLBACK_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"  # CLAUDE.md 의 예비 모델
RETRY_WAIT_SEC = 5  # 재시도 전 대기
PREVIEW_LEN = 80  # 표에 넣을 답 앞부분 글자 수
TAG = "3-1-rag"
OUT_PATH = Path("/app/out/trace_rag.md")


def check_env() -> None:
    """필요한 환경 변수가 있는지 이름만 본다. 값은 찍지 않는다."""
    need = ["OPENROUTER_API_KEY", "LLM_MODEL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]
    missing = [k for k in need if not os.environ.get(k)]
    if not (os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST")):
        missing.append("LANGFUSE_BASE_URL(또는 LANGFUSE_HOST)")
    if missing:
        sys.exit(f"환경 변수가 없습니다: {', '.join(missing)}")


def short_name(model: str) -> str:
    """trace 이름에 넣을 짧은 모델 이름 (회사 이름 · :free 를 뗀다)."""
    return model.split("/")[-1].split(":")[0]


def ask(chain, model: str, q_no: int, question: str) -> dict:
    """막히면 한 번만 다시 보낸다. 보낼 때마다 새 handler 로 trace 하나를 남기고, 재시도 포함 경과 시간을 잰다."""
    name = f"rag-{short_name(model)}-q{q_no}"
    tags = [TAG, model, f"q{q_no}"]
    start = time.monotonic()
    error, trace_id = "", None
    for attempt in range(2):
        # 칸마다 새로 만들어 last_trace_id 가 다른 칸과 섞이지 않게 한다
        handler = CallbackHandler()
        config = {"callbacks": [handler], "run_name": name, "metadata": {"langfuse_tags": tags}}
        ctx = propagate_attributes(trace_name=name, tags=tags) if propagate_attributes else nullcontext()
        try:
            with ctx:
                answer = chain.invoke(question, config=config)
            return {"name": name, "answer": answer, "error": "", "sends": attempt + 1,
                    "trace_id": handler.last_trace_id, "sec": time.monotonic() - start}
        except Exception as e:  # 받은 오류 원문을 그대로 남긴다
            error = f"{type(e).__name__}: {e}"
            trace_id = handler.last_trace_id
            print(f"  [다시 보냄] {error}" if attempt == 0 else f"  [실패] {error}", flush=True)
        if attempt == 0:
            time.sleep(RETRY_WAIT_SEC)
    return {"name": name, "answer": "", "error": error, "sends": 2,
            "trace_id": trace_id, "sec": time.monotonic() - start}


def trace_link(langfuse, trace_id) -> str:
    """trace 주소를 만든다. 못 만들면 id 를 그대로 적는다."""
    if not trace_id:
        return "(없음)"
    try:
        return langfuse.get_trace_url(trace_id=trace_id) or trace_id
    except Exception:
        return trace_id


def main_run() -> None:
    check_env()
    models = [os.environ["LLM_MODEL"], FALLBACK_MODEL]
    langfuse = get_client()
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    results = []  # (모델, 질문 번호, 질문, 결과)
    try:
        for model in models:
            # get_chain() 은 lru_cache 로 한 번만 만들고 LLM_MODEL 을 그때 읽으므로, 바꾼 뒤 캐시를 비운다
            os.environ["LLM_MODEL"] = model
            main.get_chain.cache_clear()
            chain = main.get_chain()
            for q_no, q in enumerate(QUESTIONS, start=1):
                print(f"[{model}] 질문 {q_no} ...", flush=True)
                r = ask(chain, model, q_no, q)
                print(f"  -> {r['sec']:.1f}초 {'오류' if r['error'] else '완료'}", flush=True)
                results.append((model, q_no, q, r))
    finally:
        # 끝나기 전에 쌓인 기록을 Langfuse 로 밀어 보낸다
        langfuse.flush()

    lines = [
        "# 3-1 RAG 체인 Langfuse trace (질문 3 × 모델 2)",
        "",
        f"확정 모델: {models[0]} · 예비 모델: {models[1]} · 실행: {started}",
        "",
        f"태그: 모든 trace 에 `{TAG}` · 모델 이름 · 질문 번호(q1~q3)",
        "",
        "## 질문",
        "",
    ]
    lines += [f"{i}. {q}" for i, q in enumerate(QUESTIONS, start=1)]
    lines += [
        "",
        "## 결과 (모델 × 질문)",
        "",
        "뒤 네 칸은 Langfuse 화면에서 읽어 사람이 채운다.",
        "",
        "| 칸 | 모델 | 질문 | 전체 걸린 초 | 보낸 횟수 | 답 앞부분 | trace 이름 | trace 주소 "
        "| 모델 줄 초 | 문서 찾기 줄 초 | 들어간 토큰 | 나온 토큰 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for no, (model, q_no, q, r) in enumerate(results, start=1):
        body = r["error"] or r["answer"][:PREVIEW_LEN]
        lines.append(
            f"| {no} | {cell(model)} | {q_no}. {cell(q)} | {r['sec']:.1f} | {r['sends']} | {cell(body)} "
            f"| {cell(r['name'])} | {cell(trace_link(langfuse, r['trace_id']))} |  |  |  |  |"
        )
    lines += ["", f"보낸 횟수 합(Tracing 목록에 뜰 trace 수): {sum(r['sends'] for *_, r in results)}"]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main_run()
