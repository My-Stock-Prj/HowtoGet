# MST 파일 생성용
import urllib.request
import ssl
import zipfile
import os
import pandas as pd
import numpy as np

# 1. 환경 설정 및 다운로드 함수
def download_master(market_type):
    ssl._create_default_https_context = ssl._create_unverified_context
    url = f"https://new.real.download.dws.co.kr/common/master/{market_type}_code.mst.zip"
    file_zip = f"{market_type}.zip"
    urllib.request.urlretrieve(url, file_zip)
    
    with zipfile.ZipFile(file_zip) as z:
        z.extractall()
    os.remove(file_zip)
    return f"{market_type}_code.mst"

# 2. 파싱 엔진 (KOSPI: 228 bytes / KOSDAQ: 222 bytes)
def parse_master(file_name, market_code):
    p2_len = 228 if market_code == "STK" else 222
    tmp1, tmp2 = "part1.tmp", "part2.tmp"
    
    with open(file_name, mode="r", encoding="cp949") as f, \
         open(tmp1, mode="w", encoding="cp949") as wf1, \
         open(tmp2, mode="w", encoding="cp949") as wf2:
        for row in f:
            p1 = row[0:len(row) - p2_len]
            # 구분자(sep)를 | 로 설정하여 종목명 내 쉼표 무력화
            wf1.write(f"{p1[0:9].strip()}|{p1[9:21].strip()}|{p1[21:].strip()}\n")
            wf2.write(row[-p2_len:])

    # Part 1 공통 (종목명 통일)
    df1 = pd.read_csv(tmp1, sep="|", header=None, names=['단축코드', '표준코드', '종목명'], encoding='cp949')
    
    # Part 2 시장별 규격 정의
    if market_code == "STK":
        specs = [2, 1, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 9, 5, 5, 1, 1, 1, 2, 1, 1, 1, 2, 2, 2, 3, 1, 3, 12, 12, 8, 15, 21, 2, 7, 1, 1, 1, 1, 1, 9, 9, 9, 5, 9, 8, 9, 3, 1, 1, 1]
        cols = ['그룹코드', '시가총액규모', '지수업종대분류', '지수업종중분류', '지수업종소분류', '제조업', '저유동성', '지배구조지수종목', 'KOSPI200섹터업종', 'KOSPI100', 'KOSPI50', 'KRX', 'ETP', 'ELW발행', 'KRX100', 'KRX자동차', 'KRX반도체', 'KRX바이오', 'KRX은행', 'SPAC', 'KRX에너지화학', 'KRX철강', '단기과열', 'KRX미디어통신', 'KRX건설', 'Non1', 'KRX증권', 'KRX선박', 'KRX섹터_보험', 'KRX섹터_운송', 'SRI', '기준가', '매매수량단위', '시간외수량단위', '거래정지', '정리매매', '관리종목', '시장경고', '경고예고', '불성실공시', '우회상장', '락구분', '액면변경', '증자구분', '증거금비율', '신용가능', '신용기간', '전일거래량', '액면가', '상장일자', '상장주수', '자본금', '결산월', '공모가', '우선주', '공매도과열', '이상급등', 'KRX300', 'KOSPI', '매출액', '영업이익', '경상이익', '당기순이익', 'ROE', '기준년월', '시가총액', '그룹사코드', '회사신용한도초과', '담보대출가능', '대주가능']
    else:
        specs = [2, 1, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 9, 5, 5, 1, 1, 1, 2, 1, 1, 1, 2, 2, 2, 3, 1, 3, 12, 12, 8, 15, 21, 2, 7, 1, 1, 1, 1, 1, 9, 9, 9, 5, 9]
        # KOSDAQ '기업인수목적회사여부' -> 'SPAC'으로 통일
        cols = ['그룹코드', '중소기업여부', '지수업종대분류', '지수업종중분류', '지수업종소분류', '벤처기업여부', '저유동성', 'KRX종목여부', 'ETP구분', 'KRX100여부', 'KRX자동차', 'KRX반도체', 'KRX바이오', 'KRX은행', 'SPAC', 'KRX에너지화학', 'KRX철강', '단기과열', 'KRX미디어통신', 'KRX건설', '투자주의환기', 'KRX증권', 'KRX선박', 'KRX보험', 'KRX운송', 'KOSDAQ150', 'SRI', '기준가', '매매수량단위', '시간외수량단위', '거래정지', '정리매매', '관리종목', '시장경고', '경고예고', '불성실공시', '우회상장', '락구분', '액면변경', '증자구분', '증거금비율', '신용가능', '신용기간', '전일거래량', '액면가', '상장일자', '상장주수', '자본금', '결산월', '공모가', '우선주', '공매도과열', '이상급등', 'KRX300', 'KOSDAQ', '매출액', '영업이익', '경상이익', '당기순이익', 'ROE', '기준년월', '시가총액', '그룹사코드', '담보대출가능']

    df2 = pd.read_fwf(tmp2, widths=specs, names=cols, encoding='cp949', dtype=str)
    full_df = pd.concat([df1, df2], axis=1)
    full_df['시장구분'] = market_code
    
    # [디버깅] 시장별 파싱 결과 확인
    print(f"[{market_code}] 파싱 완료 - 전체 건수: {len(full_df)}")
    
    for f in [tmp1, tmp2, file_name]: os.remove(f)
    return full_df

