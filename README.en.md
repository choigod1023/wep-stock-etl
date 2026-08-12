# wep-stock-etl

[한국어](README.md) · [日本語](README.ja.md) · **English**

The **raw-data ingestion ETL** for WeP-Stock, a medical-supply inventory forecasting project for public health centers.
It downloads the source zips (distributed as SSIS large attachments), unpacks them, consolidates them by schema, and loads them verbatim into **Neon (PostgreSQL)**.

## About

WeP-Stock's source datasets ship as zips whose inner files have inconsistent schemas.
This ETL fetches those zips and loads them **grouping files with identical headers into a single table**.
The guiding principle is to make every column `TEXT` so the source text is preserved losslessly (type conversion belongs to downstream pipelines).

It is designed to **run remotely on GitHub Actions rather than a local PC**, so the large downloads and loads happen on a CI runner.

## ✨ Features

- **Remote download**: fetches the zips listed in `DATA_URLS` (whitespace/newline separated) with `curl` (3 retries).
- **Extraction**: unzips, plus **one more level of nested zips**. Non-zip inputs are treated as raw files.
- **Many input formats**: supports `.csv/.tsv/.txt/.xlsx/.xls/.parquet`. CSVs get delimiter sniffing (`sep=None`) and encoding fallback (`utf-8-sig → cp949 → euc-kr → utf-8 → latin-1`).
- **Automatic schema separation**: schemas are distinguished by an MD5 signature of the file header — identical schemas go into one table (`stock_raw`), and any differing schemas go to `stock_raw_2`, `stock_raw_3`, …
- **Verbatim loading**: creates tables with all-`TEXT` columns and bulk-loads via `COPY ... FROM STDIN` (CSV).
- **Completion notice**: if an app password is configured, sends a load summary by Gmail (SMTP SSL); a failure here does not kill the job.

## 🛠 Tech stack

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Neon%20Postgres-4169E1?logo=postgresql&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)

- **Python**: pandas, psycopg2(-binary), openpyxl (Excel), pyarrow (Parquet)
- **DB**: Neon (PostgreSQL) — loaded via `COPY`
- **Runtime**: GitHub Actions (manual `workflow_dispatch` trigger)

## 🏗 How it works

```
DATA_URLS (zips) ──curl──▶ data/part_i.zip
        │
        ├─ unzip ──▶ data/ext_i/...  (one extra level of nested zips)
        │
        ├─ read_any(): load csv/tsv/txt/xlsx/parquet (encoding & delimiter fallback)
        │
        ├─ group schemas by MD5 signature of the header
        │       same signature → same table
        │       different signature → stock_raw_2, stock_raw_3 ...
        │
        └─ CREATE TABLE (all columns TEXT) ─▶ COPY FROM STDIN ─▶ Neon
                                                 │
                                                 └─ optional Gmail notification on completion
```

## 🚀 Getting started

### Prerequisites
- Python 3.12 (recommended)
- A target Neon/PostgreSQL instance and its connection string
- Download URLs for the source zips

### Install
```bash
pip install -r requirements.txt
```

### Environment variables

The variables the code actually reads:

| Variable | Required | Description |
|------|:---:|------|
| `DATABASE_URL` | ✅ | Neon/PostgreSQL connection string |
| `DATA_URLS` | ✅ | List of zip URLs to download (whitespace/newline separated) |
| `TABLE_NAME` | ⭕ | Base table name (defaults to `stock_raw`) |
| `GMAIL_ADDRESS` | ⭕ | Gmail address that sends the completion notice |
| `GMAIL_APP_PASSWORD` | ⭕ | That account's **app password** (for SMTP SSL login) |
| `NOTIFY_TO` | ⭕ | Notification recipient (defaults to `GMAIL_ADDRESS`) |

> Without `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD`, email notification is skipped automatically.

### Running

**Locally:**
```bash
export DATABASE_URL="postgresql://..."
export DATA_URLS="https://.../part1.zip https://.../part2.zip"
python etl.py
```

**On GitHub Actions (recommended):**
- Add `DATABASE_URL` and `DATA_URLS` (plus optionally `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `NOTIFY_TO`) to the repository secrets.
- Actions tab → **"Load WeP-Stock → Neon"** → **Run workflow** (`.github/workflows/load.yml`).

## 📁 Project structure

```
etl.py                       # download → extract → separate schemas → load into Neon → notify
requirements.txt             # pandas, psycopg2-binary, openpyxl, pyarrow
.github/workflows/load.yml   # manual workflow_dispatch workflow
```

## Notes

- This repository covers only the **raw-ingestion stage** of the WeP-Stock forecasting pipeline. The loaded `stock_raw*` tables feed downstream pipelines.
- On each run the target table is dropped (`DROP TABLE IF EXISTS`) and recreated — an idempotent full load.

---

## 👤 Contribution & development environment

| Item | Detail |
|---|---|
| **Contribution share** | **100%** (solo development) |
| **Commits** | 4 / 4 (mine / all human commits) |
| **Contributors** | 1 |
| **AI coding tool** | Claude Code |

<sub>Contribution share is counted by commit author email; bot and automation commits are excluded.</sub>
