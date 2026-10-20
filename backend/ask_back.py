"""정보가 모자란 말 넷을 하나씩 그래프에 넣어 되묻는지 표로 남긴다.

python ask_back.py
"""
import json
from pathlib import Path

from langchain_core.messages import HumanMessage

from run_graph import RECURSION_LIMIT, cell, run

OUT_PATH = Path("/app/out/ask_back.md")

# (고객 말, 빠진 정보)
CASES = [
    ("제 딸 수업진도 알려주세요", "이름 · 학교 · 학년"),
    ("송혜교 진도 알려주세요", "학교 · 학년"),
    ("쌍문초등학교 6학년 딸 진도요", "이름"),
    ("고마워요", "없음(인사)"),
]


def main() -> None:
    rows, answers = [], []
    for i, (question, missing) in enumerate(CASES, 1):
        # run 이 처음 기록지에 TEAM_MEMBERS 를 넣고 걸음 한도로 돌린다. 오류는 상태 글로 돌아온다
        steps, plan, status, total = run([HumanMessage(question)])
        names = [s[0] for s in steps]
        title = json.loads(plan).get("title", "-") if plan else "-"
        last = steps[-1][1] if steps else "-"
        rows.append(
            f"| {i} | {cell(question)} | {missing} | {' → '.join(names) or '-'} | {names[-1] if names else '-'} "
            f"| {cell(title)} | {cell(last)} | {total:.1f} | {cell(status)} |"
        )
        answers += ["", f"### {i}. {question}", "", last]
    lines = [
        "# 되묻기 표: 정보가 모자란 말 넷",
        "",
        f"말마다 한 턴씩 따로 넣음 · 걸음 한도: {RECURSION_LIMIT}",
        "",
        "| 말 | 고객 말 | 빠진 정보 | 지나간 칸 | 끝난 칸 | planner 계획 제목 | 마지막 답 | 걸린 초 | 상태 |",
        "|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "## 마지막 답 (원문)",
        *answers,
        "",
        "## 사람이 채울 칸",
        "",
        "| 말 | 빠진 정보를 물었나 | 한국어인가 | 도구 이름이 보이나 |",
        "|---|---|---|---|",
        *[f"| {i} |  |  |  |" for i in range(1, len(CASES) + 1)],
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
