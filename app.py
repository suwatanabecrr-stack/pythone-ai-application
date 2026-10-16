"""AIライティングツール（Streamlit + Gemini API）

起動方法:  streamlit run app.py
"""

import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from gemini_client import AVAILABLE_MODELS, generate_stream
from tools import TOOLS, TOOLS_BY_KEY, Field, Tool

load_dotenv()

st.set_page_config(page_title="AIライティングツール", page_icon="✍️", layout="wide")

HISTORY_PAGE = "history"
# 入力文字数の上限（1回の生成で使う量を抑えるため）
MAX_TEXTAREA_CHARS = 20000
MAX_TEXT_CHARS = 500

if "results" not in st.session_state:
    st.session_state.results = {}  # ツールごとの最新の生成結果
if "history" not in st.session_state:
    st.session_state.history = []  # 生成履歴（新しい順）


def get_default_api_key() -> str:
    """環境変数（.env）→ st.secrets の順で APIキーを探す。"""
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""


# ================================================================ サイドバー
with st.sidebar:
    st.title("✍️ AIライティング")

    page = st.radio(
        "ツール",
        [t.key for t in TOOLS] + [HISTORY_PAGE],
        format_func=lambda k: "🕘 履歴" if k == HISTORY_PAGE else f"{TOOLS_BY_KEY[k].icon} {TOOLS_BY_KEY[k].name}",
        label_visibility="collapsed",
    )

    st.divider()
    server_key = get_default_api_key()
    with st.expander("⚙️ 設定", expanded=not server_key):
        # サーバー側のキーは初期値にしない（type="password" でも値はブラウザに送られるため）
        user_key = st.text_input(
            "Gemini APIキー（空ならサーバーの設定を使用）",
            type="password",
            help="https://aistudio.google.com/apikey で取得できます。.env に書いておくと毎回の入力が不要です。",
        ).strip()  # コピー時に紛れ込んだ空白・改行を除く
        api_key = user_key or server_key
        if server_key and not user_key:
            st.caption("✅ .env / secrets に設定されたキーを使用中")
        model = st.selectbox("モデル", AVAILABLE_MODELS)
        use_tool_default = st.checkbox("ツールごとのおすすめ値を使う", value=True)
        temperature_override = st.slider(
            "創造性（temperature）",
            0.0, 2.0, value=0.7, step=0.1,
            help="高いほど自由で多様な文章、低いほど安定した文章になります。",
            disabled=use_tool_default,
        )


# ================================================================ 共通処理
def render_field(tool: Tool, f: Field):
    """フィールド定義に応じて入力ウィジェットを描画し、値を返す。"""
    key = f"{tool.key}__{f.key}"
    label = f"{f.label} *" if f.required else f.label
    if f.kind == "textarea":
        return st.text_area(label, key=key, placeholder=f.placeholder, height=f.height, max_chars=MAX_TEXTAREA_CHARS)
    if f.kind == "select":
        return st.selectbox(label, f.options, key=key)
    if f.kind == "slider":
        default = f.default if f.default is not None else f.min_value
        return st.slider(label, f.min_value, f.max_value, default, f.step, key=key)
    return st.text_input(label, key=key, placeholder=f.placeholder, max_chars=MAX_TEXT_CHARS)


def explain_error(e: Exception) -> str:
    """よくある API エラーを、対処法つきの日本語メッセージにする。"""
    msg = str(e)
    if "API_KEY_INVALID" in msg or "API key not valid" in msg:
        return (
            "APIキーが無効です。https://aistudio.google.com/apikey で表示されているキー"
            "（AIza で始まる39文字）を、欠けがないようにコピーし直して貼り付けてください。"
        )
    if "NOT_FOUND" in msg or "404" in msg:
        return f"モデル「{model}」が見つかりません。サイドバーの「⚙️ 設定」で別のモデルを選んでください。"
    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
        return "無料枠の利用上限に達しました。しばらく時間をおくか、別のモデルを選んでください。"
    if "PERMISSION_DENIED" in msg or "403" in msg:
        return "このAPIキーには Gemini API の利用権限がありません。Google AI Studio で作成したキーを使ってください。"
    return "生成中にエラーが発生しました。しばらく待ってから、もう一度お試しください。"


