# -*- coding: utf-8 -*-
import pandas as pd
import os
import time
import sys
from datetime import datetime
import kis_auth as ka

# ==========================================
# [수동 설정 구역]
TARGET_DATE = '2026-04-23'  # 수집 및 덮어쓰기를 원하는 날짜 입력 (YYYYMMDD)
# ==========================================

BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')
SAVE_PATH = os.path.join(BASE_DIR, 'raw_daily_PQ.parquet')
MST_PATH = os.path.join(BASE_DIR, 'raw_mst_krx_full.parquet')

def fetch_daily_price(ticker, target_date, mst_info):
    """KIS API 호출 로직 (기존 구조 유지 및 정책 준수)"""
    try:
        # 일별 시세/수급
        res = ka.get_daily_price(ticker, target_date)
        out2 = ka.AttrDict(res.get('output2', [{}])[0])
        if not out2: return None

        # 공매도 및 대차
        res_short = ka.get_short_sale_daily(ticker, target_date)
        out_short = ka.AttrDict(res_short.get('output', [{}])[0])
        
        res_loan = ka.get_loan_trans_daily(ticker, target_date)
        out_loan = ka.AttrDict(res_loan.get('output', [{}])[0])

        return {
            "날짜": target_date, "종목코드": ticker, "종목명": mst_info['name'], "구분(출처)": mst_info['label'],
            "종가": ka.to_int(out2.stck_prpr), "시가": ka.to_int(out2.stck_oprc),
            "고가": ka.to_int(out2.stck_hgpr), "저가": ka.to_int(out2.stck_lwpr),
            "거래량": ka.to_int(out2.acml_vol), "거래대금": ka.to_int(out2.acml_tr_pbmn),
            "회전율": ka.to_float(out2.prdy_vol_rvrt), "상장주수": ka.to_int(out2.lstg_stqt),
            "락구분": out2.flng_cls_code, "재평가사유": out2.prdy_vrss_sign,
            "외국인순매수수량": ka.to_int(out2.ntby_cnt), "외국인순매수대금": ka.to_int(out2.ntby_tr_pbmn),
            "기관계순매수수량": ka.to_int(out2.orgn_ntby_qty), "기관계순매수대금": ka.to_int(out2.orgn_ntby_tr_pbmn),
            "기금순매수수량": ka.to_int(out2.pnsn_fund_buy_qty) - ka.to_int(out2.pnsn_fund_sel_qty),
            "기금순매수대금": ka.to_int(out2.pnsn_fund_buy_amt) - ka.to_int(out2.pnsn_fund_sel_amt),
            "개인순매수수량": ka.to_int(out2.indv_ntby_qty), "개인순매수대금": ka.to_int(out2.indv_ntby_tr_pbmn),
            "증권순매수수량": ka.to_int(out2.prsn_ntby_qty), "투자신탁순매수수량": ka.to_int(out2.invt_trust_ntby_qty),
            "사모펀드순매수수량": ka.to_int(out2.priv_fund_ntby_qty), "은행순매수수량": ka.to_int(out2.bank_ntby_qty),
            "보험순매수수량": ka.to_int(out2.insu_ntby_qty), "종금순매수수량": ka.to_int(out2.etc_finc_ntby_qty),
            "프로그램순매수수량": ka.to_int(out2.pgm_ntby_qty), "프로그램순매수대금": ka.to_int(out2.pgm_ntby_tr_pbmn),
            "공매도체결수량": ka.to_int(out_short.sstk_cnt), "누적공매도체결수량": ka.to_int(out_short.cncl_sstk_cnt),
            "공매도거래량비중": ka.to_float(out_short.prdy_vol_rvrt), "당일대차잔고주수": ka.to_int(out_loan.whol_loan_rmnd_stcn),
            "전체융자잔고주수": ka.to_int(out_loan.whol_loan_rmnd_stcn), "전체융자잔고비율": ka.to_float(out_loan.whol_loan_rmnd_rate)
        }
    except Exception as e:
        raise e

def main():
    print(f"🚀 [{TARGET_DATE}] 하루치 정밀 수집 및 덮어쓰기 시작")
    
    # 1. 대상 로드
    df_mst = pd.read_parquet(MST_PATH)
    cond = (df_mst['KOSPI200'] == 'Y') | (df_mst['KOSDAQ150'] == 'Y')
    target_df = df_mst[cond].copy()
    tickers = target_df['단축코드'].unique().tolist()
    mst_info_map = {row['단축코드']: {"name": row['종목명'], "label": "K200" if row['KOSPI200'] == 'Y' else "K150"} for _, row in target_df.iterrows()}

    # 2. 기존 DB 로딩 (루프 밖에서 1회만 실행하여 시간 단축)
    df_existing = pd.read_parquet(SAVE_PATH) if os.path.exists(SAVE_PATH) else pd.DataFrame()

    collected = []
    errors = []

    # 3. 수집 루프
    for i, ticker in enumerate(tickers):
        print(f"   ⏳ ({i+1}/{len(tickers)}) [{ticker}] 수집 중...", end='\r')
        try:
            res = fetch_daily_price(ticker, TARGET_DATE, mst_info_map[ticker])
            if res: collected.append(res)
            time.sleep(ka.POLICY["SLEEP_TIME"])
        except Exception as e:
            err_msg = str(e).upper()
            if any(x in err_msg for x in ["403", "LIMIT", "AUTH"]): # 치명적 에러 시 즉시 중단
                print(f"\n🚫 [CRITICAL ERROR] {err_msg}. 프로세스를 중단합니다.")
                sys.exit(1)
            errors.append(f"{ticker}({mst_info_map[ticker]['name']}): {err_msg}")

    # 4. 데이터 병합 (동일 날짜는 덮어쓰고 나머지는 보존)
    if collected:
        df_new = pd.DataFrame(collected)
        if not df_existing.empty:
            # 덮어쓰기 핵심: 기존 데이터에서 현재 TARGET_DATE만 제거 후 신규 데이터 결합
            df_final = pd.concat([df_existing[df_existing['날짜'] != TARGET_DATE], df_new], ignore_index=True)
        else:
            df_final = df_new
        
        df_final.sort_values(['날짜', '종목코드']).to_parquet(SAVE_PATH, index=False)
        print(f"\n\n✅ [{TARGET_DATE}] 저장 완료 ({len(df_new)}건)")
    
    if errors:
        print("\n--- 📝 오류 발생 리포트 ---")
        for err in errors: print(f"- {err}")

if __name__ == "__main__":
    main()
