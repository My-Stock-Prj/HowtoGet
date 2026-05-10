# 이 코드는 kis_auth.py (정책 집중화 보강본_policy 적용)
import os
import json
import logging
import requests
import time
from google.oauth2 import service_account

# --- [1. KIS 시스템 중앙 정책 정의] ---
# 모든 실행 파일(build_raw_PQ, build_ADB 등)은 이 POLICY를 참조합니다.
POLICY = {
    "LOOKBACK_DAYS": 20,      # 전체 소급 및 백필링 기준 기간 (영업일 기준)
    "MIN_PERIODS": 1,         # ADB 지표 계산 허용 최소 일수 (NaN 방지용)
    "REQUIRED_DAYS": 5,       # 추천 종목으로 분류되기 위한 최소 데이터 보유 일수 (안전장치)
    "SLEEP_TIME": 0.07,       # API 호출 간 표준 대기 시간 (초당 18회 제한 준수)
    "CHUNK_SIZE": 2           # 수집 시 분할 실행 단위 (일수)
}

class AttrDict(dict):
    """ 딕셔너리 데이터를 dict.key 형태로 접근 가능하게 하는 클래스 """
    def __init__(self, mapping=None, **kwargs):
        if mapping is None: mapping = {}
        if kwargs: mapping.update(kwargs)
        for k, v in mapping.items():
            if isinstance(v, dict): mapping[k] = AttrDict(v)
            elif isinstance(v, list): mapping[k] = [AttrDict(i) if isinstance(i, dict) else i for i in v]
        super().__init__(mapping)

    def __getattr__(self, key):
        # 키 부재 시 빈 AttrDict 반환하여 Crash 방지
        return self.get(key, AttrDict({}))

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

# [유틸리티] 수치 데이터 정제
def to_int(val):
    try:
        if val is None or str(val).strip() == "": return 0
        return int(float(str(val).replace(',', '')))
    except: return 0

def to_float(val, precision=2):
    try:
        if val is None or str(val).strip() == "": return 0.0
        return round(float(str(val).replace(',', '')), precision)
    except: return 0.0

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class TREnv:
    def __init__(self):
        self.my_app = os.getenv('KIS_APP_KEY', '').strip()
        self.my_sec = os.getenv('KIS_APP_SECRET', '').strip()
        self.my_env = os.getenv('KIS_ENV_DV', 'real').strip()
        self.my_url = "https://openapi.koreainvestment.com:9443" if self.my_env == 'real' else "https://openapivts.koreainvestment.com:29443"
        self.access_token = ""

_env = None

def getTREnv():
    global _env
    if _env is None: _env = TREnv()
    return _env

def auth():
    global _env
    if _env is None: _env = getTREnv()
    if not _env.my_app or not _env.my_sec:
        logger.error("에러: KIS_APP_KEY 또는 KIS_APP_SECRET 미설정")
        return None

    url = f"{_env.my_url}/oauth2/tokenP"
    data = {"grant_type": "client_credentials", "appkey": _env.my_app, "appsecret": _env.my_sec}
    try:
        res = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(data))
        if res.status_code == 200:
            _env.access_token = res.json().get('access_token', '').strip()
            logger.info("KIS 인증 성공")
            return res.json()
        return None
    except Exception as e:
        logger.error(f"인증 오류: {e}")
        return None

def get_gcp_creds(scopes=None):
    gcp_json_raw = os.getenv('GCP_CREDENTIALS')
    if not gcp_json_raw: return None
    try:
        creds_info = json.loads(gcp_json_raw)
        return service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
    except: return None

