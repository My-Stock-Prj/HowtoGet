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
        # [수정] 전처리는 kis_auth에 일임하되, 숫자가 아닌 경우 skip 로직은 유지
        raw_code = str(row['단축코드']).strip()
        name = row['종목명']
        
        if not raw_code.isdigit():
            continue
        
        try:
            # 🔍 API 호출 (zfill 등 정제는 ka.get_stock_base_info 내부에서 수행됨)
            res = ka.get_stock_base_info(raw_code)
            
            # [유지] 디버깅 코드: 서버의 원시 응답 확인
            if res:
                try:
                    raw_res_log = json.dumps(dict(res), ensure_ascii=False)
                except:
                    raw_res_log = str(res)
            else:
                raw_res_log = "None (No Response)"

            # 1. 서버 회신이 아예 없는 경우
            if not res:
                print(f"   [FAIL] {raw_code} | {name} | 서버 응답 없음")
                fail_cnt += 1
                continue

            # 2. 서버가 에러 코드를 보낸 경우 (rt_cd != '0')
            # AttrDict 활용으로 점(.) 표기법 사용
            if res.rt_cd != '0':
                msg = res.msg1 if res.msg1 else '메시지 없음'
                print(f"   [DEBUG JSON] {raw_code} | {raw_res_log}")
                print(f"   [API ERR] {res.msg_cd} | {name.ljust(10)} | 코드:{res.rt_cd} | 사유:{msg}")
                fail_cnt += 1
                continue

            # 3. 정상 응답 처리 (output 존재)
            if 'output' in res:
                out = res.output
                
                # 데이터 매핑 (AttrDict 덕분에 get 없이 속성 접근 가능)
                if row['시장구분'] == 'STK' and out.kospi200_item_yn == 'Y':
                    df.at[idx, '수집대상'] = 'KSP200'
                
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

            # [삭제] time.sleep(0.12) -> kis_auth._url_fetch 내부에서 공통 수행됨

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
