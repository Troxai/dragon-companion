# Dragon Companion — Nuôi rồng desktop, tăng năng suất làm việc

Mình vừa build xong một con rồng desktop companion — bạn nuôi nó, nó giúp bạn tập trung làm việc. Toàn bộ bằng Python + PyQt6, chạy local 100%, không gửi data đi đâu.

## Con rồng làm được gì?

**Nuôi & Tiến hoá:**
Bắt đầu từ quả trứng, mỗi lần bạn hoàn thành task, focus làm việc, hay chat với nó là nó được XP. Đủ XP là tiến hoá: Trứng → Rồng con → Vị thành niên → Trưởng thành → Cổ đại → Huyền thoại. Mỗi stage có hình ảnh riêng.

**Pomodoro tích hợp:**
Click phải → Start Pomodoro. Rồng đếm ngược cùng bạn 25 phút, xong là được thưởng XP + tăng mood.

**Quản lý mục tiêu:**
Sáng mở máy, chat: `/goal học Python 2 tiếng` — rồng nhớ. Tối 9h nó tự review: "Hôm nay anh đạt 2/3 mục tiêu (67%)". Done thì `/done 1` — +25 XP.

**Chat thông minh (LLM):**
Click vô rồng → gõ chat. Nếu có Ollama (qwen3:4b) thì nó trả lời bằng tiếng Việt tự nhiên. Không có thì fallback canned responses.

**Nhắc nhở không annoying:**
- 20-20-20: mỗi 20 phút nhắc nhìn xa
- Burnout: sau 10 tiếng liên tục → cảnh báo
- Ngủ: sau 23h nhắc, sau 1h sáng rồng tự ngủ

**Gamification đầy đủ:**
- 10+ achievement badges (first_goal, pomo_5, streak_7, legend...)
- Streak ngày liên tiếp
- HP bar, mood indicator
- 4 hệ phái (Lửa/Băng/Vàng/Bóng tối)

**Privacy first:**
Tất cả data lưu local SQLite trong %APPDATA%, không gửi đi đâu. LLM gọi local Ollama hoặc không dùng.

## Tech Stack
- Python 3.12 + PyQt6 (desktop overlay)
- SQLite (local-first storage)
- Ollama API (optional LLM)
- PyInstaller (build standalone EXE)

## Cài đặt 1 click
Tải EXE từ Release → chạy → xong. Có kèm Setup.bat tạo shortcut desktop + auto-start Windows.

## Source Code
Toàn bộ code là 1 file Python duy nhất (~500 dòng), dễ đọc, dễ custom.

GitHub: [link]

## Screenshot
[Ảnh rồng các stage]

---

Thấy hay thì ⭐ repo, share cho ae dev cùng nuôi rồng!
