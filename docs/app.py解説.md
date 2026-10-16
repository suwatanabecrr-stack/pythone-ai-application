# 【初心者向け】AIライティングツールの `app.py` を上から順番に読んでみよう

自分で作った（作ってもらった）アプリなのに、中身がよくわからない……。そんなモヤモヤを解消するために、この記事では AIライティングツールの心臓部 **`app.py`** を、上から順番にやさしく解説していきます。

この記事を読み終わるころには、次のことがわかるようになります。

- Streamlit のアプリが「どういう順番で」動いているのか
- ボタンを押してから AI の文章が表示されるまでの流れ
- 自分で画面をちょっと変えたいとき、どこをいじればいいのか

---

## 目次

1. まず知っておきたい「Streamlit の不思議なルール」
2. ファイルの全体マップ
3. 準備：部品を読み込む（1〜25行目）
4. APIキーを探す関数（28〜36行目）
5. サイドバーを作る（39〜66行目）
6. 便利な関数たち（69〜153行目）
7. 履歴ページ（156〜171行目）
8. メインのツールページ（174〜218行目）
9. ボタンを押してから結果が出るまでの流れ（まとめ）
10. 自分でいじってみよう

---

## 1. まず知っておきたい「Streamlit の不思議なルール」

コードを読む前に、これだけは押さえておいてください。**ここが一番大事です。**

> **Streamlit は、ボタンを押したり入力したりするたびに、`app.py` を「上から下まで全部」実行し直す。**

たとえば、サイドバーで「メール返信」をクリックすると……

1. `app.py` の1行目から実行が始まる
2. サイドバーを描く
3. 「今はメール返信が選ばれている」とわかる
4. メール返信の画面を描く
5. 最後の行まで来たら終わり

という流れが、**クリックのたびに毎回** 起きています。

「え、毎回全部やり直したら、さっき生成した文章も消えちゃうのでは？」と思いますよね。そのとおりで、普通の変数は毎回リセットされてしまいます。

そこで登場するのが **`st.session_state`（セッションステート）** です。これは「やり直しても消えない、特別なメモ帳」のようなもの。生成結果や履歴は、ここに保存しておくことで消えずに残ります。

この「毎回やり直す」「消したくないものは session_state に」という2つを頭に入れておけば、このあとのコードがすっと読めるようになります。

---

## 2. ファイルの全体マップ

`app.py` は、大きく分けて次の5つのブロックでできています。

| 行 | ブロック | ひとことで言うと |
| --- | --- | --- |
| 1〜36 | 準備 | 部品を読み込み、メモ帳（session_state）を用意する |
| 39〜66 | サイドバー | 左側のメニューと設定欄を作る |
| 69〜153 | 便利な関数 | あとで何度も使う「道具」を作っておく |
| 156〜171 | 履歴ページ | 「🕘 履歴」が選ばれたときの画面 |
| 174〜218 | ツールページ | ブログ執筆などの各ツールの画面 |

ちなみに、このアプリは3つのファイルで役割分担しています。

- **`app.py`** … 画面を作る（今回の主役）
- **`tools.py`** … 「ブログ執筆にはこんな入力欄が必要」といった、各ツールの設計図
- **`gemini_client.py`** … Google の AI（Gemini）に話しかける係

`app.py` は「設計図（tools.py）を見ながら画面を組み立て、AIへの連絡は係（gemini_client.py）に任せる」という、いわば **現場監督** のような役割です。

---

## 3. 準備：部品を読み込む（1〜25行目）

```python
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from gemini_client import AVAILABLE_MODELS, generate_stream
from tools import TOOLS, TOOLS_BY_KEY, Field, Tool
```

`import` は「この道具を使います」という宣言です。

- `os` … パソコンの環境変数（APIキーなど）を読むため
- `datetime` … 履歴に「いつ生成したか」を記録するため
- `streamlit as st` … 画面づくりの道具。以降 `st.〇〇` と書いたら Streamlit の機能です
- `load_dotenv` … `.env` ファイルを読み込むため
- 下の2行 … 自分たちで作った `gemini_client.py` と `tools.py` から部品を借りてきています

```python
load_dotenv()

st.set_page_config(page_title="AIライティングツール", page_icon="✍️", layout="wide")
```

