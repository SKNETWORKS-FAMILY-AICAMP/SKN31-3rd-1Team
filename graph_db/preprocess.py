# -*- coding: utf-8 -*-
"""
치매알람 GraphDB 전처리 파이프라인
파일1: 국립중앙의료원_치매안심센터_정보_20260128.csv (256행, 시도/시군구 정제됨)
파일2: 전국치매센터표준데이터_utf8.csv (317행, 프로그램/유형/인원현황 포함)
"""
import pandas as pd
import numpy as np
import re
import math
import json
import os

pd.set_option('future.no_silent_downcasting', True)

# ============================================================
# 경로 설정 (data/ 가 graph_db/ 폴더 안에 있음: graph_db/data/raw, graph_db/data/processed)
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')
OUT_DIR = os.path.join(BASE_DIR, 'data', 'processed')
os.makedirs(OUT_DIR, exist_ok=True)

def raw(fname):
    return os.path.join(RAW_DIR, fname)

def out(fname):
    return os.path.join(OUT_DIR, fname)

# ============================================================
# 0. 로드
# ============================================================
df1 = pd.read_csv(raw('국립중앙의료원_치매안심센터_정보_20260128.csv'), encoding='utf-8-sig')
df2 = pd.read_csv(raw('전국치매센터표준데이터_utf8.csv'), encoding='utf-8-sig')

# ============================================================
# 1. 컬럼 선별
# ============================================================
df1 = df1[['치매안심센터명', '시도', '시군구', '우편번호', '주소1', '주소2',
           '위도', '경도', '홈페이지', '전화번호', '팩스번호', '개소일']].copy()
df1['주소'] = df1['주소1'].fillna('') + ' ' + df1['주소2'].fillna('')
df1['주소'] = df1['주소'].str.strip()
df1 = df1.drop(columns=['주소1', '주소2'])
df1 = df1.rename(columns={'개소일': '설립일'})

df2 = df2[['치매센터명', '치매센터유형', '소재지도로명주소', '위도', '경도',
           '설립연월', '의사인원수', '간호사인원수', '사회복지사인원수', '기타인원현황',
           '운영기관명', '운영기관대표자명', '운영기관전화번호', '주요치매관리프로그램소개']].copy()

# ============================================================
# 2. 파일2 주소 → 시도/시군구 파싱
# ============================================================
SIDO_NORMALIZE = {
    '전라북도': '전북특별자치도',
}

def parse_address(addr):
    tokens = str(addr).split()
    if not tokens:
        return None, None
    sido = tokens[0]
    sido = SIDO_NORMALIZE.get(sido, sido)
    if sido == '세종특별자치시':
        sigungu = '세종시'
    else:
        sigungu = tokens[1] if len(tokens) > 1 else None
    return sido, sigungu

parsed = df2['소재지도로명주소'].apply(parse_address)
df2['시도'] = parsed.apply(lambda x: x[0])
df2['시군구'] = parsed.apply(lambda x: x[1])

# ============================================================
# 3. 센터 매칭 (파일1 <-> 파일2) : 같은 시군구 내에서 좌표 최근접 매칭
# ============================================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

df1['_matched'] = False
df2['_matched'] = False
df1['_match_idx2'] = -1
df2['_match_idx1'] = -1

DIST_THRESHOLD_KM = 5.0
NAME_FALLBACK_DIST_KM = 30.0  # 이름이 일치하면 좌표 오차가 있어도 넓게 허용

SUFFIX_PATTERN = re.compile(r'(치매안심센터|광역치매센터|치매정신통합센터|치매센터)$')

def strip_name(name, sido, sigungu):
    n = re.sub(r'\s+', '', str(name))
    n = SUFFIX_PATTERN.sub('', n)
    n = n.replace(str(sido), '').replace(str(sigungu), '')
    return n

