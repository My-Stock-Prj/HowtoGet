# MST 파일 생성용 및 구글 시트 통합 (방법 A 적용 버전)
import urllib.request
import ssl
import zipfile
import os
import pandas as pd
import numpy as np
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
import json

# 사용자님의 표준 인증 모듈 임포트
try:
    import kis_auth
except ImportError:
    kis_auth = None

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

# 2. 파싱 엔진
def parse_master(file_name, market_code):
    p2_len = 228 if market_code == "STK" else 222
    tmp1, tmp2 = "part1.tmp", "part2.tmp"
    
    with open(file_name, mode="r", encoding="cp949") as f, \
         open(tmp1, mode="w", encoding="cp949") as wf1, \
         open(tmp2, mode="w", encoding="cp949") as wf2:
        for row in f:
            p1 = row[0:len(row) - p2_len]
            wf1.write(f"{p1[0:9].strip()}|{p1[9:21].strip()}|{p1[21:].strip()}\n")
            wf2.write(row[-p2_len:])

    df1 = pd.read_csv(tmp1, sep="|", header=None, names=['단축코드', '표준코드', '종목명'], encoding='cp949')
    
    if market_code == "STK":
        specs = [2, 1, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 9, 5, 5, 1, 1, 1, 2, 1, 1, 1, 2, 2, 2, 3, 1, 3, 12, 12, 8, 15, 21, 2, 7, 1, 1, 1, 1, 1, 9, 9, 9, 5, 9, 8, 9, 3, 1, 1, 1]
        cols = ['그룹코드', '시가총액규모', '지수업종대분류', '지수업종중분류', '지수업종소분류', '제조업', '저유동성', '지배구조지수종목', 'KOSPI200섹터업종', 'KOSPI100', 'KOSPI50', 'KRX', 'ETP', 'ELW발행', 'KRX100', 'KRX자동차', 'KRX반도체', 'KRX바이오', 'KRX은행', 'SPAC', 'KRX에너지화학', 'KRX철강', '단기과열', 'KRX미디어통신', 'KRX건설', 'Non1', 'KRX증권', 'KRX선박', 'KRX섹터_보험', 'KRX섹터_운송', 'SRI', '기준가', '매매수량단위', '시간외수량단위', '거래정지', '정리매매', '관리종목', '시장경고', '경고예고', '불성실공시', '우회상장', '락구분', '액면변경', '증자구분', '증거금비율', '신용가능', '신용기간', '전일거래량', '액면가', '상장일자', '상장주수', '자본금', '결산월', '공모가', '우선주', '공매도과열', '이상급등', 'KRX300', 'KOSPI', '매출액', '영업이익', '경상이익', '당기순이익', 'ROE', '기준년월', '시가총액', '그룹사코드', '회사신용한도초과', '담보대출가능', '대주가능']
    else:
        specs = [2, 1, 4, 4, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 9, 5, 5, 1, 1, 1, 2, 1, 1, 1, 2, 2, 2, 3, 1, 3, 12, 12, 8, 15, 21, 2, 7, 1, 1, 1, 1, 1, 9, 9, 9, 5, 9]
        cols = ['그룹코드', '중소기업여부', '지수업종대분류', '지수업종중분류', '지수업종소분류', '벤처기업여부', '저유동성', 'KRX종목여부', 'ETP구분', 'KRX100여부', 'KRX자동차', 'KRX반도체', 'KRX바이오', 'KRX은행', 'SPAC', 'KRX에너지화학', 'KRX철강', '단기과열', 'KRX미디어통신', 'KRX건설', '투자주의환기', 'KRX증권', 'KRX선박', 'KRX보험', 'KRX운송', 'KOSDAQ150', 'SRI', '기준가', '매매수량단위', '시간외수량단위', '거래정지', '정리매매', '관리종목', '시장경고', '경고예고', '불성실공시', '우회상장', '락구분', '액면변경', '증자구분', '증거금비율', '신용가능', '신용기간', '전일거래량', '액면가', '상장일자', '상장주수', '자본금', '결산월', '공모가', '우선주', '공매도과열', '이상급등', 'KRX300', 'KOSDAQ', '매출액', '영업이익', '경상이익', '당기순이익', 'ROE', '기준년월', '시가총액', '그룹사코드', '담보대출가능']

    df2 = pd.read_fwf(tmp2, widths=specs, names=cols, encoding='cp949', dtype=str)
    full_df = pd.concat([df1, df2], axis=1)
    full_df['시장구분'] = market_code
    
    print(f"[{market_code}] 파싱 완료 - 전체 건수: {len(full_df)}")
    for f in [tmp1, tmp2, file_name]: os.remove(f)
    return full_df