- `load_dotenv()` で `.env` に書いた APIキーを読み込みます。
- `st.set_page_config(...)` はブラウザのタブに表示される名前とアイコン、そして画面を横に広く使う（`wide`）設定です。

```python
if "results" not in st.session_state:
    st.session_state.results = {}  # ツールごとの最新の生成結果
if "history" not in st.session_state:
    st.session_state.history = []  # 生成履歴（新しい順）
```

ここで先ほどの **消えないメモ帳** を用意しています。

「もしメモ帳にまだ `results` がなければ、空のものを作る」という意味です。2回目以降の実行では「もうある」ので何もしません。だから中身が消えずに残るわけですね。

- `results` … ツールごとの「最新の生成結果」を入れる箱（`{}` は辞書＝名前付きの箱）
- `history` … 生成した結果をすべて並べておくリスト（`[]` はリスト＝順番付きの箱）

---

## 4. APIキーを探す関数（28〜36行目）

```python
def get_default_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""
```

`def` は **関数（＝名前を付けた手順書）** を作る書き方です。この関数は「APIキーを探してきて」という手順書です。

1. まず `.env`（環境変数）を見る。あれば、それを返して終わり
2. なければ Streamlit の秘密設定ファイル（`st.secrets`）を見る
3. それもなければ、空っぽ `""` を返す

`try 〜 except` は「やってみて、エラーになったら代わりにこうする」という書き方です。秘密設定ファイルが存在しないとエラーになるので、そのときは空っぽを返すようにしています。

---

## 5. サイドバーを作る（39〜66行目）

```python
with st.sidebar:
    st.title("✍️ AIライティング")
```

`with st.sidebar:` の下に書いたものは、すべて **左側のサイドバー** に表示されます。字下げ（インデント）されている範囲が「サイドバーの中身」です。

### ツールの一覧

```python
    page = st.radio(
        "ツール",
        [t.key for t in TOOLS] + [HISTORY_PAGE],
        format_func=lambda k: "🕘 履歴" if k == HISTORY_PAGE else f"{TOOLS_BY_KEY[k].icon} {TOOLS_BY_KEY[k].name}",
        label_visibility="collapsed",
    )
```

`st.radio` は「どれか1つを選ぶ」ボタンの一覧です。選ばれたものが `page` という変数に入ります。

- `[t.key for t in TOOLS]` … `tools.py` に登録されているツールの名前（`blog`、`email` など）を全部集めたリスト。最後に `history`（履歴）も足しています
- `format_func=...` … 画面に表示するときの見た目を決める部分。`blog` という内部名を「📝 ブログ執筆」という表示名に変換しています

ポイントは、**ツールの一覧を `app.py` に直接書いていない** ことです。`tools.py` にツールを1つ足せば、ここにも自動で並ぶ仕組みになっています。

### 設定欄

```python
    with st.expander("⚙️ 設定", expanded=not get_default_api_key()):
```

`st.expander` は、クリックで開いたり閉じたりできる折りたたみ欄です。`expanded=not get_default_api_key()` は「APIキーが見つからなかったら、最初から開いておく」という気配りです。

```python
        api_key = st.text_input(
            "Gemini APIキー",
            value=get_default_api_key(),
            type="password",
            ...
        ).strip()
```

APIキーの入力欄です。

- `value=...` … 最初から入っている値。`.env` にキーがあればそれが入ります
- `type="password"` … 入力した文字を ●●● で隠す
- `.strip()` … 前後の余計な空白や改行を取り除く（コピペのミス対策）

```python
        model_choice = st.selectbox("モデル", AVAILABLE_MODELS + [CUSTOM_MODEL])
        model = st.text_input("モデル名", value=AVAILABLE_MODELS[0]) if model_choice == CUSTOM_MODEL else model_choice
```

AIのモデルを選ぶプルダウンです。「その他（手入力）」が選ばれたときだけ、モデル名を自由に入力できる欄が出てきます。

```python
        use_tool_default = st.checkbox("ツールごとのおすすめ値を使う", value=True)
        temperature_override = st.slider(
            "創造性（temperature）",
            0.0, 2.0, value=0.7, step=0.1,
            disabled=use_tool_default,
        )
```

