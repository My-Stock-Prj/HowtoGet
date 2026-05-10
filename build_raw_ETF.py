# 이 코드는 build_raw_ETF.py
# -*- coding: utf-8 -*-
import pandas as pd
from pykrx import stock
from datetime import datetime
import os
from tqdm import tqdm
import time

def collect_etf_data():
    # 1. 수집 날짜 설정 및 영업일 보정 로직 (오늘이 휴장일이면 가장 가까운 과거 영업일 탐색)
    raw_today = datetime.now().strftime("%Y%m%d")
    print(f"🔍 [DEBUG] 현재 시스템 시간 기반 날짜: {raw_today}")
    
    try:
        # pykrx 내부 함수를 사용하여 영업일 보정
        today = stock.get_nearest_business_day(raw_today)
        print(f"🚀 [DEBUG] 최종 수집 기준 영업일: {today}")
        print(f"🚀 {today} 기준 ETF 구성 종목(PDF) 수집 시작...")
    except Exception as e:
        print(f"❌ [DEBUG] 날짜 보정 중 에러 발생: {e}")
        today = raw_today # 에러 시 오늘 날짜로 강행

    # 2. 모든 ETF 목록 및 이름 가져오기
    try:
        etf_tickers = stock.get_etf_ticker_list(today)
        print(f"📡 [DEBUG] 서버 응답: {len(etf_tickers)} 개의 ETF 티커를 수신함.")
    except Exception as e:
        print(f"❌ [DEBUG] etf_ticker_list 수신 중 에러 발생: {e}")
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
                # 데이터가 비어있는 경우 로그 출력 (첫 5개 종목만 샘플로 출력)
                if len(all_current_data) < 5:
                    print(f"⚠️ [DEBUG] {etf_name}({ticker}) 구성 종목 없음 (데이터 빈칸)")
            
            # KRX 서버 부하 방지를 위한 미세 지연 (0.05초)
            time.sleep(0.05)
            
        except Exception as e:
            # 에러 발생 시 서버 메시지 포함 상세 출력
            print(f"\n❌ [DEBUG] 종목 수집 에러 | 티커: {ticker} | 메시지: {e}")
            continue # 에러 발생 시 해당 ETF는 건너뜀

    if not all_current_data:
        print("❌ [DEBUG] 수집된 데이터가 하나도 없습니다. 파일 생성을 중단합니다.")
        return

    # 4. 오늘 수집 데이터 통합
    new_df = pd.concat(all_current_data, ignore_index=True)
    print(f"✅ [DEBUG] 오늘 수집 완료 데이터 크기: {new_df.shape}")

    # 5. 기존 DB 로드 및 누적 (Incremental Update)
    db_path = './DB/raw_daily_ETF.parquet'
    os.makedirs('./DB', exist_ok=True)

    if os.path.exists(db_path):
        try:
            old_df = pd.read_parquet(db_path)
            print(f"📁 [DEBUG] 기존 DB 로드 성공: {old_df.shape}")
            # 오늘 날짜 데이터가 이미 있다면 제거 후 업데이트 (중복 방지)
            old_df = old_df[old_df['날짜'] != today]
            final_df = pd.concat([old_df, new_df], ignore_index=True)
            print(f"🔄 [DEBUG] 데이터 합치기 완료. 현재 총 행 수: {len(final_df)}")
        except Exception as e:
            print(f"⚠️ [DEBUG] 기존 파일 로드 실패: {e}. 새로 생성합니다.")
            final_df = new_df
    else:
        final_df = new_df
        print(f"🆕 [DEBUG] 기존 DB 없음. 신규 데이터베이스 생성.")

    # 6. 최종 저장
    try:
        final_df.to_parquet(db_path, index=False)
        print(f"✅ 저장 완료: {db_path}")
        # 파일이 실제 생성되었는지 확인하는 디버깅 코드
        if os.path.exists(db_path):
            print(f"🎯 [DEBUG] 파일 존재 확인 성공: {os.path.getsize(db_path)} bytes")
    except Exception as e:
        print(f"❌ [DEBUG] 파일 저장 중 에러 발생: {e}")

if __name__ == "__main__":
    collect_etf_data()
