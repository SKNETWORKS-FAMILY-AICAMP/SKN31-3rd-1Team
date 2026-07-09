# VectorDB & Qdrant 가이드
> 치매 조기 안내 RAG 챗봇 프로젝트 — VectorDB 담당자(영선) 작업 문서

---

## 목차
1. [Vector Database란?](#1-vector-database란)
2. [Qdrant란?](#2-qdrant란)
3. [왜 VectorDB를 쓰는가?](#3-왜-vectordb를-쓰는가)
4. [우리 프로젝트 설계](#4-우리-프로젝트-설계)
5. [작업 순서 (Step by Step)](#5-작업-순서-step-by-step)

---

## 1. Vector Database란?

**Vector Database(벡터 데이터베이스)**는 텍스트, 이미지 등을 **숫자 벡터(임베딩)**로 변환하여 저장하고, **의미 기반 유사도 검색**을 수행하는 데이터베이스다.

> **핵심 개념**
> - **임베딩(Embedding)**: 텍스트를 숫자 배열로 변환한 것. 의미가 비슷한 텍스트는 벡터 공간에서 가까운 위치에 존재한다.
> - **유사도 검색**: "치매 초기 증상"을 검색하면 의미적으로 유사한 문서를 찾아온다. 키워드가 정확히 일치하지 않아도 된다.
> - **컬렉션(Collection)**: RDB의 테이블에 해당한다. 벡터와 메타데이터를 함께 저장한다.
> - **페이로드(Payload)**: 벡터와 함께 저장되는 메타데이터. 문서 출처, 챕터명 등을 저장한다.

### RDB vs VectorDB 비교

| 개념 | RDB | VectorDB |
|------|-----|----------|
| 저장 단위 | 행 (Row) | 벡터 + 페이로드 |
| 검색 방식 | 정확한 키워드 매칭 | 의미 기반 유사도 검색 |
| 적합한 데이터 | 구조화된 데이터 | 비정형 텍스트, 이미지 |
| 질의 언어 | SQL | 벡터 유사도 쿼리 |

### 검색 방식 종류

| 방식 | 설명 | 특징 |
|------|------|------|
| **Dense Search** | 임베딩 벡터 유사도 기반 | 의미 기반, 문맥 이해 |
| **Sparse Search** | 키워드 빈도 기반 (BM25) | 정확한 단어 매칭에 강함 |
| **Hybrid Search** | Dense + Sparse 결합 | 둘의 장점을 모두 활용 ✅ |

---

## 2. Qdrant란?

**Qdrant**는 오픈소스 벡터 데이터베이스로, 고성능 유사도 검색과 필터링을 지원한다.

> **Qdrant Cloud**
> - 이번 프로젝트에서는 **Qdrant Cloud 무료 클러스터**를 사용한다.
> - 무료 플랜: 1GB RAM, 4GB 저장공간
> - 우리 프로젝트 규모 (PDF 몇 개 chunking)는 무료 플랜으로 충분

### LangChain 연동

```python
from langchain_qdrant import QdrantVectorStore
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient

# Qdrant Cloud 연결
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

# VectorStore 생성
vectorstore = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=embeddings
)
```

---

## 3. 왜 VectorDB를 쓰는가?

### 이 프로젝트에서 VectorDB가 필요한 이유

치매 관련 가이드라인 PDF는 **비정형 텍스트**다. 보호자가 "치매 초기 증상이 뭔가요?"라고 물으면, 정확한 키워드 없이도 의미적으로 관련된 문서를 찾아야 한다.

```
보호자: "우리 엄마가 요즘 자꾸 깜빡해요. 치매인가요?"

챗봇:  → VectorDB에서 의미 기반 검색
         "기억력 저하", "인지기능 감소" 관련 문서 검색
       → 치매 조기 증상 가이드라인 내용 반환
       → LLM이 자연어로 답변 생성
```

### VectorDB와 GraphDB의 역할 분리

| 역할 | 담당 DB | 처리하는 질문 예시 |
|------|---------|------------------|
| 비정형 문서 검색 | VectorDB (Qdrant) ✅ | "치매 초기 증상이 뭔가요?" |
| 구조화된 관계 조회 | GraphDB (Neo4j) | "서울 강남구 치매안심센터 알려줘" |

---

## 4. 우리 프로젝트 설계

### 수집 데이터

| 문서 | 출처 | 형식 |
|------|------|------|
| 치매 조기 검진 가이드라인 | 중앙치매센터 / 보건복지부 | PDF |

### 컬렉션 설계

| 항목 | 값 |
|------|-----|
| Collection명 | `dementia_guidelines` |
| 임베딩 모델 | `text-embedding-3-small` (1536차원) |
| 검색 방식 | Hybrid (Dense + Sparse) |
| 청킹 기준 | 담당자(영선) 결정 |

### 메타데이터 (Payload) 설계

```python
{
    "source": "중앙치매센터_가이드라인.pdf",  # 출처 파일명
    "page": 3,                               # 페이지 번호
    "chapter": "2장. 치매 초기 증상",          # 챕터명
}
```

---

## 5. 작업 순서 (Step by Step)

### Step 1. 환경 세팅

```bash
pip install langchain-qdrant langchain-openai qdrant-client pypdf pdfplumber python-dotenv
```

`.env` 파일:
```dotenv
QDRANT_URL=https://bdf12f44-f71b-4e8a-86f0-2a7cacc93ca5.eu-west-2-0.aws.cloud.qdrant.io
QDRANT_API_KEY=발급받은_키
OPENAI_API_KEY=발급받은_키
```

**체크포인트**
- [ ] 패키지 설치 완료
- [ ] `.env` 파일 세팅 완료
- [ ] Qdrant Cloud 대시보드 접속 확인

---

### Step 2. PDF 문서 수집 및 로드

```python
# collect_docs.py
from langchain_community.document_loaders import PyPDFLoader
import os

def load_pdfs(pdf_dir: str) -> list:
    """PDF 폴더에서 문서 로드"""
    documents = []
    for filename in os.listdir(pdf_dir):
        if filename.endswith('.pdf'):
            loader = PyPDFLoader(os.path.join(pdf_dir, filename))
            docs = loader.load()
            documents.extend(docs)
            print(f"로드 완료: {filename} ({len(docs)}페이지)")
    return documents

# 실행
documents = load_pdfs('data/raw/')
print(f"총 {len(documents)}개 문서 로드 완료")
```

**체크포인트**
- [ ] PDF 파일 `data/raw/` 에 저장 완료
- [ ] 문서 로드 확인

---

### Step 3. 문서 정제 및 Chunking

```python
# chunking.py
from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_documents(documents: list) -> list:
    """문서를 청크로 분할"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,       # 청크 크기 (담당자 조정)
        chunk_overlap=50,     # 청크 간 중복 (문맥 유지)
        separators=["\n\n", "\n", ".", " "]
    )
    chunks = splitter.split_documents(documents)
    print(f"청킹 완료: {len(chunks)}개 청크")
    return chunks
```

**체크포인트**
- [ ] 청킹 기준 결정 (chunk_size, chunk_overlap)
- [ ] 청크 수 및 내용 확인

---

### Step 4. Qdrant 컬렉션 생성 및 임베딩 적재

```python
# embed_load.py
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, SparseVectorParams, SparseIndexParams
import os
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = "dementia_guidelines"
VECTOR_SIZE = 1536  # text-embedding-3-small

# Qdrant Cloud 연결
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

# 컬렉션 생성 (Hybrid: Dense + Sparse)
if client.collection_exists(COLLECTION_NAME):
    client.delete_collection(COLLECTION_NAME)

client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config={
        "dense": VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
    },
    sparse_vectors_config={
        "sparse": SparseVectorParams(
            index=SparseIndexParams(on_disk=False)
        )
    }
)

# 임베딩 모델
dense_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
sparse_embeddings = FastEmbedSparse(model_name="qdrant/bm25")

# VectorStore 생성
vectorstore = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=dense_embeddings,
    sparse_embedding=sparse_embeddings,
    vector_name="dense",
    sparse_vector_name="sparse",
    retrieval_mode=RetrievalMode.HYBRID
)

# 문서 적재
vectorstore.add_documents(chunks)
print(f"적재 완료: {len(chunks)}개 청크")
```

**체크포인트**
- [ ] 컬렉션 생성 확인
- [ ] 임베딩 적재 완료
- [ ] Qdrant 대시보드에서 벡터 수 확인

---

### Step 5. Retriever 생성 → 파이프라인팀 전달

> **이 단계가 핵심이에요.** `retriever`는 Runnable이라서 파이프라인팀이 체인에 바로 연결할 수 있어요.

```python
# retriever.py
from langchain_qdrant import QdrantVectorStore, FastEmbedSparse, RetrievalMode
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = "dementia_guidelines"

# Qdrant Cloud 연결
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

# 임베딩 모델
dense_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
sparse_embeddings = FastEmbedSparse(model_name="qdrant/bm25")

# VectorStore 연결
vectorstore = QdrantVectorStore(
    client=client,
    collection_name=COLLECTION_NAME,
    embedding=dense_embeddings,
    sparse_embedding=sparse_embeddings,
    vector_name="dense",
    sparse_vector_name="sparse",
    retrieval_mode=RetrievalMode.HYBRID
)

# Retriever 생성 (Runnable) → 파이프라인팀 전달
retriever = vectorstore.as_retriever(
    search_type="mmr",           # 다양성 고려 검색
    search_kwargs={
        "k": 5,                  # 반환할 문서 수
        "fetch_k": 10,           # 후보 문서 수
        "lambda_mult": 0.7       # 유사도 vs 다양성 균형
    }
)

# 테스트
if __name__ == "__main__":
    result = retriever.invoke("치매 초기 증상이 뭔가요?")
    for doc in result:
        print(doc.page_content[:100])
        print("---")
```

**파이프라인팀에게 전달하는 인터페이스**

```python
# pipeline/retriever.py 에서 이렇게 import해서 쓰면 됩니다
from vector_db.retriever import retriever

# retriever는 Runnable이라서 체인에 바로 연결 가능
chain = retriever | prompt | llm | parser
```

**체크포인트**
- [ ] `retriever.invoke("치매 초기 증상")` 결과 확인
- [ ] 파이프라인팀(효민·연아)에게 retriever 공유

---

## 참고 자료

- [Qdrant Cloud 콘솔](https://cloud.qdrant.io)
- [Qdrant Python Client 문서](https://python-client.qdrant.tech/)
- [LangChain Qdrant 연동 문서](https://python.langchain.com/docs/integrations/vectorstores/qdrant/)
- [중앙치매센터](https://www.nid.or.kr)