**temperature（温度）** は、AIの文章の「自由さ」を決める数値です。

- 低い（0に近い）… 毎回同じような、堅実な文章
- 高い（2に近い）… 毎回違う、冒険した文章

各ツールには「要約は正確さ重視で低め」「キャッチコピーは発想重視で高め」といったおすすめ値が `tools.py` で決めてあります。チェックを外したときだけ、スライダーの値が使われます（`disabled=use_tool_default` で、チェック中はスライダーを触れなくしています）。

---

## 6. 便利な関数たち（69〜153行目）

ここでは、あとで何度も使う「道具」を関数として作っています。この時点ではまだ **作っただけで、使ってはいません**。

### `render_field` … 入力欄を1つ作る

```python
def render_field(tool: Tool, f: Field):
    key = f"{tool.key}__{f.key}"
    label = f"{f.label} *" if f.required else f.label
    if f.kind == "textarea":
        return st.text_area(...)
    if f.kind == "select":
        return st.selectbox(...)
    if f.kind == "slider":
        ...
        return st.slider(...)
    return st.text_input(...)
```

`tools.py` には、各入力欄が「どんな種類か（`kind`）」が書いてあります。この関数は、その種類を見て適切な部品を作ります。

| kind | 作られる部品 |
| --- | --- |
| `textarea` | 複数行の大きな入力欄 |
| `select` | プルダウン |
| `slider` | スライダー |
| それ以外 | 1行の入力欄 |

必須の項目には、ラベルの後ろに ` *` を付けています。

### `explain_error` … エラーをわかりやすくする

```python
def explain_error(e: Exception) -> str:
    msg = str(e)
    if "API_KEY_INVALID" in msg or ...:
        return "APIキーが無効です。…"
    if "NOT_FOUND" in msg or "404" in msg:
        return f"モデル「{model}」が見つかりません。…"
    ...
```

Google から返ってくるエラーは英語で長く、初心者には読みにくいもの。この関数は、エラー文の中に特定の言葉が含まれているかを調べて、**原因と対処法を日本語で返します**。

- `API_KEY_INVALID` → APIキーが間違っている
- `NOT_FOUND` → モデル名が間違っている
- `RESOURCE_EXHAUSTED` → 無料枠を使い切った
- `PERMISSION_DENIED` → キーに権限がない

### `run_generation` … AI に文章を作ってもらう（一番大事！）

```python
def run_generation(tool: Tool, prompt: str, title: str):
    if not api_key:
        st.error("サイドバーの「⚙️ 設定」で Gemini APIキーを入力してください。")
        return
```

まず APIキーがなければ、エラーを出してすぐ終了（`return`）します。

```python
    temperature = tool.temperature if use_tool_default else temperature_override
```

使う temperature を決めます。チェックが入っていればツールのおすすめ値、外れていればスライダーの値です。

```python
    try:
        with st.container(border=True):
            text = st.write_stream(
                generate_stream(api_key, model, prompt, tool.system_instruction, temperature)
            )
    except Exception as e:
        st.error(explain_error(e))
        ...
        return
```

ここがAIを呼び出す本体です。

- `generate_stream(...)` … `gemini_client.py` の関数。AIの文章を **少しずつ** 受け取ります
- `st.write_stream(...)` … 受け取った文章を、届いたそばから画面に表示します。ChatGPT のように文字がスラスラ出てくるのはこのおかげです
- 全部表示し終わると、完成した文章が `text` に入ります
- 途中でエラーが起きたら、`except` の中で先ほどの `explain_error` を使ってメッセージを表示します

```python
    st.session_state.results[tool.key] = {"text": text, "prompt": prompt}
    st.session_state.history.insert(0, {
        "time": datetime.now().strftime("%m/%d %H:%M"),
        "tool": tool.key,
        "title": title,
        "text": text,
    })
    st.rerun()
```

できあがった文章を **消えないメモ帳** に保存します。

- `results` … 「このツールの最新結果」として保存（あとで修正するときのために、AIへの指示文 `prompt` も一緒に）
- `history` … 履歴リストの **先頭** に追加（`insert(0, ...)` で先頭に入れるので、新しい順に並ぶ）

最後の `st.rerun()` は「もう一度、上から全部やり直して！」という命令です。やり直すと、保存した結果がきれいな形（次の `render_output`）で表示されます。

