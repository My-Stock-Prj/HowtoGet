# 이 코드는 build_raw_ETF.py
# -*- coding: utf-8 -*-
import pandas as pd
from pykrx import stock
from datetime import datetime
import os
from tqdm import tqdm
import time

def collect_etf_data():
    # 1. 수집 날짜 설정 및 영업일 보정 로직 추가
    raw_today = datetime.now().strftime("%Y%m%d")
    print(f"🔍 시스템 현재 날짜: {raw_today}")
    
    try:
        # 주말/공휴일인 경우 가장 가까운 과거 영업일로 보정
        today = stock.get_nearest_business_day(raw_today)
        print(f"🚀 {today} 기준 ETF 구성 종목(PDF) 수집 시작... (요청일: {raw_today})")
    except Exception as e:
        print(f"❌ 날짜 보정 중 에러 발생: {e}")
        today = raw_today

    # 2. 모든 ETF 목록 및 이름 가져오기
    try:
        etf_tickers = stock.get_etf_ticker_list(today)
        print(f"✅ ETF 티커 리스트 수신 성공. 총 {len(etf_tickers)}개 종목 발견.")
    except Exception as e:
        print(f"❌ ETF 티커 리스트 호출 실패. 서버 응답 에러: {e}")
        return
    
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
            else:
                # 빈 데이터가 올 경우 디버깅용 로그
                if ticker == etf_tickers[0]: # 너무 많은 출력을 방지하기 위해 첫 번째 항목 정도만 샘플링
                    print(f"⚠️ {etf_name}({ticker}) 의 구성 종목 데이터가 비어있습니다.")
            
            # KRX 서버 부하 및 차단 방지를 위한 미세 지연
            time.sleep(0.05)
            
        except Exception as e:
            # 에러 발생 시 상세 정보 출력
            print(f"\n❌ 에러 발생 종목: {ticker} | 사유: {e}")
            continue # 에러 발생 시 해당 ETF는 건너뜀

    if not all_current_data:
        print("❌ 최종 통합할 데이터가 없습니다. 프로세스를 종료합니다.")
        return

    # 4. 오늘 수집 데이터 통합
    new_df = pd.concat(all_current_data, ignore_index=True)

    # 5. 기존 DB 로드 및 누적 (Incremental Update)
    db_path = './DB/raw_daily_ETF.parquet'
    os.makedirs('./DB', exist_ok=True)

    if os.path.exists(db_path):
        try:
            old_df = pd.read_parquet(db_path)
            # 오늘 날짜 데이터가 이미 있다면 제거 후 업데이트 (중복 방지)
            old_df = old_df[old_df['날짜'] != today]
            final_df = pd.concat([old_df, new_df], ignore_index=True)
            print(f"🔄 기존 데이터에 추가 완료. (기존 데이터 로드 성공, 총 {len(final_df)}행)")
        except Exception as e:
            print(f"⚠️ 기존 파일 로드 실패(손상 등): {e}. 신규 파일로 대체합니다.")
            final_df = new_df
    else:
        final_df = new_df
        print(f"🆕 신규 데이터베이스 생성 완료. ({len(final_df)}행)")

    # 6. 최종 저장
    try:
        final_df.to_parquet(db_path, index=False)
        print(f"✅ 저장 완료: {db_path}")
    except Exception as e:
        print(f"❌ 파일 저장 중 치명적 에러 발생: {e}")

if __name__ == "__main__":
    collect_etf_data()
