import urllib.request
import ssl
import zipfile
import os
import time
import json
import pandas as pd
import numpy as np
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials

# 1. 한국투자증권 인증 및 API 호출 모듈 임포트
try:
    import kis_auth as ka  # 사용자님의 인증 파일명에 맞춰주세요
except ImportError:
    print("경고: kis_auth.py 모듈을 찾을 수 없습니다.")
    ka = None

# --------------------------------------------------------------------------------
# [1단계] MST 파일 파싱: 기초 4개 칼럼 + KRQ150 사전 판별
# --------------------------------------------------------------------------------
def get_base_mst():
    def download_and_parse(m_type, m_code):
        ssl._create_default_https_context = ssl._create_unverified_context
        url = f"https://new.real.download.dws.co.kr/common/master/{m_type}_code.mst.zip"
        file_zip = f"{m_type}.zip"
        print(f"[{m_code}] MST 다운로드 중...")
        urllib.request.urlretrieve(url, file_zip)
        
        with zipfile.ZipFile(file_zip) as z:
            z.extractall()
        os.remove(file_zip)
        
        file_name = f"{m_type}_code.mst"
        data = []
        # 코스닥 MST 규격에 따른 KOSDAQ150 위치 추출용 (KSQ: 222, STK: 228)
        p2_len = 228 if m_code == "STK" else 222
        
        with open(file_name, mode="r", encoding="cp949") as f:
            for row in f:
                code = row[0:9].strip()      # 단축코드
                std_code = row[9:21].strip() # 표준코드
                name = row[21:61].strip()    # 종목명
                
                # '수집대상' 초기 설정 (KRQ150 선점)
                target_val = '0'
                if m_code == "KSQ":
                    part2 = row[-p2_len:]
                    # 코스닥 마스터에서 150 지수 여부('1')가 확인된 경우
                    if len(part2) > 55 and part2[55:56] == '1':
                        target_val = 'KRQ150'
                
                data.append({
                    '단축코드': code,
                    '표준코드': std_code,
                    '종목명': name,
                    '시장구분': m_code,
                    '수집대상': target_val
                })
        
        os.remove(file_name)
        return pd.DataFrame(data)

    df_stk = download_and_parse("kospi", "STK")
    df_ksq = download_and_parse("kosdaq", "KSQ")
    return pd.concat([df_stk, df_ksq], ignore_index=True)

# --------------------------------------------------------------------------------
# [2단계] API(CTPF1101R) 보완: KSP200 확정 및 상세 6개 칼럼 추가
# --------------------------------------------------------------------------------
def augment_master_via_api(df):
    print(f"🚀 API 상세 보강 시작 (대상: {len(df)}건)...")
    
    # 6~11번 상세 칼럼 초기화
    df['섹터(대분류)'] = ''
    df['업종(중분류)'] = ''
    df['거래정지여부'] = 'N'
    df['관리종목여부'] = 'N'
    df['상장주수'] = 0
    df['주식종류코드'] = ''
    
    if ka is None: return df

    for idx, row in df.iterrows():
        code = row['단축코드']
        try:
            # 주식기본조회 API 호출 (CTPF1101R)
            # ※ 주의: kis_auth 내부의 함수명이 다를 경우 해당 이름으로 수정하세요.
            res = ka.get_stock_base_info(code) 
            
            if res and 'output' in res:
                out = res['output']
                
                # [수집대상 업데이트] 코스피200 여부 확인
                if row['시장구분'] == 'STK' and out.get('kospi200_item_yn') == 'Y':
                    df.at[idx, '수집대상'] = 'KSP200'
                
                # [상세 정보 채우기]
                df.at[idx, '섹터(대분류)'] = out.get('idx_bztp_lcls_cd_name', '')
                df.at[idx, '업종(중분류)'] = out.get('idx_bztp_mcls_cd_name', '')
                df.at[idx, '거래정지여부'] = out.get('tr_stop_yn', 'N')
                df.at[idx, '관리종목여부'] = out.get('admn_item_yn', 'N')
                df.at[idx, '상장주수'] = int(out.get('lstg_stqt', 0))
                df.at[idx, '주식종류코드'] = out.get('stck_kind_cd', '')
            
            # API 제한(TPS) 준수: 초당 약 15건 처리
            time.sleep(0.07)
            
            if (idx + 1) % 100 == 0:
                print(f"   - {idx + 1}개 진행 중... 현재: {row['종목명']}")
                
        except Exception as e:
            print(f"   ⚠️ {code} 조회 건너뜀: {e}")
            continue

    return df

# --------------------------------------------------------------------------------
# [3단계] 결과 저장 및 구글 시트 업데이트
# --------------------------------------------------------------------------------
def save_and_upload(df):
    # 1. 로컬 저장 (Parquet)
    os.makedirs("DB", exist_ok=True)
    df.to_parquet("DB/raw_mst_krx_full.parquet", index=False)
    print("💾 로컬 DB(Parquet) 저장 완료.")

    # 2. 구글 시트 업로드
    try:
        creds_json = os.environ.get('GCP_CREDENTIALS')
        if not creds_json: return
        
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes)
        gc = gspread.authorize(creds)
        
        sh = gc.open('my')
        try:
            ws = sh.worksheet('mst')
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title='mst', rows='100', cols='20')
        
        ws.clear()
        ws.format("A:A", {"numberFormat": {"type": "TEXT"}}) # 단축코드 0 유지
        set_with_dataframe(ws, df)
        print("✅ 구글 시트 'mst' 업데이트 완료!")
    except Exception as e:
        print(f"❌ 시트 업데이트 중 오류: {e}")

def main():
    print("=== 마스터 DB 구축 시작 ===")
    # 1단계: MST 리스트업
    base_df = get_base_mst()
    # 2단계: API 상세 보강
    final_df = augment_master_via_api(base_df)
    # 3단계: 마무리
    save_and_upload(final_df)
    
    print(f"\n📊 구축 결과")
    print(f"- 전체 종목: {len(final_df)}건")
    print(f"- KSP200: {len(final_df[final_df['수집대상'] == 'KSP200'])}건")
    print(f"- KRQ150: {len(final_df[final_df['수집대상'] == 'KRQ150'])}건")
    print("=== 모든 공정 완료 ===")

if __name__ == "__main__":
    main()
