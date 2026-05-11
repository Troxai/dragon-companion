# Gắn Model Chat cho Rồng

Mặc định rồng dùng canned responses (có sẵn). Muốn rồng trả lời thông minh bằng AI, chọn 1 trong các cách dưới.

Rồng dùng chuẩn **OpenAI Compatible API** → tương thích với OpenAI, Gemini, Claude, Ollama, và mọi API có format giống OpenAI.

---

## Cách 1: Ollama Local (Miễn phí, offline)

### Cài đặt
```bash
# Tải Ollama từ https://ollama.com

# Pull model (chọn 1):
ollama pull qwen3:4b        # Nhẹ (~2.5GB), tiếng Việt tốt
ollama pull llama3.2:3b     # Meta, 2GB
ollama pull gemma3:4b       # Google, 3GB
ollama pull hermes3:8b      # Mạnh hơn (~5GB)
```

### Chạy
Rồng tự kết nối `http://localhost:11434`. Không cần config.

---

## Cách 2: OpenAI API

Sửa trong `dragon_app.py`:

```python
class LLM:
    def __init__(self):
        self.url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o-mini"
        self.api_key = "sk-xxxxxxxx"  # Thêm key OpenAI

    def ask(self, system_prompt, msg, callback):
        def go():
            try:
                data = json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": msg},
                    ],
                    "stream": False,
                    "max_tokens": 80,
                }).encode()
                req = urllib.request.Request(
                    self.url, data=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    resp = json.loads(r.read())
                    text = resp["choices"][0]["message"]["content"].strip()
                    callback(text[:200] if text else None)
            except:
                callback(None)
        threading.Thread(target=go, daemon=True).start()
```

---

## Cách 3: Google Gemini API

Miễn phí 1500 request/ngày. Lấy key tại https://aistudio.google.com/apikey

Sửa trong `dragon_app.py`:

```python
class LLM:
    def __init__(self):
        self.url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        self.api_key = "AIza..."  # Key Gemini

    def ask(self, system_prompt, msg, callback):
        def go():
            try:
                full_prompt = f"{system_prompt}\n\nUser: {msg}"
                data = json.dumps({
                    "contents": [{"parts": [{"text": full_prompt}]}],
                }).encode()
                url = f"{self.url}?key={self.api_key}"
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    resp = json.loads(r.read())
                    text = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
                    callback(text[:200] if text else None)
            except:
                callback(None)
        threading.Thread(target=go, daemon=True).start()
```

---

## Cách 4: Claude API (Anthropic)

```python
class LLM:
    def __init__(self):
        self.url = "https://api.anthropic.com/v1/messages"
        self.model = "claude-3-haiku-20240307"
        self.api_key = "sk-ant-..."  # Key Anthropic
```

---

## Cách 5: DeepSeek / Groq / TogetherAI / OpenRouter

Bất kỳ API nào có OpenAI-compatible endpoint. Chỉ cần sửa URL + model:

```python
# DeepSeek
self.url = "https://api.deepseek.com/chat/completions"
self.model = "deepseek-chat"

# Groq (miễn phí, siêu nhanh)
self.url = "https://api.groq.com/openai/v1/chat/completions"
self.model = "llama-3.2-3b-preview"

# OpenRouter (truy cập 200+ model)
self.url = "https://openrouter.ai/api/v1/chat/completions"
self.model = "google/gemini-2.0-flash-001"
```

---

## Cách 6: Agent VPS tự build

```python
self.url = "http://YOUR_VPS_IP:8080/v1/chat/completions"
self.model = "hermes-agent"
```

---

## Test xem LLM hoạt động chưa

1. Chạy rồng
2. Click vào rồng → gõ 1 câu bất kỳ (không phải lệnh `/goal`, `/stats`,...)
3. Rồng trả lời thông minh = LLM OK
4. Rồng trả lời "LV.1 Trứng | XP: 0/100" = Đang fallback, LLM chưa kết nối

---

## Bảng so sánh

| API | Giá | Độ trễ | Tiếng Việt |
|---|---|---|---|
| Ollama (qwen3:4b) | Miễn phí | Nhanh | Tốt |
| OpenAI (gpt-4o-mini) | $0.15/1M token | Nhanh | Tốt |
| Gemini (flash) | Miễn phí 1500/ngày | Nhanh | Khá |
| Groq (llama 3.2) | Miễn phí | Rất nhanh | Trung bình |
| DeepSeek | Rẻ (~$0.14/1M) | Trung bình | Rất tốt |
| Claude (haiku) | $0.25/1M token | Nhanh | Tốt |
