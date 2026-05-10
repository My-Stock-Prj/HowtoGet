# 이 코드는 build_ADB_main.py 파일
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# kis_auth 연동 (정책 및 유틸리티 활용)
try:
    import kis_auth as ka
except ImportError:
    print("❌ 에러: kis_auth.py 파일을 찾을 수 없습니다.")
    sys.exit(1)

# --- [설정 로드] ---
BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')
PQ_PATH = os.path.join(BASE_DIR, 'raw_daily_PQ.parquet')
MST_PATH = os.path.join(BASE_DIR, 'raw_mst_krx_full.parquet')
ADB_PATH = os.path.join(BASE_DIR, 'ADB_main.parquet')

def build_adb():
    print(f"🚀 {datetime.now()} ADB_main 구축 시작...")

    # 1. 소스 데이터 로드
    if not os.path.exists(PQ_PATH) or not os.path.exists(MST_PATH):
        print(f"❌ 소스 파일 누락: PQ({os.path.exists(PQ_PATH)}), MST({os.path.exists(MST_PATH)})")
        return

    df_pq = pd.read_parquet(PQ_PATH)
    df_mst = pd.read_parquet(MST_PATH)

    # 2. 데이터 병합 (PQ + MST)
    # MST에서 필요한 칼럼만 필터링 (명세서 순서 6, 8, 9번 대응)
    df_mst_sub = df_mst[['단축코드', '업종(중분류)', '거래정지여부', '관리종목여부']]
    df = pd.merge(df_pq, df_mst_sub, left_on='종목코드', right_on='단축코드', how='left')

    # 3. 시계열 정렬 (종목별/날짜별)
    df = df.sort_values(by=['종목코드', '날짜']).reset_index(drop=True)

    # 4. 수급 비중 계산 (명세서 11~21번)
    # 분모가 0인 경우를 대비해 replace(0, np.nan) 처리
    denom_amt = df['거래대금'].replace(0, np.nan)
    denom_vol = df['거래량'].replace(0, np.nan)

    # [대금 기준 비중 - % 단위 소수점 2자리]
    df['기관_순수_비중'] = ((df['기관계순매수대금'] - df['기금순매수대금']) / denom_amt * 100).round(2)
    df['기금_비중'] = (df['기금순매수대금'] / denom_amt * 100).round(2)
    df['외국인_비중'] = (df['외국인순매수대금'] / denom_amt * 100).round(2)
    df['개인_비중'] = (df['개인순매수대금'] / denom_amt * 100).round(2)
    # 기타법인: (전체순매수(0) - 개인 - 외인 - 기관계) / 대금
    df['기타법인_비중'] = ((0 - df['개인순매수대금'] - df['외국인순매수대금'] - df['기관계순매수대금']) / denom_amt * 100).round(2)

    # [수량 기준 비중 - % 단위 소수점 2자리]
    sub_inv_map = {
        '증권_비중': '증권순매수수량', '투신_비중': '투자신탁순매수수량', 
        '사모_비중': '사모펀드순매수수량', '보험_비중': '보험순매수수량', 
        '은행_비중': '은행순매수수량', '종금_비중': '종금순매수수량'
    }
    for col, src in sub_inv_map.items():
        df[col] = (df[src] / denom_vol * 100).round(2)

    # 5. 가격 액션 및 이동평균 (명세서 22~25번)
    # 캔들장악지수: (종가-시가)/(고가-저가)
    candle_denom = (df['고가'] - df['저가']).replace(0, np.nan)
    df['캔들장악지수'] = ((df['종가'] - df['시가']) / candle_denom).round(2)
    df['꼬리비율'] = ((df['고가'] - df[['시가', '종가']].max(axis=1)) / candle_denom).round(2)

    # 이격도 계산을 위한 이동평균 (종목별 그룹화)
    gp = df.groupby('종목코드')['종가']
    df['ma5'] = gp.transform(lambda x: x.rolling(window=5, min_periods=ka.POLICY["MIN_PERIODS"]).mean())
    df['ma20'] = gp.transform(lambda x: x.rolling(window=20, min_periods=ka.POLICY["MIN_PERIODS"]).mean())
    
    df['단기이격도_5'] = (df['종가'] / df['ma5'] * 100).round(2)
    df['단기이격도_20'] = (df['종가'] / df['ma20'] * 100).round(2)

    # 6. 리스크/에너지 (명세서 26~28번)
    df['공매도_비중'] = df['공매도거래량비중'].round(2) # PQ에서 이미 비중으로 수집됨
    
    # 변화율 계산 (당일 - 전일) / 전일
    gp_loan = df.groupby('종목코드')['당일대차잔고주수']
    df['대차잔고_변화율'] = gp_loan.transform(lambda x: (x - x.shift(1)) / x.shift(1) * 100).round(2)
    
    gp_cred = df.groupby('종목코드')['전체융자잔고비율']
    df['신용잔고_변화율'] = gp_cred.transform(lambda x: (x - x.shift(1))).round(2) # 비율의 증감(ppt)

    # 7. 최종 칼럼 정렬 (명세서 v5 순서 1~28 준수)
    final_cols = [
        "날짜", "종목코드", "종목명", "종가", "거래량", "업종(중분류)", "구분(출처)", 
        "거래정지여부", "관리종목여부", "거래대금", 
        "기관_순수_비중", "기금_비중", "외국인_비중", "개인_비중", "기타법인_비중", 
        "증권_비중", "투신_비중", "사모_비중", "보험_비중", "은행_비중", "종금_비중", 
        "캔들장악지수", "꼬리비율", "단기이격도_5", "단기이격도_20", 
        "공매도_비중", "대차잔고_변화율", "신용잔고_변화율"
    ]

    # 계산 중 발생한 inf, nan 처리
    df_adb = df[final_cols].replace([np.inf, -np.inf], 0).fillna(0)

    # 8. 저장
    os.makedirs(os.path.dirname(ADB_PATH), exist_ok=True)
    df_adb.to_parquet(ADB_PATH, index=False)
    print(f"✅ ADB_main 구축 완료! (총 {len(df_adb)} rows)")

if __name__ == "__main__":
    build_adb()
