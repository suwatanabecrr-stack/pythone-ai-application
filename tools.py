"""ライティングツールの定義。

ツールを追加したいときは、Tool を作って TOOLS に足すだけで
画面（入力フォーム）が自動的に作られます。
"""

from collections.abc import Callable
from dataclasses import dataclass, field

BASE_SYSTEM = (
    "あなたはプロの日本語ライター兼編集者です。"
    "ユーザーの指示に忠実に、読みやすく自然な文章を書いてください。"
    "前置きや「承知しました」などの返事は書かず、成果物だけを出力してください。"
)


@dataclass
class Field:
    """入力フォームの1項目。"""

    key: str
    label: str
    kind: str = "text"  # text / textarea / select / slider
    options: list[str] = field(default_factory=list)
    default: str | int | None = None
    placeholder: str = ""
    required: bool = False
    min_value: int = 0
    max_value: int = 100
    step: int = 1
    height: int = 200


@dataclass
class Tool:
    """1つのライティングツール。"""

    key: str
    name: str
    icon: str
    description: str
    fields: list[Field]
    build_prompt: Callable[[dict], str]
    system: str = ""
    temperature: float = 0.7

    @property
    def system_instruction(self) -> str:
        return f"{BASE_SYSTEM}\n{self.system}".strip()


def _line(label: str, value) -> str:
    """値が空でなければ「ラベル: 値」の行を返す。"""
    return f"- {label}: {value}\n" if value not in (None, "") else ""


TONES = ["丁寧・フォーマル", "親しみやすい", "カジュアル", "ビジネスライク", "熱意がある", "落ち着いた"]


# ---------------------------------------------------------------- ブログ
def _blog(v: dict) -> str:
    return (
        "以下の条件で、SEOを意識したブログ記事を執筆してください。\n\n"
        + _line("テーマ", v["topic"])
        + _line("メインキーワード（上位表示を狙う検索語）", v["main_keyword"])
        + _line("検索意図", v["intent"])
        + _line("関連キーワード", v["keywords"])
        + _line("想定読者", v["audience"])
        + _line("文体", v["tone"])
        + _line("文字数の目安", f"約{v['length']}文字")
        + _line("補足・盛り込みたい内容", v["notes"])
        + "\n# 出力形式（Markdown）\n"
        "1. 1行目: 記事タイトルを `# ` で書く。32文字前後で、メインキーワードをなるべく前半に入れる\n"
        "2. 2行目: `> メタディスクリプション: ` に続けて、メインキーワードを含む120文字前後の記事要約を書く\n"
        "3. 導入文: 最初の段落にメインキーワードを入れ、読者の悩みへの共感と「この記事でわかること」を示す\n"
        "4. 本文: `##`（大見出し）と `###`（小見出し）で階層構造にし、見出しにも関連キーワードを自然に入れる\n"
        "5. 箇条書きや表を適宜使い、結論を先に述べてから理由・具体例を説明する\n"
        "6. 終盤に `## よくある質問` を設け、検索されそうな質問を3つ程度 `###` の質問＋回答の形で書く\n"
        "7. 最後に `## まとめ` で要点を振り返り、読者が次に取るべき行動を示す\n"
        "\nキーワードは不自然に繰り返さず、検索意図に正面から答える内容を最優先してください。\n"
    )


# ---------------------------------------------------------------- メール返信
def _email(v: dict) -> str:
    return (
        "以下の受信メールへの返信文を作成してください。\n\n"
        f"# 受信メール\n{v['received']}\n\n"
        "# 返信の条件\n"
        + _line("相手との関係", v["relation"])
        + _line("返信の方針", v["stance"])
        + _line("伝えたい要点", v["points"])
        + _line("差出人（自分）の名前", v["sender"])
        + _line("トーン", v["tone"])
        + f"\n返信文の案を{v['variations']}パターン作成し、"
        "それぞれ「件名」と「本文」を書いてください。"
        "パターンごとに `## 案1` のように見出しを付けてください。"
    )


