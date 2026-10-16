# ✍️ AIライティングツール

Python + Streamlit + Gemini API で作った、個人用のAIライティングツールです。

## 機能

| ツール | 内容 |
| --- | --- |
| 📝 ブログ執筆 | テーマ・読者・キーワードから見出し付きの記事を作成 |
| ✉️ メール返信 | 受信メールを貼り付けて、方針に沿った返信案を複数作成 |
| 📄 文章要約 | 箇条書き／3行／結論ファーストなどの形式で要約 |
| ✅ 校正・推敲 | 誤字脱字や表現を直し、修正点を説明 |
| 🔄 リライト | トーンや長さ、対象読者に合わせて書き換え |
| 🌐 翻訳 | 自然な表現で多言語に翻訳 |
| 📣 SNS投稿 | X・Instagram などに合わせた投稿文を作成 |
| 💡 タイトル・コピー | 記事タイトルやキャッチコピー案を量産 |
| 🧠 アイデア出し | ブログネタや企画のブレスト |
| ✨ フリー入力 | 自由な依頼 |

共通機能:

- 生成結果のストリーミング表示
- 「この結果を修正する」で追加指示による書き直し
- コピー用テキスト表示・Markdown ダウンロード
- 生成履歴（ブラウザを開いている間のみ）
- モデル・創造性（temperature）の切り替え

## セットアップ

```powershell
# 1. 仮想環境を作成して有効化
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. ライブラリをインストール
pip install -r requirements.txt

# 3. APIキーを設定（.env.example をコピーして編集）
copy .env.example .env
```

`.env` の `GEMINI_API_KEY` に [Google AI Studio](https://aistudio.google.com/apikey) で取得したキーを書きます。
（`.env` を作らず、アプリのサイドバーで入力してもかまいません。）

## 起動

```powershell
streamlit run app.py
```

ブラウザで http://localhost:8501 が開きます。

## ファイル構成

```
app.py            画面（Streamlit）
tools.py          各ライティングツールの定義（入力項目とプロンプト）
gemini_client.py  Gemini API の呼び出し
```

## ツールの追加方法

`tools.py` の `TOOLS` リストに `Tool(...)` を1つ足すだけで、サイドバーと入力フォームが自動で作られます。
入力項目は `Field` で定義し、`build_prompt` 関数で入力値からプロンプトを組み立てます。
