# wep-stock-etl

**한국어** · [日本語](README.ja.md) · [English](README.en.md)

보건소 의료물품 재고예측(WeP-Stock) 프로젝트의 **원천 데이터 적재 ETL**.
SSIS 대용량첨부 형태의 zip 원본을 내려받아 압축을 풀고, 스키마별로 통합해 **Neon(PostgreSQL)** 에 원문 그대로 적재합니다.

## 소개

WeP-Stock의 원천 데이터셋은 zip으로 배포되며 내부 파일들의 스키마가 제각각입니다.
이 ETL은 그 zip들을 받아 **헤더가 같은 파일끼리 하나의 테이블로 묶어** 적재합니다.
모든 컬럼을 `TEXT`로 만들어 원문을 손실 없이 보존하는 것이 핵심 원칙입니다(형변환은 후속 파이프라인의 몫).

**로컬 PC를 쓰지 않고 GitHub Actions에서 원격 실행**하도록 설계되어 있어, 대용량 다운로드/적재를 CI 러너에서 처리합니다.

## ✨ 주요 기능

- **원격 다운로드**: `DATA_URLS`(공백/줄바꿈 구분)에 나열된 zip들을 `curl`(재시도 3회)로 다운로드.
- **압축 해제**: zip 해제 + **중첩 zip 한 겹 더** 해제. zip이 아니면 원문 그대로 취급.
- **다양한 포맷 로드**: `.csv/.tsv/.txt/.xlsx/.xls/.parquet` 지원. CSV는 구분자 자동 추론(`sep=None`)과 인코딩 폴백(`utf-8-sig → cp949 → euc-kr → utf-8 → latin-1`).
- **스키마 자동 분리**: 파일 헤더의 MD5 서명으로 스키마를 구분해, 같은 스키마는 한 테이블(`stock_raw`)로, 다른 스키마가 있으면 `stock_raw_2`, `stock_raw_3` … 로 분리 적재.
- **원문 보존 적재**: 전 컬럼 `TEXT`로 테이블 생성 후 `COPY ... FROM STDIN`(CSV)으로 대량 적재.
- **완료 알림**: 앱 비밀번호가 설정된 경우 Gmail(SMTP SSL)로 적재 요약 메일 발송(실패해도 잡은 죽지 않음).

## 🛠 기술 스택

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Neon%20Postgres-4169E1?logo=postgresql&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)

- **Python**: pandas, psycopg2(-binary), openpyxl(Excel), pyarrow(Parquet)
- **DB**: Neon(PostgreSQL) — `COPY`로 적재
- **실행 환경**: GitHub Actions (`workflow_dispatch` 수동 트리거)

## 🏗 동작 방식

```
DATA_URLS(zip들) ──curl──▶ data/part_i.zip
        │
        ├─ unzip ──▶ data/ext_i/...  (중첩 zip 한 겹 더 해제)
        │
        ├─ read_any(): csv/tsv/txt/xlsx/parquet 로드 (인코딩·구분자 폴백)
        │
        ├─ 헤더 MD5 서명으로 스키마 그룹핑
        │       같은 서명 → 같은 테이블
        │       다른 서명 → stock_raw_2, stock_raw_3 ...
        │
        └─ CREATE TABLE (전 컬럼 TEXT) ─▶ COPY FROM STDIN ─▶ Neon
                                                 │
                                                 └─ 완료 시 Gmail 알림(선택)
```

## 🚀 시작하기

### 사전 요구사항
- Python 3.12 (권장)
- 적재 대상 Neon/PostgreSQL 인스턴스와 접속 문자열
- 원천 데이터 zip의 다운로드 URL

### 설치
```bash
pip install -r requirements.txt
```

### 환경변수

코드에서 실제로 참조하는 환경변수는 다음과 같습니다.

| 변수 | 필수 | 설명 |
|------|:---:|------|
| `DATABASE_URL` | ✅ | Neon/PostgreSQL 접속 문자열 |
| `DATA_URLS` | ✅ | 다운로드할 zip URL 목록 (공백/줄바꿈으로 구분) |
| `TABLE_NAME` | ⭕ | 기본 테이블명 (미설정 시 `stock_raw`) |
| `GMAIL_ADDRESS` | ⭕ | 완료 알림 발신 Gmail 주소 |
| `GMAIL_APP_PASSWORD` | ⭕ | 위 계정의 **앱 비밀번호**(SMTP SSL 로그인용) |
| `NOTIFY_TO` | ⭕ | 알림 수신 주소 (미설정 시 `GMAIL_ADDRESS`로 발송) |

> `GMAIL_ADDRESS`/`GMAIL_APP_PASSWORD` 가 없으면 이메일 알림은 자동으로 건너뜁니다.

### 실행

**로컬 실행:**
```bash
export DATABASE_URL="postgresql://..."
export DATA_URLS="https://.../part1.zip https://.../part2.zip"
python etl.py
```

**GitHub Actions 실행(권장):**
- 리포지토리 Secrets에 `DATABASE_URL`, `DATA_URLS`(+ 선택적으로 `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `NOTIFY_TO`)를 등록.
- Actions 탭 → **"Load WeP-Stock → Neon"** → **Run workflow** 로 수동 실행 (`.github/workflows/load.yml`).

## 📁 프로젝트 구조

```
etl.py                       # 다운로드 → 해제 → 스키마 분리 → Neon 적재 → 알림
requirements.txt             # pandas, psycopg2-binary, openpyxl, pyarrow
.github/workflows/load.yml   # workflow_dispatch 수동 실행 워크플로
```

## 비고

- 이 리포지토리는 WeP-Stock 재고예측 파이프라인의 **원천 적재 단계**만 담당합니다. 적재된 `stock_raw*` 테이블은 후속 파이프라인의 입력으로 쓰입니다.
- 적재 시 대상 테이블은 매 실행마다 `DROP TABLE IF EXISTS` 후 재생성됩니다(멱등적 전량 적재).

---

## 👤 기여도 & 개발 환경

| 항목 | 내용 |
|---|---|
| **기여 비율** | **100%** (단독 개발) |
| **커밋** | 6 / 6 (본인 / 전체 사람 커밋) |
| **참여 인원** | 1명 |
| **AI 코딩 도구** | Claude Code |

<sub>집계 기준(2026-08-12 스냅샷): origin의 **모든 브랜치**에서 도달 가능한 커밋(머지 커밋·빈 커밋 제외), 커밋 author 이메일 기준이며 동일인의 여러 이메일은 하나로 합산, 봇·자동화 커밋은 제외했습니다.</sub>
