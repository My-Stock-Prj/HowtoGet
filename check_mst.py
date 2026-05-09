import urllib.request, ssl, zipfile, os

def check_kosdaq_mst():
    ssl._create_default_https_context = ssl._create_unverified_context
    url = "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip"
    
    print("📡 MST 다운로드 중...")
    urllib.request.urlretrieve(url, "kosdaq.zip")
    
    with zipfile.ZipFile("kosdaq.zip") as z:
        z.extractall()
    
    file_name = "kosdaq_code.mst"
    # 확인 타겟: 코스닥 150 주요 종목
    target_codes = ['293490', '247540', '086520', '035900'] 
    
    print("\n" + "="*100)
    print("🔍 KOSDAQ MST 인덱스 정밀 분석 (0 ~ 150 바이트)")
    print("="*100)

    # 상단 인덱스 가이드 (10단위) 생성
    guide_10 = "".join([str(i//10).ljust(10) for i in range(15)])
    guide_1 = "0123456789" * 15
    
    with open(file_name, mode="r", encoding="cp949") as f:
        for row in f:
            code = row[0:9].strip()
            if any(tc in code for tc in target_codes):
                name = row[21:61].strip()
                # 0부터 150바이트까지 데이터 추출
                raw_data = row[0:150]
                
                print(f"\n[종목명: {name} / 코드: {code}]")
                print(f"인덱스(10단위): {guide_10}")
                print(f"인덱스(1단위) : {guide_1}")
                print(f"실제 데이터   : {raw_data}")
                
                # 'Y'가 발견되는 모든 인덱스 번호를 출력
                found_indices = [str(i) for i, char in enumerate(raw_data) if char == 'Y']
                if found_indices:
                    print(f"💡 'Y' 발견 위치(Index): {', '.join(found_indices)}")
                else:
                    print("💡 'Y'를 찾지 못했습니다.")
                print("-" * 100)

    if os.path.exists("kosdaq.zip"): os.remove("kosdaq.zip")
    if os.path.exists(file_name): os.remove(file_name)

if __name__ == "__main__":
    check_kosdaq_mst()
