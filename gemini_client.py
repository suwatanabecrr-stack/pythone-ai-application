"""Gemini API との通信を担当するモジュール。"""

from collections.abc import Iterator

from google import genai
from google.genai import types

# サイドバーで選べるモデル（公開しているため、一覧以外のモデルは選べない）
AVAILABLE_MODELS = [
    "gemini-3.8-flash",  # 先頭がデフォルト
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
]


def generate_stream(
    api_key: str,
    model: str,
    prompt: str,
    system_instruction: str,
    temperature: float,
) -> Iterator[str]:
    """プロンプトを送信し、生成されたテキストを少しずつ返す。"""
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=8192,  # 1回の生成で使う量の上限
    )
    for chunk in client.models.generate_content_stream(
        model=model, contents=prompt, config=config
    ):
        if chunk.text:
            yield chunk.text
