# Setup Supabase cho Crypto Bot

Mục tiêu:

```text
Local bot (python main.py) -> Supabase PostgreSQL <- Streamlit Cloud dashboard
```

Khi bạn chạy bot ở máy local, bot sẽ ghi dữ liệu lên Supabase. Streamlit Cloud đọc cùng database đó nên data Telegram và dashboard sẽ giống nhau.

---

## 1. Tạo Supabase project

1. Vào Supabase.
2. New project.
3. Đặt password database và lưu lại password này.
4. Chờ project tạo xong.

---

## 2. Lấy DATABASE_URL

Trong Supabase:

```text
Project Settings -> Database -> Connection string
```

Chọn dạng **Transaction pooler** hoặc **Session pooler** đều được cho bot nhỏ.

Chuỗi thường giống như:

```text
postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres
```

Thay `YOUR_PASSWORD` bằng password database bạn đặt lúc tạo project.

---

## 3. Cấu hình local Windows

Mở CMD trong folder bot, chạy:

```bat
setx DATABASE_URL "postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres"
setx OPENAI_API_KEY "sk-proj-..."
setx TELEGRAM_BOT_TOKEN "..."
setx TELEGRAM_CHAT_ID "..."
setx CMC_API_KEY "..."
```

Sau đó **đóng CMD/Terminal và mở lại** để biến môi trường có hiệu lực.

Test:

```bat
python database.py
```

Nếu đúng, bạn sẽ thấy:

```text
[DB] Database ready: Supabase/PostgreSQL
Mode: PostgreSQL/Supabase
```

---

## 4. Cấu hình Streamlit Cloud Secrets

Vào app Streamlit:

```text
App -> Settings -> Secrets
```

Dán mẫu này:

```toml
DATABASE_URL = "postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres"

OPENAI_API_KEY = "sk-proj-..."
ANTHROPIC_API_KEY = ""
GEMINI_API_KEY = ""
GROQ_API_KEY = ""
CMC_API_KEY = ""
CRYPTOPANIC_API_KEY = ""
TELEGRAM_BOT_TOKEN = "..."
TELEGRAM_CHAT_ID = "..."
```

Bấm Save rồi Reboot app.

---

## 5. Chạy bot khi nào bạn muốn

Chạy cả BTC + Alt một lần:

```bat
python main.py
```

Chỉ BTC:

```bat
python main.py --btc-only
```

Chỉ Alt:

```bat
python main.py --alt-only
```

Sau khi chạy xong, mở dashboard Streamlit Cloud và bấm Refresh/Reload là thấy dữ liệu mới.

---

## 6. File không được upload public

Không upload các file này lên GitHub:

```text
crypto_bot.db
.env
.streamlit/secrets.toml
BK_config.py
```

Repo public chỉ nên có `config.py` bản an toàn, không có API key thật.
