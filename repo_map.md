# 🗺️ Project Repository Map (Security-First)
- **Generated Date**: 2026-05-08 10:26:07
- **Status**: Strict Data Integrity Monitoring

---

## 📂 Directory: Root
### 📄 `build_raw_PQ.py`
  - `get_combined_targets()` - *저장 대상 종목 확정: KOSPI200/KOSDAQ150 + 구글시트 'goingup'*
  - `fetch_daily_price(ticker, target_date, token, app_key, app_secret)` - *TR FHKST03010100 (국내주식 기간별 시세) 호출*
  - `main()`
### 📄 `build_raw_master.py`
  - `download_master(market_type)`
  - `parse_master(file_name, market_code)`
  - `update_gsheet(df)`
  - `build_raw_db()`
### 📄 `kis_auth.py`
  - `getEnv()` - *서버 주소 정보 반환*
  - `getTREnv()` - *현재 설정된 환경 객체 반환*
  - `auth()` - *KIS 인증 실행: 매번 새로 발급 (1번 원칙: 옵션 A)*
  - `get_gcp_creds(scopes)` - *GCP 크리덴셜 객체 생성 (3번 원칙)*
  - `set_order_hash(headers, data)` - *주문 해시값 설정 (기존 기능 유지)*

## 📂 Directory: DB
### 📊 `raw_mst_krx_full.parquet`
  - **Stats**: `3,821 rows` | 🏷️ `Master Data`
  - **Columns**: `단축코드`, `표준코드`, `종목명`, `그룹코드`, `시가총액규모`, `지수업종대분류`, `지수업종중분류`, `지수업종소분류`, `제조업`, `저유동성`, `지배구조지수종목`, `KOSPI200섹터업종`, `KOSPI100`, `KOSPI50`, `KRX`, `ETP`, `ELW발행`, `KRX100`, `KRX자동차`, `KRX반도체`, `KRX바이오`, `KRX은행`, `SPAC`, `KRX에너지화학`, `KRX철강`, `단기과열`, `KRX미디어통신`, `KRX건설`, `Non1`, `KRX증권`, `KRX선박`, `KRX섹터_보험`, `KRX섹터_운송`, `SRI`, `기준가`, `매매수량단위`, `시간외수량단위`, `거래정지`, `정리매매`, `관리종목`, `시장경고`, `경고예고`, `불성실공시`, `우회상장`, `락구분`, `액면변경`, `증자구분`, `증거금비율`, `신용가능`, `신용기간`, `전일거래량`, `액면가`, `상장일자`, `상장주수`, `자본금`, `결산월`, `공모가`, `우선주`, `공매도과열`, `이상급등`, `KRX300`, `KOSPI`, `매출액`, `영업이익`, `경상이익`, `당기순이익`, `ROE`, `기준년월`, `시가총액`, `그룹사코드`, `회사신용한도초과`, `담보대출가능`, `대주가능`, `시장구분`, `중소기업여부`, `벤처기업여부`, `KRX종목여부`, `ETP구분`, `KRX100여부`, `투자주의환기`, `KRX보험`, `KRX운송`, `KOSDAQ150`, `KOSDAQ`

## 📂 Directory: workflows
### ⚙️ `raw_master.yml` (Workflow)
### ⚙️ `repo_map_update.yml` (Workflow)