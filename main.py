import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json

from agent import run_agent
from tools import ALLOWED_READ_DIR

app = FastAPI(title="claude-autonomous-agent")

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")


class QueryRequest(BaseModel):
    message: str


@app.post("/chat/stream")
async def chat_stream(req: QueryRequest):
    """Server-Sent Events stream — yields agent events as they happen."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    def event_generator():
        for event in run_agent(req.message):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file to the workspace so the agent can read it."""
    safe_name = Path(file.filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid filename.")
    dest = ALLOWED_READ_DIR / safe_name
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit.")
    dest.write_bytes(content)
    return {"filename": safe_name, "size_bytes": len(content),
            "message": f"Uploaded. Ask the agent: 'Read {safe_name} and summarize it.'"}


@app.get("/workspace")
def list_workspace():
    files = [{"name": f.name, "size_bytes": f.stat().st_size}
             for f in ALLOWED_READ_DIR.iterdir() if f.is_file()]
    return {"files": files}


@app.get("/health")
def health():
    return {"status": "ok"}
