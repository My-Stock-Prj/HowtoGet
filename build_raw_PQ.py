# 이 코드는 build_raw_PQ.py full > 20일 확장
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import time
import traceback
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
                    mst_info_map[code] = {"종목명": row.get('종목명', ''), "구분": label}
                print(f"   - 마스터 필터링 결과: {len(idx_tickers)} 건")
        
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = ka.get_gcp_creds(scopes)
        gsheet_tickers = []
        if creds:
            try:
                client = gspread.authorize(creds)
                sheet = client.open("my").worksheet("goingup")
                gsheet_tickers = sheet.col_values(1)[1:]
            except Exception as e:
                print(f"   ⚠️ 구글 시트 로드 실패: {e}")
        
        all_tickers = list(set([str(t).strip().zfill(6) for t in (idx_tickers + gsheet_tickers) if t]))
        print(f"🚀 최종 수집 대상: {len(all_tickers)} 건")
        return all_tickers, mst_info_map
    except Exception as e:
        print(f"❌ [ERROR] get_combined_targets 실패: {str(e)}")
        return [], {}

def fetch_daily_price(ticker, target_date, mst_info):
    """
    kis_auth.py를 수정하지 않고 기존의 단일 일자 조회 방식을 그대로 사용
    """
    try:
        # 1. 일별 차트 시세 조회 (인자 2개 전달 시 kis_auth가 1개만 받더라도 오류 안 나게 대응)
        # 만약 kis_auth가 (ticker, date)만 받는다면 아래 호출은 그대로 동작함
        res = ka.get_daily_price(ticker, target_date, target_date)
        out1 = res.get('output1', ka.AttrDict({}))
        out2_list = res.get('output2', [])
        if not out2_list: return None
        d2 = ka.AttrDict(out2_list[0])
        if d2.stck_bsop_date != target_date: return None

        # 2. 투자자 매매동향
        res_inv = ka.get_investor_trade(ticker, target_date)
        inv = ka.AttrDict(res_inv.get('output2', [{}])[0])

        # 3. 프로그램 매매추이
        res_pgm = ka.get_program_trade(ticker, target_date)
        pgm = ka.AttrDict(res_pgm.get('output', [{}])[0])

        # 4. 공매도 일별추이 (인자 2개 대응)
        res_shrt = ka.get_short_sale_daily(ticker, target_date, target_date)
        shrt = ka.AttrDict(res_shrt.get('output2', [{}])[0])

        # 5. 대차거래추이
        res_loan = ka.get_loan_trans_daily(ticker, target_date)
        loan = ka.AttrDict(res_loan.get('output', [{}])[0])

        # 6. 신용잔고추이 (인자 2개 대응)
        res_cred = ka.get_credit_balance_daily(ticker, target_date, target_date)
        cred = ka.AttrDict(res_cred.get('output', [{}])[0])

        return {
            "날짜": target_date, "종목코드": ticker, "종목명": mst_info.get("종목명", ""), "구분(출처)": mst_info.get("구분", "MY"),
            "종가": ka.to_int(d2.stck_clpr), "시가": ka.to_int(d2.stck_oprc), "고가": ka.to_int(d2.stck_hgpr), "저가": ka.to_int(d2.stck_lwpr),
            "거래량": ka.to_int(d2.acml_vol), "거래대금": ka.to_int(d2.acml_tr_pbmn), "회전율": ka.to_float(out1.vol_tnrt),
            "상장주수": ka.to_int(out1.lstn_stcn), "락구분": d2.flng_cls_code, "재평가사유": d2.revl_issu_reas,
            "외국인순매수수량": ka.to_int(inv.frgn_ntby_qty), "외국인순매수대금": ka.to_int(inv.frgn_ntby_tr_pbmn),
            "기관계순매수수량": ka.to_int(inv.orgn_ntby_qty), "기관계순매수대금": ka.to_int(inv.orgn_ntby_tr_pbmn),
            "기금순매수수량": ka.to_int(inv.fund_ntby_qty), "기금순매수대금": ka.to_int(inv.fund_ntby_tr_pbmn),
            "개인순매수수량": ka.to_int(inv.prsn_ntby_qty), "개인순매수대금": ka.to_int(inv.prsn_ntby_tr_pbmn),
            "증권순매수수량": ka.to_int(inv.scrt_ntby_qty), "투자신탁순매수수량": ka.to_int(inv.ivtr_ntby_qty),
            "사모펀드순매수수량": ka.to_int(inv.pe_fund_ntby_vol), "은행순매수수량": ka.to_int(inv.bank_ntby_qty),
            "보험순매수수량": ka.to_int(inv.insu_ntby_qty), "종금순매수수량": ka.to_int(inv.mrbn_ntby_qty),
            "프로그램순매수수량": ka.to_int(pgm.whol_smtn_ntby_qty), "프로그램순매수대금": ka.to_int(pgm.whol_smtn_ntby_tr_pbmn),
            "공매도체결수량": ka.to_int(shrt.ssts_cntg_qty), "누적공매도체결수량": ka.to_int(shrt.acml_ssts_cntg_qty),
            "공매도거래량비중": ka.to_float(shrt.ssts_vol_rlim), "당일대차잔고주수": ka.to_int(loan.rmnd_stcn),
            "전체융자잔고주수": ka.to_int(cred.whol_loan_rmnd_stcn), "전체융자잔고비율": ka.to_float(cred.whol_loan_rmnd_rate)
        }
    except Exception as e:
        print(f"⚠️ [{ticker}] 데이터 처리 실패: {str(e)}")
        return None

