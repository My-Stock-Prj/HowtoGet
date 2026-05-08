# 이 코드는 auth_functions.py
# -*- coding: utf-8 -*-
import os
import kis_auth as ka

def get_base_url():
    """
    kis_auth.py의 설정을 바탕으로 현재 환경(실전/모의)에 맞는 베이스 URL을 반환합니다.
    """
    env = ka.getTREnv()
    return env.my_url

def auth_token():
    """
    kis_auth.py의 auth 함수를 호출하여 접근 토큰을 발급받고 결과를 반환합니다.
    표준 함수들이 이 토큰 정보를 참조하여 API를 호출하게 됩니다.
    """
    # kis_auth.py 내의 auth() 실행 (토큰 발급 및 _env.access_token 설정)
    res = ka.auth()
    
    if res and 'access_token' in res:
        return res
    else:
        print("❌ [auth_functions] 토큰 발급에 실패했습니다.")
        return None

def get_header():
    """
    API 호출에 필요한 표준 헤더 구성을 도와주는 유틸리티 함수입니다.
    """
    env = ka.getTREnv()
    if not env.access_token:
        auth_token()
        
    return {
        "Content-Type": "application/json",
        "authorization": f"Bearer {env.access_token}",
        "appkey": env.my_app,
        "appsecret": env.my_sec
    }

# 기존 auth_functions.py에서 기대하는 최소한의 인터페이스 유지
def get_env_info():
    """현재 접속 환경 정보를 반환합니다."""
    env = ka.getTREnv()
    return env.my_env
