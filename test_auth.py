import kis_auth as ka
import os

# 1. KIS 인증 테스트
print("--- KIS 인증 테스트 시작 ---")
ka.auth()
trenv = ka.getTREnv()

if trenv.access_token:
    print(f"✅ KIS 토큰 발급 성공!")
else:
    print("❌ KIS 토큰 발급 실패. 시크릿 설정을 확인하세요.")

# 2. 구글 크리덴셜 테스트
print("\n--- Google 인증 테스트 시작 ---")
creds = ka.get_gcp_creds()

if creds:
    print("✅ Google 서비스 계정 인증 성공!")
else:
    print("❌ Google 인증 실패. GCP_CREDENTIALS 설정을 확인하세요.")