# ---------------------------------------------------------------- 要約
def _summary(v: dict) -> str:
    styles = {
        "箇条書き": "重要なポイントを箇条書きでまとめる",
        "短い文章": "自然な文章で簡潔にまとめる",
        "3行要約": "ちょうど3行でまとめる",
        "結論ファースト": "最初に結論を1文で述べ、その後に根拠・詳細を箇条書きで示す",
    }
    return (
        "以下の文章を要約してください。\n\n"
        f"# 要約の形式\n- {styles[v['style']]}\n"
        + _line("長さの目安", f"約{v['length']}文字")
        + _line("特に注目してほしい観点", v["focus"])
        + f"\n# 元の文章\n{v['text']}"
    )


# ---------------------------------------------------------------- 校正
def _proofread(v: dict) -> str:
    return (
        f"以下の文章を「{v['level']}」のレベルで校正・推敲してください。\n\n"
        "# 出力形式\n"
        "## 修正後の文章\n（修正した全文）\n\n"
        "## 主な修正点\n（何をなぜ直したかを箇条書きで）\n\n"
        f"# 元の文章\n{v['text']}"
    )


# ---------------------------------------------------------------- リライト
def _rewrite(v: dict) -> str:
    return (
        "以下の文章を、意味を保ったまま書き換えてください。\n\n"
        + _line("目的", v["purpose"])
        + _line("トーン", v["tone"])
        + _line("その他の指示", v["notes"])
        + f"\n# 元の文章\n{v['text']}"
    )


# ---------------------------------------------------------------- 翻訳
def _translate(v: dict) -> str:
    return (
        f"以下の文章を{v['target']}に翻訳してください。\n"
        + _line("スタイル", v["style"])
        + "翻訳文のみを出力し、専門用語や訳しにくい表現があれば最後に `---` の後で短く注記してください。\n\n"
        f"# 原文\n{v['text']}"
    )


# ---------------------------------------------------------------- SNS投稿
def _sns(v: dict) -> str:
    limits = {"X (Twitter)": "全角140文字以内", "Instagram": "改行や絵文字を活用", "Threads": "500文字以内", "LinkedIn": "ビジネス向け、やや長めでも可", "Facebook": "読みやすい長さ"}
    return (
        f"{v['platform']} 向けの投稿文を{v['variations']}パターン作成してください。\n\n"
        + _line("投稿内容", v["content"])
        + _line("文字数の制約", limits[v["platform"]])
        + _line("トーン", v["tone"])
        + _line("ハッシュタグ", "適切なものを3〜5個付ける" if v["hashtags"] == "付ける" else "付けない")
        + "\nパターンごとに `## 案1` のように見出しを付けてください。"
    )


# ---------------------------------------------------------------- タイトル・キャッチコピー
def _titles(v: dict) -> str:
    return (
        f"以下の内容に対して、{v['kind']}を{v['count']}個提案してください。\n\n"
        + _line("内容・商品・記事の概要", v["content"])
        + _line("ターゲット", v["audience"])
        + _line("方向性", v["tone"])
        + "\n番号付きリストで出力し、それぞれに狙い（なぜ効果的か）を一言添えてください。"
    )


# ---------------------------------------------------------------- 文章の続き・アイデア出し
def _ideas(v: dict) -> str:
    return (
        f"「{v['theme']}」について、{v['kind']}を{v['count']}個出してください。\n"
        + _line("補足", v["notes"])
        + "\n番号付きリストで、それぞれ簡単な説明を付けてください。"
    )


# ---------------------------------------------------------------- 自由入力
def _free(v: dict) -> str:
    return v["prompt"]


