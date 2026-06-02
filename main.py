from pathlib import Path
from fastapi import FastAPI, HTTPException, Body, Query
import time
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import uvicorn
import os
import re
import json
import base64
import bson
from google import genai
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from dotenv import load_dotenv

# Load secrets from .env (must be before anything that reads os.getenv)
load_dotenv()

# --- PHẦN 1: CẤU HÌNH HỆ THỐNG (CONFIGURATION) ---

# Absolute path to project root (works regardless of cwd)
BASE_DIR = Path(__file__).resolve().parent

# Only override DNS when running locally (Render sets the RENDER env var)
if not os.getenv("RENDER"):
    import dns.resolver
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

# Khóa admin cố định để bảo vệ các endpoint quản trị
ADMIN_KEY = "UET_MASTER"

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
        "options": q.get("options", []),
        "type": q.get("type", "multiple_choice"),  # short_answer or multiple_choice
    }


# --- PHẦN 3: CÁC ĐIỂM CUỐI (ENDPOINTS) ---


@app.get("/")
async def read_index():
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
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
                # Lấy đáp án: text cho short_answer, index cho multiple_choice
                if q.get("type") == "short_answer":
                    answers[q_id] = {"type": "short_answer", "ans": q.get("ans", "")}
                else:
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


# --- GHI NHẬN VI PHẠM & ĐÌNH CHỈ THÍ SINH (ĐÃ GỘP 2 HANDLER TRÙNG LẶP) ---
@app.post("/api/security-breach")
async def security_breach(data: dict = Body(...)):
    """Ghi lại vết gian lận vào security_logs VÀ đánh dấu DISQUALIFIED trong results"""
    try:
        # Bước 1: Lưu log vi phạm vào collection security_logs
        await db.security_logs.insert_one(data)

        # Bước 2: Đánh dấu trạng thái DISQUALIFIED (Đình chỉ) trong results
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
        return {"status": "logged_and_disqualified"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/dashboard/{mssv}")
async def get_dashboard_stats(mssv: str):
    """Lấy thống kê tổng hợp cho Dashboard của sinh viên"""
    try:
        # Đếm số bài thi đã hoàn thành
        quiz_count = await db.results.count_documents({"mssv": mssv, "status": "COMPLETED"})

        # Lấy lịch sử điểm gần đây
        cursor = db.results.find({"mssv": mssv}).sort("timestamp", -1).limit(20)
        history = []
        async for r in cursor:
            history.append({
                "status": r.get("status", ""),
                "timestamp": r.get("timestamp", ""),
                "score": r.get("score", ""),
            })

        return {
            "quiz_count": quiz_count,
            "history": history,
        }
    except Exception as e:
        return {"error": str(e)}


# --- PHẦN 4: API MỚI — DANH SÁCH MÔN HỌC & GIẢI THÍCH AI ---


@app.get("/api/subjects")
async def get_subjects():
    """Lấy danh sách các môn học có trong ngân hàng câu hỏi"""
    try:
        subjects = await db.questions.distinct("subject")
        return subjects
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/explain")
async def explain_answer(data: dict = Body(...)):
    """Gọi Gemini AI giải thích đáp án bằng tiếng Việt"""
    question = data.get("question", "")
    options = data.get("options", [])
    correct_answer = data.get("correct_answer", "")
    user_answer = data.get("user_answer", "")

    if not question:
        raise HTTPException(status_code=400, detail="Thiếu nội dung câu hỏi!")

    try:
        # Tạo prompt yêu cầu Gemini giải thích chi tiết bằng tiếng Việt
        options_text = "\n".join(
            [f"  {i+1}. {opt}" for i, opt in enumerate(options)]
        )
        prompt = (
            f"Hãy giải thích câu hỏi trắc nghiệm sau bằng tiếng Việt:\n\n"
            f"Câu hỏi: {question}\n"
            f"Các đáp án:\n{options_text}\n"
            f"Đáp án đúng: {correct_answer}\n"
            f"Đáp án người dùng chọn: {user_answer}\n\n"
            f"Yêu cầu:\n"
            f"1. Giải thích tại sao đáp án đúng là đúng.\n"
            f"2. Nếu đáp án người dùng chọn khác đáp án đúng, giải thích tại sao nó sai.\n"
            f"3. Đưa ra một mẹo ghi nhớ ngắn gọn để nhớ kiến thức này.\n"
        )

        response = client_gemini.models.generate_content(
            model="gemini-3.1-flash-lite-preview", contents=prompt
        )
        return {"explanation": response.text}
    except Exception as e:
        print(f"Lỗi Gemini AI (explain): {e}")
        raise HTTPException(
            status_code=500,
            detail="Gemini AI đang gặp sự cố, cậu chủ thử lại sau nhé!",
        )


# --- PHẦN 5: API QUẢN TRỊ (ADMIN ENDPOINTS) ---


def verify_admin_key(admin_key: str):
    """Kiểm tra khóa admin, ném lỗi 403 nếu sai"""
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Sai khóa admin! Truy cập bị từ chối.")


@app.get("/api/admin/questions")
async def admin_get_questions(
    subject: str = Query(None, description="Lọc theo môn học"),
    search: str = Query(None, description="Tìm kiếm trong nội dung câu hỏi"),
):
    """Lấy danh sách câu hỏi cho trang quản trị (có lọc & tìm kiếm)"""
    try:
        query_filter = {}
        if subject:
            query_filter["subject"] = subject
        if search:
            # Tìm kiếm regex không phân biệt hoa thường trong nội dung câu hỏi
            query_filter["q"] = {"$regex": search, "$options": "i"}

        cursor = db.questions.find(query_filter).limit(200)
        questions = []
        async for q in cursor:
            q_type = q.get("type", "multiple_choice")
            questions.append({
                "_id": str(q["_id"]),
                "q_id": str(q.get("q_id", q["_id"])),
                "q": q.get("q", ""),
                "options": q.get("options", []),
                "answer": q.get("answer", q.get("ans")),
                "subject": q.get("subject", ""),
                "type": q_type,
                "ans_text": q.get("ans", "") if q_type == "short_answer" else "",
            })
        return questions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/question")
async def admin_create_question(data: dict = Body(...)):
    """Thêm câu hỏi mới vào ngân hàng đề (yêu cầu admin_key)"""
    verify_admin_key(data.get("admin_key", ""))

    # Kiểm tra các trường bắt buộc
    q_type = data.get("type", "multiple_choice")
    if not data.get("q"):
        raise HTTPException(status_code=400, detail="Thiếu nội dung câu hỏi!")
    if q_type == "short_answer" and not data.get("ans"):
        raise HTTPException(status_code=400, detail="Thiếu đáp án cho câu hỏi điền!")
    if q_type != "short_answer" and not data.get("options"):
        raise HTTPException(status_code=400, detail="Thiếu các lựa chọn cho câu trắc nghiệm!")

    try:
        # Tự sinh q_id theo format admin_{timestamp}
        q_id = f"admin_{int(time.time())}"
        new_question = {
            "q_id": q_id,
            "q": data["q"],
            "options": data.get("options", []),
            "subject": data.get("subject", "general"),
            "type": q_type,
        }
        if q_type == "short_answer":
            new_question["ans"] = data.get("ans", "")  # Text answer
        else:
            new_question["answer"] = data.get("answer", 0)
            new_question["options"] = data["options"]
        result = await db.questions.insert_one(new_question)
        return {
            "status": "success",
            "q_id": q_id,
            "_id": str(result.inserted_id),
            "message": "Đã thêm câu hỏi mới thành công!",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/admin/question/{question_id}")
async def admin_update_question(question_id: str, data: dict = Body(...)):
    """Cập nhật câu hỏi theo _id hoặc q_id (yêu cầu admin_key)"""
    verify_admin_key(data.get("admin_key", ""))

    try:
        # Loại bỏ admin_key khỏi dữ liệu cập nhật
        update_data = {k: v for k, v in data.items() if k != "admin_key"}
        if not update_data:
            raise HTTPException(status_code=400, detail="Không có dữ liệu để cập nhật!")

        # Thử tìm theo ObjectId trước, nếu không hợp lệ thì tìm theo q_id
        result = None
        try:
            result = await db.questions.update_one(
                {"_id": ObjectId(question_id)}, {"$set": update_data}
            )
        except bson.errors.InvalidId:
            result = await db.questions.update_one(
                {"q_id": question_id}, {"$set": update_data}
            )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi!")

        return {"status": "success", "message": "Đã cập nhật câu hỏi thành công!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/admin/question/{question_id}")
async def admin_delete_question(question_id: str, data: dict = Body(...)):
    """Xóa câu hỏi theo _id hoặc q_id (yêu cầu admin_key)"""
    verify_admin_key(data.get("admin_key", ""))

    try:
        # Thử xóa theo ObjectId trước, nếu không hợp lệ thì xóa theo q_id
        result = None
        try:
            result = await db.questions.delete_one({"_id": ObjectId(question_id)})
        except bson.errors.InvalidId:
            result = await db.questions.delete_one({"q_id": question_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Không tìm thấy câu hỏi để xóa!")

        return {"status": "success", "message": "Đã xóa câu hỏi thành công!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/subjects")
async def admin_create_subject(data: dict = Body(...)):
    """Tạo môn học mới bằng cách thêm câu hỏi placeholder (yêu cầu admin_key)"""
    verify_admin_key(data.get("admin_key", ""))

    subject_name = data.get("name", "").strip()
    if not subject_name:
        raise HTTPException(status_code=400, detail="Thiếu tên môn học!")

    try:
        # Kiểm tra xem môn học đã tồn tại chưa
        existing = await db.questions.find_one({"subject": subject_name})
        if existing:
            return {"status": "exists", "message": f"Môn '{subject_name}' đã tồn tại!"}

        # Tạo câu hỏi placeholder để đăng ký môn học mới
        placeholder = {
            "q_id": f"placeholder_{subject_name}_{int(time.time())}",
            "q": f"[Placeholder] Câu hỏi mẫu cho môn {subject_name}",
            "options": ["A", "B", "C", "D"],
            "answer": 0,
            "subject": subject_name,
        }
        await db.questions.insert_one(placeholder)
        return {
            "status": "success",
            "message": f"Đã tạo môn học '{subject_name}' thành công!",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
