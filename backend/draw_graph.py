"""학습지 챗봇 그래프의 Mermaid 글을 남긴다. 모델은 부르지 않는다."""
from pathlib import Path

from src.graph.builder import build_graph

OUT_PATH = Path("/app/out/manus_graph.md")


def main() -> None:
    mermaid = build_graph().get_graph().draw_mermaid().strip()
    print(mermaid)
    lines = [
        "# 학습지 챗봇 그래프 (coordinator · planner · supervisor · 일꾼 둘)",
        "",
        "```mermaid",
        mermaid,
        "```",
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"그림 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
