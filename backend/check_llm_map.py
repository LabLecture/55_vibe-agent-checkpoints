"""칸별 모델 종류 표, basic 모델에 「안녕」 한 번, 같은 종류 재호출이 같은 물건인지를 표로 남긴다."""
import time
from pathlib import Path

from src.agents.llm import get_llm_by_type
from src.config.agents import AGENT_LLM_MAP

OUT_PATH = Path("/app/out/llm_map.md")
QUESTION = "안녕"


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 와 줄바꿈을 바꾼다
    return str(text).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def main() -> None:
    start = time.monotonic()
    answer = get_llm_by_type("basic").invoke(QUESTION).content
    sec = time.monotonic() - start
    same = get_llm_by_type("basic") is get_llm_by_type("basic")
    print(f"=== {QUESTION} ({sec:.1f}초) -> {answer}")
    print(f"같은 물건: {same}")

    lines = ["# 모델 표 확인", "", "| 칸 | 종류 |", "|---|---|"]
    lines += [f"| {name} | {kind} |" for name, kind in AGENT_LLM_MAP.items()]
    lines += [
        "",
        "| 종류 | 질문 | 답 | 걸린 초 |",
        "|---|---|---|---|",
        f"| basic | {QUESTION} | {cell(answer)} | {sec:.1f} |",
        "",
        "| 확인 | 결과 |",
        "|---|---|",
        f"| get_llm_by_type(\"basic\") 두 번이 같은 물건 | {same} |",
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
