"""docs 폴더의 PDF를 조각내 임베딩하고 Chroma(vector_store 폴더)에 저장한다. LLM은 부르지 않는다."""
import shutil
import sys
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ---- 설정: 값은 여기 한 곳에서만 바꾼다 ----
CHUNK_SIZE = 500  # 조각 크기(글자 수)
CHUNK_OVERLAP = 20  # 이웃 조각과 겹치는 글자 수
MODEL_NAME = "intfloat/multilingual-e5-small"
DOCS_DIR = Path("/app/docs")
STORE_DIR = Path("/app/vector_store")
PREVIEW_COUNT = 3  # 미리보기로 보여줄 첫 조각 수
PREVIEW_LEN = 50  # 조각 앞부분 글자 수

# e5 모델 안내: 문서 조각에는 "passage: ", 질문에는 "query: " 를 붙여 임베딩한다
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


class E5Embeddings(Embeddings):
    """e5 접두어 규칙을 지켜 벡터를 만든다. 접두어는 벡터 계산에만 쓰고 저장 본문에는 넣지 않는다."""

    def __init__(self, model_name: str = MODEL_NAME):
        # CPU 전용, 벡터 길이를 1로 맞춰(정규화) 코사인 유사도에 쓰기 좋게 한다
        self._model = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.embed_documents([PASSAGE_PREFIX + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._model.embed_query(QUERY_PREFIX + text)


def load_pdfs() -> list:
    """docs 폴더의 PDF를 모두 읽어 쪽 단위 문서로 돌려주고, 문서별 쪽 수를 출력한다."""
    pdf_paths = sorted(DOCS_DIR.glob("*.pdf"))
    if not pdf_paths:
        sys.exit(f"PDF가 없습니다: {DOCS_DIR}")

    pages = []
    for path in pdf_paths:
        loaded = PyPDFLoader(str(path)).load()
        for doc in loaded:
            # 문서 이름과 사람 기준 쪽 번호(1부터)를 남긴다. PyPDFLoader 의 page 는 0부터다
            doc.metadata = {"source": path.name, "page": doc.metadata["page"] + 1}
        print(f"{path.name}: {len(loaded)}쪽")
        pages.extend(loaded)
    return pages


def main() -> None:
    pages = load_pdfs()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    # 빈 쪽(그림만 있는 쪽 등)은 조각이 생기지 않으므로 그대로 둔다. 메타데이터는 조각이 물려받는다
    chunks = splitter.split_documents(pages)
    if not chunks:
        sys.exit("PDF에서 읽어낸 글자가 없습니다.")
    print(f"전체 조각 수: {len(chunks)}")

    for i, chunk in enumerate(chunks[:PREVIEW_COUNT], start=1):
        head = chunk.page_content[:PREVIEW_LEN].replace("\n", " ")
        print(f"조각 {i}: 길이 {len(chunk.page_content)} / {head}")

    # 돌릴 때마다 저장 폴더를 지우고 새로 만든다
    if STORE_DIR.exists():
        shutil.rmtree(STORE_DIR)
    Chroma.from_documents(
        documents=chunks,
        embedding=E5Embeddings(),
        persist_directory=str(STORE_DIR),
    )
    print(f"저장 완료: {STORE_DIR}")


if __name__ == "__main__":
    main()
