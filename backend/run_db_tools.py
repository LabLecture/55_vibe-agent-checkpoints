"""DB 도구 둘을 모델 · 그래프 없이 .invoke 로 하나씩 불러 돌려준 글을 표로 남긴다.

인자 없이: ①~④ 를 불러 표를 새로 쓴다 (db 상자가 떠 있을 때)
인자 5: ⑤ 하나만 불러 표 끝에 덧붙인다 (db 상자를 멈춘 뒤, 상자 안에서는 db 를 멈출 수 없어 나눔)
"""
import sys
import time
from pathlib import Path

from src.tools.class_progress import class_progress_tool
from src.tools.user_class import user_class_tool

OUT_PATH = Path("/app/out/db_tools.md")

USER_CLASS_ARGS = {"user_name": "송혜교", "user_school": "쌍문초등학교", "user_grade": 6}

CASES = [
    ("①", user_class_tool, USER_CLASS_ARGS),
    ("②", class_progress_tool, {"user_name": "송혜교", "class_data": "AI수학 프로그램", "class_id": "1"}),
    ("③", class_progress_tool, {"user_name": "장원영", "class_data": "샘플", "class_id": "1"}),
    ("④", user_class_tool, {"user_name": "송혜교", "user_school": "미아초등학교", "user_grade": 6}),
]
DB_DOWN_CASE = ("⑤ db 상자 멈춤", user_class_tool, USER_CLASS_ARGS)

HEADER = [
    "# DB 도구 단독 호출 (user_class_tool · class_progress_tool)",
    "",
    "실행: `도구.invoke(넣은 값)` 을 하나씩 부름 (모델 · 그래프 없음). ⑤ 는 `docker compose stop db` 뒤 ① 과 같은 값",
    "",
    "| 번호 | 도구 | 넣은 값 | 돌려준 글 원문 | 걸린 초 | 섹션 3-3 표와 같은가 |",
    "|---|---|---|---|---|---|",
]


def cell(text: str) -> str:
    # 표가 깨지지 않게 | 는 바꾸고 줄바꿈은 <br> 로 (원문 줄 나눔을 보이게)
    return str(text).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def run(label, t, args) -> str:
    start = time.monotonic()
    try:
        out = t.invoke(args)
    except Exception as e:  # 도구 밖에서 난 오류도 원문 그대로 남긴다
        out = f"{type(e).__name__}: {e}"
    sec = time.monotonic() - start
    print(f"=== {label} {t.name} {args} ({sec:.2f}초)\n{out}")
    return f"| {label} | {t.name} | {cell(args)} | {cell(out)} | {sec:.2f} |  |"


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ["5"]:
        with OUT_PATH.open("a", encoding="utf-8") as f:
            f.write(run(*DB_DOWN_CASE) + "\n")
    else:
        rows = [run(*c) for c in CASES]
        OUT_PATH.write_text("\n".join(HEADER + rows) + "\n", encoding="utf-8")
    print(f"표 저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
