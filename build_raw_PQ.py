# 이 코드는 build_raw_PQ.py
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import time
import requests
import json
from datetime import datetime
import kis_auth  # 인증 및 환경 설정 참조
import gspread   # 구글 시트 접근용

# --- [설정 로드] ---
BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')
SAVE_PATH = os.path.join(BASE_DIR, 'raw_daily_PQ.parquet')
MST_PATH = os.path.join(BASE_DIR, 'raw_mst_krx_full.parquet')

def get_combined_targets():
    """
    저장 대상 종목 확정: KOSPI200/KOSDAQ150 + 구글시트 'goingup'
    """
    print("🔍 [DEBUG] 수집 대상 종목 분석 시작...")
    try:
        # 1. 마스터 파일 분석
        if not os.path.exists(MST_PATH):
            raise FileNotFoundError(f"마스터 파일이 없습니다: {MST_PATH}")
            
        df_mst = pd.read_parquet(MST_PATH)
        # KOSPI200, KOSDAQ150 컬럼이 1인 종목 추출
        idx_df = df_mst[(df_mst['KOSPI200섹터업종'] == 1) | (df_mst['KOSDAQ150'] == 1)]
        idx_tickers = idx_df['단축코드'].unique().tolist()
        print(f"   - 지수 구성 종목 추출 완료: {len(idx_tickers)}개")

        # 2. 구글 시트 'my' 파일의 'goingup' 시트 분석
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = kis_auth.get_gcp_creds(scopes)
        client = gspread.authorize(creds)
        
        # 'my' 파일 오픈 및 'goingup' 시트 데이터 로드
        sheet = client.open("my").worksheet("goingup")
        # 종목코드가 있는 A열 수집 (첫 행 헤더 제외) 
        gsheet_tickers = sheet.col_values(1)[1:] 
        print(f"   - 구글 시트 'goingup' 종목 추출 완료: {len(gsheet_tickers)}개")

        # 3. 합병 및 중복 제거
        final_list = list(set(idx_tickers + gsheet_tickers))
        final_list = [t.strip() for t in final_list if t.strip()]
        print(f"✅ [DEBUG] 최종 합산 타겟 종목 수: {len(final_list)}개")
        return final_list

    except Exception as e:
        print(f"❌ [ERROR] 대상 종목 선정 중 오류 발생: {str(e)}")
        raise

def fetch_daily_price(ticker, target_date, token, app_key, app_secret):
    """
    TR FHKST03010100 (국내주식 기간별 시세) 호출
    """
    url = f"{kis_auth.getEnv().real_url}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST03010100",
        "custtype": "P"
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": ticker,
        "FID_INPUT_DATE_1": target_date,
        "FID_INPUT_DATE_2": target_date,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0" # 수정주가 반영
    }
    
    try:
        res = requests.get(url, headers=headers, params=params)
        res_data = res.json()
        
        if res.status_code == 200 and res_data.get('rt_cd') == '0':
            # output2 리스트의 첫 번째 항목(해당 날짜) 데이터 추출
            outputs = res_data.get('output2', [])
            if not outputs:
                return None
                
            day_data = outputs[0]
            return {
                "날짜": target_date,
                "종목코드": ticker,
                "시가": int(day_data['stck_oprc']),
                "고가": int(day_data['stck_hgpr']),
                "저가": int(day_data['stck_lwpr']),
                "종가": int(day_data['stck_clpr']),
                "거래량": int(day_data['acml_vol']),
                "거래대금": int(day_data['acml_tr_pbmn'])
            }
        else:
            print(f"   ⚠️ [{ticker}] API 응답 에러: {res_data.get('msg1')}")
            return None
            
    except Exception as e:
        print(f"   ⚠️ [{ticker}] 요청 중 예외 발생: {str(e)}")
        return None

def main():
    print(f"🚀 {datetime.now()} 데이터 수집 프로세스 시작")
    
    try:
        # 1. 환경 변수 및 인증 확인
        app_key = os.environ.get('KIS_APP_KEY')
        app_secret = os.environ.get('KIS_APP_SECRET')
        
        if not app_key or not app_secret:
            raise ValueError("KIS_APP_KEY 또는 KIS_APP_SECRET 환경변수가 설정되지 않았습니다.")

        token_info = kis_auth.auth()
        access_token = token_info['access_token']
        
        # 2. 대상 종목 리스트 확보
        tickers = get_combined_targets()
        
        # 3. 데이터 수집 (최초 테스트: 20260504)
        target_date = "20260504"
        collected_results = []
        
        print(f"📅 수집 기준일: {target_date}")
        for i, ticker in enumerate(tickers):
            # 디버깅: 진행 상황 출력
            if (i + 1) % 10 == 0 or (i + 1) == len(tickers):
                print(f"🔄 진행률: {i+1}/{len(tickers)} ({((i+1)/len(tickers)*100):.1f}%)")
            
            result = fetch_daily_price(ticker, target_date, access_token, app_key, app_secret)
            if result:
                collected_results.append(result)
            
            # API 과부하 방지 (초당 2회 제한 준수)
            time.sleep(0.5)

        # 4. 저장 및 데이터 완결성 검증
        if collected_results:
            df_new = pd.DataFrame(collected_results)
            
            # 기존 데이터가 있다면 로드 후 병합
            if os.path.exists(SAVE_PATH):
                df_old = pd.read_parquet(SAVE_PATH)
                # 날짜와 종목코드 기준으로 중복 제거 (완결성 유지)
                df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['날짜', '종목코드'], keep='last')
                print(f"📝 기존 데이터와 병합 완료 (총 {len(df_final)}행)")
            else:
                df_final = df_new
                print(f"📝 신규 파일 생성 완료 ({len(df_final)}행)")
            
            # 저장 전 데이터 타입 재검증 (디버깅)
            if df_final['날짜'].isin(['0', 0]).any():
                print("⚠️ [WARNING] 데이터 중 '0'으로 된 날짜가 발견되었습니다. 저장 전 확인 필요.")

            df_final.to_parquet(SAVE_PATH, index=False)
            print(f"✅ 저장 완료: {SAVE_PATH}")
        else:
            print("⚠️ 수집된 데이터가 없어 파일을 업데이트하지 않았습니다.")

    except Exception as e:
        print(f"❌ [CRITICAL ERROR] 메인 프로세스 중단: {str(e)}")

if __name__ == "__main__":
    main()
