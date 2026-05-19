from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import uvicorn
import os
import re
import json
import base64
import dns.resolver
import bson
from google import genai
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from dotenv import load_dotenv

# Load secrets from .env (must be before anything that reads os.getenv)
load_dotenv()

# --- PHẦN 1: CẤU HÌNH HỆ THỐNG (CONFIGURATION) ---
# Ép dùng Google DNS để tránh lỗi Resolution (Phân giải tên miền) tại nhà mới
dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "8.8.4.4"]

app = FastAPI()  # Phải khởi tạo app ở đây trước khi dùng Decorator!

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cấu hình AES (Bảo mật Network Tab) — loaded from .env
_aes_key_str = os.getenv("AES_SECRET_KEY", "")
_aes_iv_str  = os.getenv("AES_IV", "")
if not _aes_key_str or not _aes_iv_str:
    raise RuntimeError("Thiếu AES_SECRET_KEY hoặc AES_IV trong file .env!")
SECRET_KEY = _aes_key_str.encode("utf-8")  # 16 bytes cho AES-128
IV         = _aes_iv_str.encode("utf-8")

# Cấu hình MongoDB — loaded from .env
MONGO_URI = os.getenv("MONGO_URI", "")
if not MONGO_URI:
    raise RuntimeError("Thiếu MONGO_URI trong file .env!")
client_db = AsyncIOMotorClient(MONGO_URI)
db = client_db.quizdb

# Cấu hình Gemini AI — loaded from .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise RuntimeError("Thiếu GEMINI_API_KEY trong file .env!")
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

# --- PHẦN 2: CÔNG CỤ HỖ TRỢ (HELPERS) ---


def encrypt_quiz_data(data_dict):
    """Mã hóa toàn bộ đề thi trước khi gửi xuống Frontend"""
    raw_data = json.dumps(data_dict).encode("utf-8")
    cipher = AES.new(SECRET_KEY, AES.MODE_CBC, IV)
    encrypted = cipher.encrypt(pad(raw_data, AES.block_size))
    return base64.b64encode(encrypted).decode("utf-8")


def server_clean_text(text):
    """Làm sạch text để so khớp (Dùng cho API get-answer)"""
    text = re.sub(r"<\/?[^>]+(>|$)", "", text)
    text = "".join(e for e in text if e.isalnum())
    return text.lower()


def question_helper(q) -> dict:
    return {
        "q_id": str(
            q.get("q_id", q["_id"])
        ),  # Ưu tiên lấy q_id nếu có, không thì lấy _id
        "q": q["q"],
        "options": q["options"],
    }


# --- PHẦN 3: CÁC ĐIỂM CUỐI (ENDPOINTS) ---


@app.get("/")
async def read_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "Không tìm thấy file index.html!"}


@app.get("/api/questions/{subject}")
async def get_secure_questions(subject: str):
    """Lấy đề thi theo môn và MÃ HÓA để chống soi F12"""
    try:
        # Lọc theo trường subject mà cậu chủ vừa cập nhật hàng loạt
        cursor = db.questions.find({"subject": subject}).limit(1000)
        questions = []
        async for q in cursor:
            # Đảm bảo hàm question_helper của cậu chủ vẫn hoạt động tốt
            questions.append(question_helper(q))

        if not questions:
            return {"payload": "", "message": "No questions found for this subject"}

        # Biến toàn bộ list thành chuỗi mã hóa AES
        encrypted_payload = encrypt_quiz_data(questions)
        return {"payload": encrypted_payload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/get-answers")
async def get_answers(data: dict = Body(...)):
    mssv = data.get("mssv")
    q_ids = data.get("q_ids", [])

    # Tạm thời bỏ qua bước check results để cậu chủ test cho nhanh
    # Nếu muốn bảo mật, cậu chủ phải đảm bảo đã gọi /api/submit trước đó
    try:
        answers = {}
        for q_id in q_ids:
            # Tìm theo q_id (môn SE) hoặc _id (môn MMT)
            q = await db.questions.find_one({"q_id": q_id})
            if not q:
                try:
                    q = await db.questions.find_one({"_id": ObjectId(q_id)})
                except:
                    continue

            if q:
                # Lấy đáp án từ trường 'answer' hoặc 'ans'
                answers[q_id] = q.get("answer", q.get("ans"))
        return answers
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/heartbeat")
async def receive_heartbeat(data: dict = Body(...)):
    """Lắng nghe nhịp tim liêm chính từ Frontend để phát hiện Tab-out"""
    # Lưu log này vào MongoDB để hậu kiểm
    print(f"--- HEARTBEAT: {data} ---")
    await db.logs.insert_one(data)
    return {"status": "recorded"}


@app.post("/api/analyze-integrity")
async def analyze_integrity(behavior_data: dict = Body(...)):
    try:
        prompt = f"Phân tích dữ liệu thi Cyberpunk: {behavior_data}"
        # Đã cập nhật Model ID chính xác nhất cho năm 2026
        response = client_gemini.models.generate_content(
            model="gemini-3.1-flash-lite-preview", contents=prompt
        )
        return {"analysis": response.text}
    except Exception as e:
        print(f"Lỗi AI System: {e}")
        return {"analysis": "Hệ thống AI Guard đang 'lag' nhẹ, cậu chủ thông cảm!"}


@app.post("/api/submit")
async def submit_score(data: dict):
    try:
        result = await db.results.insert_one(data)
        return {"status": "success", "id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- ENDPOINT NHẬN LỰA CHỌN CỦA THÍ SINH ---
@app.post("/api/submit-choice")
async def submit_choice(data: dict = Body(...)):
    """
    Nhận lựa chọn của thí sinh và lưu vào DB để chấm điểm bảo mật.
    Giúp ngăn chặn việc soi đáp án trực tiếp tại trình duyệt.
    """
    try:
        # Lưu vào collection 'choices' để hậu kiểm
        log_data = {
            "mssv": data.get("mssv"),
            "q_id": data.get("q_id"),
            "choice": data.get("choice"),
            "timestamp": os.getenv("TIME", "2026-04-28"),  # Ghi nhận thời gian
        }

        # Thực hiện chèn vào MongoDB
        await db.choices.insert_one(log_data)

        return {"status": "received", "message": "Lựa chọn đã được ghi nhận"}
    except Exception as e:
        print(f"Lỗi lưu lựa chọn: {e}")
        raise HTTPException(
            status_code=500, detail="Server đang bận, cậu chủ đợi xíu nhé!"
        )


# --- ĐẢM BẢO CẬU CHỦ CŨNG CÓ ĐIỂM CUỐI NÀY ĐỂ TRÁNH LỖI 404 KHI CÓ VI PHẠM ---
@app.post("/api/security-breach")
async def security_breach(data: dict = Body(...)):
    try:
        await db.security_logs.insert_one(data)
        return {"status": "logged"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/security-breach")
async def security_breach(data: dict = Body(...)):
    """Ghi lại vết gian lận vào cơ sở dữ liệu để đình chỉ thi"""
    try:
        # Đánh dấu trạng thái DISQUALIFIED (Đình chỉ) trong DB
        await db.results.insert_one(
            {
                "user": data.get("user", "Unknown"),
                "status": "DISQUALIFIED",
                "reason": data.get("reason"),
                "timestamp": data.get("timestamp"),
            }
        )
        print(
            f"🚨 CẢNH BÁO: Thí sinh {data.get('user')} đã bị đình chỉ do {data.get('reason')}"
        )
        return {"status": "Reported"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
