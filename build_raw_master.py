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
        urllib.request.urlretrieve(url, file_zip)
        with zipfile.ZipFile(file_zip) as z:
            z.extractall()
        os.remove(file_zip)
        
        file_name = f"{m_type}_code.mst"
        data = []
        p2_len = 228 if m_code == "STK" else 222
        with open(file_name, mode="r", encoding="cp949") as f:
            for row in f:
                code, std_code, name = row[0:9].strip(), row[9:21].strip(), row[21:61].strip()
                target_val = '0'
                if m_code == "KSQ":
                    part2 = row[-p2_len:]
                    if len(part2) > 55 and part2[55:56] == '1':
                        target_val = 'KRQ150'
                data.append({'단축코드': code, '표준코드': std_code, '종목명': name, '시장구분': m_code, '수집대상': target_val})
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
        code, name = row['단축코드'], row['종목명']
        
        try:
            # 🔍 API 호출
            res = ka.get_stock_base_info(code)
            
            # 1. 서버 회신이 아예 없는 경우 (None)
            if not res:
                print(f"   [FAIL] {code} | {name.ljust(15)} | 서버 응답 없음 (None)")
                fail_cnt += 1
                continue

            # 2. 서버가 에러 코드를 보낸 경우 (rt_cd != '0')
            if res.get('rt_cd') != '0':
                msg = res.get('msg1', '메시지 없음')
                print(f"   [API ERR] {code} | {name.ljust(10)} | 코드:{res.get('rt_cd')} | 사유:{msg}")
                fail_cnt += 1
                continue

            # 3. 정상 응답 처리 (output 존재)
            if 'output' in res:
                out = res.output # AttrDict 점 표기법
                
                # 데이터 매핑
                if row['시장구분'] == 'STK' and out.kospi200_item_yn == 'Y':
                    df.at[idx, '수집대상'] = 'KSP200'
                
                df.at[idx, '섹터(대분류)'] = out.get('idx_bztp_lcls_cd_name', '')
                df.at[idx, '업종(중분류)'] = out.get('idx_bztp_mcls_cd_name', '')
                df.at[idx, '거래정지여부'] = out.get('tr_stop_yn', 'N')
                df.at[idx, '관리종목여부'] = out.get('admn_item_yn', 'N')
                df.at[idx, '상장주수'] = int(out.lstg_stqt) if out.get('lstg_stqt') else 0
                df.at[idx, '주식종류코드'] = out.get('stck_kind_cd', '')
                
                success_cnt += 1
                # 🔍 [성공 디버깅] 100건마다 한 번씩 회신 샘플 출력
                if success_cnt % 100 == 0:
                    print(f"   ✅ [SAMPLE] {code}({name}) -> 섹터: {out.get('idx_bztp_lcls_cd_name')}, KSP200: {out.get('kospi200_item_yn')}")

            # 초당 호출 제한(TPS) 준수
            time.sleep(0.07)

        except Exception as e:
            print(f"   [CRITICAL] {code} | {name} | 에러 내용: {str(e)}")
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