def main():
    print(f"🚀 {datetime.now()} 프로세스 시작 (2차: 최근 10일 분할 수집 - kis_auth 유지형)")
    try:
        tickers, mst_info_map = get_combined_targets()
        if not tickers: return

        # 1. 최근 20영업일 생성 및 최근 10일(2차 대상) 추출
        full_date_list = pd.bdate_range(end=datetime.now(), periods=20).strftime('%Y%m%d').tolist()
        recent_10_days = full_date_list[10:] 
        
        # 2. 남은 10일을 2일씩 5번으로 나누기 (Chunking)
        chunk_size = 2
        date_chunks = [recent_10_days[i:i + chunk_size] for i in range(0, len(recent_10_days), chunk_size)]
        
        total_tickers = len(tickers)
        
        # 3. 회차별(2일씩) 순차적 실행
        for idx, chunk in enumerate(date_chunks):
            collected = [] # 각 회차별로 수집된 데이터를 저장
            print(f"\n🔄 [회차 {idx+1}/5] 구간 수집 시작: {chunk[0]} ~ {chunk[-1]}")
            
            for target_date in chunk:
                print(f"📂 {target_date} 데이터 수집 중...")
                day_count = 0
                for i, ticker in enumerate(tickers):
                    mst_info = mst_info_map.get(ticker, {"종목명": "", "구분": "MY"})
                    res = fetch_daily_price(ticker, target_date, mst_info)
                    if res:
                        collected.append(res)
                        day_count += 1
                    if (i + 1) % 50 == 0:
                        print(f"   ⏳ {target_date} 진행 중... ({i+1}/{total_tickers})")
                print(f"✅ {target_date} 완료: {day_count}건 수집")

            # 4. 회차별 즉시 저장 (안정성을 위해 한 회차 끝날 때마다 병합 및 저장)
            if collected:
                df_new = pd.DataFrame(collected)
                base_cols = ["날짜", "종목코드", "종목명", "구분(출처)", "종가", "시가", "고가", "저가", "거래량", "거래대금", "회전율", "상장주수", "락구분", "재평가사유"]
                investor_cols = ["외국인순매수수량", "외국인순매수대금", "기관계순매수수량", "기관계순매수대금", "기금순매수수량", "기금순매수대금", "개인순매수수량", "개인순매수대금", "증권순매수수량", "투자신탁순매수수량", "사모펀드순매수수량", "은행순매수수량", "보험순매수수량", "종금순매수수량"]
                program_cols = ["프로그램순매수수량", "프로그램순매수대금"]
                extended_cols = ["공매도체결수량", "누적공매도체결수량", "공매도거래량비중", "당일대차잔고주수", "전체융자잔고주수", "전체융자잔고비율"]
                df_new = df_new[base_cols + investor_cols + program_cols + extended_cols]

                if os.path.exists(SAVE_PATH):
                    df_old = pd.read_parquet(SAVE_PATH)
                    df_final = pd.concat([df_old, df_new]).drop_duplicates(subset=['날짜', '종목코드'], keep='last')
                else:
                    df_final = df_new
                
                os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
                df_final.to_parquet(SAVE_PATH, index=False)
                print(f"💾 [회차 {idx+1}] 저장 완료. 총 데이터: {len(df_final)} rows")
            
            if idx < len(date_chunks) - 1:
                print("💤 다음 회차를 위해 3초 대기합니다...")
                time.sleep(3)

    except Exception as e:
        print(f"❌ [CRITICAL ERROR] {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
