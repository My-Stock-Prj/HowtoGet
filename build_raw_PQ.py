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
    기존 로직 엄격 유지 + 데이터 무결성 체크 추가
    """
    try:
        # 1. 일별 차트 시세 조회
        res = ka.get_daily_price(ticker, target_date, target_date)
        out1 = res.get('output1', ka.AttrDict({}))
        out2_list = res.get('output2', [])
        
        # [데이터 무결성 강제] 핵심 시세 데이터가 없으면 None이 아닌 에러 발생
        if not out2_list: 
            raise ValueError(f"시세 데이터(output2)가 비어있음")
            
        d2 = ka.AttrDict(out2_list[0])
        if d2.stck_bsop_date != target_date: 
            raise ValueError(f"조회일 불일치(요청:{target_date}, 응답:{d2.stck_bsop_date})")

        # 2. 투자자 매매동향
        res_inv = ka.get_investor_trade(ticker, target_date)
        inv = ka.AttrDict(res_inv.get('output2', [{}])[0])

        # 3. 프로그램 매매추이
        res_pgm = ka.get_program_trade(ticker, target_date)
        pgm = ka.AttrDict(res_pgm.get('output', [{}])[0])

        # 4. 공매도 일별추이
        res_shrt = ka.get_short_sale_daily(ticker, target_date, target_date)
        shrt = ka.AttrDict(res_shrt.get('output2', [{}])[0])

        # 5. 대차거래추이
        res_loan = ka.get_loan_trans_daily(ticker, target_date)
        loan = ka.AttrDict(res_loan.get('output', [{}])[0])

        # 6. 신용잔고추이
        res_cred = ka.get_credit_balance_daily(ticker, target_date, target_date)
        cred = ka.AttrDict(res_cred.get('output', [{}])[0])

        # [리턴 딕셔너리 구조 원본과 100% 동일]
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
        print(f"\n❌ [{ticker}] 수집 중단: {str(e)}")
        raise  # 메인 루프에서 즉시 멈추도록 예외 전파

def main():
    print(f"🚀 {datetime.now()} 프로세스 시작 (최근 20일 확장 수집형)")
    try:
        tickers, mst_info_map = get_combined_targets()
        if not tickers: return

        # 1. 최근 20영업일 생성 (전체 기간 수집을 위해 보강)
        full_date_list = pd.bdate_range(end=datetime.now(), periods=20).strftime('%Y%m%d').tolist()
        
        # [스마트 스킵용 기존 데이터 로딩]
        existing_keys = set()
        if os.path.exists(SAVE_PATH):
            df_existing = pd.read_parquet(SAVE_PATH, columns=['날짜', '종목코드'])
            existing_keys = set(df_existing['날짜'] + "_" + df_existing['종목코드'])
            print(f"📊 기존 데이터 {len(existing_keys)}건 로드 완료. 중복 건너뜀 활성화.")

        total_tickers = len(tickers)
        
        # 2. 날짜 루프 (기존의 Chunk 구조를 유지하면서 '하루 단위 저장' 반영)
        for target_date in full_date_list:
            collected_today = []
            print(f"\n📅 [기준일: {target_date}] 수집 시작")
            
            for i, ticker in enumerate(tickers):
                # [스마트 스킵]
                if f"{target_date}_{ticker}" in existing_keys:
                    continue
                
                # [진행상황 표시]
                print(f"\r   ⏳ {target_date} ({i+1}/{total_tickers}) [{ticker}] 수집 중...", end="", flush=True)
                
                mst_info = mst_info_map.get(ticker, {"종목명": "", "구분": "MY"})
                res = fetch_daily_price(ticker, target_date, mst_info)
                
                if res:
                    collected_today.append(res)
                    # [데이터 샘플 로그] 하루의 첫 데이터 성공 시 정보 노출
                    if len(collected_today) == 1:
                        print(f"\n   ✅ 샘플 확인: {res['종목명']}({ticker}) | 종가: {res['종가']} | 거래량: {res['거래량']}")

            # 3. 하루 완료 시 즉시 저장 (원본 칼럼 구조 유지)
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
                else:
                    df_final = df_new
                
                os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
                df_final.to_parquet(SAVE_PATH, index=False)
                print(f"\n💾 {target_date} 저장 완료. (누적: {len(df_final)} rows)")
            else:
                print(f"\n⏩ {target_date}: 수집할 신규 종목 없음.")

    except Exception as e:
        print(f"\n\n❌ [CRITICAL ERROR] {str(e)}")
        traceback.print_exc()
        sys.exit(1)  # 에러 발생 시 데이터 누락 방지를 위해 프로세스 즉시 종료

if __name__ == "__main__":
    main()