for sgg, group1 in df1.groupby(['시도', '시군구']):
    # 파일1은 전부 '치매안심센터' 타입이므로, 매칭 후보도 같은 타입으로 제한한다.
    # (제한 안 하면 근거리에 있는 광역치매센터/치매상담전화센터로 잘못 매칭되는 문제가 있었음)
    group2 = df2[(df2['시도'] == sgg[0]) & (df2['시군구'] == sgg[1]) & (df2['치매센터유형'] == '치매안심센터')]
    if group2.empty:
        continue

    used1, used2 = set(), set()

    # 1차: 같은 시군구 내에서 센터명 핵심부(시군구/접미어 제거 후) 일치 매칭
    for i1, r1 in group1.iterrows():
        core1 = strip_name(r1['치매안심센터명'], r1['시도'], r1['시군구'])
        for i2, r2 in group2.iterrows():
            if i2 in used2:
                continue
            core2 = strip_name(r2['치매센터명'], r2['시도'], r2['시군구'])
            if core1 == core2:
                used1.add(i1)
                used2.add(i2)
                df1.loc[i1, '_matched'] = True
                df1.loc[i1, '_match_idx2'] = i2
                df2.loc[i2, '_matched'] = True
                df2.loc[i2, '_match_idx1'] = i1
                break

    # 2차: 남은 것들 좌표 최근접 매칭 (기본 5km, 이름이 부분적으로라도 겹치면 30km까지 허용)
    candidates = []
    for i1, r1 in group1.iterrows():
        if i1 in used1:
            continue
        core1 = strip_name(r1['치매안심센터명'], r1['시도'], r1['시군구'])
        for i2, r2 in group2.iterrows():
            if i2 in used2:
                continue
            if pd.isna(r1['위도']) or pd.isna(r2['위도']):
                continue
            core2 = strip_name(r2['치매센터명'], r2['시도'], r2['시군구'])
            d = haversine(r1['위도'], r1['경도'], r2['위도'], r2['경도'])
            name_overlap = (core1 and core1 in core2) or (core2 and core2 in core1) or (not core1 and not core2)
            threshold = NAME_FALLBACK_DIST_KM if name_overlap else DIST_THRESHOLD_KM
            if d <= threshold:
                candidates.append((d, i1, i2))
    candidates.sort(key=lambda x: x[0])
    for d, i1, i2 in candidates:
        if i1 in used1 or i2 in used2:
            continue
        used1.add(i1)
        used2.add(i2)
        df1.loc[i1, '_matched'] = True
        df1.loc[i1, '_match_idx2'] = i2
        df2.loc[i2, '_matched'] = True
        df2.loc[i2, '_match_idx1'] = i1

n_matched = (df1['_matched']).sum()
print(f'매칭 성공: {n_matched} / {len(df1)} (파일1 기준)')
print(f'파일2 중 매칭 안 된 행(파일2 단독 센터 후보): {(~df2["_matched"]).sum()}')

# ============================================================
# 4. 기타인원현황 표준 직종 매핑
# ============================================================
JOB_MAP = {
    '임상심리사': ['임상심리사', '임상심리상담사', '정신건강임상심리사', '심리상담사'],
    '작업치료사': ['작업치료사'],
    '물리치료사': ['물리치료사'],
    '방사선사': ['방사선사'],
    '의무기록사': ['의무기록사', '보건의료정보관리사'],
    '치위생사': ['치위생사', '치과위생사'],
    '임상병리사': ['임상병리사'],
    '영양사': ['영양사'],
    '음악치료사': ['음악치료사'],
    '운동치료사': ['운동치료사', '운동처방사', '비약물치료사'],
    '응급구조사': ['응급구조사'],
    '행정인력': ['행정', '공무원', '공무직', '보건직', '센터장', '부센터장', '팀장', '총괄',
              '회계사', '청년인턴', '사회복무', '기간제', '대체인력', '조무사', '간호조무사'],
    '송영인력': ['송영', '운전'],
    '시설관리': ['위생사', '청소', '청사관리', '청원경찰'],
}

# 메인 컬럼(의사/간호사/사회복지사)과 중복되는 표현은 기타인원현황 파싱에서 제외
EXCLUDE_FROM_ETC = ['간호사', '사회복지사', '의사']


