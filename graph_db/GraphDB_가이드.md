# GraphDB & Neo4j 가이드
> 치매 조기 안내 RAG 챗봇 프로젝트 — GraphDB 담당자(진영) 작업 문서

---

## 목차
1. [Graph Database란?](#1-graph-database란)
2. [Neo4j란?](#2-neo4j란)
3. [왜 GraphDB를 쓰는가?](#3-왜-graphdb를-쓰는가)
4. [우리 프로젝트 설계](#4-우리-프로젝트-설계)
5. [작업 순서 (Step by Step)](#5-작업-순서-step-by-step)

---

## 1. Graph Database란?

**Graph Database(그래프 데이터베이스)**는 데이터를 **노드(Node)**와 **관계(Relationship)**로 표현하는 데이터베이스다.

> **핵심 구성요소**
> - **Node (노드)**: 데이터 객체 하나. 사람, 장소, 사물 등 개별 엔티티를 나타낸다.
> - **Relationship (관계)**: 노드와 노드를 연결하는 선. 두 데이터 사이의 관계를 나타낸다.
> - **Property (프로퍼티)**: 노드나 관계가 가지는 속성값. RDB의 컬럼에 해당한다.
> - **Label (레이블)**: 노드의 종류를 구분하는 태그. RDB의 테이블명에 해당한다.

### RDB와 비교

| 개념 | RDB | Graph DB |
|------|-----|----------|
| 데이터 단위 | 행 (Row) | 노드 (Node) |
| 데이터 종류 | 테이블 (Table) | 레이블 (Label) |
| 속성 | 컬럼 (Column) | 프로퍼티 (Property) |
| 연결 | JOIN | 관계 (Relationship) |
| 조회 언어 | SQL | Cypher |

### 예시로 이해하기

RDB에서 "서울특별시에 있는 치매안심센터를 조회"하려면:

```sql
-- RDB 방식: 테이블 JOIN 필요
SELECT c.name, c.phone
FROM centers c
JOIN regions r ON c.region_id = r.id
WHERE r.sido = '서울특별시';
```

GraphDB에서는 관계를 따라가기만 하면 된다:

```cypher
-- Cypher 방식: 관계를 화살표로 표현
MATCH (:시도 {name: "서울특별시"})-[:CONTAINS]->(:시군구)-[:HAS_CENTER]->(c:치매안심센터)
RETURN c.name, c.phone
```

---

## 2. Neo4j란?

**Neo4j**는 세계에서 가장 널리 사용되는 **오픈소스 그래프 데이터베이스**다.

> **Cypher 쿼리 언어**
> - Neo4j 전용 쿼리 언어로, SQL과 유사하지만 그래프 구조에 최적화되어 있다.
> - 노드는 `()`, 관계는 `-->`, 레이블은 `:Label`로 표현한다.
>
> ```cypher
> -- 기본 문법 구조
> MATCH (a:레이블 {프로퍼티: "값"})-[:관계명]->(b:레이블)
> RETURN a, b
> ```

### Neo4j AuraDB

이번 프로젝트에서는 **Neo4j AuraDB** (클라우드 무료 버전)를 사용한다.

- 별도 설치 없이 브라우저에서 바로 사용 가능
- 무료 플랜: 200,000 노드, 400,000 관계까지 지원
- 우리 프로젝트 규모 (506 노드, 489 관계)는 무료 플랜으로 충분

---

## 3. 왜 GraphDB를 쓰는가?

### 이 프로젝트에서 GraphDB가 필요한 이유

이번 챗봇은 두 가지 질문을 동시에 처리해야 한다.

```
보호자: "우리 엄마가 자꾸 같은 말을 반복해요. 치매인가요? 
         서울 강남구에 있는 치매안심센터도 알려주세요."
         
챗봇:  ① 증상 관련 답변  →  VectorDB (Qdrant) 에서 검색
       ② 센터 위치 조회  →  GraphDB (Neo4j) 에서 조회
```

**센터 위치 조회**는 `시도 → 시군구 → 센터`라는 **계층 구조**를 가진다. 이런 계층적 관계 탐색은 GraphDB가 RDB보다 직관적이고 빠르다.

### VectorDB와 GraphDB의 역할 분리

| 역할 | 담당 DB | 처리하는 질문 예시 |
|------|---------|------------------|
| 비정형 문서 검색 | VectorDB (Qdrant) | "치매 초기 증상이 뭔가요?" |
| 구조화된 관계 조회 | GraphDB (Neo4j) | "서울 강남구 치매안심센터 알려줘" |

---

## 4. 우리 프로젝트 설계

### 노드 설계

| 레이블 | 개수 | 프로퍼티 |
|--------|------|----------|
| `:시도` | 17개 | `name` |
| `:시군구` | 233개 | `name` |
| `:치매안심센터` | 256개 | `name`, `address`, `phone`, `lat`, `lng`, `homepage`, `open_date` |

### 관계 설계

| 관계 | 개수 | 방향 | 의미 |
|------|------|------|------|
| `CONTAINS` | 233개 | 시도 → 시군구 | 시도가 시군구를 포함한다 |
| `HAS_CENTER` | 256개 | 시군구 → 치매안심센터 | 시군구에 센터가 있다 |

### 그래프 구조도

```
(:시도 {name: "서울특별시"})
        |
    [CONTAINS]
        |
        ▼
(:시군구 {name: "강남구"})
        |
    [HAS_CENTER]
        |
        ▼
(:치매안심센터 {
    name: "서울특별시강남구치매안심센터",
    address: "서울특별시 강남구 ...",
    phone: "02-568-4203",
    lat: 37.xx,
    lng: 127.xx,
    homepage: "...",
    open_date: "2018-12-18"
})
```

### 주요 Cypher 쿼리 예시

```cypher
-- 1. 시도로 센터 전체 조회
MATCH (:시도 {name: "서울특별시"})-[:CONTAINS]->(:시군구)-[:HAS_CENTER]->(c:치매안심센터)
RETURN c.name, c.address, c.phone

-- 2. 시도 + 시군구로 센터 조회
MATCH (:시도 {name: "서울특별시"})-[:CONTAINS]->(:시군구 {name: "강남구"})-[:HAS_CENTER]->(c:치매안심센터)
RETURN c.name, c.address, c.phone

-- 3. 전체 센터 조회
MATCH (c:치매안심센터)
RETURN c.name, c.address, c.phone
```

---

## 5. 작업 순서 (Step by Step)

### Step 1. 데이터 파악 및 정제

**목표**: 원본 CSV를 Neo4j에 적재하기 좋은 형태로 정제한다.

```python
# preprocess.py
import pandas as pd

df = pd.read_csv('data/raw/국립중앙의료원_치매안심센터_정보_20260128.csv', encoding='utf-8')

# 1. 필요한 컬럼만 선택
df = df[['치매안심센터명', '시도', '시군구', '주소1', '전화번호', '위도', '경도', '홈페이지', '개소일']]

# 2. 컬럼명 영문으로 변경 (Neo4j 적재 시 편의)
df.columns = ['name', 'sido', 'sigungu', 'address', 'phone', 'lat', 'lng', 'homepage', 'open_date']

# 3. 결측치 처리
df['homepage'] = df['homepage'].fillna('')
df['phone'] = df['phone'].fillna('')

# 4. 저장
df.to_csv('data/processed/치매안심센터_cleaned.csv', index=False, encoding='utf-8-sig')
print(f"정제 완료: {len(df)}개 센터")
```

**체크포인트**
- [ ] 원본 CSV 256행 확인
- [ ] 결측치 처리 완료 (주소2, 팩스번호 제외)
- [ ] `data/processed/치매안심센터_cleaned.csv` 저장

---

### Step 2. Neo4j AuraDB 세팅

**목표**: 클라우드 Neo4j 인스턴스를 생성하고 접속 정보를 확보한다.

1. [https://console.neo4j.io](https://console.neo4j.io) 접속 → 회원가입
2. **New Instance** → **AuraDB Free** 선택
3. 인스턴스 생성 후 접속 정보 저장

```bash
# .env 파일에 저장
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

> ⚠️ `.env` 파일은 절대 GitHub에 커밋하지 않는다. `.env.example`에 키 이름만 남긴다.

**체크포인트**
- [ ] AuraDB 인스턴스 생성 완료
- [ ] `.env` 파일에 접속 정보 저장
- [ ] Python에서 접속 테스트 완료

```python
# 접속 테스트
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)
driver.verify_connectivity()
print("Neo4j 접속 성공!")
```

---

### Step 3. 데이터 적재 (load_neo4j.py)

**목표**: 정제된 CSV를 Neo4j에 노드와 관계로 적재한다.

```python
# load_neo4j.py
import pandas as pd
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)

df = pd.read_csv('data/processed/치매안심센터_cleaned.csv', encoding='utf-8-sig')

def load_data(tx, row):
    tx.run("""
        // 시도 노드 생성 (중복 방지)
        MERGE (sido:시도 {name: $sido})
        
        // 시군구 노드 생성 (중복 방지)
        MERGE (sigungu:시군구 {name: $sigungu})
        
        // 시도 → 시군구 관계
        MERGE (sido)-[:CONTAINS]->(sigungu)
        
        // 치매안심센터 노드 생성
        MERGE (center:치매안심센터 {name: $name})
        SET center.address  = $address,
            center.phone    = $phone,
            center.lat      = $lat,
            center.lng      = $lng,
            center.homepage = $homepage,
            center.open_date = $open_date
        
        // 시군구 → 센터 관계
        MERGE (sigungu)-[:HAS_CENTER]->(center)
    """,
        sido=row['sido'],
        sigungu=row['sigungu'],
        name=row['name'],
        address=row['address'],
        phone=row['phone'],
        lat=row['lat'],
        lng=row['lng'],
        homepage=row['homepage'],
        open_date=row['open_date']
    )

with driver.session() as session:
    for _, row in df.iterrows():
        session.execute_write(load_data, row)

print(f"적재 완료: {len(df)}개 센터")
driver.close()
```

> **MERGE란?**
> - `CREATE`는 중복 상관없이 무조건 생성한다.
> - `MERGE`는 이미 존재하면 가져오고, 없으면 생성한다.
> - 시도/시군구 노드는 여러 센터가 공유하므로 반드시 `MERGE`를 써야 중복 노드가 생기지 않는다.

**체크포인트**
- [ ] 노드 수 확인: 시도 17개, 시군구 233개, 센터 256개 (총 506개)
- [ ] 관계 수 확인: CONTAINS 233개, HAS_CENTER 256개 (총 489개)
- [ ] Neo4j Browser에서 `MATCH (n) RETURN count(n)` 으로 검증

---

### Step 4. 조회 함수 구현 (query_functions.py)

**목표**: 프롬프트팀(효민·연아)이 LangChain 파이프라인에서 바로 호출할 수 있는 함수를 만든다.

```python
# query_functions.py
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URI'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)

def get_centers_by_sido(sido: str) -> list[dict]:
    """시도명으로 치매안심센터 목록 조회"""
    with driver.session() as session:
        result = session.run("""
            MATCH (:시도 {name: $sido})-[:CONTAINS]->(:시군구)-[:HAS_CENTER]->(c:치매안심센터)
            RETURN c.name AS name, c.address AS address, c.phone AS phone
            ORDER BY c.name
        """, sido=sido)
        return [dict(record) for record in result]


def get_centers_by_sigungu(sido: str, sigungu: str) -> list[dict]:
    """시도 + 시군구로 치매안심센터 조회"""
    with driver.session() as session:
        result = session.run("""
            MATCH (:시도 {name: $sido})-[:CONTAINS]->(:시군구 {name: $sigungu})-[:HAS_CENTER]->(c:치매안심센터)
            RETURN c.name AS name, c.address AS address, c.phone AS phone
        """, sido=sido, sigungu=sigungu)
        return [dict(record) for record in result]


def get_all_centers() -> list[dict]:
    """전체 치매안심센터 조회"""
    with driver.session() as session:
        result = session.run("""
            MATCH (c:치매안심센터)
            RETURN c.name AS name, c.address AS address, c.phone AS phone
            ORDER BY c.name
        """)
        return [dict(record) for record in result]


# 사용 예시
if __name__ == "__main__":
    # 서울 전체 센터
    centers = get_centers_by_sido("서울특별시")
    print(f"서울 센터 수: {len(centers)}")
    
    # 강남구 센터
    center = get_centers_by_sigungu("서울특별시", "강남구")
    print(center)
```

**체크포인트**
- [ ] `get_centers_by_sido()` 동작 확인
- [ ] `get_centers_by_sigungu()` 동작 확인
- [ ] 프롬프트팀(효민·연아)에게 함수 시그니처 공유

---

### Step 5. 산출물 문서 작성

**목표**: `docs/03_DB설계.md` 에 GraphDB 설계 내용을 정리한다. (발표 자료 반영)

작성 항목:
- [ ] 노드 종류 및 프로퍼티 표
- [ ] 관계 종류 및 방향 표
- [ ] 그래프 구조도 (ASCII)
- [ ] 데이터 출처 및 수집 방법
- [ ] 정제 기준 (결측치 처리 등)

---

## 참고 자료

- [Neo4j AuraDB 콘솔](https://console.neo4j.io)
- [Neo4j Python Driver 공식 문서](https://neo4j.com/docs/python-manual/current/)
- [Cypher 쿼리 치트시트](https://neo4j.com/docs/cypher-cheat-sheet/)
- [공공데이터포털 치매안심센터 원본](https://www.data.go.kr/data/15138421/fileData.do)
