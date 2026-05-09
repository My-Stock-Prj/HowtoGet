# 이 코드는 check_parquet.py
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import argparse
import traceback
from datetime import datetime
import kis_auth as ka  # 구글 인증 및 유틸리티
import gspread

# --- [설정 로드] ---
BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')

def sync_to_dpq(filename):
    """
    Parquet 데이터를 읽어 구글 시트 'my' 파일의 'dpq' 시트에 덮어쓰기
    """
    # 1. 파일 경로 확인
    target_path = os.path.join(BASE_DIR, filename) if not os.path.isabs(filename) else filename
    
    print(f"🔍 [CHECK] '{filename}' 데이터를 'dpq' 시트로 전송 시작...")
    
    if not os.path.exists(target_path):
        print(f"❌ [ERROR] 파일을 찾을 수 없습니다: {target_path}")
        return

    try:
        # 2. 데이터 로딩 및 정제
        df = pd.read_parquet(target_path)
        
        # 시트 업로드 안정성을 위해 NaN 처리 및 전체 문자열 변환
        # (숫자나 날짜 데이터가 JSON 직렬화 오류를 일으키는 것을 방지)
        df_clean = df.fillna("").astype(str)
        
        # 헤더를 포함한 리스트 데이터 생성
        data_to_send = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        
        # 3. 구글 인증 및 시트 연결
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = ka.get_gcp_creds(scopes)
        
        if not creds:
            print("❌ [ERROR] 구글 인증에 실패했습니다.")
            return

        client = gspread.authorize(creds)
        spreadsheet = client.open("my")
        worksheet = spreadsheet.worksheet("dpq") # 대상 시트: dpq
        
        # 4. 데이터 갱신 (기존 내용 전체 삭제 후 기록)
        worksheet.clear()
        worksheet.update('A1', data_to_send)
        
        print(f"✅ [SUCCESS] 전송 완료!")
        print(f"📊 요약: 총 {len(df):,} 행 / {len(df.columns)}개 칼럼이 dpq 시트에 기록되었습니다.")
        
    except Exception as e:
        print(f"❌ [ERROR] 작업 중 오류 발생: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parquet Data Checker (Sheet Sync)")
    # 실행 시 파일명을 인자로 받음
    parser.add_argument("--file", type=str, required=True, help="대상 Parquet 파일명 (예: raw_daily_PQ.parquet)")
    
    args = parser.parse_args()
    
    sync_to_dpq(args.file)
