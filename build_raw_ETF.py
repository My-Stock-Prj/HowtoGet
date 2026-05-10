# 이 코드는 build_raw_ETF.py
# -*- coding: utf-8 -*-
import pandas as pd
from pykrx import stock
from datetime import datetime
import os
from tqdm import tqdm

def collect_etf_data():
    # 1. 수집 날짜 설정 (오늘 기준)
    today = datetime.now().strftime("%Y%m%d")
    print(f"🚀 {today} 기준 ETF 구성 종목(PDF) 수집 시작...")

    # 2. 모든 ETF 목록 및 이름 가져오기
    etf_tickers = stock.get_etf_ticker_list(today)
    
    all_current_data = []

    # 3. 각 ETF별 구성 종목 추출
    for ticker in tqdm(etf_tickers, desc="ETF PDF 추출 중"):
        try:
            # ETF 명칭 가져오기
            etf_name = stock.get_etf_ticker_name(ticker)
            
            # 구성 종목(PDF) 가져오기
            df = stock.get_etf_constituent(ticker)
            
            if not df.empty:
                temp_df = pd.DataFrame()
                temp_df['종목코드'] = df # 결과값이 리스트 형태일 수 있어 DataFrame화
                temp_df['ETF코드'] = ticker
                temp_df['ETF명'] = etf_name
                temp_df['날짜'] = today
                all_current_data.append(temp_df)
        except Exception as e:
            continue # 에러 발생 시 해당 ETF는 건너뜀

    if not all_current_data:
        print("❌ 수집된 데이터가 없습니다.")
        return

    # 4. 오늘 수집 데이터 통합
    new_df = pd.concat(all_current_data, ignore_index=True)

    # 5. 기존 DB 로드 및 누적 (Incremental Update)
    db_path = './DB/raw_daily_ETF.parquet'
    os.makedirs('./DB', exist_ok=True)

    if os.path.exists(db_path):
        old_df = pd.read_parquet(db_path)
        # 오늘 날짜 데이터가 이미 있다면 제거 후 업데이트 (중복 방지)
        old_df = old_df[old_df['날짜'] != today]
        final_df = pd.concat([old_df, new_df], ignore_index=True)
        print(f"🔄 기존 데이터에 추가 완료. (총 {len(final_df)}행)")
    else:
        final_df = new_df
        print(f"🆕 신규 데이터베이스 생성 완료. ({len(final_df)}행)")

    # 6. 최종 저장
    final_df.to_parquet(db_path, index=False)
    print(f"✅ 저장 완료: {db_path}")

if __name__ == "__main__":
    collect_etf_data()
