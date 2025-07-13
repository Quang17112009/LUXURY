import json
import asyncio
import datetime
import aiohttp
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Thêm import cho Flask và threading
from flask import Flask
from threading import Thread

# ==== Cấu hình ====
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8137068939:AAG19xO92yXsz_d9vz_m2aJW2Wh8JZnvSPQ") # Đã cập nhật TOKEN
ADMIN_ID = int(os.getenv("ADMIN_ID", "6915752059")) # Đã cập nhật ADMIN_ID
USER_FILE = "users.json"
STATUS_FILE = "status.json"
SUNWIN_API_URL = "https://sunwin-taixiu-1.onrender.com/taixiu" 

# ==== Keyboard layouts ====
def get_user_keyboard():
    """Keyboard cho người dùng thường"""
    keyboard = [
        ["📆 Kiểm tra thời hạn", "🎮 Chọn game"],
        ["📞 Liên hệ Admin", "ℹ️ Trợ giúp"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def get_admin_keyboard():
    """Keyboard cho admin"""
    keyboard = [
        ["📆 Kiểm tra thời hạn", "🎮 Chọn game"],
        ["👑 Thêm key", "🗑️ Xóa key"],
        ["📋 Danh sách user", "📦 Backup dữ liệu"],
        ["📊 Trạng thái bot", "📞 Liên hệ Admin"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

# ==== Quản lý người dùng ====
def load_users():
    """Tải danh sách người dùng"""
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    """Lưu danh sách người dùng"""
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_user_active(user_id):
    """Kiểm tra người dùng có đang hoạt động"""
    users = load_users()
    info = users.get(str(user_id), {})
    return info.get("active", False)

def is_admin(user_id):
    """Kiểm tra quyền admin"""
    return user_id == ADMIN_ID

# ==== Trạng thái tổng ====
def get_status():
    """Lấy trạng thái bot"""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("status", "off")
    except:
        return "off"

def set_status(value):
    """Đặt trạng thái bot"""
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({"status": value}, f)

# ==== API Functions ====
async def fetch_sunwin_data():
    """Lấy dữ liệu từ Sunwin API (API mới trả về JSON)"""
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(SUNWIN_API_URL) as response:
                if response.status == 200:
                    data = await response.json() # Đọc phản hồi dưới dạng JSON
                    return data
                else:
                    print(f"API Error: Status {response.status}")
                    return None
    except asyncio.TimeoutError:
        print("API Timeout Error")
        return None
    except Exception as e:
        print(f"API Error: {str(e)}")
        return None

def format_sunwin_result(data):
    """Format kết quả Sunwin để gửi cho người dùng (đã cập nhật cho JSON)"""
    if not data:
        return "❌ Không thể lấy dữ liệu từ Sunwin"
    
    try:
        # Lấy thông tin từ JSON parsed data
        phien_truoc = data.get('phien_truoc', 'N/A')
        ket_qua = data.get('ket_qua', 'N/A')
        dice = data.get('Dice', [])
        phien_hien_tai = data.get('phien_hien_tai', 'N/A')
        du_doan = data.get('du_doan', 'N/A')
        do_tin_cay = data.get('do_tin_cay', 'N/A')
        cau = data.get('cau', 'N/A')
        ngay = data.get('ngay', 'N/A') # Lấy trường 'ngay' mới

        # Format dice string
        dice_str = "-".join(map(str, dice)) if dice else 'N/A'

        # Sử dụng mẫu tin nhắn mới được cung cấp
        message = (
            f"🏆 <b>SUNWIN LUXURY VIP</b> 🏆\n"
            f"🎯 Phiên: <code>{phien_truoc}</code>\n" 
            f"🎲 Kết quả: <b>{ket_qua}</b>\n"
            f"🧩 Pattern: <code>{cau}</code>\n"
            f"🎮 Phiên: <code>{phien_hien_tai}</code> : <b>{du_doan}</b> (MODEL BASIC)\n" 
            f"🌟 Độ tin cậy: <code>🔥 {do_tin_cay} 🔥</code>\n"
            f"⏰ Thời Gian: <code>{ngay.split(' ')[0]}</code>\n" # Lấy chỉ phần thời gian từ trường 'ngay'
            f"🪼 <b>LUXURY VIP BOT PREMIUM</b> 🪼"
        )
        
        return message
    except Exception as e:
        return f"❌ Lỗi xử lý dữ liệu: {str(e)}"

# ==== Auto Notification Function ====
async def send_auto_notification(context: ContextTypes.DEFAULT_TYPE):
    """Gửi thông báo tự động cho tất cả user active"""
    # Kiểm tra trạng thái bot
    if get_status() != "on":
        return
    
    # Lấy dữ liệu từ API
    data = await fetch_sunwin_data()
    message = format_sunwin_result(data)
    
    # Lấy danh sách user active
    users = load_users()
    active_users = []
    
    for user_id, info in users.items():
        # Kiểm tra user có active và key còn hạn
        if info.get("active", False):
            try:
                expire = datetime.datetime.fromisoformat(info["expire"])
                if datetime.datetime.now() < expire:
                    active_users.append(int(user_id))
            except:
                continue
    
    # Gửi tin nhắn cho tất cả user active
    sent_count = 0
    for user_id in active_users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="HTML"
            )
            sent_count += 1
            # Delay nhỏ để tránh spam
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Không thể gửi cho user {user_id}: {str(e)}")
    
    print(f"Auto notification sent to {sent_count} users")

# ==== Lệnh bắt đầu ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /start"""
    if not update.message or not update.effective_user:
        return
    
    user = update.effective_user
    user_id = user.id
    
    # Chọn keyboard phù hợp
    if is_admin(user_id):
        keyboard = get_admin_keyboard()
        role_text = "👑 ADMIN"
        extra_info = "\n🔹 Sử dụng /bat để bật bot\n🔹 Sử dụng /tat để tắt bot"
    else:
        keyboard = get_user_keyboard()
        role_text = "👤 NGƯỜI DÙNG"
        extra_info = ""
    
    welcome = (
        f"🌟 <b>CHÀO MỪNG ĐẾN BOT VIP PRO</b> 🌟\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Người dùng: <b>{user.full_name}</b>\n"
        f"🎭 Vai trò: <b>{role_text}</b>\n\n"
        "🔑 Hỗ trợ phân tích & dự đoán kết quả\n"
        "📌 Game: <b>SUNWIN.US</b>\n"
        "👑 Dành cho thành viên có key\n"
        f"{extra_info}\n\n"
        "⬇️ Sử dụng các nút bên dưới để điều khiển bot ⬇️"
    )
    
    await update.message.reply_text(
        welcome, 
        parse_mode="HTML", 
        reply_markup=keyboard
    )

# ==== Admin Commands ====
async def bat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /bat - Bật bot (chỉ admin)"""
    if not update.message or not update.effective_user:
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này.")
        return
    
    set_status("on")
    
    # Gửi thông báo cho tất cả user active
    users = load_users()
    active_users = []
    
    for user_id, info in users.items():
        if info.get("active", False):
            try:
                expire = datetime.datetime.fromisoformat(info["expire"])
                if datetime.datetime.now() < expire:
                    active_users.append(int(user_id))
            except:
                continue
    
    notification_message = (
        "🟢 <b>BOT ĐÃ ĐƯỢC BẬT</b>\n\n"
        "🎮 Game: <b>SUNWIN.US</b>\n"
        "⏰ Chu kì gửi: <b>30 giây</b>\n"
        "📡 Bạn sẽ nhận được kết quả tự động\n\n"
        "💎 Bot VIP Pro đang hoạt động!"
    )
    
    sent_count = 0
    for user_id in active_users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=notification_message,
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception as e:
            print(f"Không thể gửi thông báo bật bot cho user {user_id}: {str(e)}")
    
    await update.message.reply_text(
        f"🟢 <b>BOT ĐÃ ĐƯỢC BẬT</b>\n\n"
        f"📡 Đã thông báo cho {sent_count} user active\n"
        f"⏰ Tự động gửi kết quả mỗi 30 giây",
        parse_mode="HTML"
    )

async def tat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh /tat - Tắt bot (chỉ admin)"""
    if not update.message or not update.effective_user:
        return
    
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này.")
        return
    
    set_status("off")
    
    # Gửi thông báo cho tất cả user active
    users = load_users()
    active_users = []
    
    for user_id, info in users.items():
        if info.get("active", False):
            try:
                expire = datetime.datetime.fromisoformat(info["expire"])
                if datetime.datetime.now() < expire:
                    active_users.append(int(user_id))
            except:
                continue
    
    notification_message = (
        "🔴 <b>BOT ĐÃ ĐƯỢC TẮT</b>\n\n"
        "⏸️ Tạm dừng gửi kết quả tự động\n"
        "🎮 Game: <b>SUNWIN.US</b>\n\n"
        "💎 Bot VIP Pro đã dừng hoạt động!"
    )
    
    sent_count = 0
    for user_id in active_users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=notification_message,
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception as e:
            print(f"Không thể gửi thông báo tắt bot cho user {user_id}: {str(e)}")
    
    await update.message.reply_text(
        f"🔴 <b>BOT ĐÃ ĐƯỢC TẮT</b>\n\n"
        f"📡 Đã thông báo cho {sent_count} user active\n"
        f"⏸️ Dừng gửi kết quả tự động",
        parse_mode="HTML"
    )

# ==== Xử lý tin nhắn nút ====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý tin nhắn từ nút bấm"""
    if not update.message or not update.effective_user:
        return
    
    text = update.message.text
    if not text:
        return
    
    user_id = update.effective_user.id
    
    # Kiểm tra quyền admin cho các chức năng admin
    admin_functions = [
        "👑 Thêm key", "🗑️ Xóa key", "📋 Danh sách user", 
        "📦 Backup dữ liệu", "📊 Trạng thái bot"
    ]
    
    if text in admin_functions and not is_admin(user_id):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng chức năng này.")
        return
    
    # Xử lý các nút
    if text == "📆 Kiểm tra thời hạn":
        await check_expire(update, context)
    elif text == "🎮 Chọn game":
        await select_game(update, context)
    elif text == "📞 Liên hệ Admin":
        await contact_admin(update, context)
    elif text == "ℹ️ Trợ giúp":
        await show_help(update, context)
    elif text == "👑 Thêm key":
        await prompt_add_key(update, context)
    elif text == "🗑️ Xóa key":
        await prompt_delete_key(update, context)
    elif text == "📋 Danh sách user":
        await list_users(update, context)
    elif text == "📦 Backup dữ liệu":
        await backup_users(update, context)
    elif text == "📊 Trạng thái bot":
        await check_bot_status(update, context)
    else:
        # Xử lý input cho add key và delete key
        await handle_admin_input(update, context)

# ==== Các chức năng người dùng ====
async def check_expire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiểm tra thời hạn key"""
    if not update.message or not update.effective_user:
        return
    
    user_id = str(update.effective_user.id)
    users = load_users()
    
    if user_id in users:
        expire = datetime.datetime.fromisoformat(users[user_id]["expire"])
        now = datetime.datetime.now()
        if expire > now:
            remain = expire - now
            bot_status = "🟢 Đang hoạt động" if get_status() == "on" else "🔴 Đã tắt"
            await update.message.reply_text(
                f"✅ Key còn hạn: {remain.days} ngày\n"
                f"📊 Trạng thái bot: {bot_status}"
            )
        else:
            await update.message.reply_text("❌ Key đã hết hạn.")
    else:
        await update.message.reply_text("❌ Chưa kích hoạt! Liên hệ admin.")

async def select_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chọn game"""
    if not update.message or not update.effective_user:
        return
    
    user_id = str(update.effective_user.id)
    users = load_users()
    
    if user_id not in users:
        await update.message.reply_text("❌ Bạn chưa có key. Liên hệ admin để kích hoạt.")
        return
    
    # Kiểm tra key có còn hạn không
    expire = datetime.datetime.fromisoformat(users[user_id]["expire"])
    if datetime.datetime.now() >= expire:
        await update.message.reply_text("❌ Key đã hết hạn. Liên hệ admin để gia hạn.")
        return
    
    # Kích hoạt user để nhận thông báo tự động
    users[user_id]["active"] = True
    save_users(users)
    
    bot_status = get_status()
    status_text = "🟢 Đang hoạt động" if bot_status == "on" else "🔴 Đã tắt"
    
    await update.message.reply_text(
        f"🎮 <b>Đã chọn game SUNWIN.US</b>\n\n"
        f"📊 Trạng thái bot: {status_text}\n"
        f"🔑 Bạn đã được kích hoạt nhận kết quả tự động\n\n"
        f"💡 Khi admin bật bot, bạn sẽ nhận kết quả mỗi 30 giây",
        parse_mode="HTML"
    )

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liên hệ admin"""
    if not update.message:
        return
    
    keyboard = [[InlineKeyboardButton("📞 Liên hệ Admin", url="https://t.me/nhutquangdz")]] 
    await update.message.reply_text(
        "📞 Để liên hệ với admin, vui lòng nhấn nút bên dưới:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị trợ giúp"""
    if not update.message:
        return
    
    help_text = (
        "ℹ️ <b>HƯỚNG DẪN SỬ DỤNG BOT</b>\n\n"
        "🔹 <b>📆 Kiểm tra thời hạn:</b> Xem thời gian còn lại của key\n"
        "🔹 <b>🎮 Chọn game:</b> Chọn game SUNWIN.US và kích hoạt nhận thông báo\n"
        "🔹 <b>📞 Liên hệ Admin:</b> Liên hệ để hỗ trợ\n\n"
        "🎯 <b>Hệ thống tự động:</b>\n"
        "• Khi admin bật bot, bạn sẽ nhận kết quả mỗi 30 giây\n"
        "• Khi admin tắt bot, hệ thống sẽ dừng gửi kết quả\n\n"
        "💡 <b>Lưu ý:</b> Cần có key hợp lệ và chọn game để nhận thông báo"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

# ==== Các chức năng admin ====
async def prompt_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yêu cầu nhập thông tin để thêm key"""
    if not update.message:
        return
    
    if context.user_data is None:
        context.user_data = {}
    
    context.user_data['waiting_for'] = 'add_key'
    await update.message.reply_text(
        "👑 <b>THÊM KEY CHO NGƯỜI DÙNG</b>\n\n"
        "Vui lòng nhập theo định dạng:\n"
        "<code>user_id số_ngày</code>\n\n"
        "Ví dụ: <code>123456789 30</code>",
        parse_mode="HTML"
    )

async def prompt_delete_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yêu cầu nhập thông tin để xóa key"""
    if not update.message:
        return
    
    if context.user_data is None:
        context.user_data = {}
    
    context.user_data['waiting_for'] = 'delete_key'
    await update.message.reply_text(
        "🗑️ <b>XÓA KEY NGƯỜI DÙNG</b>\n\n"
        "Vui lòng nhập user_id cần xóa:\n\n"
        "Ví dụ: <code>123456789</code>",
        parse_mode="HTML"
    )

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý input từ admin"""
    if not update.message or not update.effective_user:
        return
    
    # Kiểm tra nếu không phải admin thì bỏ qua
    if not is_admin(update.effective_user.id):
        return
    
    # Kiểm tra user_data và waiting_for
    if not context.user_data or 'waiting_for' not in context.user_data:
        return
    
    waiting_for = context.user_data['waiting_for']
    text = update.message.text
    
    if not text:
        return
    
    if waiting_for == 'add_key':
        await process_add_key(update, context, text)
    elif waiting_for == 'delete_key':
        await process_delete_key(update, context, text)
    
    # Xóa trạng thái chờ
    if 'waiting_for' in context.user_data:
        del context.user_data['waiting_for']

async def process_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Xử lý thêm key"""
    if not update.message:
        return
    
    try:
        parts = text.strip().split()
        if len(parts) != 2:
            raise ValueError("Sai định dạng")
        
        user_id = parts[0]
        days = int(parts[1])
        
        users = load_users()
        expire_date = datetime.datetime.now() + datetime.timedelta(days=days)
        users[user_id] = {"expire": expire_date.isoformat(), "active": True}
        save_users(users)
        
        await update.message.reply_text(
            f"✅ Đã kích hoạt key cho user <code>{user_id}</code> ({days} ngày)",
            parse_mode="HTML"
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Sai định dạng! Vui lòng nhập: <code>user_id số_ngày</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")

async def process_delete_key(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Xử lý xóa key"""
    if not update.message:
        return
    
    try:
        user_id = text.strip()
        users = load_users()
        
        if user_id in users:
            del users[user_id]
            save_users(users)
            await update.message.reply_text(
                f"✅ Đã xóa key của user <code>{user_id}</code>",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(
                f"❌ Không tìm thấy user <code>{user_id}</code>",
                parse_mode="HTML"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liệt kê danh sách user"""
    if not update.message:
        return
    
    users = load_users()
    if not users:
        await update.message.reply_text("📋 Danh sách người dùng trống.")
        return
    
    message = "📋 <b>DANH SÁCH NGƯỜI DÙNG</b>\n\n"
    count = 0
    
    for user_id, info in users.items():
        count += 1
        expire = datetime.datetime.fromisoformat(info["expire"])
        now = datetime.datetime.now()
        
        if expire > now:
            remain = expire - now
            status = "✅ Còn hạn" if info.get("active", False) else "⏸️ Tạm dừng"
            message += f"{count}. ID: <code>{user_id}</code>\n"
            message += f"   📅 Còn: {remain.days} ngày\n"
            message += f"   📊 Trạng thái: {status}\n\n"
        else:
            message += f"{count}. ID: <code>{user_id}</code>\n"
            message += f"   ❌ Hết hạn\n\n"
    
    await update.message.reply_text(message, parse_mode="HTML")

async def backup_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Backup dữ liệu người dùng"""
    if not update.message:
        return
    
    try:
        with open(USER_FILE, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"backup_users_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                caption="📦 Backup dữ liệu người dùng"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi backup: {str(e)}")

async def check_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kiểm tra trạng thái bot"""
    if not update.message:
        return
    
    status = get_status()
    users = load_users()
    total_users = len(users)
    active_users = sum(1 for info in users.values() if info.get("active", False))
    
    status_text = "🟢 Đang hoạt động" if status == "on" else "🔴 Đã tắt"
    
    message = (
        f"📊 <b>TRẠNG THÁI BOT</b>\n\n"
        f"🤖 Bot: {status_text}\n"
        f"👥 Tổng users: {total_users}\n"
        f"📡 Users active: {active_users}\n"
        f"🎮 Game: SUNWIN.US\n"
        f"⏰ Chu kì: 30 giây\n\n"
        f"💎 Bot VIP Pro"
    )
    
    await update.message.reply_text(message, parse_mode="HTML")

---

### Phần mã Health Check (Flask) mới được thêm

```python
# Khởi tạo Flask app
app = Flask(__name__)

# Định nghĩa điểm cuối Health Check
@app.route('/')
def health_check():
    return 'Bot is alive and running!'

# Hàm chạy Flask app trong một luồng riêng
def run_flask_app():
    # Lấy cổng từ biến môi trường PORT (đặc biệt hữu ích khi triển khai trên Render)
    # Nếu không có biến môi trường PORT, mặc định dùng cổng 5000
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
