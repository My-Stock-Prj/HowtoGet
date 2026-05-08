# 🗺️ Project Repository Map (Security-First)
- **Generated Date**: 2026-05-08 09:46:33
- **Status**: Strict Data Integrity Monitoring

---

## 📂 Directory: Root
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
  - ❌ **DATA INTEGRITY ERROR**: `Invalid date format in '상장일자': time data "0" doesn't match format "%Y%m%d", at position 2017. You might want to try:`

## 📂 Directory: workflows
### ⚙️ `raw_master.yml` (Workflow)
### ⚙️ `repo_map_update.yml` (Workflow)