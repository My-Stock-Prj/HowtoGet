import urllib.request, ssl, zipfile, os

def check_kosdaq_mst():
    ssl._create_default_https_context = ssl._create_unverified_context
    url = "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip"
    
    print("📡 MST 다운로드 중...")
    urllib.request.urlretrieve(url, "kosdaq.zip")
    
    with zipfile.ZipFile("kosdaq.zip") as z:
        z.extractall()
    
    file_name = "kosdaq_code.mst"
    # 확인하고 싶은 대표 코스닥 150 종목들
    target_codes = ['293490', '247540', '086520', '066970', '035900'] 
    
    print(f"\n{'종목명':<15} | {'코드':<8} | {'주변 데이터 (Index 90~120)'}")
    print("-" * 60)
    
    with open(file_name, mode="r", encoding="cp949") as f:
        for row in f:
            code = row[0:9].strip()
            # 단축코드는 보통 앞에 '0' 혹은 공백이 있으므로 포함 여부로 체크
            if any(tc in code for tc in target_codes):
                name = row[21:61].strip()
                # 인덱스 90부터 120까지 넉넉하게 추출 (Y가 어디 있는지 눈으로 확인)
                surrounding_data = row[90:120]
                
                # 가독성을 위해 인덱스 번호를 위에 표시
                print(f"{name:<15} | {code:<8} | {surrounding_data}")
                
    os.remove("kosdaq.zip")
    os.remove(file_name)

if __name__ == "__main__":
    check_kosdaq_mst()
