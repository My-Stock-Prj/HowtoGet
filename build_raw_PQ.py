# 이 코드는 build_raw_PQ.py
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import time
import traceback
from datetime import datetime
import kis_auth as ka  # 별칭 사용 권장
import gspread
# 국내 주식 표준 함수 임포트
from domestic_stock_functions import inquire_daily_itemchartprice

# --- [설정 로드] ---
BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')
SAVE_PATH = os.path.join(BASE_DIR, 'raw_daily_PQ.parquet')
MST_PATH = os.path.join(BASE_DIR, 'raw_mst_krx_full.parquet')

def get_combined_targets():
    print("🔍 [DEBUG] 1. 수집 대상 종목 분석 시작...")
    try:
        idx_tickers = []
        if os.path.exists(MST_PATH):
            df_mst = pd.read_parquet(MST_PATH)
            
            if not df_mst.empty:
                cond = pd.Series([False] * len(df_mst))
                
                # [수정 핵심] 마스터 생성 코드에서 1을 'Y'로 변환했으므로 조건을 'Y'로 변경
                if 'KOSPI200섹터업종' in df_mst.columns:
                    cond |= (df_mst['KOSPI200섹터업종'] == 'Y')
                
                if 'KOSDAQ150' in df_mst.columns:
                    cond |= (df_mst['KOSDAQ150'] == 'Y')
                
                # 만약 위 두 조건으로도 부족하다면, 시장 전체를 가져오는 대안 (선택 사항)
                # cond |= df_mst['시장구분'].isin(['STK', 'KSQ'])
                
                idx_tickers = df_mst[cond]['단축코드'].unique().tolist()
                print(f"   - 필터링 결과 ('Y' 기준): {len(idx_tickers)} 건")
        
        # 구글 시트 부분 (기존 유지)
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = ka.get_gcp_creds(scopes)
        gsheet_tickers = []
        if creds:
            client = gspread.authorize(creds)
            sheet = client.open("my").worksheet("goingup")
            gsheet_tickers = sheet.col_values(1)[1:]
        
        final_list = list(set(idx_tickers + gsheet_tickers))
        print(f"🚀 최종 합계: {len(final_list)} 건")
        return [str(t).strip() for t in final_list if t]
        
    except Exception as e:
        print(f"❌ [ERROR] get_combined_targets 실패: {str(e)}")
        return []
        
def fetch_daily_price(ticker, target_date):
    try:
        # GEMS 표준 함수는 (DataFrame, Response) 형태의 튜플을 반환합니다.
        # GEMS 표준 함수 호출
        result = inquire_daily_itemchartprice(
            "real", "J", ticker, target_date, target_date, "D", "1"
        )

        # 1. 튜플에서 데이터프레임만 분리 (표준 규격 대응)
        df_res = result[0] if isinstance(result, tuple) else result

        # 2. 데이터 존재 여부 및 컬럼명 확인 후 매핑
        if df_res is not None and not df_res.empty:
            # 첫 번째 행 데이터 가져오기
            d = df_res.iloc[0]
            
            # API 응답 필드명이 대문자인 경우와 소문자인 경우 모두 대응
            # 딕셔너리의 .get()을 사용하여 키가 없어도 에러가 나지 않게 방어
            return {
                "날짜": target_date, 
                "종목코드": ticker,
                "시가": int(d.get('stck_oprc', d.get('STCK_OPRC', 0))), 
                "고가": int(d.get('stck_hgpr', d.get('STCK_HGPR', 0))),
                "저가": int(d.get('stck_lwpr', d.get('STCK_LWPR', 0))), 
                "종가": int(d.get('stck_clpr', d.get('STCK_CLPR', 0))),
                "거래량": int(d.get('acml_vol', d.get('ACML_VOL', 0))), 
                "거래대금": int(d.get('acml_tr_pbmn', d.get('ACML_TR_PBMN', 0))),
                "재평가사유": d.get('revl_issu_reas', '')
            }
            
    except Exception as e:
        # traceback을 통해 정확히 어디서 에러가 나는지 출력 (디버깅용)
        # print(traceback.format_exc()) 
        print(f"⚠️ [{ticker}] 데이터 처리 실패: {str(e)}")
    return None

def main():
    print(f"🚀 {datetime.now()} 프로세스 시작")
    try:
        # 1. 인증 초기화 (내부 전역 변수에 세팅됨)
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
            
            # API 제한 방지를 위한 지연
            time.sleep(0.2) 

        # 4. 저장 로직
        if collected:
            df_new = pd.DataFrame(collected)
            if os.path.exists(SAVE_PATH):
                df_old = pd.read_parquet(SAVE_PATH)
                df_new = pd.concat([df_old, df_new]).drop_duplicates(subset=['날짜', '종목코드'], keep='last')
            
            # 상위 폴더 생성 보장
            os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
            df_new.to_parquet(SAVE_PATH, index=False)
            print(f"✅ 저장 완료: {len(df_new)} rows (신규 {len(collected)}건)")

    except Exception as e:
        print(f"❌ [CRITICAL ERROR] {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
