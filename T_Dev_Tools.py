# 이 코드는 T_Dev_Tools.py 파일
# -*- coding: utf-8 -*-
import pandas as pd
import numpy as np
import os
import argparse
import ast
import re
from datetime import datetime
import C_Global_Config as cfg  # [핵심] 모든 설정의 기준

# --- [Tool 1] Repo Map Generator (High-Resolution Version) ---
def generate_repo_map():
    """
    [Tool 1] Project Repository Map 생성 (고도화 버전)
    - 함수명, 인자, Docstring, 외부 의존성(cfg, kis_auth 등) 분석
    - 데이터 파일(.parquet)의 행 수 및 날짜 범위 추출
    - 프로젝트 내 TODO/FIXME 작업 현황 수집
    """
    target_file = "repo_map.md"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    lines = [
        "# 🗺️ Project Repository Map (High-Res)",
        f"- **Generated Date**: {now_str}",
        "- **Status**: Active Analysis for AI Collaboration",
        "\n> **AI Instruction**: 이 문서는 시스템의 인터페이스, 데이터 스펙, 의존성 및 잔여 과제를 포함합니다. 답변 시 이 구조를 참조하십시오.",
        "\n---"
    ]

    # 탐색 디렉토리 설정
    search_dirs = [".", cfg.BASE_DIR if hasattr(cfg, 'BASE_DIR') else "./DB", ".github/workflows"]
    unique_dirs = []
    for d in search_dirs:
        if os.path.exists(d) and d not in unique_dirs:
            unique_dirs.append(d)

    all_todos = []

    for d in unique_dirs:
        lines.append(f"\n## 📂 Directory: {d}")
        try:
            items = sorted(os.listdir(d))
        except Exception:
            continue
            
        for item in items:
            path = os.path.join(d, item)
            if os.path.isdir(path):
                continue
            
            # 1. 파이썬 파일 분석 (.py)
            if item.endswith(".py"):
                functions_info = []
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                        # TODO/FIXME 추출
                        todos = re.findall(r'#\s*(TODO|FIXME):?\s*(.*)', content, re.IGNORECASE)
                        for tag, msg in todos:
                            all_todos.append(f"- [`{item}`] **{tag}**: {msg.strip()}")

                        # AST 분석
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef):
                                if not node.name.startswith("__"):
                                    # 인자 추출
                                    args = [a.arg for a in node.args.args]
                                    arg_str = ", ".join(args)
                                    
                                    # Docstring 요약 (첫 줄)
                                    doc = ast.get_docstring(node)
                                    doc_summary = f" - *{doc.splitlines()[0]}*" if doc else ""
                                    
                                    # 의존성 분석 (함수 내 cfg, kis_auth 등 참조 확인)
                                    deps = []
                                    func_source = ast.get_source_segment(content, node)
                                    if func_source:
                                        if 'cfg.' in func_source: deps.append("cfg")
                                        if 'kis_auth' in func_source: deps.append("kis_auth")
                                        if 'pd.' in func_source: deps.append("pandas")
                                    dep_str = f" `[{', '.join(deps)}]`" if deps else ""
                                    
                                    functions_info.append(f"  - `{node.name}({arg_str})`{dep_str}{doc_summary}")
                except Exception:
                    pass
                
                lines.append(f"### 📄 `{item}`")
                if functions_info:
                    lines.extend(functions_info)
                else:
                    lines.append("  - *No public functions or parsing failed*")

            # 2. 데이터 파일 분석 (.parquet)
            elif item.endswith(".parquet"):
                try:
                    df = pd.read_parquet(path)
                    row_count = len(df)
                    cols = ", ".join([f"`{c}`" for c in df.columns])
                    
                    # 날짜 범위 추출 (날짜/일자 칼럼 존재 시)
                    date_info = ""
                    date_cols = [c for c in df.columns if '날짜' in c or '일자' in c]
                    if date_cols and not df.empty:
                        try:
                            min_date = pd.to_datetime(df[date_cols[0]]).min().strftime('%Y-%m-%d')
                            max_date = pd.to_datetime(df[date_cols[0]]).max().strftime('%Y-%m-%d')
                            date_info = f" | 📅 `{min_date} ~ {max_date}`"
                        except:
                            pass
                    
                    lines.append(f"### 📊 `{item}`")
                    lines.append(f"  - **Stats**: `{row_count:,} rows`{date_info}")
                    lines.append(f"  - **Columns**: {cols}")
                except Exception:
                    lines.append(f"### 📊 `{item}` (Error reading file)")

            # 3. 워크플로우 분석 (.yml)
            elif item.endswith((".yml", ".yaml")):
                lines.append(f"### ⚙️ `{item}` (Workflow)")

    # 4. 잔여 과제(TODO) 섹션 추가
    if all_todos:
        lines.append("\n---")
        lines.append("## 📝 Pending Tasks (TODO/FIXME)")
        lines.extend(all_todos)

    # 파일 저장
    with open(target_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"✅ {target_file} 가 고도화된 버전으로 갱신되었습니다.")

# --- 메인 실행부 (현재는 Tool 1만 존재) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stock Project Dev Tools")
    parser.add_argument('--mode', type=str, choices=['map'], default='map')
    args = parser.parse_args()

    if args.mode == "map":
        generate_repo_map()
