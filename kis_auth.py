# 이 코드는 kis_auth.py
import os
import json
import logging
import requests
from google.oauth2 import service_account

# 1. 클래스 상단(import 아래)에 추가
class AttrDict(dict):
    """딕셔너리 데이터를 dict.key 형태로 접근 가능하게 해주는 클래스"""
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__

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
    global _env
    if _env is None: _env = getTREnv()
    
    full_url = f"{_env.my_url}{url}" if url.startswith('/') else url

    # 1. 헤더 규격 강제 교정 (문자열 에러 원천 차단)
    # headers가 문자열이거나 None이면 새 딕셔너리로 교체
    if not isinstance(headers, dict):
        headers = {}

    # 2. 필수 인증 정보 강제 주입
    headers["Content-Type"] = "application/json"
    token = _env.access_token.strip() if _env.access_token else ""
    headers["authorization"] = f"Bearer {token}"
    headers["appkey"] = _env.my_app.strip()
    headers["appsecret"] = _env.my_sec.strip()
    headers["tr_id"] = tr_id if tr_id else "FHKST03010100" # TR_ID 누락 방어
    headers["custtype"] = "P"

    # [DEBUG] 보낼 데이터 확인
    print(f"\n📡 [DEBUG SEND] URL: {full_url}")
    print(f"📡 [DEBUG SEND] TR_ID: {headers['tr_id']}")
    
    try:
        # [수정 사항 반영] params 규격 교정 및 데이터 타입 강제
        if params is not None:
            if isinstance(params, str):
                try: 
                    params = json.loads(params)
                except: 
                    pass
            
            # [핵심] 상품번호(PDNO)가 숫자형으로 유실되지 않도록 문자열로 강제 변환
            if isinstance(params, dict) and "PDNO" in params:
                params["PDNO"] = str(params["PDNO"]).strip().zfill(6)

        # 3. 통신 수행
        if is_post:
            # POST 방식: json 인자로 전달
            resp = requests.post(full_url, headers=headers, json=params)
        else:
            # GET 방식: params 인자로 전달 (이 부분이 명확해야 서버가 PDNO를 읽음)
            resp = requests.get(full_url, headers=headers, params=params)
        
        # [DEBUG RECV] 응답 확인
        print(f"📥 [DEBUG RECV] Status Code: {resp.status_code}")
        if resp.status_code != 200:
            print(f"📥 [DEBUG RECV] Error Body: {resp.text}")

        resp.isOK = lambda: resp.status_code == 200
        resp.printError = lambda *args, **kwargs: None 
        # [추가] getBody() 호출 시 json 데이터를 반환하도록 연결
        # [수정 핵심] json 데이터를 AttrDict로 감싸서 점(.) 표기법 지원
        resp.getBody = lambda: AttrDict(resp.json())
        return resp

    except Exception as e:
        print(f"❗ [DEBUG ERROR] 통신 자체 실패: {str(e)}")
        class MockResp:
            def isOK(self): return False
            def printError(self, *args, **kwargs): pass
            def json(self): return {}
            def getBody(self): return AttrDict({}) # getBody 호출 시 에러 방지
            @property
            def status_code(self): return 500
        return MockResp()


def get_stock_base_info(stock_code):
    """
    국내주식 종목정보 상세조회 (CTPF1002R)
    """
    global _env
    if _env is None: _env = getTREnv()
    
    # 1. URL 설정
    url = "/uapi/domestic-stock/v1/quotations/search-stock-info"
    
    # 2. 헤더 설정 (헤더는 _url_fetch에서 자동으로 채워주므로 빈 딕셔너리만 선언해도 됨)
    tr_id = "CTPF1002R"
    headers = {"tr_id": tr_id}

    # 3. 파라미터 설정 (이 부분이 가장 중요!)
    params = {
        "PRDT_TYPE_CD": "300",
        "PDNO": str(stock_code).strip().zfill(6)
    }

    # 4. _url_fetch 호출 (is_post=False 이므로 GET 방식으로 전송됨)
    res = _url_fetch(url, headers, tr_id, params, is_post=False)
    
    # res 자체가 resp 객체이므로 getBody()를 호출하여 결과 반환
    return res.getBody()
