# 이 코드는 kis_auth.py
import os
import json
import logging
import requests
from google.oauth2 import service_account

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class TREnv:
    def __init__(self):
        self.my_app = os.getenv('KIS_APP_KEY')
        self.my_sec = os.getenv('KIS_APP_SECRET')
        self.my_env = os.getenv('KIS_ENV_DV', 'real') 
        
        if self.my_env == 'real':
            self.my_url = "https://openapi.koreainvestment.com:9443"
        else:
            self.my_url = "https://openapivts.koreainvestment.com:29443"
        self.access_token = ""

_env = None

def getEnv():
    """auth_functions.py와의 호환성을 위한 서버 주소 반환"""
    return {
        "prod": "https://openapi.koreainvestment.com:9443",
        "vps": "https://openapivts.koreainvestment.com:29443"
    }

def getTREnv():
    global _env
    if _env is None:
        _env = TREnv()
    return _env

def auth():
    """
    [수정 핵심] 인증 성공 시 반드시 결과를 리턴합니다.
    auth_functions.py의 auth_token 로직을 참조하여 보강되었습니다.
    """
    global _env
    if _env is None:
        _env = TREnv()
    
    if not _env.my_app or not _env.my_sec:
        logger.error("에러: KIS_APP_KEY 또는 KIS_APP_SECRET이 설정되지 않았습니다.")
        return None

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
            res_data = res.json()
            _env.access_token = res_data.get('access_token')
            logger.info("KIS 인증 성공: 접근 토큰 발급 완료")
            # [핵심] NoneType 에러 방지를 위해 결과 딕셔너리를 리턴합니다.
            return res_data 
        else:
            logger.error(f"KIS 인증 실패: {res.text}")
            return None
    except Exception as e:
        logger.error(f"인증 중 오류 발생: {str(e)}")
        return None

def get_gcp_creds(scopes=None):
    if scopes is None:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    gcp_json_raw = os.getenv('GCP_CREDENTIALS')
    if not gcp_json_raw:
        return None
    try:
        creds_info = json.loads(gcp_json_raw)
        return service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
    except:
        return None
        
def _url_fetch(url, headers, tr_id, params=None, is_post=False):
    """
    domestic_stock_functions.py에서 호출하는 실제 API 통신 함수입니다.
    """
    try:
        if is_post:
            res = requests.post(url, headers=headers, json=params)
        else:
            res = requests.get(url, headers=headers, params=params)
        
        if res.status_code == 200:
            return res
        else:
            logger.error(f"API 호출 실패: {res.status_code} - {res.text}")
            return res
    except Exception as e:
        logger.error(f"API 통신 오류: {str(e)}")
        return None