def classify_job(token_name):
    """직종 단일 표기(괄호/숫자 제거된 상태)를 표준 카테고리로 매핑"""
    name = token_name.strip()
    if not name:
        return None
    for excl in EXCLUDE_FROM_ETC:
        if name == excl:
            return None  # 메인 컬럼과 중복 -> 제외
    for std, variants in JOB_MAP.items():
        for v in variants:
            if v in name:
                return std
    return '기타'


def parse_etc_personnel(raw):
    """'임상심리사 1, 음악치료사 1, 작업치료사2' 같은 원본 문자열을 {표준직종: 인원수} 로 파싱"""
    if pd.isna(raw):
        return {}
    result = {}
    # +와 ,를 모두 구분자로 사용
    parts = re.split(r'[+,]', str(raw))
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 숫자만 있는 오염값(예: "1","2","3")은 기타로 카운트하지 않고 스킵 (직종 불명)
        if re.fullmatch(r'\d+', part):
            continue
        # 인원수 추출 (뒤에 붙은 숫자 또는 "N명")
        m = re.search(r'(\d+)\s*명?\)?$', part)
        count = int(m.group(1)) if m else 1
        # 직종명만 추출 (숫자/괄호 제거)
        name_part = re.sub(r'\(.*?\)', '', part)
        name_part = re.sub(r'\d+\s*명?\)?$', '', name_part).strip()
        if not name_part:
            continue
        std = classify_job(name_part)
        if std is None:
            continue
        result[std] = result.get(std, 0) + count
    return result


df2['인원현황_파싱'] = df2['기타인원현황'].apply(parse_etc_personnel)

# ============================================================
# 5. 프로그램 텍스트 분리
# ============================================================
def split_programs(raw):
    if pd.isna(raw):
        return []
    parts = [p.strip() for p in str(raw).split('+')]
    return [p for p in parts if p]

df2['프로그램_리스트'] = df2['주요치매관리프로그램소개'].apply(split_programs)

# ============================================================
# 6. 검수용 통합본 (centers_merged.csv)
# ============================================================
merged_rows = []

# 6-1. 파일1 기준 매칭된 센터 (+ 파일1 단독 센터)
for i1, r1 in df1.iterrows():
    i2 = r1['_match_idx2']
    row = {
        '센터명': r1['치매안심센터명'],
        '시도': r1['시도'],
        '시군구': r1['시군구'],
        '유형': None,
        '주소': r1['주소'],
        '우편번호': r1['우편번호'],
        '위도': r1['위도'],
        '경도': r1['경도'],
        '전화번호': r1['전화번호'],
        '팩스번호': r1['팩스번호'],
        '홈페이지': r1['홈페이지'],
        '설립일': r1['설립일'],
        '의사인원수': None,
        '간호사인원수': None,
        '사회복지사인원수': None,
        '기타인원_파싱': {},
        '운영기관명': None,
        '운영기관대표자명': None,
        '운영기관전화번호': None,
        '프로그램_개수': 0,
        '프로그램_리스트': [],
        '데이터출처': '파일1',
    }
    if i2 != -1:
        r2 = df2.loc[i2]
        row['유형'] = r2['치매센터유형']
        row['의사인원수'] = r2['의사인원수']
        row['간호사인원수'] = r2['간호사인원수']
        row['사회복지사인원수'] = r2['사회복지사인원수']
        row['기타인원_파싱'] = r2['인원현황_파싱']
        row['운영기관명'] = r2['운영기관명']
        row['운영기관대표자명'] = r2['운영기관대표자명']
        row['운영기관전화번호'] = r2['운영기관전화번호']
        row['프로그램_개수'] = len(r2['프로그램_리스트'])
        row['프로그램_리스트'] = r2['프로그램_리스트']
        row['데이터출처'] = '파일1+파일2'
    else:
        row['유형'] = '치매안심센터'  # 파일1은 전부 치매안심센터
    merged_rows.append(row)

