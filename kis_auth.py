# 이 코드는 kis_auth.py 첫 생성
import os
import json
import logging
import requests
import pandas as pd
from google.oauth2 import service_account

# 로깅 설정: 필수 메시지만 출력 (4번 원칙)
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class TREnv:
    """거래 환경 변수 및 설정 관리 클래스 (5번 원칙: 일원화)"""
    def __init__(self):
        # 깃허브 시크릿에서 값 로드
        self.my_app = os.getenv('KIS_APP_KEY')
        self.my_sec = os.getenv('KIS_APP_SECRET')
        self.my_cano = os.getenv('KIS_CANO')
        self.my_acnt_prdt_cd = os.getenv('KIS_ACNT_PRDT_CD', '01')
        self.my_env = os.getenv('KIS_ENV_DV', 'real') # 기본값 real (2번 원칙)
        
        # 서버 주소 설정
        if self.my_env == 'real':
            self.my_url = "https://openapi.koreainvestment.com:9443"
        else:
            # 모의투자 미사용 시에도 대비하여 기본 주소 설정
            self.my_url = "https://openapivts.koreainvestment.com:29443"
        
        self.access_token = ""

# 전역 환경 객체
_env = None

def getEnv():
    """서버 주소 정보 반환"""
    return {
        "prod": "https://openapi.koreainvestment.com:9443",
        "vps": "https://openapivts.koreainvestment.com:29443"
    }

def getTREnv():
    """현재 설정된 환경 객체 반환"""
    global _env
    if _env is None:
        _env = TREnv()
    return _env

def auth():
    """KIS 인증 실행: 매번 새로 발급 (1번 원칙: 옵션 A)"""
    global _env
    if _env is None:
        _env = TREnv()
    
    if not _env.my_app or not _env.my_sec:
        logger.error("에러: KIS_APP_KEY 또는 KIS_APP_SECRET이 설정되지 않았습니다.")
        return

    # 토큰 발급 API 호출
    url = f"{_env.my_url}/oauth2/tokenP"
    headers = {"Content-Type": "application/json"}
    data = {
        "grant_type": "client_credentials",
        "appkey": _env.my_app,
        "appsecret": _env.my_sec
    }

    try:
        res = requests.post(url, headers=headers, data=json.dumps(data))
        if res.status_code == 200:
            _env.access_token = res.json().get('access_token')
            logger.info("KIS 인증 성공: 접근 토큰 발급 완료")
        else:
            logger.error(f"KIS 인증 실패: {res.text}")
    except Exception as e:
        logger.error(f"인증 중 오류 발생: {str(e)}")

def get_gcp_creds(scopes=None):
    """GCP 크리덴셜 객체 생성 (3번 원칙)"""
    if scopes is None:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    
    gcp_json_raw = os.getenv('GCP_CREDENTIALS')
    if not gcp_json_raw:
        logger.error("에러: GCP_CREDENTIALS가 설정되지 않았습니다.")
        return None

    try:
        creds_info = json.loads(gcp_json_raw)
        credentials = service_account.Credentials.from_service_account_info(
            creds_info, scopes=scopes
        )
        logger.info("GCP 인증 성공: 구글 서비스 연결 완료")
        return credentials
    except Exception as e:
        logger.error(f"GCP 인증 객체 생성 실패: {str(e)}")
        return None

def set_order_hash(headers, data):
    """주문 해시값 설정 (기존 기능 유지)"""
    global _env
    url = f"{_env.my_url}/uapi/hashkey"
    res = requests.post(url, headers=headers, data=json.dumps(data))
    if res.status_code == 200:
        headers["hashkey"] = res.json().get('hashkey')
    return headers
