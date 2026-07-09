# Pipeline 가이드
> 치매 조기 안내 RAG 챗봇 프로젝트 — 파이프라인 담당자(효민·연아) 작업 문서

---

## 목차
1. [전체 시스템 구조](#1-전체-시스템-구조)
2. [LCEL 기본 RAG 체인](#2-lcel-기본-rag-체인)
3. [LangGraph 멀티노드 구조](#3-langgraph-멀티노드-구조)
4. [작업 순서 (Step by Step)](#4-작업-순서-step-by-step)

---

## 1. 전체 시스템 구조

```
사용자 질문
    ↓
[라우터 Node] — 질문 분류
"센터 찾기" vs "증상/가이드라인"
    ↓
┌──────────────────────────────┐
│                              │
[VectorDB Node]          [GraphDB Node]
영선님 retriever          진영님 GraphCypherQAChain
(증상/가이드라인 검색)     (센터 위치 조회)
│                              │
└──────────────┬───────────────┘
               ↓
        [답변 생성 Node]
               ↓
    체크포인트 저장 (대화 기록)
               ↓
           사용자 출력
```

### 각 파트에서 받는 것

| 담당자 | 전달 받는 것 | 사용 방법 |
|--------|-------------|----------|
| 진영 (GraphDB) | `GraphCypherQAChain` + `cypher_prompt` | GraphDB Node에 연결 |
| 영선 (VectorDB) | `retriever` (Runnable) | VectorDB Node에 연결 |

---

## 2. LCEL 기본 RAG 체인

> LangGraph 전에 LCEL로 기본 체인 먼저 만들고 동작 확인 후 LangGraph로 확장한다.

### 설치

```bash
pip install langchain langchain-openai langgraph python-dotenv
```

### 기본 RAG 체인 (VectorDB)

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

MODEL = "gpt-5.4-mini"

# 영선님한테 받은 retriever import
from vector_db.retriever import retriever

# 문서 포맷터
def format_docs(docs):
    """검색된 문서를 하나의 문자열로 합치기"""
    return "\n\n".join(doc.page_content for doc in docs)

# 프롬프트
prompt = ChatPromptTemplate.from_template("""
당신은 치매 보호자를 위한 안내 챗봇입니다.
주어진 context를 기반으로 친절하게 답변해주세요.
context에 관련 내용이 없으면 "해당 정보를 찾을 수 없습니다"라고 답하세요.

context:
{context}

질문: {question}
""")

llm = ChatOpenAI(model=MODEL, temperature=0)
parser = StrOutputParser()

# LCEL 체인
rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough()
    }
    | prompt
    | llm
    | parser
)

# 테스트
result = rag_chain.invoke("치매 초기 증상이 뭔가요?")
print(result)
```

### GraphDB 체인 (진영님한테 받은 것)

```python
from langchain_neo4j import GraphCypherQAChain, Neo4jGraph
from langchain_core.prompts import PromptTemplate

# Neo4j 연결
graph = Neo4jGraph(
    url=os.getenv('NEO4J_URI'),
    username=os.getenv('NEO4J_USERNAME'),
    password=os.getenv('NEO4J_PASSWORD'),
    database=os.getenv('NEO4J_DATABASE')
)

# Cypher 생성 프롬프트 (관계 방향 명시 필수)
CYPHER_PROMPT = PromptTemplate(
    input_variables=["schema", "question"],
    template="""당신은 Neo4j Cypher 쿼리 전문가입니다.
아래 스키마를 참고하여 질문에 맞는 Cypher 쿼리를 생성하세요.

스키마:
{schema}

관계 방향 규칙 (반드시 지켜야 함):
- (:치매안심센터)-[:LOCATED_IN]->(:시군구)
- (:시군구)-[:CONTAINS]->(:시도)

올바른 예시:
MATCH (c:치매안심센터)-[:LOCATED_IN]->(sg:시군구)-[:CONTAINS]->(sd:시도 {{시도명: '서울특별시'}})
WHERE sg.시군구명 = '강남구'
RETURN c.센터명, c.주소, c.전화번호

질문: {question}
Cypher 쿼리:"""
)

# GraphDB 체인
graph_chain = GraphCypherQAChain.from_llm(
    llm=llm,
    graph=graph,
    allow_dangerous_requests=True,
    verbose=True,
    cypher_prompt=CYPHER_PROMPT
)

# 테스트
result = graph_chain.invoke({"query": "서울특별시 강남구 치매안심센터 알려줘"})
print(result["result"])
```

---

## 3. LangGraph 멀티노드 구조

> LCEL 체인 동작 확인 후 LangGraph로 확장한다.

### State 정의

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class ChatState(TypedDict):
    """대화 상태"""
    messages: Annotated[list, add_messages]  # 대화 기록
    query: str                                # 현재 질문
    route: str                                # 라우팅 결과 ("vector" or "graph")
    context: str                              # 검색 결과
```

### Node 구현

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage

llm = ChatOpenAI(model=MODEL, temperature=0)

# =====================
# 1. 라우터 Node
# =====================
def router_node(state: ChatState) -> ChatState:
    """질문을 분류해서 라우팅"""
    query = state["query"]

    # 센터 관련 키워드 체크
    center_keywords = ["센터", "어디", "주소", "전화번호", "위치", "찾아줘", "알려줘"]
    is_center_query = any(keyword in query for keyword in center_keywords)

    route = "graph" if is_center_query else "vector"
    return {**state, "route": route}


# =====================
# 2. VectorDB Node
# =====================
def vector_node(state: ChatState) -> ChatState:
    """VectorDB에서 증상/가이드라인 검색"""
    docs = retriever.invoke(state["query"])
    context = "\n\n".join(doc.page_content for doc in docs)
    return {**state, "context": context}


# =====================
# 3. GraphDB Node
# =====================
def graph_node(state: ChatState) -> ChatState:
    """GraphDB에서 센터 정보 조회"""
    result = graph_chain.invoke({"query": state["query"]})
    return {**state, "context": result["result"]}


# =====================
# 4. 답변 생성 Node
# =====================
def answer_node(state: ChatState) -> ChatState:
    """최종 답변 생성"""
    answer_prompt = ChatPromptTemplate.from_template("""
당신은 치매 보호자를 위한 안내 챗봇입니다.
주어진 정보를 바탕으로 친절하게 답변해주세요.

정보:
{context}

질문: {query}
""")
    chain = answer_prompt | llm | StrOutputParser()
    answer = chain.invoke({
        "context": state["context"],
        "query": state["query"]
    })

    messages = state.get("messages", [])
    messages.append(HumanMessage(content=state["query"]))
    messages.append(AIMessage(content=answer))

    return {**state, "messages": messages}


# =====================
# 라우팅 함수
# =====================
def route_decision(state: ChatState) -> str:
    """라우터 결과에 따라 다음 노드 결정"""
    return state["route"]  # "vector" or "graph"
```

### 그래프 구성

```python
# 그래프 생성
graph_builder = StateGraph(ChatState)

# 노드 추가
graph_builder.add_node("router", router_node)
graph_builder.add_node("vector", vector_node)
graph_builder.add_node("graph", graph_node)
graph_builder.add_node("answer", answer_node)

# 엣지 연결
graph_builder.set_entry_point("router")

# 조건부 엣지 (라우터 결과에 따라 분기)
graph_builder.add_conditional_edges(
    "router",
    route_decision,
    {
        "vector": "vector",
        "graph": "graph"
    }
)

graph_builder.add_edge("vector", "answer")
graph_builder.add_edge("graph", "answer")
graph_builder.add_edge("answer", END)

# 체크포인트 (대화 기록 저장)
checkpointer = MemorySaver()

# 그래프 컴파일
app = graph_builder.compile(checkpointer=checkpointer)
```

### 실행

```python
# 대화 실행
config = {"configurable": {"thread_id": "user-001"}}  # 사용자별 thread_id

# 첫 번째 질문
result = app.invoke(
    {"query": "치매 초기 증상이 뭔가요?", "messages": []},
    config=config
)
print(result["messages"][-1].content)

# 두 번째 질문 (이전 대화 기억)
result = app.invoke(
    {"query": "서울 강남구 치매안심센터 알려줘", "messages": result["messages"]},
    config=config
)
print(result["messages"][-1].content)
```

---

## 4. 작업 순서 (Step by Step)

### Step 1. 환경 세팅 및 각 파트 연결 확인

```python
# 진영님 GraphDB 연결 확인
from langchain_neo4j import Neo4jGraph
graph = Neo4jGraph(...)
print(graph.schema)  # 스키마 출력되면 성공

# 영선님 VectorDB 연결 확인
from vector_db.retriever import retriever
result = retriever.invoke("치매 초기 증상")
print(len(result))  # 문서 개수 출력되면 성공
```

**체크포인트**
- [ ] Neo4j 스키마 확인
- [ ] Qdrant retriever 동작 확인
- [ ] OpenAI API 키 확인

---

### Step 2. LCEL 기본 체인 동작 확인

```python
# VectorDB 체인 테스트
result = rag_chain.invoke("치매 초기 증상이 뭔가요?")
print(result)

# GraphDB 체인 테스트
result = graph_chain.invoke({"query": "서울 강남구 치매안심센터 알려줘"})
print(result["result"])
```

**체크포인트**
- [ ] VectorDB 체인 답변 확인
- [ ] GraphDB 체인 답변 확인

---

### Step 3. LangGraph 노드 구성

**체크포인트**
- [ ] State 정의
- [ ] 4개 노드 구현 (router, vector, graph, answer)
- [ ] 조건부 엣지 연결
- [ ] 체크포인트 (MemorySaver) 적용

---

### Step 4. 통합 테스트

```python
# 다양한 질문으로 테스트
test_queries = [
    "치매 초기 증상이 뭔가요?",
    "서울 강남구 치매안심센터 알려줘",
    "치매 예방 방법은?",
    "경기도 수원시 치매안심센터 전화번호는?"
]

config = {"configurable": {"thread_id": "test-001"}}
messages = []

for query in test_queries:
    result = app.invoke({"query": query, "messages": messages}, config=config)
    messages = result["messages"]
    print(f"Q: {query}")
    print(f"A: {result['messages'][-1].content}")
    print("---")
```

**체크포인트**
- [ ] 라우팅 정확도 확인 (센터 질문 → graph, 증상 질문 → vector)
- [ ] 멀티턴 대화 기록 확인
- [ ] 프론트엔드(동민)에 연결

---

## 참고 자료

- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [LangChain LCEL 문서](https://python.langchain.com/docs/expression_language/)
- [Neo4j LangChain 연동](https://python.langchain.com/docs/integrations/graphs/neo4j_cypher/)
- [Qdrant LangChain 연동](https://python.langchain.com/docs/integrations/vectorstores/qdrant/)
