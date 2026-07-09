# CLAUDE.md
> Claude Code가 이 프로젝트를 처음 열었을 때 자동으로 읽는 파일입니다.

---

## 프로젝트 개요

치매 조기 의심 증상 안내 및 검진 가이드 RAG 챗봇입니다.
VectorDB(Qdrant)와 GraphDB(Neo4j AuraDB)를 결합한 하이브리드 RAG 구조에
LangGraph 멀티노드 파이프라인을 사용합니다.

- **기간**: 2026.07.08 ~ 2026.07.15
- **언어**: Python 3.12.9
- **패키지 관리**: uv

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| LLM | OpenAI gpt-5.4-mini |
| LLM Pipeline | LangChain + LangGraph |
| VectorDB | Qdrant Cloud |
| GraphDB | Neo4j AuraDB |
| 임베딩 | OpenAI text-embedding-3-small |
| 문서 처리 | pypdf |

---

## 디렉토리 구조

```
SKN31-3rd-팀명/
├── graph_db/        # 진영 — CSV 정제, Neo4j 적재, GraphCypherQAChain
│   ├── __init__.py
│   ├── preprocess.py
│   ├── load_neo4j.py
│   └── query_functions.py
├── vector_db/       # 영선 — PDF 수집, chunking, Qdrant 임베딩, retriever
│   ├── __init__.py
│   ├── embed_load.py
│   └── retriever.py
├── pipeline/        # 효민·연아 — LangGraph 노드 구성, 체인 연결
│   ├── __init__.py
│   ├── graph.py
│   └── chain.py
├── frontend/        # 동민 — 웹 UI
├── data/
│   ├── raw/         # 원본 데이터 (절대 수정 금지)
│   └── processed/   # 정제 데이터
└── docs/            # 산출물 문서
```

---

## Neo4j 그래프 스키마

```
Node properties:
시도 {시도명: STRING}
시군구 {시군구명: STRING}
치매안심센터 {센터명: STRING, 주소: STRING, 우편번호: INTEGER,
              전화번호: STRING, 팩스번호: STRING,
              위도: FLOAT, 경도: FLOAT, 홈페이지: STRING, 설립일: STRING}

Relationships:
(:치매안심센터)-[:LOCATED_IN]->(:시군구)
(:시군구)-[:CONTAINS]->(:시도)
```

### Cypher 쿼리 방향 규칙 (반드시 지켜야 함)

```cypher
-- 시도 + 시군구로 센터 조회
MATCH (c:치매안심센터)-[:LOCATED_IN]->(sg:시군구)-[:CONTAINS]->(sd:시도 {시도명: '서울특별시'})
WHERE sg.시군구명 = '강남구'
RETURN c.센터명, c.주소, c.전화번호
```

---

## LangGraph 파이프라인 구조

```
[라우터 Node] → "센터 찾기" → [GraphDB Node] → [답변 생성 Node]
               → "증상/가이드라인" → [VectorDB Node] → [답변 생성 Node]
```

---

## 환경변수 (.env)

```dotenv
# Neo4j
NEO4J_URI=neo4j+ssc://19f5f7c5.databases.neo4j.io
NEO4J_USERNAME=19f5f7c5
NEO4J_PASSWORD=
NEO4J_DATABASE=19f5f7c5

# Qdrant
QDRANT_URL=https://bdf12f44-f71b-4e8a-86f0-2a7cacc93ca5.eu-west-2-0.aws.cloud.qdrant.io
QDRANT_API_KEY=

# OpenAI
OPENAI_API_KEY=
```

---

## 코드 작성 규칙

- 환경변수는 반드시 `.env`에서 `os.getenv()`로 불러올 것, 하드코딩 금지
- 네이밍은 Python 관행대로 (PEP8)
- 함수마다 docstring 작성
- 주석은 코드 의도 위주로 작성
- import 순서: 표준 라이브러리 → 서드파티 → 로컬 모듈
- `data/raw/` 파일은 읽기만 할 것, 절대 덮어쓰기 금지

---

## Git 규칙

- 브랜치: `feat/graph-db`, `feat/vector-db`, `feat/pipeline`, `feat/frontend`
- 커밋: `[파트] 작업내용` 형식 (예: `[graph_db] CSV 정제 완료`)
- `main` 직접 push 금지, 반드시 `dev` 경유