### `render_output` … 結果を表示する

```python
def render_output(text: str, file_stem: str, key: str):
    st.caption(f"{len(text):,} 文字")
    preview, raw = st.tabs(["プレビュー", "テキスト（右上のボタンでコピー）"])
    with preview:
        ...
        st.markdown(text)
    with raw:
        st.code(text, language=None, wrap_lines=True)
    st.download_button(...)
```

生成された文章を表示する係です。

1. 文字数を表示
2. タブを2つ作る
   - **プレビュー** … 見出しや箇条書きが整った、読みやすい表示（`st.markdown`）
   - **テキスト** … 飾りなしの文章。右上にコピーボタンが付きます（`st.code`）
3. `.md` ファイルとしてダウンロードできるボタン

### `summarize_input` … 履歴用の見出しを作る

```python
def summarize_input(tool: Tool, values: dict) -> str:
    first = next((str(values[f.key]) for f in tool.fields if f.required), "")
    first = first.replace("\n", " ")
    return first[:40] + ("…" if len(first) > 40 else "")
```

履歴に並べるときの「タイトル」を作ります。最初の必須項目（ブログならテーマ）の内容を、改行を空白に変えて、40文字までに切り詰めています。長いときは最後に「…」を付けます。

---

## 7. 履歴ページ（156〜171行目）

```python
if page == HISTORY_PAGE:
    st.header("🕘 生成履歴")
    ...
    for i, item in enumerate(history):
        tool = TOOLS_BY_KEY[item["tool"]]
        with st.expander(f"{item['time']}　{tool.icon} {tool.name}　｜　{item['title']}"):
            render_output(item["text"], tool.key, f"hist_{i}")
    st.stop()
```

サイドバーで「🕘 履歴」が選ばれたときだけ実行されるブロックです。

- 履歴が空なら「まだ生成履歴はありません」と表示
- あれば、1件ずつ折りたたみ欄にして並べる。中身の表示には、さっき作った `render_output` を再利用しています
- 「履歴をすべて削除」ボタンで、メモ帳の `history` を空にできます

最後の **`st.stop()`** がポイントです。「ここで実行を止めて！」という意味で、これがあるおかげで、この下にあるツールページの処理は実行されません。

---

## 8. メインのツールページ（174〜218行目）

いよいよ、ブログ執筆やメール返信などの画面です。

```python
tool = TOOLS_BY_KEY[page]
st.header(f"{tool.icon} {tool.name}")
st.caption(tool.description)
```

サイドバーで選ばれたツールの設計図を `tools.py` から取り出し、タイトルと説明文を表示します。

```python
input_col, output_col = st.columns([1, 2], gap="large")
```

画面を **左右2列** に分けます。`[1, 2]` は幅の比率で、左（入力）が 1、右（結果）が 2 の割合です。

### 左側：入力フォーム

```python
with input_col:
    with st.form(f"form_{tool.key}"):
        values = {f.key: render_field(tool, f) for f in tool.fields}
        submitted = st.form_submit_button("✨ 生成する", type="primary", width="stretch")
```

- `st.form` … 入力欄をひとまとめにする枠。**フォームの中では、入力するたびに画面がやり直されません**。「生成する」を押したときにまとめて1回だけやり直されるので、入力中に画面がチラつかずに済みます
- `values = {...}` … ツールの入力欄をすべて `render_field` で作り、入力された値を `{"topic": "在宅ワーク", "tone": "です・ます調", ...}` のような辞書にまとめます
- `submitted` … 「生成する」ボタンが押されたら `True`（はい）、押されていなければ `False`（いいえ）

### 右側：生成結果

```python
with output_col:
    st.subheader("生成結果")
    if submitted:
        missing = [f.label for f in tool.fields if f.required and not str(values[f.key]).strip()]
        if missing:
            st.warning(f"必須項目を入力してください: {', '.join(missing)}")
        else:
            with st.spinner("生成中…"):
                run_generation(tool, tool.build_prompt(values), summarize_input(tool, values))
```

ボタンが押されたときの処理です。

