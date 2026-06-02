import os

try:
    import streamlit as st
except Exception:
    st = None


def get_secret(name, default=""):
    if st is not None:
        try:
            return st.secrets[name]
        except Exception:
            pass
    return os.getenv(name, default)


OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
CMC_API_KEY = get_secret("CMC_API_KEY")
TELEGRAM_BOT_TOKEN = get_secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = get_secret("TELEGRAM_CHAT_ID")
CRYPTOPANIC_API_KEY = get_secret("CRYPTOPANIC_API_KEY", "")

CMC_ENABLED = bool(CMC_API_KEY)
