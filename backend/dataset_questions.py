"""1-6 표의 질문 셋과 기대답으로 Langfuse 데이터셋 「saessak-questions」 를 만들고(이미 있으면 확인만), 다시 읽은 항목을 표로 남긴다."""
import json
import sys
from pathlib import Path

from langfuse import get_client

# 서버의 거절 문장 · 실습2 의 키 확인 · 표 도우미를 고치지 않고 가져다 쓴다
from main import NO_ANSWER
from search import cell
from trace_rag import check_env

DATASET_NAME = "saessak-questions"
SOURCE_TABLE = Path("/app/out/chat_questions_rag.md")  # 1-6 표 (읽기만)
IN_DOC = "문서에 있는 답"  # 「문서에 있는 답인가(오늘)」 칸이 이 값이면 그 줄의 답 전문을 기대답으로 쓴다
PREVIEW_LEN = 80  # 표에 넣을 기대답 앞부분 글자 수
OUT_PATH = Path("/app/out/dataset_questions.md")


def read_source() -> list[tuple[str, str]]:
    """1-6 표에서 (질문, 기대답) 셋을 읽는다."""
    pairs = []
    for line in SOURCE_TABLE.read_text(encoding="utf-8").splitlines():
        parts = [p.strip() for p in line.split("|")]
        # 칸: 1 질문 · 2 답 전문(JSON) · 6 문서에 있는 답인가(오늘). 머리 줄 · 나눔 줄은 건너뛴다
        if len(parts) < 8 or parts[1] in ("질문", "---"):
            continue
        question, body, verdict = parts[1], parts[2], parts[6]
        expected = json.loads(body)["answer"] if verdict == IN_DOC else NO_ANSWER
        pairs.append((question, expected))
    if len(pairs) != 3:  # 잘못 읽은 채 올리지 않게 멈춘다
        sys.exit(f"1-6 표에서 읽은 줄이 3이 아닙니다: {len(pairs)}")
    return pairs


def main_run() -> None:
    check_env()
    pairs = read_source()
    langfuse = get_client()
    try:
        try:
            langfuse.get_dataset(name=DATASET_NAME)
            status = "이미 있음 → 확인만"
        except Exception as e:
            # 판마다 import 경로가 달라 예외 이름으로 '없음' 을 가린다. 그 밖의 오류는 그대로 멈춘다
            if type(e).__name__ != "NotFoundError":
                raise
            langfuse.create_dataset(name=DATASET_NAME, description="1-6 RAG 질문 셋과 기대답")
            for q, a in pairs:
                langfuse.create_dataset_item(
                    dataset_name=DATASET_NAME,
                    input={"question": q},
                    expected_output={"answer": a},
                    metadata={"source": "1-6 chat_questions_rag.md"},
                )
            status = "새로 만듦"
        print(f"[{DATASET_NAME}] {status}", flush=True)
        # 올린 것이 실제로 들어갔는지 Langfuse 에서 다시 읽는다
        items = langfuse.get_dataset(name=DATASET_NAME).items
    finally:
        # 끝나기 전에 쌓인 기록을 Langfuse 로 밀어 보낸다
        langfuse.flush()

    # 1-6 표의 질문 차례로 늘어놓는다 (표에 없는 항목은 뒤에)
    order = {q: i for i, (q, _) in enumerate(pairs)}
    items = sorted(items, key=lambda it: order.get((it.input or {}).get("question"), len(order)))

    lines = [
        "# 3-1 Langfuse 데이터셋",
        "",
        "마지막 칸은 Langfuse 화면에서 읽어 사람이 채운다.",
        "",
        "| 데이터셋 이름 | 상태 | 항목 수(Langfuse 에서 다시 읽음) | Langfuse 화면 항목 수가 같은가 |",
        "|---|---|---|---|",
        f"| {DATASET_NAME} | {status} | {len(items)} |  |",
        "",
        "## 항목",
        "",
        "| 차례 | 질문 | 기대답 앞부분 |",
        "|---|---|---|",
    ]
    for no, it in enumerate(items, start=1):
        q = (it.input or {}).get("question", str(it.input))
        a = (it.expected_output or {}).get("answer", str(it.expected_output))
        lines.append(f"| {no} | {cell(q)} | {cell(a[:PREVIEW_LEN])} |")
        print(f"  {no}. {q} -> {a[:PREVIEW_LEN]}", flush=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main_run()