# 6-2. 파일2 단독 센터 (매칭 안 된 것 = 광역치매센터/치매상담전화센터/추가 지점 등)
for i2, r2 in df2[~df2['_matched']].iterrows():
    row = {
        '센터명': r2['치매센터명'],
        '시도': r2['시도'],
        '시군구': r2['시군구'],
        '유형': r2['치매센터유형'],
        '주소': r2['소재지도로명주소'],
        '우편번호': None,
        '위도': r2['위도'],
        '경도': r2['경도'],
        '전화번호': r2['운영기관전화번호'],
        '팩스번호': None,
        '홈페이지': None,
        '설립일': r2['설립연월'],
        '의사인원수': r2['의사인원수'],
        '간호사인원수': r2['간호사인원수'],
        '사회복지사인원수': r2['사회복지사인원수'],
        '기타인원_파싱': r2['인원현황_파싱'],
        '운영기관명': r2['운영기관명'],
        '운영기관대표자명': r2['운영기관대표자명'],
        '운영기관전화번호': r2['운영기관전화번호'],
        '프로그램_개수': len(r2['프로그램_리스트']),
        '프로그램_리스트': r2['프로그램_리스트'],
        '데이터출처': '파일2',
    }
    merged_rows.append(row)

centers_merged = pd.DataFrame(merged_rows)
centers_merged.insert(0, '센터ID', ['C' + str(i + 1).zfill(4) for i in range(len(centers_merged))])
centers_merged['기타인원_파싱_JSON'] = centers_merged['기타인원_파싱'].apply(lambda d: json.dumps(d, ensure_ascii=False))
centers_merged['프로그램_리스트_텍스트'] = centers_merged['프로그램_리스트'].apply(lambda l: ' | '.join(l))

# 검수용 CSV 저장 (기타인원_파싱/프로그램_리스트 원본 dict/list 컬럼은 제외하고 텍스트화된 것만)
review_cols = ['센터ID', '센터명', '시도', '시군구', '유형', '주소', '우편번호', '위도', '경도',
               '전화번호', '팩스번호', '홈페이지', '설립일', '의사인원수', '간호사인원수', '사회복지사인원수',
               '기타인원_파싱_JSON', '운영기관명', '운영기관대표자명', '운영기관전화번호',
               '프로그램_개수', '프로그램_리스트_텍스트', '데이터출처']
centers_merged[review_cols].to_csv(out('centers_merged.csv'), index=False, encoding='utf-8-sig')
print(f'centers_merged.csv 저장 완료: {len(centers_merged)}행')

# ============================================================
# 7. 노드 CSV 생성
# ============================================================
# 7-1. 시도
sido_list = sorted(centers_merged['시도'].dropna().unique())
nodes_sido = pd.DataFrame({'name': sido_list})
nodes_sido.to_csv(out('nodes_시도.csv'), index=False, encoding='utf-8-sig')

# 7-2. 시군구 (시도+시군구 조합, 시도명도 같이 저장해서 관계 생성에 사용)
sgg_df = centers_merged[['시도', '시군구']].dropna().drop_duplicates().sort_values(['시도', '시군구'])
sgg_df.columns = ['시도', 'name']
sgg_df.to_csv(out('nodes_시군구.csv'), index=False, encoding='utf-8-sig')

# 7-3. 치매안심센터
# 다른 노드(시도/시군구/운영기관/프로그램)와 식별 프로퍼티명을 'name'으로 통일한다.
# (이전 버전에서는 '센터명'으로 남겨둬서 cypher_prompt/검증 쿼리와 불일치가 생겼던 문제 수정)
nodes_center = centers_merged[['센터ID', '센터명', '유형', '시도', '시군구', '주소', '우편번호',
                                '위도', '경도', '전화번호', '팩스번호', '홈페이지', '설립일',
                                '의사인원수', '간호사인원수', '사회복지사인원수']].copy()
nodes_center = nodes_center.rename(columns={'센터명': 'name'})
# 기타인원 파싱 결과를 개별 컬럼으로 펼치기
etc_expanded = pd.json_normalize(centers_merged['기타인원_파싱'])
etc_expanded = etc_expanded.add_prefix('인원_')
nodes_center = pd.concat([nodes_center.reset_index(drop=True), etc_expanded.reset_index(drop=True)], axis=1)
nodes_center.to_csv(out('nodes_치매안심센터.csv'), index=False, encoding='utf-8-sig')

