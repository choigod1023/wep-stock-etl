# wep-stock-etl

[한국어](README.md) · **日本語** · [English](README.en.md)

保健所の医療物品 在庫予測（WeP-Stock）プロジェクトの **原本データ取り込み ETL**。
SSIS の大容量添付形式で配布される zip 原本をダウンロードして展開し、スキーマ別に統合して **Neon (PostgreSQL)** へ原文のまま格納します。

## 紹介

WeP-Stock の原本データセットは zip で配布され、内部のファイルはスキーマがまちまちです。
この ETL はそれらの zip を取得し、**ヘッダーが同じファイル同士を 1 つのテーブルにまとめて** 格納します。
全カラムを `TEXT` にして原文を欠損なく保存することが基本原則です（型変換は後続パイプラインの担当）。

**ローカル PC を使わず GitHub Actions 上でリモート実行する** 設計になっており、大容量のダウンロード／取り込みを CI ランナーで処理します。

## ✨ 主な機能

- **リモートダウンロード**: `DATA_URLS`（空白／改行区切り）に並べた zip を `curl`（リトライ 3 回）でダウンロード。
- **展開**: zip の展開＋**入れ子になった zip をもう 1 段** 展開。zip でなければ原文としてそのまま扱います。
- **多様なフォーマットの読み込み**: `.csv/.tsv/.txt/.xlsx/.xls/.parquet` に対応。CSV は区切り文字の自動推定（`sep=None`）とエンコーディングのフォールバック（`utf-8-sig → cp949 → euc-kr → utf-8 → latin-1`）。
- **スキーマの自動分離**: ファイルヘッダーの MD5 署名でスキーマを判別し、同じスキーマは 1 テーブル（`stock_raw`）へ、異なるスキーマがあれば `stock_raw_2`, `stock_raw_3` … に分けて格納。
- **原文保存での取り込み**: 全カラム `TEXT` でテーブルを作成し、`COPY ... FROM STDIN`（CSV）で一括ロード。
- **完了通知**: アプリパスワードが設定されていれば Gmail（SMTP SSL）で取り込みサマリのメールを送信（失敗してもジョブは落ちません）。

## 🛠 技術スタック

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-150458?logo=pandas&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Neon%20Postgres-4169E1?logo=postgresql&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)

- **Python**: pandas, psycopg2(-binary), openpyxl（Excel）, pyarrow（Parquet）
- **DB**: Neon (PostgreSQL) — `COPY` で取り込み
- **実行環境**: GitHub Actions（`workflow_dispatch` の手動トリガー）

## 🏗 動作の流れ

```
DATA_URLS(zip 群) ──curl──▶ data/part_i.zip
        │
        ├─ unzip ──▶ data/ext_i/...  (入れ子 zip をもう 1 段展開)
        │
        ├─ read_any(): csv/tsv/txt/xlsx/parquet を読み込み（エンコーディング・区切り文字のフォールバック）
        │
        ├─ ヘッダーの MD5 署名でスキーマをグルーピング
        │       同じ署名 → 同じテーブル
        │       異なる署名 → stock_raw_2, stock_raw_3 ...
        │
        └─ CREATE TABLE (全カラム TEXT) ─▶ COPY FROM STDIN ─▶ Neon
                                                 │
                                                 └─ 完了時に Gmail 通知（任意）
```

## 🚀 はじめかた

### 前提条件
- Python 3.12（推奨）
- 取り込み先の Neon/PostgreSQL インスタンスと接続文字列
- 原本データ zip のダウンロード URL

### インストール
```bash
pip install -r requirements.txt
```

### 環境変数

コードが実際に参照する環境変数は次のとおりです。

| 変数 | 必須 | 説明 |
|------|:---:|------|
| `DATABASE_URL` | ✅ | Neon/PostgreSQL の接続文字列 |
| `DATA_URLS` | ✅ | ダウンロードする zip の URL 一覧（空白／改行区切り） |
| `TABLE_NAME` | ⭕ | 基本テーブル名（未設定なら `stock_raw`） |
| `GMAIL_ADDRESS` | ⭕ | 完了通知の送信元 Gmail アドレス |
| `GMAIL_APP_PASSWORD` | ⭕ | 上記アカウントの **アプリパスワード**（SMTP SSL ログイン用） |
| `NOTIFY_TO` | ⭕ | 通知の宛先（未設定なら `GMAIL_ADDRESS` へ送信） |

> `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` が無い場合、メール通知は自動的にスキップされます。

### 実行

**ローカル実行:**
```bash
export DATABASE_URL="postgresql://..."
export DATA_URLS="https://.../part1.zip https://.../part2.zip"
python etl.py
```

**GitHub Actions での実行（推奨）:**
- リポジトリの Secrets に `DATABASE_URL`, `DATA_URLS`（＋任意で `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `NOTIFY_TO`）を登録。
- Actions タブ → **"Load WeP-Stock → Neon"** → **Run workflow** で手動実行（`.github/workflows/load.yml`）。

## 📁 プロジェクト構成

```
etl.py                       # ダウンロード → 展開 → スキーマ分離 → Neon 取り込み → 通知
requirements.txt             # pandas, psycopg2-binary, openpyxl, pyarrow
.github/workflows/load.yml   # workflow_dispatch 手動実行ワークフロー
```

## 備考

- 本リポジトリは WeP-Stock 在庫予測パイプラインの **原本取り込み段階** のみを担当します。格納された `stock_raw*` テーブルは後続パイプラインの入力として使われます。
- 取り込み時、対象テーブルは実行のたびに `DROP TABLE IF EXISTS` の後に再作成されます（冪等な全量ロード）。

---

## 👤 コントリビューションと開発環境

| 項目 | 内容 |
|---|---|
| **貢献比率** | **100%**（単独開発） |
| **コミット** | 6 / 6（本人 / 全人力コミット） |
| **参加人数** | 1 名 |
| **AI コーディングツール** | Claude Code |

<sub>集計基準（2026-08-12 時点のスナップショット）: origin の **すべてのブランチ** から到達可能なコミット（マージコミット・空コミットは除外）を対象とし、コミットの author メールアドレス基準で、同一人物の複数のメールアドレスは合算、ボット・自動化コミットは除外しています。</sub>
