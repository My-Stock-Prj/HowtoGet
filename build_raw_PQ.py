# 이 코드는 build_raw_PQ.py
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import time
import requests
import json
import traceback  # 에러 추적을 위해 추가
from datetime import datetime
import kis_auth  
import gspread   

# --- [설정 로드] ---
BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')
SAVE_PATH = os.path.join(BASE_DIR, 'raw_daily_PQ.parquet')
MST_PATH = os.path.join(BASE_DIR, 'raw_mst_krx_full.parquet')

def get_combined_targets():
    """저장 대상 종목 확정"""
    print("🔍 [DEBUG] 1. 수집 대상 종목 분석 시작...")
    try:
        idx_tickers = []
        if os.path.exists(MST_PATH):
            df_mst = pd.read_parquet(MST_PATH)
            # 마스터 파일이 비어있는지 확인 (Empty or Locked 방어)
            if df_mst.empty:
                print(f"   ⚠️ [DEBUG] 마스터 파일이 비어있습니다: {MST_PATH}")
            else:
                cond = pd.Series([False] * len(df_mst))
                if 'KOSPI200섹터업종' in df_mst.columns:
                    cond |= (df_mst['KOSPI200섹터업종'] == 1)
                if 'KOSDAQ150' in df_mst.columns:
                    cond |= (df_mst['KOSDAQ150'] == 1)
                idx_tickers = df_mst[cond]['단축코드'].unique().tolist()
                print(f"   - [DEBUG] 지수 종목 추출 완료: {len(idx_tickers)}개")

        # 구글 시트 분석
        print("🔍 [DEBUG] 2. 구글 시트 접근 시도...")
        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = kis_auth.get_gcp_creds(scopes)
            if creds:
                client = gspread.authorize(creds)
                sheet = client.open("my").worksheet("goingup")
                gsheet_tickers = sheet.col_values(1)[1:] 
                print(f"   - [DEBUG] 시트 종목 추출 완료: {len(gsheet_tickers)}개")
            else:
                print("   ⚠️ [DEBUG] 구글 크리덴셜을 가져오지 못했습니다. 시트 스킵.")
                gsheet_tickers = []
        except Exception as ge:
            print(f"   ⚠️ [DEBUG] 구글 시트 읽기 실패: {str(ge)}")
            gsheet_tickers = []

        final_list = list(set(idx_tickers + gsheet_tickers))
        final_list = [str(t).strip() for t in final_list if t]
        print(f"✅ [DEBUG] 최종 타겟 종목: {len(final_list)}개")
        return final_list
    except Exception as e:
        print(f"❌ [ERROR] get_combined_targets 실패: {str(e)}")
        return []

def fetch_daily_price(ticker, target_date, token, app_key, app_secret):
    """API 호출 부분 (이전과 동일하나 안전장치 추가)"""
    url = f"{kis_auth.getEnv().real_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key, "appsecret": app_secret,
        "tr_id": "FHKST03010100", "custtype": "P"
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker,
        "FID_INPUT_DATE_1": target_date, "FID_INPUT_DATE_2": target_date,
        "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "0"
    }
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        data = res.json()
        if data.get('rt_cd') == '0' and data.get('output2'):
            d = data['output2'][0]
            return {
                "날짜": target_date, "종목코드": ticker,
                "시가": int(d['stck_oprc']), "고가": int(d['stck_hgpr']),
                "저가": int(d['stck_lwpr']), "종가": int(d['stck_clpr']),
                "거래량": int(d['acml_vol']), "거래대금": int(d['acml_tr_pbmn'])
            }
    except: return None
    return None

def main():
    print(f"🚀 {datetime.now()} 프로세스 시작")
    try:
        # 1. 인증 정보 확인 (가장 의심되는 구간)
        token_info = kis_auth.auth()
        
        if token_info is None:
            raise ValueError("kis_auth.auth()가 None을 반환했습니다. 인증 로직을 확인하세요.")
        
        if not isinstance(token_info, dict) or 'access_token' not in token_info:
            raise ValueError(f"token_info 구조가 올바르지 않습니다: {type(token_info)}")
            
        access_token = token_info['access_token']
        app_key = os.environ.get('KIS_APP_KEY')
        app_secret = os.environ.get('KIS_APP_SECRET')

        # 2. 대상 리스트 확보
        tickers = get_combined_targets()
        if not tickers:
            print("⚠️ 수집할 종목이 없습니다. 종료합니다.")
            return

        # 3. 데이터 수집
        target_date = "20260504"
        collected = []
        for i, ticker in enumerate(tickers):
            res = fetch_daily_price(ticker, target_date, access_token, app_key, app_secret)
            if res: collected.append(res)
            time.sleep(0.5) # 초당 2회 제한

        # 4. 저장
        if collected:
            df_new = pd.DataFrame(collected)
            if os.path.exists(SAVE_PATH):
                df_old = pd.read_parquet(SAVE_PATH)
                df_new = pd.concat([df_old, df_new]).drop_duplicates(subset=['날짜', '종목코드'], keep='last')
            df_new.to_parquet(SAVE_PATH, index=False)
            print(f"✅ 저장 완료: {len(df_new)} rows")

    except Exception as e:
        print(f"❌ [CRITICAL ERROR] 메인 프로세스 중단: {str(e)}")
        traceback.print_exc() # 에러가 발생한 정확한 라인번호와 호출 스택 출력

if __name__ == "__main__":
    main()
