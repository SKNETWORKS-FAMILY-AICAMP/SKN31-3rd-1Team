# SKN31-3rd-1Team

# 1. 팀 및 팀원 소개

### 1.1 팀 명
<!-- TODO -->


### 1.2 팀원 및 담당업무
<!-- TODO: GitHub 아이디, 프로필 사진 채우기 -->
| 안영선 | 김동민 | 박연아  | 김효민 | 유진영 |
| :---: | :---: | :---: | :---: | :---: |
| <a href="#"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=GitHub&logoColor=white"/> | <a href="#"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=GitHub&logoColor=white"/> | <a href="#"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=GitHub&logoColor=white"/> | <a href="#"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=GitHub&logoColor=white"/> | <a href="#"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=GitHub&logoColor=white"/> |
| <img src="images/placeholder.png" width="150" height="150"> | <img src="images/placeholder.png" width="150" height="150"> | <img src="images/placeholder.png" width="150" height="150"> | <img src="images/placeholder.png" width="150" height="150"> | <img src="images/placeholder.png" width="150" height="150"> |
|  | |  |  |  |


### 1.3 기술 스택 🛠

<!-- TODO -->


---

### 1.4 WBS

<!-- TODO -->



---

## 2. 프로젝트 개요

### 2.1 프로젝트명
- AI 치매 정보 알리미
- https://dementia-front.vercel.app/

### 2.2 프로젝트 소개

- 이번 프로젝트는 치매가 걱정되는 보호자를 대상으로, 전국 치매안심센터 정보(GraphDB)와 치매 조기검진·증상 가이드라인 문서(VectorDB)를 결합한 RAG 기반 챗봇을 개발하는 프로젝트입니다.

- 보호자가 자연어로 증상을 설명하면 관련 가이드라인을 근거로 안내하고, 거주 지역을 알려주면 가까운 치매안심센터의 위치·운영기관·제공 프로그램 정보를 함께 제공합니다. LangGraph 기반 에이전트가 질문 - 내용에 따라 GraphDB/VectorDB 조회 tool을 스스로 판단해 호출하는 구조로 구현했습니다.

### 2.3 배경 및 선정 이유

<!-- TODO -->
               
### 2.4 주요 기능 및 요구사항

- 전국 치매안심센터 데이터를 GraphDB(Neo4j)로 구조화해 지역/운영기관/프로그램 기준 조회 제공
- 치매 조기검진·증상 관련 가이드라인 문서를 VectorDB(Qdrant)로 임베딩해 의미 기반 검색 제공
- LangGraph 기반 에이전트(`create_react_agent`)가 사용자 질문에 따라 GraphDB/VectorDB tool을 스스로 호출해 답변 생성
- Supabase 기반 단기(세션)/장기(사용자별) 대화 상태 관리



## 3. 디렉토리 구조

```
SKN31-3rd-1Team/
├── config.py                   # 프로젝트 전역 설정 상수 (모델명, 경로, DB 접속 정보 등)
├── .env                        # 환경변수 (API 키, DB 접속 정보 — git 미포함)
├── requirements.txt
├── README.md
│
├── 산출물/                      # 프로젝트 산출물 문서
│   ├── 데이터수집및전처리문서.md
│   ├── 시스템아키텍처.md
│   └── images/
│       └── architecture.png
│
├── graph_db/                    # GraphDB(Neo4j) 관련 코드
│   ├── data/
│   │   ├── raw/                
│   │   └── processed/          
│   ├── preprocess.py            
│   ├── load_to_aura.py          
│   ├── cypher_prompt.py         
│   └── graph_search_tool.py     
│
├── vector_db/                   # VectorDB(Qdrant) 관련 코드
│   ├── data/
│   │   ├── raw/                
│   │   └── processed/         
│   ├── run_vector.py            
│   └── vector_search_tool.py   
│
├── modules/                     # LangGraph 파이프라인 (에이전트, State, 그래프 구성)
│   └── state.py      
│
├── server/                      # FastAPI 서버
│   └── main.py          
```


---


## 4. 수집 데이터 설명
- [데이터 수집 및 전처리 문서](./산출물/데이터수집및전처리문서.md)


---

## 5. Application의 주요 기능

- [시스템 아키텍처 및 DB 설계](./산출물/시스템아키텍쳐.md)

---

## ６. 성능 평가

- [성능 평가](./산출물/성능평가.md)


---
## 7. 회고

<!-- TODO -->
#### 구현 중 겪었던 문제와 해결 or 각자 느낀 점

#### 영선
-

#### 동민
-

#### 연아
-

#### 효민
-

#### 진영
-

---
