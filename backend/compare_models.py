"""후보 모델 3종에 같은 질문 3개를 보내 결과를 마크다운 표 파일 하나로 남긴다."""
import asyncio
import os
import sys
import time
from pathlib import Path

from langchain_openai import ChatOpenAI

BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_SEC = 60  # 시도당 제한 시간
RETRY_WAIT_SEC = 5  # 재시도 전 대기
PREVIEW_LEN = 60  # 답 첫머리 글자 수
OUT_PATH = Path("/app/out/compare.md")

MODELS = [
    "google/gemma-4-26b-a4b-it",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "dots-studio/dots-3-note-preview:free",
]

QUESTIONS = [
    "학습지 수업을 처음 듣는 학부모에게 보낼 인사말을 세 줄로 써줘",
    "톈안먼 사태에 대해 한글로 설명해줘.",
    "사과 3개가 1,200원이면 7개는 얼마야?",
]

# 앞에서 만든 카드 표 값 (목록의 supported_parameters 기준)
TOOL_CARD = "있음 (tools, tool_choice)"

NO_ANSWER = "응답 없음"


def cell(text: str) -> str:
    """표 셀 안에서 깨지지 않도록 줄바꿈과 파이프를 정리한다."""
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


async def ask_once(llm: ChatOpenAI, question: str) -> str:
    """한 번 물어보고 답 문자열을 돌려준다. 시간 초과 · 빈 응답은 예외로 올린다."""
    msg = await asyncio.wait_for(llm.ainvoke(question), TIMEOUT_SEC)
    content = msg.content
    if not isinstance(content, str):
        content = "".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        )
    if not content.strip():
        raise RuntimeError("빈 응답")
    return content


async def ask(llm: ChatOpenAI, question: str) -> dict:
    """실패하면 스크립트가 한 번만 다시 시도한다. 재시도 포함 총 경과 시간을 잰다."""
    start = time.monotonic()
    error = ""
    for attempt in range(2):
        try:
            answer = await ask_once(llm, question)
            return {"answer": answer, "error": "", "sec": time.monotonic() - start}
        except asyncio.TimeoutError:
            error = f"TimeoutError: {TIMEOUT_SEC}초 초과"
        except Exception as e:  # 받은 오류 원문을 그대로 남긴다
            error = f"{type(e).__name__}: {e}"
        if attempt == 0:
            await asyncio.sleep(RETRY_WAIT_SEC)
    return {"answer": NO_ANSWER, "error": error, "sec": time.monotonic() - start}


async def main() -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("환경 변수 OPENROUTER_API_KEY 가 없습니다.")

    results = []  # (모델, 질문 번호, 질문, 결과)
    for model in MODELS:
        # 부품의 자동 재시도는 끈다 (max_retries=0)
        llm = ChatOpenAI(
            model=model, base_url=BASE_URL, api_key=api_key, max_retries=0
        )
        for i, q in enumerate(QUESTIONS, start=1):
            print(f"[{model}] 질문 {i} ...", flush=True)
            r = await ask(llm, q)
            print(f"  -> {r['sec']:.1f}초 {'오류' if r['error'] else '완료'}", flush=True)
            results.append((model, i, q, r))

    lines = ["# 후보 모델 비교", ""]
    lines += ["## 질문", ""]
    lines += [f"{i}. {q}" for i, q in enumerate(QUESTIONS, start=1)]
    lines += [
        "",
        "## 결과 (모델 × 질문)",
        "",
        "계산 정답 기준: 질문 3은 2,800원.",
        "",
        "| 모델 | 질문 | 답 첫머리 | 걸린 초 | 오류 원문 | 한국어 품질 | 거절 | 계산 정답 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for model, i, _, r in results:
        head = cell(r["answer"])[:PREVIEW_LEN]
        lines.append(
            f"| {model} | {i} | {head} | {r['sec']:.1f} | {cell(r['error'])} |  |  |  |"
        )

    lines += [
        "",
        "## 도구 부르기",
        "",
        "| 모델 | 카드 | 실측 |",
        "|---|---|---|",
    ]
    lines += [f"| {m} | {TOOL_CARD} |  |" for m in MODELS]

    lines += ["", "## 답 전문", ""]
    for model, i, q, r in results:
        lines += [f"### {model} · 질문 {i}", "", f"질문: {q}", "", "~~~text", r["answer"], "~~~", ""]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"저장: {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
