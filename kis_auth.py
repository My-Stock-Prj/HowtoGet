# 이 코드는 kis_auth.py
import os
import json
import logging
import requests
import time
from google.oauth2 import service_account

# 1. AttrDict 클래스 (dict.key 접근 지원)
class AttrDict(dict):
    """딕셔너리 데이터를 dict.key 형태로 접근 가능하게 해주는 클래스"""
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class TREnv:
    def __init__(self):
        # [수정] 입구 정제: 환경 변수 로드 시 앞뒤 공백을 즉시 제거합니다.
        self.my_app = os.getenv('KIS_APP_KEY', '').strip()
        self.my_sec = os.getenv('KIS_APP_SECRET', '').strip()
        self.my_env = os.getenv('KIS_ENV_DV', 'real').strip()
        
        if self.my_env == 'real':
            self.my_url = "https://openapi.koreainvestment.com:9443"
        else:
            self.my_url = "https://openapivts.koreainvestment.com:29443"
        self.access_token = ""

_env = None

def getEnv():
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
    global _env
    if _env is None: _env = getTREnv()
    
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
            # [수정] 저장 정제: 발급된 토큰도 저장 시점에 strip()을 강제합니다.
            _env.access_token = res_data.get('access_token', '').strip()
            logger.info("KIS 인증 성공: 접근 토큰 발급 완료")
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
    global _env
    if _env is None: _env = getTREnv()
    
    # ---------------------------------------------------------
    # [추가] 공통 속도 제한: 모든 요청 전 0.12초 대기
    # ---------------------------------------------------------
    time.sleep(0.12)

    # 토큰 유실 방어
    if not _env.access_token:
        auth()

    full_url = f"{_env.my_url}{url}" if url.startswith('/') else url

    if not isinstance(headers, dict):
        headers = {}

    # [수정] 헤더 조립: 모든 def에서 중복되던 정제 로직을 여기서 한 번에 처리합니다.
    token = str(_env.access_token).strip()
    headers["Content-Type"] = "application/json"
    headers["Authorization"] = f"Bearer {token}"  # 대문자 Authorization 권장
    headers["appkey"] = _env.my_app
    headers["appsecret"] = _env.my_sec
    headers["tr_id"] = tr_id if tr_id else "CTPF1002R"
    headers["custtype"] = "P"

    print(f"\n📡 [DEBUG SEND] URL: {full_url} | TR_ID: {headers['tr_id']}")
    
    try:
        if params is not None:
            if isinstance(params, str):
                try: params = json.loads(params)
                except: pass
            
            if isinstance(params, dict) and "PDNO" in params:
                params["PDNO"] = str(params["PDNO"]).strip().zfill(6)

        # 통신 수행
        if is_post:
            resp = requests.post(full_url, headers=headers, json=params)
        else:
            resp = requests.get(full_url, headers=headers, params=params)
        
        # ---------------------------------------------------------
        # [추가] 자동 재시도: 토큰 이슈(EGW) 발생 시 재인증 후 1회 재시도
        # ---------------------------------------------------------
        if resp.status_code != 200:
            err_body = resp.text
            if "EGW00205" in err_body or "EGW00201" in err_body:
                print("🔑 [RETRY] 토큰 무효화 감지. 재인증 후 재시도 중...")
                auth()
                headers["Authorization"] = f"Bearer {_env.access_token.strip()}"
                if is_post:
                    resp = requests.post(full_url, headers=headers, json=params)
                else:
                    resp = requests.get(full_url, headers=headers, params=params)

        print(f"📥 [DEBUG RECV] Status Code: {resp.status_code}")
        if resp.status_code != 200:
            print(f"📥 [DEBUG RECV] Error Body: {resp.text}")

        resp.isOK = lambda: resp.status_code == 200
        resp.printError = lambda *args, **kwargs: None 
        resp.getBody = lambda: AttrDict(resp.json())
        return resp

    except Exception as e:
        print(f"❗ [DEBUG ERROR] 통신 실패: {str(e)}")
        class MockResp:
            def isOK(self): return False
            def printError(self, *args, **kwargs): pass
            def json(self): return {}
            def getBody(self): return AttrDict({})
            @property
            def status_code(self): return 500
        return MockResp()


def get_stock_base_info(stock_code):
    """
    국내주식 종목정보 상세조회 (CTPF1002R)
    """
    global _env
    if _env is None: _env = getTREnv()
    
    url = "/uapi/domestic-stock/v1/quotations/search-stock-info"
    tr_id = "CTPF1002R"
    
    params = {
        "PRDT_TYPE_CD": "300",
        "PDNO": str(stock_code).strip().zfill(6)
    }

    # _url_fetch에서 인증, 정제, 속도제한을 모두 처리하므로 호출부만 남깁니다.
    res = _url_fetch(url, {}, tr_id, params, is_post=False)
    return res.getBody()
