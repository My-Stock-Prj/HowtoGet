# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import argparse
import ast
import re
from datetime import datetime

# --- [설정 로드 섹션] 파일 대신 환경 변수나 기본값 사용 ---
# 보안을 위해 파일 대신 시스템 환경 변수에서 경로를 읽어옵니다.
BASE_DIR = os.environ.get('DATA_BASE_DIR', './DB')

# --- [Tool 1] Repo Map Generator (High-Resolution Version) ---
def generate_repo_map():
    """
    [Tool 1] Project Repository Map 생성
    - 파이썬 파일 분석: 함수 인터페이스, Docstring, TODO 추출
    - 데이터 파일 분석: Parquet 통계 및 날짜 범위 추출
    """
    target_file = "repo_map.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lines = [
        "# 🗺️ Project Repository Map (Security-First)",
        f"- **Generated Date**: {now_str}",
        "- **Status**: Security Managed (Environment Variables Used)",
        "\n> **AI Instruction**: 이 프로젝트는 보안을 위해 민감한 설정을 환경 변수로 관리합니다.",
        "\n---"
    ]

    # 탐색 디렉토리 설정
    search_dirs = [".", BASE_DIR, ".github/workflows"]
    unique_dirs = []
    for d in search_dirs:
        if os.path.exists(d) and d not in unique_dirs:
            unique_dirs.append(d)

    all_todos = []

    for d in unique_dirs:
        # 경로 표시 시 보안을 위해 절대경로 노출 최소화
        display_name = "Root" if d == "." else os.path.basename(d)
        lines.append(f"\n## 📂 Directory: {display_name}")
        
        try:
            items = sorted(os.listdir(d))
        except Exception:
            continue
            
        for item in items:
            path = os.path.join(d, item)
            if os.path.isdir(path): continue
            
            # 1. 파이썬 파일 분석 (.py)
            if item.endswith(".py") and item != "T_Dev_Tools.py":
                functions_info = []
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # TODO 추출
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
                                    
                                    # 보안 관련 키워드 사용 여부 체크 (의존성 대신 보안 모니터링)
                                    sec_tags = []
                                    if 'os.environ' in ast.get_source_segment(content, node): sec_tags.append("EnvRef")
                                    tag_str = f" `[{', '.join(sec_tags)}]`" if sec_tags else ""
                                    
                                    functions_info.append(f"  - `{node.name}({arg_str})`{tag_str}{doc_summary}")
                except Exception: pass
                
                lines.append(f"### 📄 `{item}`")
                if functions_info: lines.extend(functions_info)
                else: lines.append("  - *No public functions*")

            # 2. 데이터 파일 분석 (.parquet)
            elif item.endswith(".parquet"):
                try:
                    # 데이터 로드 시 보안 유의 (샘플만 확인)
                    df = pd.read_parquet(path)
                    row_count = len(df)
                    cols = ", ".join([f"`{c}`" for c in df.columns])
                    
                    date_info = ""
                    date_cols = [c for c in df.columns if any(x in c for x in ['날짜', '일자'])]
                    if date_cols and not df.empty:
                        min_date = pd.to_datetime(df[date_cols[0]]).min().strftime('%Y-%m-%d')
                        max_date = pd.to_datetime(df[date_cols[0]]).max().strftime('%Y-%m-%d')
                        date_info = f" | 📅 `{min_date} ~ {max_date}`"
                    
                    lines.append(f"### 📊 `{item}`")
                    lines.append(f"  - **Stats**: `{row_count:,} rows`{date_info}")
                    lines.append(f"  - **Columns**: {cols}")
                except Exception:
                    lines.append(f"### 📊 `{item}` (Empty or Locked)")

    # 3. 작업 현황 추가
    if all_todos:
        lines.append("\n---\n## 📝 Pending Tasks")
        lines.extend(all_todos)

    with open(target_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"✅ {target_file} 가 보안 가이드를 준수하며 생성되었습니다.")

if __name__ == "__main__":
    generate_repo_map()
