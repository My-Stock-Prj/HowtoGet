# 🗺️ Project Repository Map (Security-First)
- **Generated Date**: 2026-05-08 14:55:33
- **Status**: Strict Data Integrity Monitoring

---

## 📂 Directory: Root
### 📄 `build_raw_PQ.py`
  - `get_combined_targets()` - *저장 대상 종목 확정 (기본 로직 유지)*
  - `fetch_daily_price(ticker, target_date)` - *지식 베이스의 표준 함수를 활용하여 데이터를 수집합니다.*
  - `main()`
### 📄 `build_raw_master.py`
  - `download_master(market_type)`
  - `parse_master(file_name, market_code)`
  - `update_gsheet(df)`
  - `build_raw_db()`
### 📄 `kis_auth.py`
  - `getEnv()` - *auth_functions.py와의 호환성을 위한 서버 주소 반환*
  - `getTREnv()`
  - `auth()` - *[수정 핵심] 인증 성공 시 반드시 결과를 리턴합니다.*
  - `get_gcp_creds(scopes)`

## 📂 Directory: DB
### 📊 `raw_mst_krx_full.parquet`
  - **Stats**: `3,821 rows` | 🏷️ `Master Data`
  - **Columns**: `단축코드`, `표준코드`, `종목명`, `그룹코드`, `시가총액규모`, `지수업종대분류`, `지수업종중분류`, `지수업종소분류`, `제조업`, `저유동성`, `지배구조지수종목`, `KOSPI200섹터업종`, `KOSPI100`, `KOSPI50`, `KRX`, `ETP`, `ELW발행`, `KRX100`, `KRX자동차`, `KRX반도체`, `KRX바이오`, `KRX은행`, `SPAC`, `KRX에너지화학`, `KRX철강`, `단기과열`, `KRX미디어통신`, `KRX건설`, `Non1`, `KRX증권`, `KRX선박`, `KRX섹터_보험`, `KRX섹터_운송`, `SRI`, `기준가`, `매매수량단위`, `시간외수량단위`, `거래정지`, `정리매매`, `관리종목`, `시장경고`, `경고예고`, `불성실공시`, `우회상장`, `락구분`, `액면변경`, `증자구분`, `증거금비율`, `신용가능`, `신용기간`, `전일거래량`, `액면가`, `상장일자`, `상장주수`, `자본금`, `결산월`, `공모가`, `우선주`, `공매도과열`, `이상급등`, `KRX300`, `KOSPI`, `매출액`, `영업이익`, `경상이익`, `당기순이익`, `ROE`, `기준년월`, `시가총액`, `그룹사코드`, `회사신용한도초과`, `담보대출가능`, `대주가능`, `시장구분`, `중소기업여부`, `벤처기업여부`, `KRX종목여부`, `ETP구분`, `KRX100여부`, `투자주의환기`, `KRX보험`, `KRX운송`, `KOSDAQ150`, `KOSDAQ`

## 📂 Directory: workflows
### ⚙️ `raw_PQ_run.yml` (Workflow)
### ⚙️ `raw_master.yml` (Workflow)
### ⚙️ `repo_map_update.yml` (Workflow)