"""
llm_client.py
LLM wrapper với auto-fallback theo thứ tự ưu tiên:
  1. Anthropic Claude Haiku  (sk-ant-...)
  2. OpenAI GPT-4o-mini      (sk-...)
  3. Google Gemini Flash      (AIza...)
  4. Groq Llama3              (gsk_...) — FREE

Bot tự động thử provider tiếp theo nếu provider hiện tại:
  - Hết quota (429)
  - Lỗi API
  - Chưa cấu hình key

Usage:
  from llm_client import call_llm, get_active_provider
  text = call_llm("your prompt here")
"""

import os
import time

# ── Lazy load config để tránh circular import ────────────────
def _get_keys() -> dict:
    try:
        from config import (
            ANTHROPIC_API_KEY, OPENAI_API_KEY,
            GEMINI_API_KEY, GROQ_API_KEY,
        )
    except ImportError:
        ANTHROPIC_API_KEY = OPENAI_API_KEY = GEMINI_API_KEY = GROQ_API_KEY = ""

    return {
        "anthropic": (ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")).strip(),
        "openai":    (OPENAI_API_KEY    or os.environ.get("OPENAI_API_KEY", "")).strip(),
        "gemini":    (GEMINI_API_KEY    or os.environ.get("GEMINI_API_KEY", "")).strip(),
        "groq":      (GROQ_API_KEY      or os.environ.get("GROQ_API_KEY", "")).strip(),
    }


def _is_valid(key: str, prefix: str) -> bool:
    return bool(key) and key.startswith(prefix) and "..." not in key


def get_providers() -> list[str]:
    """
    Trả về list provider hợp lệ theo thứ tự ưu tiên.
    Chỉ include provider có key hợp lệ.
    """
    keys = _get_keys()
    order = []
    if _is_valid(keys["anthropic"], "sk-ant-"): order.append("anthropic")
    if _is_valid(keys["openai"],    "sk-"):     order.append("openai")
    if _is_valid(keys["gemini"],    "AIza"):    order.append("gemini")
    if _is_valid(keys["groq"],      "gsk_"):    order.append("groq")
    return order


def get_active_provider() -> str:
    """Provider đầu tiên có key hợp lệ."""
    providers = get_providers()
    return providers[0] if providers else "none"


# ════════════════════════════════════════════════════════════
#  PROVIDER CALLERS
# ════════════════════════════════════════════════════════════

def _call_anthropic(prompt: str, max_tokens: int, temperature: float) -> str:
    import anthropic
    key = _get_keys()["anthropic"]
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _call_openai(prompt: str, max_tokens: int, temperature: float) -> str:
    from openai import OpenAI
    key = _get_keys()["openai"]
    client = OpenAI(api_key=key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def _call_gemini(prompt: str, max_tokens: int, temperature: float) -> str:
    import google.generativeai as genai
    key = _get_keys()["gemini"]
    genai.configure(api_key=key)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config=genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )
    resp = model.generate_content(prompt)
    return resp.text


def _call_groq(prompt: str, max_tokens: int, temperature: float) -> str:
    from groq import Groq
    key = _get_keys()["groq"]
    client = Groq(api_key=key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


_CALLERS = {
    "anthropic": _call_anthropic,
    "openai":    _call_openai,
    "gemini":    _call_gemini,
    "groq":      _call_groq,
}


# ════════════════════════════════════════════════════════════
#  MAIN CALL — AUTO FALLBACK
# ════════════════════════════════════════════════════════════

def call_llm(
    prompt:      str,
    max_tokens:  int   = 1000,
    temperature: float = 0.3,
    retry_delay: float = 2.0,
) -> str:
    """
    Gọi LLM với auto-fallback.
    Thử từng provider theo thứ tự, bỏ qua nếu lỗi.
    Raise Exception nếu tất cả fail.
    """
    providers = get_providers()

    if not providers:
        raise Exception(
            "Không có LLM API key nào được cấu hình.\n"
            "Điền ít nhất 1 key vào config.py:\n"
            "  ANTHROPIC_API_KEY (console.anthropic.com)\n"
            "  OPENAI_API_KEY    (platform.openai.com)\n"
            "  GEMINI_API_KEY    (aistudio.google.com) — free\n"
            "  GROQ_API_KEY      (console.groq.com)    — free"
        )

    last_error = None
    for provider in providers:
        try:
            caller = _CALLERS[provider]
            result = caller(prompt, max_tokens, temperature)
            # Log provider đang dùng (chỉ khi không phải provider đầu tiên → đang fallback)
            if provider != providers[0]:
                print(f"[LLM] ✅ Dùng fallback provider: {provider}")
            return result

        except Exception as e:
            err_str = str(e)
            # Detect quota/rate limit errors
            is_quota = any(k in err_str.lower() for k in [
                "quota", "rate_limit", "rate limit",
                "insufficient_quota", "429", "too many requests",
                "resource_exhausted",
            ])
            if is_quota:
                print(f"[LLM] ⚠️  {provider} hết quota/rate limit → thử provider tiếp theo")
            else:
                print(f"[LLM] ❌ {provider} lỗi: {err_str[:80]} → thử provider tiếp theo")

            last_error = e
            time.sleep(retry_delay)
            continue

    raise Exception(f"Tất cả LLM provider đều fail. Lỗi cuối: {last_error}")


# ════════════════════════════════════════════════════════════
#  STATUS / DEBUG
# ════════════════════════════════════════════════════════════

def print_status():
    """In trạng thái tất cả provider — dùng để debug."""
    keys      = _get_keys()
    providers = get_providers()

    print("╔══════════════════════════════════════╗")
    print("║       LLM Provider Status            ║")
    print("╠══════════════════════════════════════╣")

    checks = [
        ("anthropic", "Anthropic Claude", "sk-ant-"),
        ("openai",    "OpenAI GPT",       "sk-"),
        ("gemini",    "Google Gemini",    "AIza"),
        ("groq",      "Groq Llama3",      "gsk_"),
    ]
    for key_name, label, prefix in checks:
        key    = keys[key_name]
        valid  = _is_valid(key, prefix)
        status = "✅ configured" if valid else "❌ not set"
        rank   = f"[#{providers.index(key_name)+1}]" if key_name in providers else "   "
        print(f"║ {rank} {label:<20} {status:<15} ║")

    print("╠══════════════════════════════════════╣")
    active = providers[0] if providers else "none"
    print(f"║ Active provider: {active:<20} ║")
    print("╚══════════════════════════════════════╝")


if __name__ == "__main__":
    print_status()
    providers = get_providers()
    if providers:
        print(f"\nTest call với {providers[0]}...")
        try:
            result = call_llm("Trả lời đúng 1 từ: thủ đô của Việt Nam là gì?", max_tokens=50)
            print(f"Response: {result.strip()}")
            print("✅ LLM hoạt động bình thường")
        except Exception as e:
            print(f"❌ Lỗi: {e}")
    else:
        print("\n⚠️  Chưa cấu hình key nào. Điền vào config.py")

# Backward-compatible alias: các module cũ đang gọi llm_client.get_provider()
def get_provider() -> str:
    return get_active_provider()
