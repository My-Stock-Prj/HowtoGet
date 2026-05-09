# 이 코드는 T_Dev_Tools.py 
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import argparse
import ast
import re
from datetime import datetime

# --- [설정 로드] ---
BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')

def generate_repo_map():
    """
    [Tool 1] Project Repository Map 생성 (디버깅 및 완결성 검증 강화)
    """
    target_file = "repo_map.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lines = [
        "# 🗺️ Project Repository Map (Security-First)",
        f"- **Generated Date**: {now_str}",
        "- **Status**: Strict Data Integrity Monitoring",
        "\n---"
    ]

    search_dirs = [".", BASE_DIR, ".github/workflows"]
    unique_dirs = []
    for d in search_dirs:
        if os.path.exists(d) and d not in unique_dirs:
            unique_dirs.append(d)

    all_todos = []

    for d in unique_dirs:
        display_name = "Root" if d == "." else os.path.basename(d)
        lines.append(f"\n## 📂 Directory: {display_name}")
        
        try:
            items = sorted(os.listdir(d))
        except Exception as e:
            lines.append(f"  - ⚠️ Directory Read Error: {str(e)}")
            continue
            
        for item in items:
            path = os.path.join(d, item)
            if os.path.isdir(path): continue
            
            # 1. 파이썬 파일 분석
            if item.endswith(".py") and item != "T_Dev_Tools.py":
                functions_info = []
                # [추가] kis_auth.py는 핵심 보안 시스템으로 별도 표시
                is_core = "🛡️ [CORE AUTH]" if item == "kis_auth.py" else "📄"
                
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        todos = re.findall(r'#\s*(TODO|FIXME):?\s*(.*)', content, re.IGNORECASE)
                        for tag, msg in todos:
                            all_todos.append(f"- [`{item}`] **{tag}**: {msg.strip()}")

                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                if not node.name.startswith("__"):
                                    args = [a.arg for a in node.args.args]
                                    arg_str = ", ".join(args)
                                    doc = ast.get_docstring(node)
                                    doc_summary = f" - *{doc.splitlines()[0]}*" if doc else ""
                                    functions_info.append(f"   - `{node.name}({arg_str})`{doc_summary}")
                except Exception: pass
                
                lines.append(f"### {is_core} `{item}`")
                lines.extend(functions_info if functions_info else ["   - *No public functions*"])

            # 2. 데이터 파일 분석 (데이터 완결성 검증 로직 포함)
            elif item.endswith(".parquet"):
                lines.append(f"### 📊 `{item}`")
                try:
                    file_size = os.path.getsize(path)
                    if file_size == 0:
                        lines.append(f"  - **Note**: `Empty File (0 KB)` - *폴더 유지용 또는 초기화 전 상태*")
                        continue

                    df = pd.read_parquet(path)
                    if df.empty:
                        lines.append(f"  - **Note**: `No Data` - *헤더는 있으나 행이 없음*")
                        lines.append(f"  - **Columns**: {', '.join([f'`{c}`' for c in df.columns])}")
                    else:
                        row_count = len(df)
                        cols = ", ".join([f"`{c}`" for c in df.columns])
                        integrity_info = ""
                        
                        # [검증 강화] kis_auth의 정제 정책(6자리 코드) 준수 여부 확인
                        code_cols = [c for c in df.columns if any(x in c for x in ['코드', 'PDNO'])]
                        if code_cols:
                            sample_codes = df[code_cols[0]].astype(str).tolist()[:50]
                            if any(len(c) != 6 for c in sample_codes if c.isdigit()):
                                integrity_info += " | ⚠️ `Code Length Issue`"
                            else:
                                integrity_info += " | ✅ `Code Refined`"

                        # [유지] 날짜 분석 로직
                        is_master_file = "raw_mst" in item.lower()
                        date_cols = [c for c in df.columns if any(x in c for x in ['날짜', '일자'])]
                        
                        if date_cols and not is_master_file:
                            target_col = date_cols[0]
                            try:
                                valid_dates = pd.to_datetime(df[target_col], errors='raise')
                                min_dt = valid_dates.min().strftime('%Y-%m-%d')
                                max_dt = valid_dates.max().strftime('%Y-%m-%d')
                                integrity_info += f" | 📅 `{min_dt} ~ {max_dt}`"
                            except Exception as date_err:
                                raise ValueError(f"Invalid date format in '{target_col}': {str(date_err)}")
                        elif is_master_file:
                            integrity_info += " | 🏷️ `Master Data`"
                        
                        lines.append(f"  - **Stats**: `{row_count:,} rows`{integrity_info}")
                        lines.append(f"  - **Columns**: {cols}")

                except FileNotFoundError:
                    lines.append(f"  - ❌ **Error**: `File Not Found`")
                except PermissionError:
                    lines.append(f"  - ❌ **Error**: `Permission Denied` (Locked by another process)")
                except Exception as e:
                    err_msg = str(e).split('\n')[0]
                    lines.append(f"  - ❌ **DATA INTEGRITY ERROR**: `{err_msg}`")

            # 3. 워크플로우 분석
            elif item.endswith((".yml", ".yaml")):
                lines.append(f"### ⚙️ `{item}` (Workflow)")

    if all_todos:
        lines.append("\n---\n## 📝 Pending Tasks")
        lines.extend(all_todos)

    with open(target_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ {target_file} 가 갱신되었습니다. (보안 코어 식별 및 데이터 정제 검증 포함)")

if __name__ == "__main__":
    generate_repo_map()
