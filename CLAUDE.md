# CLAUDE.md

このファイルは、このリポジトリで作業する Claude Code（claude.ai/code）向けの説明書です。

## プロジェクト概要

個人用のAIライティングツール。Python + Streamlit + Gemini API で作っている。機能はブログ執筆、メール返信、要約、校正、リライト、翻訳、SNS投稿、タイトル案、アイデア出し、フリー入力。

- データベースと認証は**あえて付けていない。追加しないこと。**
- 画面の文字とプロンプトは日本語。新しく追加する画面の文字も日本語にすること。
- 新しいライティング機能は、ユーザーに確認せず適宜追加してよい（ユーザーから許可済み）。

## ユーザーとのやりとり

- 返答は日本語で行う。
- ユーザーはプログラミング初心者。手順は「どこで・何を押す/入力する」まで具体的に書き、専門用語には一言説明を添える。
- コマンドはユーザーが PowerShell にそのまま貼り付けて動く形で示す（`&&` は PowerShell 5.1 で使えない）。

## コマンド（Windows / PowerShell）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py                          # http://localhost:8501
.\.venv\Scripts\streamlit.exe run app.py --server.headless true   # 対話できないシェルから起動するとき用（初回のメールアドレス入力で止まるのを防ぐ）
```

Python はシステムのもの（3.15）ではなく、必ず `.venv` 内のものを使う。

テストもコードのチェック用ツールもない。変更後は次の2つで確認する（どちらもAPIキー不要）。

```powershell
# 画面がエラーなく表示されるか
.\.venv\Scripts\python.exe -c "from streamlit.testing.v1 import AppTest; at=AppTest.from_file('app.py').run(timeout=30); print(at.exception)"

# 全ツールの build_prompt が仮の入力値でエラーなく動くか
.\.venv\Scripts\python.exe -c "from tools import TOOLS; [print(t.key, len(t.build_prompt({f.key: (f.default if f.default is not None else (f.options[0] if f.options else 'テスト')) for f in t.fields}))) for t in TOOLS]"
```

実際の生成（Gemini 呼び出し）の確認は APIキーが必要なので、ユーザーにブラウザで試してもらう。起動中のアプリはファイル保存後、画面右上の「Rerun」で反映される。

APIキーは、`.env` の `GEMINI_API_KEY`（python-dotenv で読み込み）→ `st.secrets` の順で探す。サイドバーの「⚙️ 設定」欄に入力すると、そちらが優先される。公開しているため、サーバー側のキーは入力欄の初期値にしない（`type="password"` でも値はブラウザに送られる）。`.env` のひな形は `.env.example`。

## 構成

役割の違う3つのファイルでできている。ツールごとの違いは「データ」として定義し、画面はそれを読んで自動で作る。

- **`tools.py`**：ツールの一覧を設定として書いておく場所。1つの `Tool` は次のものを持つ。
  - 入力項目 `Field` のリスト。種類（`kind`）は `text` / `textarea` / `select` / `slider`。
  - プロンプトを組み立てる関数 `build_prompt(values: dict) -> str`。入力値は `Field.key` をキーにした辞書で渡される。
  - 共通の指示 `BASE_SYSTEM` の後ろに付け足す、ツール専用の指示 `system`（任意）。
  - おすすめの `temperature`。

  サイドバーには `TOOLS` に並べた順で表示される。**ツールを追加するときは `TOOLS` に `Tool` を1つ足すだけでよい。** サイドバーと入力フォームは `app.py` が自動で作る。

- **`app.py`**：どの `Tool` でも同じように表示する共通の画面。主な流れ：
  - フォームの各部品のキーは `f"{tool.key}__{field.key}"`。生成の前に必須項目が入力されているかを確認する。
  - `run_generation` が結果を `st.write_stream` で少しずつ表示し、終わったら次の3つを行う。
    1. 結果 `{"text", "prompt"}` を `st.session_state.results[tool.key]` に保存する
    2. 同じ結果を `st.session_state.history` の先頭に追加する
    3. `st.rerun()` で画面を描き直す

    描き直したあとの表示はすべて `render_output` が担当する（プレビュー / コピー用のコード欄 / .md ダウンロード）。
  - 「この結果を修正する」は、元のプロンプト・前回の結果・ユーザーの修正指示を1つにまとめ、新しいプロンプトとして送る。会話の続きとして扱っているわけではない。結果は新しいものに置き換わる。
  - 履歴はブラウザを開いている間だけ残り、再読み込みすると消える。保存しないのは意図的。
  - temperature は、ふだんはツールごとのおすすめ値を使う。サイドバーのチェックを外したときだけスライダーの値を使う。

- **`gemini_client.py`**：`google-genai` SDK を薄く包んだだけのファイル。書き方は `from google import genai` で、古い `google.generativeai` ではない。
  - `generate_stream` は生成された文章を少しずつ返す。
  - `AVAILABLE_MODELS` に書いたモデルがサイドバーのモデル選択に並び、先頭がデフォルトになる（現在は `gemini-3.8-flash`）。公開しているため、一覧にないモデル名は選べないようにしている。Gemini のモデル名は頻繁に変わるので、更新するときは公式ドキュメントで現行のモデル名を確認する。

## プロンプトを書くときの決まり

- 結果は `st.markdown` で表示するので、出力形式は Markdown を指定する。
- 前置きや「承知しました」などを書かせない指示は `BASE_SYSTEM` にまとめてある。ツールごとに書き足さない。
- 任意入力の項目は `_line(ラベル, 値)` で組み立てる。値が空なら行ごと省かれる。
- 複数の案を出させるツールは、案ごとに `## 案1` のような見出しを付けさせる。
- 正確さが大事なツール（要約・校正・翻訳）は temperature を低め、発想を広げたいツール（タイトル・アイデア出し）は高めにする。

## Streamlit の注意点

- 表示されていない部品の入力値は Streamlit が自動で消すため、別のツールに切り替えて戻ると入力内容はリセットされる（生成結果は `results` に残る）。
- `use_container_width` は非推奨。`width="stretch"` を使う。
