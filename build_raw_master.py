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

# 1. KIS 인증 및 API 호출 모듈 (함수가 추가된 kis_auth.py 필요)
try:
    import kis_auth as ka
except ImportError:
    print("경고: kis_auth.py 모듈을 찾을 수 없습니다. 경로를 확인하세요.")
    ka = None

# --------------------------------------------------------------------------------
# [1단계] MST 파일 파싱: 기초 4개 칼럼 + KRQ150 사전 판별
# --------------------------------------------------------------------------------
def get_base_mst():
    def download_and_parse(m_type, m_code):
        ssl._create_default_https_context = ssl._create_unverified_context
        url = f"https://new.real.download.dws.co.kr/common/master/{m_type}_code.mst.zip"
        file_zip = f"{m_type}.zip"
        print(f"[{m_code}] MST 파일 다운로드 및 파싱 중...")
        
        try:
            urllib.request.urlretrieve(url, file_zip)
            with zipfile.ZipFile(file_zip) as z:
                z.extractall()
            os.remove(file_zip)
        except Exception as e:
            print(f"❌ 다운로드 오류: {e}")
            return pd.DataFrame()
        
        file_name = f"{m_type}_code.mst"
        data = []
        # 코스닥/코스피 위치 규격 (KSQ: 222, STK: 228)
        p2_len = 228 if m_code == "STK" else 222
        
        with open(file_name, mode="r", encoding="cp949") as f:
            for row in f:
                code = row[0:9].strip()      # 단축코드
                std_code = row[9:21].strip() # 표준코드
                name = row[21:61].strip()    # 종목명
                
                # '수집대상' 초기 설정 (코스닥150 선점)
                target_val = '0'
                if m_code == "KSQ":
                    part2 = row[-p2_len:]
                    # 코스닥 마스터 특정 위치의 '1'은 KOSDAQ150을 의미함
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

    base_stk = download_and_parse("kospi", "STK")
    base_ksq = download_and_parse("kosdaq", "KSQ")
    return pd.concat([base_stk, base_ksq], ignore_index=True)

# --------------------------------------------------------------------------------
# [2단계] API(CTPF1101R) 보완: KSP200 확정 및 상세 6개 칼럼 추가
# --------------------------------------------------------------------------------
def augment_master_via_api(df):
    print(f"🚀 2단계: API 상세 조회 시작 (총 {len(df)}건)...")
    
    # 6~11번 상세 칼럼 초기화
    df['섹터(대분류)'] = ''
    df['업종(중분류)'] = ''
    df['거래정지여부'] = 'N'
    df['관리종목여부'] = 'N'
    df['상장주수'] = 0
    df['주식종류코드'] = ''
    
    if ka is None: return df

    success_count = 0
    fail_count = 0

    for idx, row in df.iterrows():
        code = row['단축코드']
        try:
            # 🔍 [DEBUG] kis_auth에 추가한 CTPF1101R 함수 호출
            res = ka.get_stock_base_info(code) 
            
            if res and 'output' in res:
                out = res.output # AttrDict 사용 (점 표기법)
                
                # 1. [수집대상 업데이트] 코스피200 여부 확인
                if row['시장구분'] == 'STK' and out.kospi200_item_yn == 'Y':
                    df.at[idx, '수집대상'] = 'KSP200'
                
                # 2. [상세 정보 채우기]
                df.at[idx, '섹터(대분류)'] = out.idx_bztp_lcls_cd_name
                df.at[idx, '업종(중분류)'] = out.idx_bztp_mcls_cd_name
                df.at[idx, '거래정지여부'] = out.tr_stop_yn
                df.at[idx, '관리종목여부'] = out.admn_item_yn
                df.at[idx, '상장주수'] = int(out.lstg_stqt) if out.lstg_stqt else 0
                df.at[idx, '주식종류코드'] = out.stck_kind_cd
                
                success_count += 1
            else:
                # API 실패 시 디버깅 정보 (rt_cd, msg1 등은 kis_auth 내부 출력 활용)
                fail_count += 1
            
            # API 제한(TPS) 준수: 초당 15건 처리 페이스
            time.sleep(0.07)
            
            if (idx + 1) % 100 == 0:
                print(f"   📊 [진행] {idx + 1}개 완료 (성공: {success_count}, 실패: {fail_count})")
                
        except Exception as e:
            print(f"   ❌ [오류] {code} ({row['종목명']}): {str(e)}")
            fail_count += 1
            continue

    print(f"✨ API 보강 완료! 성공: {success_count}건 / 실패: {fail_count}건")
    return df

# --------------------------------------------------------------------------------
# [3단계] 저장 및 구글 시트 업데이트
# --------------------------------------------------------------------------------
def save_and_upload(df):
    # 1. 로컬 저장 (Parquet)
    os.makedirs("DB", exist_ok=True)
    save_path = "DB/raw_mst_krx_full.parquet"
    df.to_parquet(save_path, index=False, compression='snappy')
    print(f"💾 로컬 DB 저장 완료: {save_path}")

    # 2. 구글 시트 업데이트 (GCP_CREDENTIALS 환경변수 필요)
    try:
        creds_json = os.environ.get('GCP_CREDENTIALS')
        if not creds_json:
            print("GCP_CREDENTIALS가 설정되지 않아 시트 업로드를 건너뜁니다.")
            return

        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scopes)
        gc = gspread.authorize(creds)
        
        sh = gc.open('my') # 구글 시트 파일명 'my'
        try:
            ws = sh.worksheet('mst') # 시트명 'mst'
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title='mst', rows='100', cols='20')
        
        ws.clear()
        # A열(단축코드) 텍스트 포맷 강제 지정
        ws.format("A:A", {"numberFormat": {"type": "TEXT"}})
        set_with_dataframe(ws, df)
        print("✅ 구글 시트 'mst' 업데이트 완료!")
    except Exception as e:
        print(f"❌ 시트 업데이트 실패: {e}")

def main():
    start_time = time.time()
    print("--- 마스터 DB 구축 공정 시작 ---")
    
    # 1단계: MST 리스트업
    raw_df = get_base_mst()
    
    # 2단계: API 상세 보충
    final_df = augment_master_via_api(raw_df)
    
    # 3단계: 마무리
    save_and_upload(final_df)
    
    duration = int(time.time() - start_time)
    print(f"\n✨ 공정 완료! (소요시간: {duration}초)")
    print(f"📊 최종 종목 수: {len(final_df)}건")
    print(f"🎯 수집 대상(KSP200+KRQ150): {len(final_df[final_df['수집대상'] != '0'])}건")

if __name__ == "__main__":
    main()
