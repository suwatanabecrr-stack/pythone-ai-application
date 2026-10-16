"""Streamlit + LLM API アプリ向けのセキュリティ一次スキャン（標準ライブラリのみ）。

使い方:  python scan.py <プロジェクトのフォルダ>

ヒットは「調べる候補」であって、問題確定ではない。必ず該当箇所のコードを読んで判断すること。
秘密情報らしき値は先頭4文字＋文字数だけを表示し、値そのものは出力しない。
"""

import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git", ".venv", "venv", "env", ".env", "node_modules", "__pycache__", "site-packages",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build", ".tox", ".idea", ".vscode",
}
MAX_BYTES = 1_000_000

SECRET_PATTERNS = [
    ("Google APIキー", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Anthropic APIキー", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI APIキー", re.compile(r"sk-(?!ant-)(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,}")),
    ("GitHub トークン", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("AWS アクセスキー", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Hugging Face トークン", re.compile(r"hf_[A-Za-z0-9]{30,}")),
    ("Slack トークン", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("秘密鍵", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
# KEY = "値" の形で、値がプレースホルダーやコードではなさそうなもの
GENERIC_SECRET = re.compile(
    r"(?i)\b([A-Z0-9_]*(?:api[_-]?key|secret|token|password|passwd))\b\s*[:=]\s*[\"']?([^\s\"'#,)]{12,})"
)
PLACEHOLDER = re.compile(
    r"(?i)(your|xxx|here|example|dummy|sample|placeholder|changeme|<|\$\{|os\.|getenv|environ|st\.secrets|secrets\[|none|null|true|false)"
)

# (ID, 正規表現, 説明)。.py ファイルだけに適用する
CODE_PATTERNS = [
    ("HTML-1", r"unsafe_allow_html\s*=\s*True", "HTML をそのまま表示している。中身にユーザー入力や LLM の出力が混ざると XSS の恐れ"),
    ("HTML-2", r"components\.v1\.html|components\.html\(|st\.html\(", "HTML/JS をそのまま埋め込んでいる。中身の出どころを確認"),
    ("EXEC-1", r"\beval\(|\bexec\(", "eval/exec。LLM の出力や入力値が渡ると任意コード実行"),
    ("EXEC-2", r"subprocess\.|os\.system\(|os\.popen\(|shell\s*=\s*True", "外部コマンドの実行。引数の出どころを確認"),
    ("DESER-1", r"pickle\.loads?\(|yaml\.load\((?!.*SafeLoader)|marshal\.loads?\(", "安全でない読み込み（デシリアライズ）"),
    ("SECRET-SHOW", r"st\.(write|json|code|text|markdown|caption|sidebar\.write)\([^)]*(os\.environ|st\.secrets|api_key|API_KEY)", "秘密情報を画面に表示している可能性"),
    ("SECRET-LOG", r"(print|logging\.\w+|logger\.\w+)\([^)]*(api_key|API_KEY|secret|token)", "秘密情報をログ・コンソールに出している可能性"),
    ("CACHE", r"@?st\.cache_(data|resource)|@st\.cache\b", "キャッシュはすべての利用者で共有される。個人の入力・APIキー・生成結果を入れていないか確認"),
    ("GLOBAL", r"^[A-Za-z_]+\s*(:\s*\w+\s*)?=\s*(\[\]|\{\}|list\(\)|dict\(\))\s*$", "モジュール直下の可変オブジェクト。利用者間でデータが混ざる恐れ（session_state を使うべき箇所か確認）"),
    ("UPLOAD", r"file_uploader\(", "ファイルアップロード。サイズ・種類の制限、保存先のパス、中身をプロンプトに入れる際の注入対策を確認"),
    ("SSRF", r"requests\.(get|post)\(|httpx\.|urllib\.request|urlopen\(", "外部へのHTTP通信。URL がユーザー入力由来なら SSRF、送る中身にも注意"),
    ("PATH", r"open\([^)]*(input|uploaded|\.name|query_params)", "ユーザー由来の名前でファイルを開いている可能性（パストラバーサル）"),
    ("SQL", r"(execute|executemany)\(\s*f[\"']|\.format\(.*(SELECT|INSERT|UPDATE|DELETE)", "SQL を文字列の組み立てで作っている（SQL インジェクション）"),
    ("QUERY", r"st\.query_params|experimental_get_query_params", "URL のパラメータを信用していないか確認"),
    ("TOOLS", r"\btools\s*=|function_declarations|tool_choice|bind_tools|AgentExecutor", "LLM のツール呼び出し。LLM に渡している権限の大きさを確認"),
]

LLM_SDKS = [
    ("google-genai（Gemini）", r"from google import genai|import google\.genai"),
    ("google-generativeai（旧Gemini SDK・非推奨）", r"google\.generativeai"),
    ("openai", r"^\s*(from openai|import openai)"),
    ("anthropic（Claude）", r"^\s*(from anthropic|import anthropic)"),
    ("langchain", r"langchain"),
    ("litellm", r"litellm"),
    ("ollama", r"^\s*(from ollama|import ollama)"),
    ("mistralai / cohere", r"mistralai|^\s*import cohere"),
]
OUTPUT_LIMIT_HINT = re.compile(r"max_output_tokens|max_tokens|max_completion_tokens")
INPUT_LIMIT_HINT = re.compile(r"max_chars\s*=")
# 複数行にまたがる呼び出しを丸ごと調べるパターン: (ID, 呼び出しの正規表現, 中身の条件, 説明)
CALL_SPAN = r"\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\)"
CALL_PATTERNS = [
    ("SECRET-UI", r"text_input" + CALL_SPAN,
     r"value\s*=\s*[^,)]*(key|secret|token|getenv|environ|st\.secrets)",
     "秘密情報を入力欄の初期値にしている（type=\"password\" でも値はブラウザに送られ、公開時は誰でも取り出せる）"),
    ("LIMIT-MODEL", r"text_input" + CALL_SPAN, r"(?i)model|モデル",
     "モデル名を自由入力できる。高額モデルを選ばれる・未知モデルへの送信に注意（公開時）"),
]


def mask(value: str) -> str:
    return f"{value[:4]}…（{len(value)}文字・伏せ字）"


def iter_files(root: Path):
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if path.is_file() and path.stat().st_size <= MAX_BYTES:
            yield path


def read_text(path: Path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="replace")


def scan_secrets_in_text(text: str):
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pat in SECRET_PATTERNS:
            for m in pat.finditer(line):
                hits.append((lineno, name, mask(m.group(0))))
        for m in GENERIC_SECRET.finditer(line):
            value = m.group(2)
            if (PLACEHOLDER.search(value) or any(p.search(value) for _, p in SECRET_PATTERNS)
                    or re.search(r"[(\[{]", value) or re.fullmatch(r"[A-Za-z_]\w*(\.\w+)+", value)):
                continue  # プレースホルダー・コード（関数呼び出しや変数名）は除く
            hits.append((lineno, f"{m.group(1)} に直書きの値（要確認）", mask(value)))
    return hits


def git(root: Path, *args):
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(f"# スキャン結果: {root}\n")
    print("※ ヒットは調べる候補。必ずコードを読んで本当に問題か判断すること。\n")

    files = list(iter_files(root))
    rel = lambda p: p.relative_to(root).as_posix()
    texts = {p: t for p in files if (t := read_text(p)) is not None}
    py_files = [p for p in texts if p.suffix == ".py"]

    # ---- 構成
    print("## 構成")
    streamlit_files = [rel(p) for p in py_files if re.search(r"import streamlit|from streamlit", texts[p])]
    print(f"- Streamlit を使うファイル: {', '.join(streamlit_files) or 'なし'}")
    sdks = sorted({name for name, pat in LLM_SDKS for p in py_files if re.search(pat, texts[p], re.M)})
    print(f"- 検出した LLM SDK: {', '.join(sdks) or 'なし'}")
    interesting = [".env", ".env.example", ".gitignore", ".streamlit/secrets.toml", ".streamlit/config.toml",
                   "requirements.txt", "pyproject.toml", "Pipfile", "poetry.lock", "uv.lock",
                   "Dockerfile", "docker-compose.yml", "Procfile", "app.yaml", "fly.toml", "render.yaml"]
    present = [f for f in interesting if (root / f).exists()]
    print(f"- 存在する設定・公開関連ファイル: {', '.join(present) or 'なし'}")
    print(f"- 出力トークン上限の指定（max_tokens 等）: {'あり' if any(OUTPUT_LIMIT_HINT.search(texts[p]) for p in py_files) else '見つからない'}")
    print(f"- 入力文字数の制限（max_chars）: {'あり' if any(INPUT_LIMIT_HINT.search(texts[p]) for p in py_files) else '見つからない'}")
    print()

    # ---- 秘密情報（作業ツリー）
    print("## 秘密情報らしき値（ファイル内）")
    found = False
    for p, t in texts.items():
        for lineno, name, masked in scan_secrets_in_text(t):
            found = True
            print(f"- {rel(p)}:{lineno}  {name}  {masked}")
    # .env 系はスキップ対象外にしたいので個別に見る（.env はディレクトリ除外名と同じため）
    for p in root.glob(".env*"):
        if p.is_file() and p not in texts and (t := read_text(p)):
            for lineno, name, masked in scan_secrets_in_text(t):
                found = True
                print(f"- {rel(p)}:{lineno}  {name}  {masked}")
    if not found:
        print("- なし")
    env, example = root / ".env", root / ".env.example"
    if env.is_file() and example.is_file() and env.read_bytes() == example.read_bytes():
        print("- メモ: .env と .env.example が同一内容（.env にキーが未設定か、.env.example に本物のキーが入っているかのどちらか）")
    print()

    # ---- .gitignore と git
    print("## .gitignore / git")
    gi = (root / ".gitignore").read_text(encoding="utf-8", errors="replace") if (root / ".gitignore").exists() else None
    if gi is None:
        print("- .gitignore がない")
    else:
        for target in [".env", ".streamlit/secrets.toml"]:
            ok = any(line.strip().rstrip("/") in (target, target.split("/")[-1], "*" + target, ".env*", ".env.*")
                     or (target == ".streamlit/secrets.toml" and line.strip() in (".streamlit/", ".streamlit"))
                     for line in gi.splitlines())
            print(f"- {target}: {'除外されている' if ok else '除外されていない（要確認）'}")
    if (root / ".git").exists():
        tracked = git(root, "ls-files") or ""
        bad = [f for f in tracked.splitlines() if re.search(r"(^|/)\.env$|secrets\.toml$|\.pem$|\.key$", f)]
        print(f"- git が管理している秘密ファイル: {', '.join(bad) or 'なし'}")
        log = git(root, "log", "--all", "-p", "--no-color", "--no-ext-diff") or ""
        hist = []
        for line in log.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                hist += [(n, m) for _, n, m in scan_secrets_in_text(line[1:])]
        if hist:
            print("- 過去のコミットに秘密情報らしき値: " + "; ".join(f"{n} {m}" for n, m in hist[:10]))
            print("  （履歴に残ったキーはファイルから消しても取り出せる。キーの無効化・再発行が必要）")
        else:
            print("- 過去のコミット: 秘密情報らしき値なし")
        remote = (git(root, "remote", "-v") or "").strip()
        print(f"- リモート: {remote.splitlines()[0] if remote else 'なし'}")
    else:
        print("- git リポジトリではない")
    print()

    # ---- コードの注意パターン
    print("## コード内の注意パターン")
    any_hit = False
    for pid, pat, note in CODE_PATTERNS:
        rx = re.compile(pat, re.M)
        locs = []
        for p in py_files:
            for lineno, line in enumerate(texts[p].splitlines(), 1):
                if rx.search(line):
                    locs.append(f"{rel(p)}:{lineno}")
        if locs:
            any_hit = True
            shown = ", ".join(locs[:8]) + (f" ほか{len(locs) - 8}件" if len(locs) > 8 else "")
            print(f"- [{pid}] {note}\n    場所: {shown}")
    for pid, call, cond, note in CALL_PATTERNS:
        locs = []
        for p in py_files:
            for m in re.finditer(call, texts[p], re.S):
                if re.search(cond, m.group(0)):
                    locs.append(f"{rel(p)}:{texts[p].count(chr(10), 0, m.start()) + 1}")
        if locs:
            any_hit = True
            print(f"- [{pid}] {note}\n    場所: {', '.join(locs[:8])}")
    if not any_hit:
        print("- なし")
    print()

    # ---- Streamlit 設定
    print("## .streamlit/config.toml")
    cfg = root / ".streamlit" / "config.toml"
    if cfg.exists():
        text = cfg.read_text(encoding="utf-8", errors="replace")
        for key in ["enableXsrfProtection", "enableCORS", "showErrorDetails", "address", "maxUploadSize", "headless"]:
            m = re.search(rf"^\s*{key}\s*=\s*(.+)$", text, re.M)
            print(f"- {key}: {m.group(1).strip() if m else '未設定（Streamlit の既定値）'}")
    else:
        print("- なし（すべて Streamlit の既定値）")
    print()

    # ---- 依存関係
    print("## 依存関係")
    req = root / "requirements.txt"
    if req.exists():
        lines = [l.strip() for l in req.read_text(encoding="utf-8", errors="replace").splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        unpinned = [l for l in lines if "==" not in l]
        print(f"- requirements.txt: {len(lines)}件、うちバージョン固定（==）なし: {', '.join(unpinned) or 'なし'}")
    else:
        print("- requirements.txt なし")


if __name__ == "__main__":
    main()
