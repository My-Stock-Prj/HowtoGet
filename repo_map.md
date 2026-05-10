# 🗺️ Project Repository Map (Security-First)
- **Generated Date**: 2026-05-10 07:54:14
- **Status**: Strict Data Integrity Monitoring

---

## 📂 Directory: Root
### 📄 `build_raw_ETF.py`
   - `collect_etf_data()`
### 📄 `build_raw_PQ.py`
   - `get_combined_targets()`
   - `fetch_daily_price(ticker, target_date, mst_info)`
   - `main()`
### 📄 `build_raw_master.py`
   - `get_base_mst()`
   - `augment_master_via_api(df)`
   - `save_and_upload(df)`
   - `main()`
   - `download_and_parse(m_type, m_code)`
### 📄 `check_PQ.py`
   - `get_combined_targets()`
   - `fetch_daily_price(ticker, target_date, mst_info)`
   - `main()`
### 📄 `check_PY.py`
   - `check_kosdaq_mst_reverse()`
### 📄 `check_parquet.py`
   - `sync_to_dpq(filename)`
### 🛡️ [CORE AUTH] `kis_auth.py`
   - `to_int(val)`
   - `to_float(val, precision)`
   - `getEnv()`
   - `getTREnv()`
   - `auth()`
   - `get_gcp_creds(scopes)`
   - `_url_fetch(url, headers, tr_id, params, is_post)`
   - `get_stock_base_info(stock_code)` - *국내주식 종목정보 상세조회 (CTPF1002R)*
   - `get_daily_price(stock_code, start_date, end_date)` - *국내주식 일별 차트 시세 조회 (FHKST03010100)*
   - `get_investor_trade(stock_code, target_date)` - *국내주식 종목별 투자자 매매동향(일별) 조회 (FHPTJ04160001)*
   - `get_program_trade(stock_code, target_date)` - *국내주식 종목별 프로그램매매추이(일별) 조회 (FHPPG04650201)*
   - `get_short_sale_daily(stock_code, target_date)` - *국내주식 공매도 일별추이 (FHPST04830000)*
   - `get_loan_trans_daily(stock_code, target_date)` - *종목별 일별 대차거래추이 (HHPST074500C0)*
   - `get_credit_balance_daily(stock_code, target_date)` - *국내주식 신용잔고 일별추이 (FHPST04760000)*
   - `isOK(self)`
   - `printError(self)`
   - `json(self)`
   - `getBody(self)`
   - `status_code(self)`

## 📂 Directory: DB
### 📊 `ADB_main.parquet`
  - ❌ **DATA INTEGRITY ERROR**: `Could not open Parquet input source '<Buffer>': Parquet file size is 1 bytes, smaller than the minimum file footer (8 bytes)`
### 📊 `raw_daily_PQ.parquet`
  - **Stats**: `353 rows` | ✅ `Code Refined` | 📅 `2026-05-04 ~ 2026-05-04`
  - **Columns**: `날짜`, `종목코드`, `시가`, `고가`, `저가`, `종가`, `거래량`, `거래대금`, `재평가사유`, `종목명`, `구분(출처)`, `회전율`, `상장주수`, `락구분`, `외국인순매수수량`, `외국인순매수대금`, `기관계순매수수량`, `기관계순매수대금`, `기금순매수수량`, `기금순매수대금`, `개인순매수수량`, `개인순매수대금`, `증권순매수수량`, `투자신탁순매수수량`, `사모펀드순매수수량`, `은행순매수수량`, `보험순매수수량`, `종금순매수수량`, `프로그램순매수수량`, `프로그램순매수대금`, `공매도체결수량`, `누적공매도체결수량`, `공매도거래량비중`, `당일대차잔고주수`, `전체융자잔고주수`, `전체융자잔고비율`
### 📊 `raw_mst_krx_full.parquet`
  - **Stats**: `4,346 rows` | ✅ `Code Refined` | 🏷️ `Master Data`
  - **Columns**: `단축코드`, `표준코드`, `종목명`, `시장구분`, `KOSPI200`, `KOSDAQ150`, `섹터(대분류)`, `업종(중분류)`, `거래정지여부`, `관리종목여부`, `상장주수`, `주식종류코드`

## 📂 Directory: workflows
### ⚙️ `check.yml` (Workflow)
### ⚙️ `raw_ETF_run.yml` (Workflow)
### ⚙️ `raw_PQ_run.yml` (Workflow)
### ⚙️ `raw_master.yml` (Workflow)
### ⚙️ `repo_map_update.yml` (Workflow)