1. 必須項目のうち、空っぽのものを探す
2. あれば「入力してください」と警告して終わり
3. 全部埋まっていれば、
   - `tool.build_prompt(values)` で、入力内容から **AIへの指示文（プロンプト）** を組み立てる（組み立て方は `tools.py` に書いてあります）
   - `run_generation` に渡して、AIに文章を作ってもらう

```python
    result = st.session_state.results.get(tool.key)
    if result:
        render_output(result["text"], tool.key, tool.key)
```

メモ帳に「このツールの結果」が保存されていれば、`render_output` で表示します。ボタンを押していない時でも、前に作った結果があれば表示されるのはこのためです。

### 「この結果を修正する」機能

```python
        with st.form(f"refine_{tool.key}", clear_on_submit=True):
            instruction = st.text_input("🔧 この結果を修正する", ...)
            refine = st.form_submit_button("修正する")
        if refine and instruction.strip():
            refine_prompt = (
                f"{result['prompt']}\n\n"
                f"# あなたが前回作成した文章\n{result['text']}\n\n"
                f"# 修正指示\n{instruction}\n\n"
                "上記の修正指示に従って、文章全体を書き直してください。"
            )
            with st.spinner("修正中…"):
                run_generation(tool, refine_prompt, f"（修正）{instruction[:30]}")
```

結果の下に出てくる修正欄です。「もっと短く」などと入力して「修正する」を押すと、

1. 最初の指示文
2. AIが前回書いた文章
3. あなたの修正指示

の3つを **1つの長い指示文** にまとめて、もう一度AIに送ります。AIは毎回「初めまして」の状態なので、こうして前回の内容も一緒に渡してあげる必要があるんですね。

`clear_on_submit=True` は、送信したら入力欄を空に戻す設定です。

```python
    elif not submitted:
        st.info("左のフォームに入力して「生成する」を押してください。")
```

まだ何も生成していないときは、使い方の案内を表示します。

---

## 9. ボタンを押してから結果が出るまでの流れ（まとめ）

「ブログ執筆」で「✨ 生成する」を押したとき、裏側ではこんなことが起きています。

```
① 「生成する」をクリック
      ↓
② app.py が上から実行し直される（submitted = True）
      ↓
③ 必須項目のチェック
      ↓
④ tools.py の build_prompt で、入力内容から AI への指示文を組み立てる
      ↓
⑤ run_generation → gemini_client.py → Google の Gemini に送信
      ↓
⑥ 返ってきた文章を st.write_stream で少しずつ表示
      ↓
⑦ 完成した文章を session_state（消えないメモ帳）に保存
      ↓
⑧ st.rerun() でもう一度、上から実行し直し
      ↓
⑨ メモ帳の結果を render_output で表示（プレビュー・コピー・ダウンロード）
```

「毎回やり直す」「消したくないものはメモ帳へ」という、最初に説明した2つのルールがちゃんと生きているのがわかりますね。

---

## 10. 自分でいじってみよう

仕組みがわかったら、少しだけカスタマイズしてみましょう。保存したあと、ブラウザの右上に出る「Rerun」を押すと反映されます。

### 入力欄と結果欄の幅を変える（179行目）

```python
input_col, output_col = st.columns([1, 2], gap="large")
```

`[1, 2]` を `[1, 3]` にすると、結果欄がもっと広くなります。

### 「生成する」ボタンの文字を変える（184行目）

```python
submitted = st.form_submit_button("✨ 生成する", ...)
```

`"✨ 生成する"` を `"🚀 書いて！"` などに変えてみましょう。

### 新しいツールを追加する

これは `app.py` ではなく **`tools.py`** の仕事です。`TOOLS` というリストに `Tool(...)` を1つ足すだけで、サイドバーにも入力フォームにも自動で反映されます。`app.py` が「設計図を見て画面を組み立てる」作りになっているおかげですね。

---

## おわりに

`app.py` は約220行ありますが、やっていることを一言でまとめると、

> **「設計図（tools.py）を見て画面を作り、ボタンが押されたら AI に頼んで、結果をメモ帳に保存して表示する」**

だけです。

最初は難しく見えたコードも、「Streamlit は毎回上から全部やり直す」というルールを知るだけで、ぐっと読みやすくなったのではないでしょうか。次は `tools.py` や `gemini_client.py` も覗いてみると、アプリ全体がつながって見えてきますよ。
