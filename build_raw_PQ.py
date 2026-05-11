# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import time
import traceback
import sys  # 무결성 강제 종료를 위해 추가
from datetime import datetime
import kis_auth as ka  # 보강된 kis_auth 사용
import gspread

# --- [설정 로드] ---
BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')
SAVE_PATH = os.path.join(BASE_DIR, 'raw_daily_PQ.parquet')
MST_PATH = os.path.join(BASE_DIR, 'raw_mst_krx_full.parquet')

def get_combined_targets():
    print("🔍 [DEBUG] 1. 수집 대상 종목 분석 시작...")
    try:
        idx_tickers = []
        mst_info_map = {}
        
        if os.path.exists(MST_PATH):
            df_mst = pd.read_parquet(MST_PATH)
            if not df_mst.empty:
                cond_k200 = (df_mst.get('KOSPI200') == 'Y')
                cond_k150 = (df_mst.get('KOSDAQ150') == 'Y')
                idx_tickers = df_mst[cond_k200 | cond_k150]['단축코드'].unique().tolist()
                
                for _, row in df_mst.iterrows():
                    code = str(row['단축코드']).strip().zfill(6)
                    label = "MY"
                    if row.get('KOSPI200') == 'Y': label = "K200"
                    elif row.get('KOSDAQ150') == 'Y': label = "K150"
                    mst_info_map[code] = {"name": row['종목명'], "label": label}
        
        print(f"✅ 수집 대상: 총 {len(idx_tickers)} 종목 (K200/K150 기준)")
        return idx_tickers, mst_info_map
    except Exception as e:
        print(f"❌ 대상 분석 중 에러: {e}")
        return [], {}

def fetch_daily_price(ticker, target_date, mst_info):
    """KIS API를 호출하여 하루치 통합 시세/수급 데이터를 가져옴"""
    try:
        # 1. 일별 시세 (OHLCV + 수급)
        res = ka.get_daily_price(ticker, target_date)
        out2_list = res.get('output2', [])
        if not out2_list:
            raise ValueError(f"시세 데이터(output2)가 비어있음")
        
        out2 = ka.AttrDict(out2_list[0])
        
        # 2. 공매도/대차/신용 데이터
        res_short = ka.get_short_sale_daily(ticker, target_date)
        out_short = ka.AttrDict(res_short.get('output', [{}])[0])
        
        res_loan = ka.get_loan_trans_daily(ticker, target_date)
        out_loan = ka.AttrDict(res_loan.get('output', [{}])[0])

        # 데이터 취합 (명세서 기준)
        data = {
            "날짜": target_date,
            "종목코드": ticker,
            "종목명": mst_info['name'],
            "구분(출처)": mst_info['label'],
            "종가": ka.to_int(out2.stck_prpr),
            "시가": ka.to_int(out2.stck_oprc),
            "고가": ka.to_int(out2.stck_hgpr),
            "저가": ka.to_int(out2.stck_lwpr),
            "거래량": ka.to_int(out2.acml_vol),
            "거래대금": ka.to_int(out2.acml_tr_pbmn),
            "회전율": ka.to_float(out2.prdy_vol_rvrt),
            "상장주수": ka.to_int(out2.lstg_stqt),
            "락구분": out2.flng_cls_code,
            "재평가사유": out2.prdy_vrss_sign,
            
            "외국인순매수수량": ka.to_int(out2.ntby_cnt),
            "외국인순매수대금": ka.to_int(out2.ntby_tr_pbmn),
            "기관계순매수수량": ka.to_int(out2.orgn_ntby_qty),
            "기관계순매수대금": ka.to_int(out2.orgn_ntby_tr_pbmn),
            "기금순매수수량": ka.to_int(out2.pnsn_fund_buy_qty) - ka.to_int(out2.pnsn_fund_sel_qty),
            "기금순매수대금": ka.to_int(out2.pnsn_fund_buy_amt) - ka.to_int(out2.pnsn_fund_sel_amt),
            "개인순매수수량": ka.to_int(out2.indv_ntby_qty),
            "개인순매수대금": ka.to_int(out2.indv_ntby_tr_pbmn),
            
            "증권순매수수량": ka.to_int(out2.prsn_ntby_qty),
            "투자신탁순매수수량": ka.to_int(out2.invt_trust_ntby_qty),
            "사모펀드순매수수량": ka.to_int(out2.priv_fund_ntby_qty),
            "은행순매수수량": ka.to_int(out2.bank_ntby_qty),
            "보험순매수수량": ka.to_int(out2.insu_ntby_qty),
            "종금순매수수량": ka.to_int(out2.etc_finc_ntby_qty),
            
            "프로그램순매수수량": ka.to_int(out2.pgm_ntby_qty),
            "프로그램순매수대금": ka.to_int(out2.pgm_ntby_tr_pbmn),
            
            "공매도체결수량": ka.to_int(out_short.sstk_cnt),
            "누적공매도체결수량": ka.to_int(out_short.cncl_sstk_cnt),
            "공매도거래량비중": ka.to_float(out_short.prdy_vol_rvrt),
            "당일대차잔고주수": ka.to_int(out_loan.whol_loan_rmnd_stcn),
            "전체융자잔고주수": ka.to_int(out_loan.whol_loan_rmnd_stcn),
            "전체융자잔고비율": ka.to_float(out_loan.whol_loan_rmnd_rate)
        }
        return data
    except Exception as e:
        print(f"❌ [{ticker}] 수집 중단: {e}")
        raise e

