from fastapi import APIRouter, UploadFile, File, Depends, Form
from app.db.neo4j_client import get_neo4j_driver
import json
import uuid

router = APIRouter(prefix="/api/v1/history", tags=["History"])

@router.post("/upload", summary="ChatGPT veya Gemini Geçmişini Yükle")
async def upload_chat_history(
    file: UploadFile = File(...), 
    limit: int = Form(50), # Varsayılan olarak 50 alıyoruz, frontend 0 gönderirse hepsini demek
    neo4j_driver = Depends(get_neo4j_driver)
):
    content = await file.read()
    
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Geçersiz JSON dosyası."}
    
    sessions = []
    
    # 1. Gemini (Google Takeout - MyActivity.json) Formatı
    if isinstance(data, list) and len(data) > 0 and "header" in data[0] and data[0].get("header") == "Gemini":
        for item in data:
            title = item.get("title", "")
            clean_title = title.replace("Kullanıcı: ", "").replace("Said ", "").strip()
            if clean_title:
                sessions.append({
                    "id": str(uuid.uuid4()),
                    "question": clean_title,
                    "answer": "Geçmiş Gemini Sohbeti",
                    "platform": "Gemini"
                })
                
    # 2. ChatGPT (conversations.json) Formatı
    elif isinstance(data, list) and len(data) > 0 and "mapping" in data[0]:
        for conv in data:
            mapping = conv.get("mapping", {})
            for node_id, node in mapping.items():
                msg = node.get("message")
                if msg and msg.get("author", {}).get("role") == "user":
                    parts = msg.get("content", {}).get("parts", [])
                    question = parts[0] if parts else ""
                    if question and isinstance(question, str) and question.strip():
                        sessions.append({
                            "id": str(uuid.uuid4()),
                            "question": question.strip(),
                            "answer": "Geçmiş ChatGPT Sohbeti",
                            "platform": "ChatGPT"
                        })
    
    if not sessions:
        return {"status": "error", "message": "Desteklenmeyen dosya formatı. Lütfen geçerli bir JSON yükleyin."}

    # Kullanıcının belirlediği limiti uygula (0 ise hepsini al)
    if limit > 0:
        sessions = sessions[-limit:]

    async with neo4j_driver.session() as db_session:
        await db_session.run("""
            UNWIND $sessions AS s
            MERGE (rs:RawSession {id: s.id})
            ON CREATE SET 
                rs.question = s.question,
                rs.answer = s.answer,
                rs.platform = s.platform,
                rs.processed = false,
                rs.created_at = datetime()
        """, sessions=sessions)
        
    return {
        "status": "success", 
        "imported_count": len(sessions), 
        "message": f"{len(sessions)} adet oturum eklendi."
    }