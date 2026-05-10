# 이 코드는 build_raw_ETF.py
# -*- coding: utf-8 -*-
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import os
from tqdm import tqdm
import time

def collect_etf_data():
    # 1. 수집 날짜 설정 및 영업일 보정 (함수 부재 시 직접 계산 로직 추가)
    raw_today = datetime.now().strftime("%Y%m%d")
    print(f"🔍 [DEBUG] 시스템 현재 날짜: {raw_today}")
    
    try:
        # 라이브러리 함수 시도
        today = stock.get_nearest_business_day(raw_today)
        print(f"🚀 [DEBUG] pykrx 함수로 보정된 영업일: {today}")
    except AttributeError:
        # 함수가 없을 경우(구버전) 직접 주말 보정 (금요일로 이동)
        print(f"⚠️ [DEBUG] stock.get_nearest_business_day 함수가 없습니다. 수동 보정을 시작합니다.")
        dt = datetime.strptime(raw_today, "%Y%m%d")
        if dt.weekday() == 5: # 토요일
            dt = dt - timedelta(days=1)
        elif dt.weekday() == 6: # 일요일
            dt = dt - timedelta(days=2)
        today = dt.strftime("%Y%m%d")
        print(f"🚀 [DEBUG] 수동 보정된 영업일(주말 제외): {today}")
    except Exception as e:
        print(f"❌ [DEBUG] 날짜 보정 중 예상치 못한 에러: {e}")
        today = raw_today

    # 2. 모든 ETF 목록 및 이름 가져오기
    print(f"📡 [DEBUG] {today} 기준 서버에 티커 리스트 요청 중...")
    try:
        etf_tickers = stock.get_etf_ticker_list(today)
        print(f"✅ [DEBUG] 서버 응답 성공: 총 {len(etf_tickers)}개 종목 발견.")
    except Exception as e:
        # 에러 발생 시 서버 응답의 내용을 더 구체적으로 출력
        print(f"❌ [DEBUG] etf_ticker_list 수신 중 치명적 에러 발생!")
        print(f"❌ [DEBUG] 서버 응답 메시지: {e}")
        print(f"💡 [ADVICE] 현재 날짜({today})가 거래소 휴장일이거나 서버 점검 시간일 수 있습니다.")
        return
    
    all_current_data = []

    # 3. 각 ETF별 구성 종목 추출
    for i, ticker in enumerate(tqdm(etf_tickers, desc="ETF PDF 추출 중")):
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
                
                # 처음 수집되는 데이터 1개만 샘플 출력
                if i == 0:
                    print(f"\n📊 [DEBUG] 데이터 샘플 수신 확인: {etf_name}({ticker}) -> {len(df)} 종목 포함")
            
            # KRX 서버 부하 방지를 위한 미세 지연
            time.sleep(0.05)
            
        except Exception as e:
            # 에러 발생 시 상세 정보 출력
            if i < 5: # 너무 많은 출력 방지를 위해 초반 5개만
                print(f"\n❌ [DEBUG] 종목 수집 중 에러 | 티커: {ticker} | 사유: {e}")
            continue

    if not all_current_data:
        print("❌ [DEBUG] 수집된 데이터가 0건입니다. 저장 과정을 건너뜁니다.")
        return

    # 4. 오늘 수집 데이터 통합
    new_df = pd.concat(all_current_data, ignore_index=True)

    # 5. 기존 DB 로드 및 누적 (Incremental Update)
    db_path = './DB/raw_daily_ETF.parquet'
    os.makedirs('./DB', exist_ok=True)

    if os.path.exists(db_path):
        try:
            old_df = pd.read_parquet(db_path)
            old_df = old_df[old_df['날짜'] != today]
            final_df = pd.concat([old_df, new_df], ignore_index=True)
            print(f"🔄 [DEBUG] 기존 DB 로드 완료. 누적 후 총 행 수: {len(final_df)}")
        except Exception as e:
            print(f"⚠️ [DEBUG] 기존 파일 읽기 실패: {e}. 신규 생성으로 전환.")
            final_df = new_df
    else:
        final_df = new_df
        print(f"🆕 [DEBUG] 첫 번째 데이터 파일을 생성합니다. (총 {len(final_df)}행)")

    # 6. 최종 저장
    try:
        final_df.to_parquet(db_path, index=False)
        print(f"✅ [DEBUG] 최종 파일 저장 성공: {db_path}")
        # 파일 물리적 존재 여부 확인
        if os.path.exists(db_path):
            print(f"🎯 [DEBUG] 최종 확인: {db_path} ({os.path.getsize(db_path)} bytes)")
    except Exception as e:
        print(f"❌ [DEBUG] 파일 물리 저장 실패: {e}")

if __name__ == "__main__":
    collect_etf_data()
