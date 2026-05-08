# 이 코드는 build_raw_PQ.py
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import time
import traceback
from datetime import datetime
import kis_auth as ka  # 별칭 사용 권장[cite: 1]
import gspread
# 국내 주식 표준 함수 임포트
from domestic_stock_functions import inquire_daily_itemchartprice[cite: 2, 3]

# --- [설정 로드] ---
BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')
SAVE_PATH = os.path.join(BASE_DIR, 'raw_daily_PQ.parquet')
MST_PATH = os.path.join(BASE_DIR, 'raw_mst_krx_full.parquet')

def get_combined_targets():
    """저장 대상 종목 확정 (기본 로직 유지)"""
    print("🔍 [DEBUG] 1. 수집 대상 종목 분석 시작...")
    try:
        idx_tickers = []
        if os.path.exists(MST_PATH):
            df_mst = pd.read_parquet(MST_PATH)
            if not df_mst.empty:
                cond = pd.Series([False] * len(df_mst))
                if 'KOSPI200섹터업종' in df_mst.columns:
                    cond |= (df_mst['KOSPI200섹터업종'] == 1)
                if 'KOSDAQ150' in df_mst.columns:
                    cond |= (df_mst['KOSDAQ150'] == 1)
                idx_tickers = df_mst[cond]['단축코드'].unique().tolist()
        
        # 구글 시트 분석
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = ka.get_gcp_creds(scopes)
        gsheet_tickers = []
        if creds:
            client = gspread.authorize(creds)
            sheet = client.open("my").worksheet("goingup")
            gsheet_tickers = sheet.col_values(1)[1:]
        
        final_list = list(set(idx_tickers + gsheet_tickers))
        return [str(t).strip() for t in final_list if t]
    except Exception as e:
        print(f"❌ [ERROR] get_combined_targets 실패: {str(e)}")
        return []

def fetch_daily_price(ticker, target_date):
    """
    지식 베이스의 표준 함수를 활용하여 데이터를 수집합니다.
    """
    try:
        # 오류 수정: 인자명을 지식 문서에 정의된 대문자(FID_...)로 변경함
        df_res = inquire_daily_itemchartprice(
            env_dv="real", 
            FID_COND_MRKT_DIV_CODE="J", 
            FID_INPUT_ISCD=ticker, 
            FID_INPUT_DATE_1=target_date, 
            FID_INPUT_DATE_2=target_date, 
            FID_PERIOD_DIV_CODE="D", 
            FID_ORG_ADJ_PRC="1"
        )[cite: 2]

        if df_res is not None and not df_res.empty:
            d = df_res.iloc[0]
            # 요청하신 prdy_ctrt, prdy_vrss_vol 칼럼 추가[cite: 2]
            return {
                "날짜": target_date, 
                "종목코드": ticker,
                "시가": int(d['stck_oprc']), 
                "고가": int(d['stck_hgpr']),
                "저가": int(d['stck_lwpr']), 
                "종가": int(d['stck_clpr']),
                "거래량": int(d['acml_vol']), 
                "거래대금": int(d['acml_tr_pbmn']),
                "전일대비등락률": float(d['prdy_ctrt']),     # 신규 추가
                "전일대비거래량": int(d['prdy_vrss_vol'])   # 신규 추가
            }
    except Exception as e:
        print(f"⚠️ [{ticker}] 데이터 파싱 실패: {str(e)}")
    return None

def main():
    print(f"🚀 {datetime.now()} 프로세스 시작")
    try:
        # 1. 인증 초기화 (내부 전역 변수에 세팅됨)[cite: 1]
        ka.auth() 
        
        # 2. 대상 리스트 확보
        tickers = get_combined_targets()
        if not tickers:
            print("⚠️ 수집할 종목이 없습니다.")
            return

        # 3. 데이터 수집
        target_date = "20260504"
        collected = []
        for ticker in tickers:
            res = fetch_daily_price(ticker, target_date)
            if res: 
                collected.append(res)
            
            # API 제한 방지를 위한 지연[cite: 3]
            time.sleep(0.2) 

        # 4. 저장 로직
        if collected:
            df_new = pd.DataFrame(collected)
            if os.path.exists(SAVE_PATH):
                df_old = pd.read_parquet(SAVE_PATH)
                df_new = pd.concat([df_old, df_new]).drop_duplicates(subset=['날짜', '종목코드'], keep='last')
            
            df_new.to_parquet(SAVE_PATH, index=False)
            print(f"✅ 저장 완료: {len(df_new)} rows (신규 {len(collected)}건)")

    except Exception as e:
        print(f"❌ [CRITICAL ERROR] {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
