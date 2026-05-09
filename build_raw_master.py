# 이 코드는 build_raw_master.py 파일
# -*- coding: utf-8 -*-
import urllib.request, ssl, zipfile, os, time, json
import pandas as pd
import numpy as np
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials

# 1. KIS 인증 모듈 연동
try:
    import kis_auth as ka
except ImportError:
    print("❌ 에러: kis_auth.py 파일을 찾을 수 없습니다.")
    ka = None

def get_base_mst():
    def download_and_parse(m_type, m_code):
        ssl._create_default_https_context = ssl._create_unverified_context
        url = f"https://new.real.download.dws.co.kr/common/master/{m_type}_code.mst.zip"
        file_zip = f"{m_type}.zip"
        print(f"📡 [{m_code}] MST 파일 다운로드 중...")
        # 원본 유지: urllib.request.urlretrieve(url, file_zip)
        urllib.request.urlretrieve(url, file_zip)
        with zipfile.ZipFile(file_zip) as z:
            z.extractall()
        os.remove(file_zip)
        
        file_name = f"{m_type}_code.mst"
        data = []
        # 원본 p2_len 로직은 후방 인덱싱에서 line[-186]으로 대체되므로 제거해도 되나, 
        # 구조적 엄격함을 위해 남겨두되 실제 판별은 line[-186]으로 수행합니다.
        with open(file_name, mode="r", encoding="cp949") as f:
            for row in f:
                # 후방 인덱싱을 위한 전처리
                line = row.strip()
                if not line: continue

                # 원본 컬럼 추출 로직 (strip 유지)
                code, std_code, name = line[0:9].strip(), line[9:21].strip(), line[21:61].strip()
                
                kospi200_val = 'N'
                kosdaq150_val = 'N'
                
                # 핵심 변경: 뒤에서부터 세는 -186 인덱스 적용
                if m_code == "KSQ":
                    if len(line) >= 186 and line[-186] == 'Y':
                        kosdaq150_val = 'Y'
                
                data.append({
                    '단축코드': code, 
                    '표준코드': std_code, 
                    '종목명': name, 
                    '시장구분': m_code, 
                    'KOSPI200': kospi200_val, 
                    'KOSDAQ150': kosdaq150_val
                })
        os.remove(file_name)
        return pd.DataFrame(data)

    return pd.concat([download_and_parse("kospi", "STK"), download_and_parse("kosdaq", "KSQ")], ignore_index=True)

def augment_master_via_api(df):
    print(f"\n🚀 2단계: API 상세 조회 시작 (총 {len(df)}건)")
    print("="*60)
    
    # 신규 칼럼 초기화
    new_cols = ['섹터(대분류)', '업종(중분류)', '거래정지여부', '관리종목여부', '상장주수', '주식종류코드']
    for col in new_cols: df[col] = ''
    df['상장주수'] = 0

    success_cnt, fail_cnt = 0, 0

    for idx, row in df.iterrows():
        raw_code = str(row['단축코드']).strip()
        name = row['종목명']
        
        if not raw_code.isdigit():
            continue
        
        try:
            res = ka.get_stock_base_info(raw_code)
            
            if res:
                try:
                    raw_res_log = json.dumps(dict(res), ensure_ascii=False)
                except:
                    raw_res_log = str(res)
            else:
                raw_res_log = "None (No Response)"

            if not res:
                print(f"   [FAIL] {raw_code} | {name} | 서버 응답 없음")
                fail_cnt += 1
                continue

            if res.rt_cd != '0':
                msg = res.msg1 if res.msg1 else '메시지 없음'
                print(f"   [DEBUG JSON] {raw_code} | {raw_res_log}")
                print(f"   [API ERR] {res.msg_cd} | {name.ljust(10)} | 코드:{res.rt_cd} | 사유:{msg}")
                fail_cnt += 1
                continue

            if 'output' in res:
                out = res.output
                
                if row['시장구분'] == 'STK' and out.kospi200_item_yn == 'Y':
                    df.at[idx, 'KOSPI200'] = 'Y'
                
                df.at[idx, '섹터(대분류)'] = out.idx_bztp_lcls_cd_name
                df.at[idx, '업종(중분류)'] = out.idx_bztp_mcls_cd_name
                df.at[idx, '거래정지여부'] = out.tr_stop_yn
                df.at[idx, '관리종목여부'] = out.admn_item_yn
                
                lstg_stqt = out.lstg_stqt
                df.at[idx, '상장주수'] = int(float(lstg_stqt)) if lstg_stqt else 0
                df.at[idx, '주식종류코드'] = out.stck_kind_cd
                
                success_cnt += 1
                if success_cnt % 100 == 0:
                    print(f"   ✅ [SAMPLE] {raw_code}({name}) 성공 | 현재 {idx+1}번째 처리 중")

        except Exception as e:
            print(f"   [CRITICAL] {raw_code} | {name} | 에러 내용: {str(e)}")
            fail_cnt += 1

    print("="*60)
    print(f"✨ API 조회 완료! (성공: {success_cnt}, 실패: {fail_cnt})")
    return df

def save_and_upload(df):
    os.makedirs("DB", exist_ok=True)
    df.to_parquet("DB/raw_mst_krx_full.parquet", index=False)
    
    try:
        creds = ka.get_gcp_creds()
        if not creds: return
        gc = gspread.authorize(creds)
        sh = gc.open('my')
        ws = sh.worksheet('mst')
        ws.clear()
        ws.format("A:A", {"numberFormat": {"type": "TEXT"}})
        set_with_dataframe(ws, df)
        print("✅ 구글 시트 업데이트 성공!")
    except Exception as e:
        print(f"❌ 시트 업데이트 실패: {e}")

def main():
    start = time.time()
    base_df = get_base_mst()
    final_df = augment_master_via_api(base_df)
    save_and_upload(final_df)
    print(f"🏁 전체 공정 종료! (소요시간: {int(time.time()-start)}초)")

if __name__ == "__main__":
    main()