# 3. 구글 시트 업데이트 함수 (방법 A 적용)
def update_gsheet(df):
    try:
        print("구글 시트 업데이트 시작 (파일명: 'my', 시트명: 'mst')...")
        
        # 1. 대상 데이터 생성 및 시장구분 명칭 변경
        target_df = df[['단축코드', '종목명', '시장구분']].copy()
        target_df['시장구분'] = target_df['시장구분'].replace({'STK': 'KOSPI', 'KSQ': 'KOSDAQ'})
        
        # 2. 인증 로직
        creds_json = os.environ.get('GCP_CREDENTIALS')
        if not creds_json:
            print("인증 정보(GCP_CREDENTIALS)가 없어 중단합니다.")
            return

        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        
        sh = gc.open('my')
        try:
            worksheet = sh.worksheet('mst')
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title='mst', rows='100', cols='10')
            
        # 3. 데이터 쓰기 로직 (방법 A 적용)
        worksheet.clear()
        
        # 💡 [핵심] A열(단축코드 열)을 텍스트 형식으로 강제 지정하여 '0' 사라짐 방지
        # 라이브러리 버전에 상관없이 작동하는 방식입니다.
        worksheet.format("A:A", {"numberFormat": {"type": "TEXT"}})
        
        # 💡 에러가 발생하는 string_cols 인자를 제거하고 호출
        set_with_dataframe(worksheet, target_df)
        
        print("구글 시트 'my' 파일의 'mst' 시트 업데이트 완료!")
        
    except Exception as e:
        print(f"구글 시트 업데이트 중 오류 발생: {e}")

# 4. 메인 통합 및 무결성 처리
def build_raw_db():
    print("마스터 데이터 다운로드 및 파싱 시작...")
    df_stk = parse_master(download_master("kospi"), "STK")
    df_ksq = parse_master(download_master("kosdaq"), "KSQ")
    
    raw_df = pd.concat([df_stk, df_ksq], ignore_index=True)
    print(f"통합 완료 - 전체 건수: {len(raw_df)}")

    # 무결성 처리: 그룹코드 필터링
    raw_df['그룹코드'] = raw_df['그룹코드'].astype(str).str.strip()
    raw_df = raw_df[raw_df['그룹코드'].isin(['ST', 'EF'])].copy()
    print(f"필터링(ST, EF) 후 건수: {len(raw_df)}")

    # 여부 칼럼 Y/N 처리
    yn_cols = [c for c in raw_df.columns if any(x in c for x in ['여부', '지목', '지수', 'KRX', 'SPAC', '제조업', '유동성', '과열', '경고', '정지', '매매', '종목', '가능'])]
    for col in yn_cols:
        raw_df[col] = raw_df[col].fillna('N').replace({'0': 'N', '1': 'Y', ' ': 'N'})

    # 수치형 칼럼 처리
    num_cols = ['기준가', '상장주수', '자본금', '액면가', '전일거래량', '매출액', '영업이익', '경상이익', '당기순이익', 'ROE', '시가총액']
    for col in num_cols:
        if col in raw_df.columns:
            raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce').fillna(0)

    # 문자열 공백 제거
    str_cols = raw_df.select_dtypes(include=['object']).columns
    for col in str_cols:
        raw_df[col] = raw_df[col].str.strip()

    # 결과 저장
    save_dir = "DB"
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, "raw_mst_krx_full.parquet")
    raw_df.to_parquet(save_path, engine='pyarrow', index=False, compression='snappy')
    
    print(f"최종 칼럼 수: {len(raw_df.columns)}, 데이터 건수: {len(raw_df)}")
    
    # 시트 업데이트 호출
    update_gsheet(raw_df)

if __name__ == "__main__":
    build_raw_db()
