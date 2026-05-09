# check_parquet.py
# -*- coding: utf-8 -*-
import pandas as pd
import os
import argparse
import traceback
import kis_auth as ka 
import gspread

def sync_to_dpq(filename):
    BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')
    target_path = os.path.join(BASE_DIR, filename)
    
    print(f"🔍 [DATA CHECK] '{filename}' -> 'dpq' 시트 전송 시작...")
    
    if not os.path.exists(target_path):
        print(f"❌ [ERROR] 파일을 찾을 수 없습니다: {target_path}")
        return

    try:
        df = pd.read_parquet(target_path)
        df_clean = df.fillna("").astype(str)
        data_to_send = [df_clean.columns.values.tolist()] + df_clean.values.tolist()
        
        # kis_auth 정책에 따라 별도의 JSON 로딩 없이 scopes만 전달하여 인증 객체를 생성합니다.
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = ka.get_gcp_creds(scopes)
        
        if not creds:
            print("❌ [ERROR] 구글 인증 실패: GCP_CREDENTIALS 환경 변수를 확인하세요.")
            return

        client = gspread.authorize(creds)
        spreadsheet = client.open("my")
        worksheet = spreadsheet.worksheet("dpq")
        
        worksheet.clear()
        worksheet.update('A1', data_to_send)
        
        print(f"✅ [SUCCESS] 시트 업데이트 완료 ({len(df)} 행)")
        
    except Exception as e:
        print(f"❌ [CRITICAL ERROR] {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, required=True)
    args = parser.parse_args()
    sync_to_dpq(args.file)
