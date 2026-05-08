# 이 코드는 build_raw_master.py 파일
def augment_master_via_api(df):
    print(f"🚀 2단계: API 상세 조회 시작 (대상: {len(df)}건)...")
    
    # 신규 칼럼 초기화
    df['섹터(대분류)'] = ''
    df['업종(중분류)'] = ''
    df['거래정지여부'] = 'N'
    df['관리종목여부'] = 'N'
    df['상장주수'] = 0
    df['주식종류코드'] = ''
    
    if ka is None: return df

    # 디버깅용 카운터
    success_count = 0
    fail_count = 0

    for idx, row in df.iterrows():
        code = row['단축코드']
        try:
            # API 호출
            res = ka.get_stock_base_info(code) 
            
            # 🔍 [디버깅] 서버 응답 상태 확인
            if res is None:
                print(f"   ❌ [FAIL] {code} ({row['종목명']}): 서버로부터 응답이 없습니다 (None)")
                fail_count += 1
                continue

            # 🔍 [디버깅] rt_cd가 '0'(성공)이 아닌 경우 상세 메시지 출력
            rt_cd = res.get('rt_cd')
            msg1 = res.get('msg1', '메시지 없음')
            
            if rt_cd != '0':
                print(f"   ⚠️ [API ERROR] {code} ({row['종목명']}): rt_cd={rt_cd}, msg='{msg1}'")
                fail_count += 1
                # 연속 에러 발생 시 토큰/권한 문제일 수 있으므로 중단 고려 가능
                if fail_count > 10: 
                    print("🚨 연속적인 API 에러 발생! 설정을 확인하세요.")
                continue

            # 성공 시 데이터 매핑
            if 'output' in res:
                out = res['output']
                
                # 수집대상 업데이트
                if row['시장구분'] == 'STK' and out.get('kospi200_item_yn') == 'Y':
                    df.at[idx, '수집대상'] = 'KSP200'
                
                # 상세 정보 채우기
                df.at[idx, '섹터(대분류)'] = out.get('idx_bztp_lcls_cd_name', '')
                df.at[idx, '업종(중분류)'] = out.get('idx_bztp_mcls_cd_name', '')
                df.at[idx, '거래정지여부'] = out.get('tr_stop_yn', 'N')
                df.at[idx, '관리종목여부'] = out.get('admn_item_yn', 'N')
                df.at[idx, '상장주수'] = int(out.get('lstg_stqt', 0)) if out.get('lstg_stqt') else 0
                df.at[idx, '주식종류코드'] = out.get('stck_kind_cd', '')
                
                success_count += 1
            
            # API 제한(TPS) 준수
            time.sleep(0.07)
            
            # 100건마다 진행 상황 요약 출력
            if (idx + 1) % 100 == 0:
                print(f"   📊 [PROGRESS] {idx + 1}개 완료 (성공: {success_count}, 실패: {fail_count})")
                
        except Exception as e:
            print(f"   ❌ [CRITICAL ERROR] {code} ({row['종목명']}): {str(e)}")
            fail_count += 1
            continue

    print(f"✨ API 보강 완료! 총 성공: {success_count}건 / 실패: {fail_count}건")
    return df