# 7-4. 운영기관 (중복 제거)
op_df = centers_merged[['운영기관명', '운영기관대표자명', '운영기관전화번호']].dropna(subset=['운영기관명']).drop_duplicates(subset=['운영기관명'])
op_df = op_df.reset_index(drop=True)
op_df.insert(0, '운영기관ID', ['O' + str(i + 1).zfill(4) for i in range(len(op_df))])
op_df.columns = ['운영기관ID', 'name', '대표자명', '전화번호']
op_df.to_csv(out('nodes_운영기관.csv'), index=False, encoding='utf-8-sig')

# 7-5. 프로그램 (고유값 기준 생성)
all_programs = {}
for _, row in centers_merged.iterrows():
    for p in row['프로그램_리스트']:
        if p not in all_programs:
            all_programs[p] = len(all_programs) + 1

nodes_program = pd.DataFrame([
    {'프로그램ID': 'P' + str(v).zfill(4), 'name': k, 'category': None,
     'source': '전국치매센터표준데이터_utf8.csv', 'raw_text': k}
    for k, v in all_programs.items()
])
nodes_program.to_csv(out('nodes_프로그램.csv'), index=False, encoding='utf-8-sig')

# ============================================================
# 8. 관계 CSV 생성 (전부 단방향)
# ============================================================
# 8-1. 시군구 -[:LOCATED_IN]-> 시도
rels_located_in_sgg = sgg_df.rename(columns={'name': '시군구'})[['시군구', '시도']]
rels_located_in_sgg.to_csv(out('rels_시군구_LOCATED_IN_시도.csv'), index=False, encoding='utf-8-sig')

# 8-2. 시도 -[:CONTAINS]-> 시군구
rels_contains = sgg_df.rename(columns={'name': '시군구'})[['시도', '시군구']]
rels_contains.to_csv(out('rels_시도_CONTAINS_시군구.csv'), index=False, encoding='utf-8-sig')

# 8-3. 치매안심센터 -[:LOCATED_IN]-> 시군구
rels_center_located = nodes_center[['센터ID', '시군구']].dropna()
rels_center_located.to_csv(out('rels_센터_LOCATED_IN_시군구.csv'), index=False, encoding='utf-8-sig')

# 8-4. 운영기관 -[:MANAGES]-> 치매안심센터
op_lookup = op_df.set_index('name')['운영기관ID'].to_dict()
manages_rows = []
for _, row in centers_merged.iterrows():
    if pd.notna(row['운영기관명']) and row['운영기관명'] in op_lookup:
        manages_rows.append({'운영기관ID': op_lookup[row['운영기관명']], '센터ID': row['센터ID']})
rels_manages = pd.DataFrame(manages_rows)
rels_manages.to_csv(out('rels_운영기관_MANAGES_센터.csv'), index=False, encoding='utf-8-sig')

# 8-5. 치매안심센터 -[:PROVIDES]-> 프로그램
prog_lookup = {row['name']: row['프로그램ID'] for _, row in nodes_program.iterrows()}
provides_rows = []
for _, row in centers_merged.iterrows():
    for p in row['프로그램_리스트']:
        provides_rows.append({'센터ID': row['센터ID'], '프로그램ID': prog_lookup[p]})
rels_provides = pd.DataFrame(provides_rows)
rels_provides.to_csv(out('rels_센터_PROVIDES_프로그램.csv'), index=False, encoding='utf-8-sig')

# ============================================================
# 9. 요약 출력
# ============================================================
print()
print('=== 노드 개수 ===')
print(f'시도: {len(nodes_sido)}')
print(f'시군구: {len(sgg_df)}')
print(f'치매안심센터: {len(nodes_center)}')
print(f'운영기관: {len(op_df)}')
print(f'프로그램: {len(nodes_program)}')
print()
print('=== 관계 개수 ===')
print(f'시군구-LOCATED_IN->시도: {len(rels_located_in_sgg)}')
print(f'시도-CONTAINS->시군구: {len(rels_contains)}')
print(f'센터-LOCATED_IN->시군구: {len(rels_center_located)}')
print(f'운영기관-MANAGES->센터: {len(rels_manages)}')
print(f'센터-PROVIDES->프로그램: {len(rels_provides)}')
