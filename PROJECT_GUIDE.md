# SKN31-3rd-팀명 프로젝트 가이드라인

## 📁 디렉토리 구조

```
SKN31-3rd-팀명/
│
├── README.md                          # 발표 자료 겸용 (필수 항목 아래 참고)
├── CLAUDE.md                          # Claude Code용 프로젝트 맥락
├── CONVENTIONS.md                     # 팀 협업 규칙 (AI 협업 포함)
├── .env.example                       # 환경변수 샘플 (실제 키 절대 커밋 금지)
├── .gitignore
├── requirements.txt                   # uv pip install -r requirements.txt
│
├── data/
│   ├── raw/                           # 원본 데이터 — 절대 수정 금지
│   │   ├── 국립중앙의료원_치매안심센터 정보_20260128.csv   # 진영 담당
│   │   └── *.pdf                      # 영선 담당 (가이드라인 원문)
│   └── processed/                     # 정제 완료 파일
│       └── 치매안심센터_cleaned.csv
│
├── graph_db/                          # GraphDB 담당: 진영
│   ├── __init__.py
│   ├── preprocess.py                  # CSV 정제
│   ├── load_neo4j.py                  # Neo4j AuraDB 적재
│   └── query_functions.py             # 센터 조회 함수 (파이프라인팀 전달용)
│
├── vector_db/                         # VectorDB 담당: 영선
│   ├── __init__.py
│   ├── embed_load.py                  # Qdrant 임베딩 및 적재
│   └── retriever.py                   # Runnable Retriever (파이프라인팀 전달용)
│
├── pipeline/                          # LangGraph 파이프라인 담당: 효민·연아
│   ├── __init__.py
│   ├── graph.py                       # LangGraph 노드 구성
│   └── chain.py                       # LCEL 기본 체인
│
├── frontend/                          # 웹 UI 담당: 동민
│
└── docs/                              # 팀 공통 산출물 문서
    ├── 01_데이터수집_전처리.md         # 산출물 ①
    ├── 02_시스템아키텍처.md            # 산출물 ②
    ├── 03_DB설계.md                    # 산출물 ③ (VectorDB metadata + GraphDB 노드/관계)
    ├── 04_RAG시스템구성도.md           # 산출물 ④
    └── architecture.png               # 아키텍처 이미지
```

---

## 📋 산출물 체크리스트

> 발표 전까지 아래 항목 전부 채워야 합니다. 각자 담당 항목에 체크해주세요.

### ① 데이터 수집 및 전처리 문서 (`docs/01_데이터수집_전처리.md`)
- [ ] 수집한 데이터와 프로젝트와의 관련성
- [ ] 어떤 데이터를 수집했는지
- [ ] 어디에서 어떻게 수집했는지
- [ ] 문서 정제 방법
- [ ] Chunking 방법 및 기준

### ② 시스템 아키텍처 구성도 (`docs/02_시스템아키텍처.md`)
- [ ] 전체 시스템 흐름도 이미지 (architecture.png)

### ③ Database 설계 (`docs/03_DB설계.md`)
- [ ] **Vector DB**: metadata 설계 — **영선**
- [ ] **GraphDB**: Node / Relationship / Property 설계 — **진영**

### ④ RAG 시스템 구성도 (`docs/04_RAG시스템구성도.md`)
- [ ] LangGraph 노드 구조 설명
- [ ] 각 노드의 역할/기능 — **효민·연아**

### ⑤ 데이터셋
- [ ] 수집한 원본 데이터셋 (`data/raw/`)
- [ ] 전처리한 데이터셋 (`data/processed/`)

### ⑥ 구현 코드
- [ ] 데이터 수집·전처리 코드
- [ ] RAG 애플리케이션 구현 코드

### ⑦ README.md (발표 자료 겸용)
- [ ] 팀원 및 담당 업무
- [ ] 프로젝트 주제 및 선정 이유
- [ ] 주요 기능
- [ ] 디렉토리 구조
- [ ] 수집 데이터 설명
- [ ] 애플리케이션 주요 기능 설명
- [ ] 회고 (문제 및 해결 방법, 각자 느낀 점)

---

## ⚠️ 공통 규칙

| 규칙 | 내용 |
|------|------|
| **원본 보존** | `data/raw/` 파일은 절대 수정 금지. 정제본은 `data/processed/`에만 저장 |
| **환경변수** | API 키, DB 비밀번호는 `.env`에만. 레포에는 `.env.example`만 커밋 |
| **파일명** | 정제된 파일명에는 `_cleaned` suffix 붙이기 |
| **패키지 관리** | `uv pip install -r requirements.txt` 로 설치, 패키지 추가 시 즉시 업데이트 |
| **커밋 메시지** | `[파트명] 작업내용` 형식 — 예: `[graph_db] 치매안심센터 CSV 정제 완료` |

---

## 🔗 담당자별 핵심 연결 관계

```
영선 (VectorDB)                진영 (GraphDB)
retriever.py (Runnable)        GraphCypherQAChain + cypher_prompt
     │                                  │
     └──────────────┬───────────────────┘
                    ↓
           효민·연아 (Pipeline)
           LangGraph 노드 구성
           (라우터 → VectorDB/GraphDB → 답변 생성)
                    ↓
               동민 (Frontend)
                API 연동
```

---

## 🗓️ 일정

| 날짜 | 목표 |
|------|------|
| 7/09 (오늘) | 레포 세팅 완료, 각자 파트 착수 |
| 7/09~10 | 진영: GraphDB 완료 / 영선: PDF 수집·임베딩 |
| 7/11~12 | 효민·연아: LCEL → LangGraph 파이프라인 구성 |
| 7/13~14 | 프론트 연동 + 산출물 문서 작성 |
| 7/14 | README 완성 |
| 7/15 | 발표 |

---

## 🔐 환경변수 (.env.example)

```dotenv
# Neo4j
NEO4J_URI=neo4j+ssc://19f5f7c5.databases.neo4j.io
NEO4J_USERNAME=19f5f7c5
NEO4J_PASSWORD=
NEO4J_DATABASE=19f5f7c5
NEO4J_QUERY_URL=https://19f5f7c5.databases.neo4j.io/db/19f5f7c5/query/v2

# Qdrant
QDRANT_URL=https://bdf12f44-f71b-4e8a-86f0-2a7cacc93ca5.eu-west-2-0.aws.cloud.qdrant.io
QDRANT_API_KEY=

# OpenAI
OPENAI_API_KEY=
```