TOOLS: list[Tool] = [
    Tool(
        key="blog",
        name="ブログ執筆",
        icon="📝",
        description="キーワードと検索意図をもとに、SEOを意識した見出し付きのブログ記事を書きます。",
        temperature=0.8,
        system=(
            "あなたはSEOに精通したプロのWebライターです。"
            "Googleの検索品質評価ガイドライン（E-E-A-T：経験・専門性・権威性・信頼性）を意識し、"
            "検索ユーザーの悩みを解決する、具体的で網羅性の高い記事を書いてください。"
            "キーワードを不自然に詰め込むことはせず、読みやすさを最優先にしてください。"
        ),
        fields=[
            Field("topic", "記事のテーマ", placeholder="例: 在宅ワークで集中力を保つ方法", required=True),
            Field("main_keyword", "メインキーワード（上位表示を狙う検索語）", placeholder="例: 在宅ワーク 集中力", required=True),
            Field("intent", "検索意図（読者が知りたいこと）", kind="select", options=["方法・やり方を知りたい", "意味・基礎知識を知りたい", "比較・違いを知りたい", "おすすめを知りたい", "原因・解決策を知りたい", "体験談・口コミを知りたい"]),
            Field("keywords", "関連キーワード（カンマ区切り・任意）", placeholder="例: ポモドーロ, 作業環境, 集中できない"),
            Field("audience", "想定読者", placeholder="例: 在宅勤務を始めたばかりの会社員"),
            Field("tone", "文体", kind="select", options=["です・ます調", "だ・である調", "会話調", "専門的"]),
            Field("length", "文字数の目安", kind="slider", default=2000, min_value=500, max_value=6000, step=500),
            Field("notes", "補足・盛り込みたい内容", kind="textarea", height=100),
        ],
        build_prompt=_blog,
    ),
    Tool(
        key="email",
        name="メール返信",
        icon="✉️",
        description="受け取ったメールを貼り付けると、返信文の案を作ります。",
        fields=[
            Field("received", "受信したメール", kind="textarea", required=True, placeholder="ここに受信メールを貼り付け"),
            Field("relation", "相手との関係", kind="select", options=["取引先・顧客", "社内の上司", "社内の同僚・部下", "友人・知人", "その他"]),
            Field("stance", "返信の方針", kind="select", options=["承諾する", "丁寧に断る", "質問・確認する", "お礼を伝える", "日程調整する", "お詫びする", "内容に応じて判断"]),
            Field("points", "伝えたい要点（任意）", kind="textarea", height=100, placeholder="例: 来週火曜なら対応可能、資料は金曜までに送る"),
            Field("sender", "自分の名前（署名用・任意）"),
            Field("tone", "トーン", kind="select", options=TONES),
            Field("variations", "パターン数", kind="slider", default=2, min_value=1, max_value=3),
        ],
        build_prompt=_email,
    ),
    Tool(
        key="summary",
        name="文章要約",
        icon="📄",
        description="長い文章を、指定した形式で短くまとめます。",
        temperature=0.3,
        fields=[
            Field("text", "要約したい文章", kind="textarea", required=True, height=300),
            Field("style", "要約の形式", kind="select", options=["箇条書き", "短い文章", "3行要約", "結論ファースト"]),
            Field("length", "長さの目安（文字）", kind="slider", default=300, min_value=50, max_value=1500, step=50),
            Field("focus", "注目してほしい観点（任意）", placeholder="例: コスト面, 今後のスケジュール"),
        ],
        build_prompt=_summary,
    ),
    Tool(
        key="proofread",
        name="校正・推敲",
        icon="✅",
        description="誤字脱字や不自然な表現を直し、修正点を説明します。",
        temperature=0.2,
        fields=[
            Field("text", "校正したい文章", kind="textarea", required=True, height=300),
            Field("level", "校正レベル", kind="select", options=["誤字脱字のみ", "読みやすさも改善", "大幅に推敲"]),
        ],
        build_prompt=_proofread,
    ),
    Tool(
        key="rewrite",
        name="リライト",
        icon="🔄",
        description="文章のトーンや長さ、対象読者に合わせて書き換えます。",
        fields=[
            Field("text", "書き換えたい文章", kind="textarea", required=True, height=250),
            Field("purpose", "目的", kind="select", options=["わかりやすく", "短く簡潔に", "詳しく膨らませる", "子ども向けに", "専門家向けに", "言い回しを変える（重複回避）"]),
            Field("tone", "トーン", kind="select", options=["変えない"] + TONES),
            Field("notes", "その他の指示（任意）"),
        ],
        build_prompt=_rewrite,
    ),
    Tool(
        key="translate",
        name="翻訳",
        icon="🌐",
        description="自然な表現で多言語に翻訳します。",
        temperature=0.3,
        fields=[
            Field("text", "翻訳したい文章", kind="textarea", required=True, height=250),
            Field("target", "翻訳先の言語", kind="select", options=["英語", "日本語", "中国語（簡体字）", "韓国語", "スペイン語", "フランス語", "ドイツ語"]),
            Field("style", "スタイル", kind="select", options=["自然な意訳", "原文に忠実な直訳", "ビジネス向け", "カジュアル"]),
        ],
        build_prompt=_translate,
    ),
    Tool(
        key="sns",
        name="SNS投稿",
        icon="📣",
        description="各SNSに合わせた投稿文を作ります。",
        temperature=0.9,
        fields=[
            Field("content", "投稿したい内容", kind="textarea", required=True, height=150),
            Field("platform", "プラットフォーム", kind="select", options=["X (Twitter)", "Instagram", "Threads", "LinkedIn", "Facebook"]),
            Field("tone", "トーン", kind="select", options=TONES),
            Field("hashtags", "ハッシュタグ", kind="select", options=["付ける", "付けない"]),
            Field("variations", "パターン数", kind="slider", default=3, min_value=1, max_value=5),
        ],
        build_prompt=_sns,
    ),
    Tool(
        key="titles",
        name="タイトル・コピー",
        icon="💡",
        description="記事タイトルやキャッチコピーの案を大量に出します。",
        temperature=1.0,
        fields=[
            Field("content", "内容・商品・記事の概要", kind="textarea", required=True, height=150),
            Field("kind", "作るもの", kind="select", options=["ブログ記事のタイトル", "キャッチコピー", "メールの件名", "YouTube動画のタイトル", "商品名・サービス名"]),
            Field("audience", "ターゲット（任意）"),
            Field("tone", "方向性", kind="select", options=["おまかせ", "数字を使って具体的に", "好奇心をくすぐる", "シンプル・端的", "エモーショナル"]),
            Field("count", "案の数", kind="slider", default=10, min_value=3, max_value=20),
        ],
        build_prompt=_titles,
    ),
    Tool(
        key="ideas",
        name="アイデア出し",
        icon="🧠",
        description="ブログネタや企画などのアイデアをブレストします。",
        temperature=1.0,
        fields=[
            Field("theme", "テーマ", required=True, placeholder="例: 料理ブログ"),
            Field("kind", "出してほしいもの", kind="select", options=["記事ネタ", "企画アイデア", "記事の構成案（見出し）", "切り口・視点", "例え話・具体例"]),
            Field("notes", "補足（任意）", kind="textarea", height=100),
            Field("count", "数", kind="slider", default=10, min_value=3, max_value=30),
        ],
        build_prompt=_ideas,
    ),
    Tool(
        key="free",
        name="フリー入力",
        icon="✨",
        description="上記に当てはまらない文章作成を自由に依頼できます。",
        fields=[
            Field("prompt", "依頼内容", kind="textarea", required=True, height=250, placeholder="例: 退職する同僚へのメッセージを3つ考えて"),
        ],
        build_prompt=_free,
    ),
]

TOOLS_BY_KEY = {t.key: t for t in TOOLS}
