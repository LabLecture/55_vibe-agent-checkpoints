"""저장된 Chroma 에서 질문마다 가까운 조각 3개를 찾아 마크다운 표 파일로 남긴다. LLM은 부르지 않는다."""
import sys
from pathlib import Path

from langchain_chroma import Chroma

# 저장할 때와 같은 임베딩 클래스·모델·저장 경로를 그대로 쓴다 (질문 앞에는 "query: " 가 붙는다)
from ingest import PREVIEW_LEN, STORE_DIR, E5Embeddings

TOP_K = 3  # 질문마다 찾을 조각 수
OUT_PATH = Path("/app/out/search.md")

QUESTIONS = [
    "교재는 언제 배송되나요?",
    "아이 공부가 어디까지 됐나요?",
    "내일 서울 날씨는 어때요?",
]


def cell(text: str) -> str:
    """표 셀 안에서 깨지지 않도록 줄바꿈과 파이프를 정리한다."""
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def main() -> None:
    # 저장 폴더는 읽기만 한다. 없으면 새로 만들지 않고 종료한다
    if not STORE_DIR.exists():
        sys.exit(f"저장 폴더가 없습니다: {STORE_DIR} (먼저 ingest.py 를 실행하세요)")

    store = Chroma(persist_directory=str(STORE_DIR), embedding_function=E5Embeddings())

    lines = [
        "| 질문 | 순위 | 문서 | 쪽 | 조각 앞부분 | 거리(작을수록 가깝다) |",
        "|---|---|---|---|---|---|",
    ]
    for q_no, question in enumerate(QUESTIONS, start=1):
        # 점수는 거리 값이다 (작을수록 가깝다)
        results = store.similarity_search_with_score(question, k=TOP_K)
        for rank, (doc, distance) in enumerate(results, start=1):
            # 쪽은 저장할 때 이미 1부터 센 번호로 넣어 두었다
            lines.append(
                f"| {cell(f'{q_no}. {question}')} | {rank} | {cell(doc.metadata['source'])} "
                f"| {doc.metadata['page']} | {cell(doc.page_content[:PREVIEW_LEN])} | {distance:.4f} |"
            )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