# 3. 메인 통합 및 무결성 처리
def build_raw_db():
    print("마스터 데이터 다운로드 및 파싱 시작...")
    df_stk = parse_master(download_master("kospi"), "STK")
    df_ksq = parse_master(download_master("kosdaq"), "KSQ")
    
    # 통합 (Outer Join 효과로 모든 칼럼 유지)
    raw_df = pd.concat([df_stk, df_ksq], ignore_index=True)
    
    # [디버깅] 통합 직후 상태 확인
    print(f"통합 완료 - 전체 건수: {len(raw_df)}")
    print(f"그룹코드 샘플(앞 5개): {raw_df['그룹코드'].head().tolist()}")
    print(f"그룹코드 유니크 값: {raw_df['그룹코드'].unique()}")

    # [무결성 처리 1] 그룹코드 필터링 (01: 주식, 02: ETF)
    raw_df['그룹코드'] = raw_df['그룹코드'].str.zfill(2)
    raw_df = raw_df[raw_df['그룹코드'].isin(['01', '02'])].copy()

    # [디버깅] 필터링 후 결과 확인
    print(f"필터링(01, 02) 후 건수: {len(raw_df)}")

    # [무결성 처리 2] 명시적 Y/N 및 Null 처리
    # YN성 칼럼 리스트 (명칭에 '여부', '지목', '지수', 'KRX' 등이 포함된 칼럼들 대상)
    yn_cols = [c for c in raw_df.columns if any(x in c for x in ['여부', '지목', '지수', 'KRX', 'SPAC', '제조업', '유동성', '과열', '경고', '정지', '매매', '종목', '가능'])]
    for col in yn_cols:
        raw_df[col] = raw_df[col].fillna('N').replace({'0': 'N', '1': 'Y', ' ': 'N'})

    # [무결성 처리 3] 수치 데이터 타입 변환 및 0 채움
    num_cols = ['기준가', '상장주수', '자본금', '액면가', '전일거래량', '매출액', '영업이익', '경상이익', '당기순이익', 'ROE', '시가총액']
    for col in num_cols:
        if col in raw_df.columns:
            raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce').fillna(0)

    # [무결성 처리 4] 문자열 칼럼 공백 제거
    str_cols = raw_df.select_dtypes(include=['object']).columns
    for col in str_cols:
        raw_df[col] = raw_df[col].str.strip()

    # 4. 저장 (DB 폴더 하위)
    save_dir = "DB"
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, "raw_mst_krx_full.parquet")
    
    raw_df.to_parquet(save_path, engine='pyarrow', index=False, compression='snappy')
    print(f"완료! RAW DB 저장 경로: {save_path}")
    print(f"최종 칼럼 수: {len(raw_df.columns)}, 데이터 건수: {len(raw_df)}")

if __name__ == "__main__":
    build_raw_db()
