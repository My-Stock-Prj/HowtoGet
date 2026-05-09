import urllib.request, ssl, zipfile, os

def check_kosdaq_mst_reverse():
    ssl._create_default_https_context = ssl._create_unverified_context
    url = "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip"
    
    print("📡 MST 다운로드 및 분석 시작...")
    urllib.request.urlretrieve(url, "kosdaq.zip")
    with zipfile.ZipFile("kosdaq.zip") as z:
        z.extractall()
    
    file_name = "kosdaq_code.mst"
    
    # [실험군] 코스닥 150 편입 종목
    target_k150 = ['293490', '247540', '086520', '035900'] 
    # [대조군] 코스닥 150 미편입 일반 종목 (무작위 선정)
    target_normal = ['000250', '001540', '001810'] # 삼천당제약, 안국약품, 무림SP 등 (시점에 따라 다를 수 있음)
    
    target_all = target_k150 + target_normal
    
    print("\n" + "="*120)
    print(f"{'그룹':<8} | {'종목명':<15} | {'코드':<8} | {'뒤에서부터의 위치 분석'}")
    print("="*120)

    with open(file_name, mode="r", encoding="cp949") as f:
        for row in f:
            line = row.strip()
            if not line: continue
            
            row_head = line[0:20]
            matched_code = next((tc for tc in target_all if tc in row_head), None)
            
            if matched_code:
                group = "⭐K150" if matched_code in target_k150 else "⚪일반"
                name = line[21:61].strip()
                
                # 음수 인덱스 계산 (줄 끝 기준)
                # 'Y'가 발견된 모든 음수 위치
                negative_y_indices = [-(len(line) - i) for i, char in enumerate(line) if char == 'Y']

                print(f"\n[{group}] {name:<15} | {matched_code:<8} | 길이: {len(line)}")
                
                # 1. 'Y' 발견 위치 출력
                if negative_y_indices:
                    print(f"   💡 'Y' 발견 위치(Negative Index): {', '.join(map(str, negative_y_indices))}")
                else:
                    print("   💡 'Y' 발견 안됨")
                
                # 2. 예상 지점 집중 탐색 (뒷부분 공통 구간 출력)
                # 명세서 기반 예측 지점(-182 부근)을 포함하여 넉넉히 출력
                test_range = line[-195:-165]
                
                # 가독성을 위해 해당 구간의 음수 인덱스 가이드 출력
                indices_guide = " ".join([str(i).replace('-', '').zfill(2) for i in range(195, 164, -1)])
                
                print(f"   🔍 후방 탐색 (-195 ~ -165): {test_range}")
                print(f"   📏 위치 가이드 (뒤에서): {indices_guide}")
                print("-" * 120)

    if os.path.exists("kosdaq.zip"): os.remove("kosdaq.zip")
    if os.path.exists(file_name): os.remove(file_name)

if __name__ == "__main__":
    check_kosdaq_mst_reverse()
