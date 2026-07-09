import pandas as pd
import os


def preprocess(input_path: str, output_path: str) -> pd.DataFrame:
    """원본 CSV를 정제하여 저장"""

    df = pd.read_csv(input_path, encoding='utf-8')

    # 필요한 컬럼만 선택
    df = df[['치매안심센터명', '시도', '시군구', '우편번호', '주소1', '전화번호', '팩스번호', '위도', '경도', '홈페이지', '개소일']]

    # 컬럼명 정리
    df = df.rename(columns={
        '주소1': '주소',
        '개소일': '설립일'
    })

    # 결측치 처리
    df['홈페이지'] = df['홈페이지'].fillna('')
    df['전화번호'] = df['전화번호'].fillna('')
    df['팩스번호'] = df['팩스번호'].fillna('')
    df['우편번호'] = df['우편번호'].fillna('')

    # 저장
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')

    print(f"정제 완료: {len(df)}개 센터")
    print(f"저장 경로: {output_path}")
    return df


if __name__ == "__main__":
    preprocess(
        input_path='data/raw/국립중앙의료원_치매안심센터 정보_20260128.csv',
        output_path='data/processed/치매안심센터_cleaned.csv'
    )
