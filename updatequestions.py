import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
import dns.resolver

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "8.8.4.4"]


async def update_700_questions():
    uri = os.getenv("MONGO_URI", "")
    if not uri:
        raise RuntimeError("Thiếu MONGO_URI trong biến môi trường!")

    client = AsyncIOMotorClient(uri)

    # Chọn Database và Collection
    db = client.quizdb  # Tên database trong ảnh của cậu chủ là quizdb
    collection = db.questions

    # Lệnh Bulk Update (Cập nhật hàng loạt)
    # Tìm tất cả câu chưa có subject và gán là "network"
    result = await collection.update_many(
        {"subject": {"$exists": False}}, {"$set": {"subject": "network"}}
    )

    print(
        f"Dạ thưa cậu chủ, em đã cập nhật xong {result.modified_count} câu hỏi thành môn Mạng máy tính ạ!"
    )


if __name__ == "__main__":
    asyncio.run(update_700_questions())