def _url_fetch(url, headers, tr_id, params=None, is_post=False):
    global _env
    if _env is None: _env = getTREnv()
    
    # [정책 반영] 중앙 제어되는 SLEEP_TIME 적용
    time.sleep(POLICY["SLEEP_TIME"])

    if not _env.access_token: auth()
    full_url = f"{_env.my_url}{url}" if url.startswith('/') else url
    
    headers["Content-Type"] = "application/json"
    headers["Authorization"] = f"Bearer {_env.access_token}"
    headers["appkey"] = _env.my_app
    headers["appsecret"] = _env.my_sec
    headers["tr_id"] = tr_id if tr_id else "CTPF1002R"
    headers["custtype"] = "P"

    if params and isinstance(params, dict):
        for k in ["PDNO", "FID_INPUT_ISCD", "FID_INPUT_SVR_ISCD", "ISCD"]:
            if k in params: params[k] = str(params[k]).strip().zfill(6)

    try:
        resp = requests.post(full_url, headers=headers, json=params) if is_post else requests.get(full_url, headers=headers, params=params)
        
        # 토큰 만료 시 재시도
        if resp.status_code != 200 and ("EGW00205" in resp.text or "EGW00201" in resp.text):
            auth()
            headers["Authorization"] = f"Bearer {_env.access_token}"
            resp = requests.post(full_url, headers=headers, json=params) if is_post else requests.get(full_url, headers=headers, params=params)

        resp.isOK = lambda: resp.status_code == 200
        resp.getBody = lambda: AttrDict(resp.json())
        return resp
    except:
        class Mock:
            def isOK(self): return False
            def getBody(self): return AttrDict({})
            @property
            def status_code(self): return 500
        return Mock()

# --- [API 호출 함수들] ---

def get_stock_base_info(stock_code):
    return _url_fetch("/uapi/domestic-stock/v1/quotations/search-stock-info", {}, "CTPF1002R", {"PRDT_TYPE_CD": "300", "PDNO": stock_code}).getBody()

# 기간 조회가 가능하도록 인자를 유연하게 받음 (build_raw_PQ 수정 없이 호환되도록 기본값 처리)
def get_daily_price(stock_code, start_date, end_date=None):
    if end_date is None: end_date = start_date
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": start_date, "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "1"
    }
    return _url_fetch("/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice", {}, "FHKST03010100", params).getBody()

def get_investor_trade(stock_code, target_date):
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": target_date, "FID_INPUT_DATE_2": target_date,
        "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "1", "FID_ETC_CLS_CODE": "1"
    }
    return _url_fetch("/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily", {}, "FHPTJ04160001", params).getBody()

def get_program_trade(stock_code, target_date):
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": target_date, "FID_INPUT_DATE_2": target_date,
        "FID_PERIOD_DIV_CODE": "D", "FID_ORG_ADJ_PRC": "1"
    }
    return _url_fetch("/uapi/domestic-stock/v1/quotations/program-trade-by-stock-daily", {}, "FHPPG04650201", params).getBody()

def get_short_sale_daily(stock_code, start_date, end_date=None):
    if end_date is None: end_date = start_date
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code,
        "FID_PERIOD_DIV_CODE": "D", "FID_INPUT_DATE_1": start_date, "FID_INPUT_DATE_2": end_date
    }
    return _url_fetch("/uapi/domestic-stock/v1/quotations/daily-short-sale", {}, "FHPST04830000", params).getBody()

def get_loan_trans_daily(stock_code, target_date):
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": target_date, "FID_INPUT_DATE_2": target_date, "mrkt_div_cls_code": "J"
    }
    return _url_fetch("/uapi/domestic-stock/v1/quotations/daily-loan-trans", {}, "HHPST074500C0", params).getBody()

def get_credit_balance_daily(stock_code, start_date, end_date=None):
    if end_date is None: end_date = start_date
    params = {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20476",
        "FID_INPUT_ISCD": stock_code, "FID_INPUT_DATE_1": start_date, "FID_INPUT_DATE_2": end_date, "FID_ORG_ADJ_PRC": "1"
    }
    return _url_fetch("/uapi/domestic-stock/v1/quotations/daily-credit-balance", {}, "FHPST04760000", params).getBody()
