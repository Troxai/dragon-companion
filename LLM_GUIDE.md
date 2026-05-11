# Gắn Model Chat cho Rồng

Mặc định rồng dùng canned responses (có sẵn). Muốn rồng trả lời thông minh bằng AI, cần cài thêm 1 trong 2 cách:

---

## Cách 1: Ollama Local (Miễn phí, chạy trên máy)

### Bước 1: Cài Ollama
Tải từ https://ollama.com → cài như app bình thường

### Bước 2: Tải model
Mở terminal (cmd/PowerShell), chạy:
```bash
ollama pull qwen3:4b
```
Đợi tải xong (~2-3GB)

### Bước 3: Chạy rồng
Rồng tự động gọi Ollama API (`http://localhost:11434`). Không cần config gì thêm.

### Đổi model khác
```bash
ollama pull llama3.2:3b
ollama pull gemma3:4b
ollama pull hermes3:8b
```
Rồi sửa trong `dragon_app.py`, dòng `self.model = "qwen3:4b"` thành model mong muốn.

---

## Cách 2: Claude API (OpenAI compatible)

Nếu có VPS chạy agent hoặc dùng API online:

Sửa trong `dragon_app.py`:
```python
class LLM:
    def __init__(self):
        self.url = "https://api.anthropic.com/v1/messages"  # URL API
        self.model = "claude-3-haiku-20240307"
        self.api_key = "YOUR_API_KEY"  # Thêm dòng này
        
    def ask(self, system_prompt, msg, callback):
        # Sửa phần này để gọi API của bạn
        ...
```

---

## Cách 3: Agent VPS (Hermes / Custom)

Nếu có agent chạy trên VPS:

```python
class LLM:
    def __init__(self):
        self.url = "http://YOUR_VPS_IP:8080/chat"  # URL agent
        self.model = "hermes"
```

---

## Test LLM đã hoạt động chưa

1. Chạy rồng
2. Click vào rồng → gõ bất kỳ câu gì không phải lệnh (`/goal`, `/stats`,...)
3. Nếu rồng trả lời bằng tiếng Việt tự nhiên → LLM hoạt động
4. Nếu rồng trả lời "LV.1 Trứng | XP: 0/100" → LLM chưa kết nối, đang dùng fallback

---

## Troubleshooting

| Lỗi | Fix |
|---|---|
| Rồng toàn fallback | Kiểm tra `ollama serve` đang chạy chưa |
| Ollama không tìm thấy | Vào http://localhost:11434 xem có hiện "Ollama is running" không |
| Model chưa có | `ollama list` để kiểm tra, `ollama pull <model>` để tải |
| Timeout | Model quá nặng so với RAM, dùng model nhỏ hơn (qwen3:4b, llama3.2:3b) |
