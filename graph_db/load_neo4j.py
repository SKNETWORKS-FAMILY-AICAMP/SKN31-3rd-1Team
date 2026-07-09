import pandas as pd
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()


def get_driver():
    """Neo4j 드라이버 생성"""
    return GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD')),
        connection_timeout=30
    )


def load_row(tx, row):
    """단일 행을 Neo4j 노드/관계로 적재"""
    tx.run("""
        MERGE (sido:시도 {시도명: $시도})
        MERGE (sigungu:시군구 {시군구명: $시군구})
        MERGE (sigungu)-[:CONTAINS]->(sido)
        MERGE (center:치매안심센터 {센터명: $센터명})
        SET center.주소     = $주소,
            center.우편번호  = $우편번호,
            center.전화번호  = $전화번호,
            center.팩스번호  = $팩스번호,
            center.위도     = $위도,
            center.경도     = $경도,
            center.홈페이지  = $홈페이지,
            center.설립일   = $설립일
        MERGE (center)-[:LOCATED_IN]->(sigungu)
    """,
        시도=row['시도'],
        시군구=row['시군구'],
        센터명=row['치매안심센터명'],
        주소=row['주소'],
        우편번호=row['우편번호'],
        전화번호=row['전화번호'],
        팩스번호=row['팩스번호'],
        위도=row['위도'],
        경도=row['경도'],
        홈페이지=row['홈페이지'],
        설립일=row['설립일']
    )


def load_data(csv_path: str) -> None:
    """정제된 CSV를 Neo4j에 적재"""
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    driver = get_driver()

    with driver.session() as session:
        for _, row in df.iterrows():
            session.execute_write(load_row, row)

    print(f"적재 완료: {len(df)}개 센터")
    driver.close()


if __name__ == "__main__":
    load_data('data/processed/치매안심센터_cleaned.csv')