def run_generation(tool: Tool, prompt: str, title: str):
    """Gemini で文章を生成（ストリーミング表示）し、結果を保存する。"""
    if not api_key:
        st.error("サイドバーの「⚙️ 設定」で Gemini APIキーを入力してください。")
        return
    temperature = tool.temperature if use_tool_default else temperature_override
    try:
        with st.container(border=True):
            text = st.write_stream(
                generate_stream(api_key, model, prompt, tool.system_instruction, temperature)
            )
    except Exception as e:  # APIキー間違い・レート制限など
        st.error(explain_error(e))  # 公開しているため、エラーの詳細は画面に出さない
        return
    if not text:
        st.warning("結果が空でした。入力内容を変えて再度お試しください。")
        return

    st.session_state.results[tool.key] = {"text": text, "prompt": prompt}
    st.session_state.history.insert(0, {
        "time": datetime.now().strftime("%m/%d %H:%M"),
        "tool": tool.key,
        "title": title,
        "text": text,
    })
    st.rerun()


def render_output(text: str, file_stem: str, key: str):
    """生成結果をプレビュー・コピー・ダウンロードできる形で表示する。"""
    st.caption(f"{len(text):,} 文字")
    preview, raw = st.tabs(["プレビュー", "テキスト（右上のボタンでコピー）"])
    with preview:
        with st.container(border=True):
            st.markdown(text)
    with raw:
        st.code(text, language=None, wrap_lines=True)
    st.download_button(
        "⬇️ ダウンロード (.md)",
        data=text,
        file_name=f"{file_stem}_{datetime.now():%Y%m%d_%H%M%S}.md",
        mime="text/markdown",
        key=f"dl_{key}",
    )


def summarize_input(tool: Tool, values: dict) -> str:
    """履歴用に入力内容から短い見出しを作る。"""
    first = next((str(values[f.key]) for f in tool.fields if f.required), "")
    first = first.replace("\n", " ")
    return first[:40] + ("…" if len(first) > 40 else "")


# ================================================================ 履歴ページ
if page == HISTORY_PAGE:
    st.header("🕘 生成履歴")
    st.caption("このブラウザを開いている間だけ保持されます（ページを再読み込みすると消えます）。")
    history = st.session_state.history
    if not history:
        st.info("まだ生成履歴はありません。")
    else:
        if st.button("🗑️ 履歴をすべて削除"):
            st.session_state.history = []
            st.rerun()
        for i, item in enumerate(history):
            tool = TOOLS_BY_KEY[item["tool"]]
            with st.expander(f"{item['time']}　{tool.icon} {tool.name}　｜　{item['title']}"):
                render_output(item["text"], tool.key, f"hist_{i}")
    st.stop()


# ================================================================ ツールページ
tool = TOOLS_BY_KEY[page]
st.header(f"{tool.icon} {tool.name}")
st.caption(tool.description)

input_col, output_col = st.columns([1, 2], gap="large")

with input_col:
    with st.form(f"form_{tool.key}"):
        values = {f.key: render_field(tool, f) for f in tool.fields}
        submitted = st.form_submit_button("✨ 生成する", type="primary", width="stretch")

with output_col:
    st.subheader("生成結果")
    if submitted:
        missing = [f.label for f in tool.fields if f.required and not str(values[f.key]).strip()]
        if missing:
            st.warning(f"必須項目を入力してください: {', '.join(missing)}")
        else:
            with st.spinner("生成中…"):
                run_generation(tool, tool.build_prompt(values), summarize_input(tool, values))

    result = st.session_state.results.get(tool.key)
    if result:
        render_output(result["text"], tool.key, tool.key)

        # 生成結果に追加の指示を出して修正する
        st.divider()
        with st.form(f"refine_{tool.key}", clear_on_submit=True):
            instruction = st.text_input(
                "🔧 この結果を修正する",
                placeholder="例: もっと短く / 2つ目の見出しを詳しく / もう少しカジュアルに",
                max_chars=MAX_TEXT_CHARS,
            )
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
    elif not submitted:
        st.info("左のフォームに入力して「生成する」を押してください。")
