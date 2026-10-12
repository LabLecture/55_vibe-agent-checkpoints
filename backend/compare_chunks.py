"""조각 크기(200/500/1000)를 바꿔가며 저장하고, 같은 질문의 1위 조각을 마크다운 표 파일 하나로 남긴다. LLM은 부르지 않는다."""
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 임베딩 클래스(접두어 "passage: " / "query: ")와 PDF 읽기는 앞에서 만든 것을 그대로 쓴다
from ingest import PREVIEW_LEN, E5Embeddings, load_pdfs
from search import QUESTIONS, cell

# 크기마다 겹침은 크기의 10%. 기본 저장 폴더(vector_store)는 건드리지 않고 크기별 폴더를 따로 쓴다
SIZES = [(200, 20), (500, 50), (1000, 100)]
STORE_ROOT = Path("/app")
OUT_PATH = Path("/app/out/chunk_compare.md")


def store_dir(chunk_size: int) -> Path:
    return STORE_ROOT / f"vector_store_{chunk_size}"


def main() -> None:
    pages = load_pdfs()
    embeddings = E5Embeddings()  # 모델은 한 번만 올려 세 크기에서 같이 쓴다

    rows = []  # 표의 행
    fulls = []  # 아래쪽에 적을 1위 조각 전문
    totals = {}  # 크기별 전체 조각 수
    cell_no = 0

    for chunk_size, overlap in SIZES:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap
        )
        chunks = splitter.split_documents(pages)
        totals[chunk_size] = len(chunks)
        print(f"크기 {chunk_size} / 겹침 {overlap}: 조각 {len(chunks)}개")

        # 크기별 폴더는 돌릴 때마다 지우고 새로 만든다
        target = store_dir(chunk_size)
        if target.exists():
            shutil.rmtree(target)
        store = Chroma.from_documents(
            documents=chunks, embedding=embeddings, persist_directory=str(target)
        )

        for q_no, question in enumerate(QUESTIONS, start=1):
            cell_no += 1
            doc, distance = store.similarity_search_with_score(question, k=1)[0]
            text = doc.page_content
            rows.append(
                f"| {cell_no} | {chunk_size}/{overlap} | {len(chunks)} "
                f"| {cell(f'{q_no}. {question}')} | {cell(doc.metadata['source'])} "
                f"| {doc.metadata['page']} | {len(text)} | {cell(text[:PREVIEW_LEN])} "
                f"| {distance:.4f} |  |"
            )
            fulls.append(
                f"### 칸 {cell_no} — 크기 {chunk_size} / 질문 {q_no}\n\n"
                f"> {question}\n\n```\n{text}\n```\n"
            )

    lines = [
        "| 칸 | 크기/겹침 | 전체 조각 수 | 질문 | 문서 | 쪽 | 길이 | 조각 앞부분 | 거리(작을수록 가깝다) | 답 문장이 들어 있나 |",
        "|---|---|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "## 1위 조각 전문",
        "",
        *fulls,
    ]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
