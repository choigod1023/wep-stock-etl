#!/usr/bin/env python3
"""WeP-Stock 원천 데이터셋(SSIS 대용량첨부 zip) → Neon 적재.
GitHub Actions 원격 실행. 로컬 PC 미사용.

동작:
  1) DATA_URLS(공백/줄바꿈 구분)의 zip 들을 curl 로 다운로드
  2) 각 zip 해제 → 내부 데이터파일(csv/tsv/txt/xlsx) 수집
  3) 헤더가 같은 파일끼리 하나의 테이블로 통합 적재 (전 컬럼 TEXT = 원문 보존)
     - 여러 서로 다른 스키마가 있으면 stock_raw, stock_raw_2 ... 로 분리
환경변수: DATABASE_URL, DATA_URLS
"""
import os, io, glob, sys, zipfile, subprocess, hashlib
import pandas as pd
import psycopg2

DB = os.environ["DATABASE_URL"]
URLS = [u.strip() for u in os.environ["DATA_URLS"].split() if u.strip()]
BASE_TABLE = os.environ.get("TABLE_NAME", "stock_raw")


def log(m): print(f"[etl] {m}", flush=True)


def fetch_and_extract():
    os.makedirs("data", exist_ok=True)
    for i, url in enumerate(URLS):
        z = f"data/part_{i}.zip"
        log(f"[{i+1}/{len(URLS)}] 다운로드")
        subprocess.run(["curl", "-fsSL", "--retry", "3", "-o", z, url], check=True)
        try:
            with zipfile.ZipFile(z) as zf:
                zf.extractall(f"data/ext_{i}")
        except zipfile.BadZipFile:
            log(f"  ⚠ zip 아님(part_{i}) — 헤더 확인 필요, 건너뜀")
    # 중첩 zip 한 겹 더
    for nz in glob.glob("data/ext_*/**/*.zip", recursive=True):
        try:
            with zipfile.ZipFile(nz) as zf:
                zf.extractall(os.path.dirname(nz))
        except zipfile.BadZipFile:
            pass


def read_any(path) -> pd.DataFrame:
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path, dtype=str)
    last = None
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8", "latin-1"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc, sep=None,
                               engine="python", on_bad_lines="warn")
        except Exception as e:
            last = e
    raise last


def sig(cols):
    return hashlib.md5("|".join(cols).encode()).hexdigest()[:8]


def main():
    fetch_and_extract()
    files = sorted(f for f in glob.glob("data/ext_*/**/*", recursive=True)
                   if f.lower().endswith((".csv", ".tsv", ".txt", ".xlsx", ".xls")))
    if not files:
        log("데이터 파일 없음 — 다운로드/해제 실패. 종료."); sys.exit(1)
    log(f"데이터 파일 {len(files)}개 발견")

    conn = psycopg2.connect(DB); conn.autocommit = False; cur = conn.cursor()
    schema_tables = {}   # header-signature → table name
    counts = {}
    try:
        for f in files:
            df = read_any(f)
            df.columns = [str(c).strip() for c in df.columns]
            s = sig(list(df.columns))
            if s not in schema_tables:
                tbl = BASE_TABLE if not schema_tables else f"{BASE_TABLE}_{len(schema_tables)+1}"
                schema_tables[s] = tbl
                coldef = ", ".join(f'"{c}" text' for c in df.columns)
                cur.execute(f'DROP TABLE IF EXISTS "{tbl}"')
                cur.execute(f'CREATE TABLE "{tbl}" ({coldef})')
                counts[tbl] = 0
                log(f"  테이블 생성 \"{tbl}\" ({len(df.columns)} 컬럼): {list(df.columns)[:6]}...")
            tbl = schema_tables[s]
            buf = io.StringIO()
            df.to_csv(buf, index=False, header=False)
            buf.seek(0)
            collist = ", ".join(f'"{c}"' for c in df.columns)
            cur.copy_expert(f'COPY "{tbl}" ({collist}) FROM STDIN WITH (FORMAT csv)', buf)
            counts[tbl] += len(df)
            conn.commit()
            log(f"  {os.path.basename(f)} → \"{tbl}\" (+{len(df):,})")
    finally:
        cur.close(); conn.close()
    log("=== 적재 요약 ===")
    for t, n in counts.items():
        log(f"  {t}: {n:,} 행")


if __name__ == "__main__":
    main()