def main():
    print(f"🚀 {datetime.now()} 프로세스 시작 (지정 기간 재수집)")
    try:
        tickers, mst_info_map = get_combined_targets()
        if not tickers: return

        # --- [날짜 범위 수정: 4/23 ~ 5/8 고정] ---
        # 원본: pd.bdate_range(end=datetime.now(), periods=ka.POLICY["LOOKBACK_DAYS"])
        full_date_list = pd.bdate_range(start='2026-04-23', end='2026-05-08').strftime('%Y%m%d').tolist()
        print(f"📅 수집 대상 날짜: {full_date_list}")

        for target_date in full_date_list:
            print(f"\n📅 --- {target_date} 데이터 처리 시작 ---")
            
            # 스마트 스킵: 이미 해당 날짜 데이터가 있는지 확인
            existing_dates = []
            if os.path.exists(SAVE_PATH):
                df_chk = pd.read_parquet(SAVE_PATH, columns=['날짜'])
                existing_dates = df_chk['날짜'].unique().tolist()
            
            collected_today = []
            for i, ticker in enumerate(tickers):
                # 해당 종목/날짜 이미 있으면 스킵
                if os.path.exists(SAVE_PATH):
                    # 전체를 읽지 않고 날짜와 종목코드로 필터링하여 확인 (무결성 정책)
                    df_chk = pd.read_parquet(SAVE_PATH)
                    if not df_chk[(df_chk['날짜'] == target_date) & (df_chk['종목코드'] == ticker)].empty:
                        continue

                mst_info = mst_info_map.get(ticker, {"name": "Unknown", "label": "MY"})
                print(f"   ⏳ {target_date} ({i+1}/{len(tickers)}) [{ticker}] 수집 중...", end='\r')
                
                res = fetch_daily_price(ticker, target_date, mst_info)
                if res:
                    collected_today.append(res)
                
                time.sleep(ka.POLICY["SLEEP_TIME"])

            # 하루 완료 시 즉시 저장
            if collected_today:
                df_new = pd.DataFrame(collected_today)
                base_cols = ["날짜", "종목코드", "종목명", "구분(출처)", "종가", "시가", "고가", "저가", "거래량", "거래대금", "회전율", "상장주수", "락구분", "재평가사유"]
                investor_cols = ["외국인순매수수량", "외국인순매수대금", "기관계순매수수량", "기관계순매수대금", "기금순매수수량", "기금순매수대금", "개인순매수수량", "개인순매수대금", "증권순매수수량", "투자신탁순매수수량", "사모펀드순매수수량", "은행순매수수량", "보험순매수수량", "종금순매수수량"]
                program_cols = ["프로그램순매수수량", "프로그램순매수대금"]
                extended_cols = ["공매도체결수량", "누적공매도체결수량", "공매도거래량비중", "당일대차잔고주수", "전체융자잔고주수", "전체융자잔고비율"]
                df_new = df_new[base_cols + investor_cols + program_cols + extended_cols]

                if os.path.exists(SAVE_PATH):
                    df_old = pd.read_parquet(SAVE_PATH)
                    df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['날짜', '종목코드'], keep='last')
                    df_final.to_parquet(SAVE_PATH, index=False)
                else:
                    df_new.to_parquet(SAVE_PATH, index=False)
                
                print(f"\n✅ {target_date} 저장 완료: {len(df_new)}건")

    except Exception as e:
        print(f"\n❌ [CRITICAL ERROR] {e}")
        traceback.print_exc()
        sys.exit(1) # 무결성을 위해 종료

if __name__ == "__main__":
    main()
