"""对话式分析API - Chat endpoints"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.chat_agent import chat_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# 请求/响应模型
class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    pass


class CreateSessionResponse(BaseModel):
    """创建会话响应"""
    session_id: str


class SendMessageRequest(BaseModel):
    """发送消息请求"""
    session_id: str
    message: str


@router.post("/session", response_model=CreateSessionResponse)
async def create_session():
    """创建新的聊天会话"""
    try:
        session_id = chat_agent.create_session()
        logger.info(f"Created session: {session_id}")
        return CreateSessionResponse(session_id=session_id)
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/{session_id}")
async def upload_document(session_id: str, file: UploadFile = File(...)):
    """上传日志文档到会话"""
    try:
        ctx = chat_agent.get_session(session_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="Session not found")

        # 读取文件内容
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)

        if file_size_mb > 50:
            raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError:
            text_content = content.decode("utf-8", errors="ignore")

        # 附加文件到会话
        success = chat_agent.attach_file(session_id, file.filename or "unknown", text_content)

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        logger.info(f"Uploaded file {file.filename} to session {session_id}")

        return {
            "status": "success",
            "filename": file.filename,
            "size_mb": round(file_size_mb, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/message")
async def send_message(request: SendMessageRequest):
    """发送消息并获取SSE流式响应"""

    async def event_generator():
        """SSE事件生成器 - 流式输出token"""
        try:
            ctx = chat_agent.get_session(request.session_id)
            if not ctx:
                yield f'event: error\ndata: {json.dumps({"message": "Session not found"})}\n\n'
                return

            accumulated = ""

            # 从chat_agent获取流式响应
            async for token in chat_agent.stream_response(
                request.session_id, request.message
            ):
                accumulated += token

                # 发送token事件
                yield f'event: token\ndata: {json.dumps({"content": token})}\n\n'

            # 发送完成事件
            yield (
                f'event: done\ndata: {json.dumps({"session_id": request.session_id})}\n\n'
            )

            logger.info(
                f"Message processed for session {request.session_id}. "
                f"Response length: {len(accumulated)}"
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            yield f'event: error\ndata: {json.dumps({"message": str(e)})}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    """获取会话历史"""
    try:
        ctx = chat_agent.get_session(session_id)
        if not ctx:
            raise HTTPException(status_code=404, detail="Session not found")

        # 将消息转换为可序列化的格式
        messages = []
        for msg in ctx.messages:
            msg_type = type(msg).__name__
            messages.append(
                {
                    "type": msg_type,
                    "role": "user" if "Human" in msg_type else "assistant",
                    "content": msg.content,
                }
            )

        return {
            "session_id": session_id,
            "messages": messages,
            "context": {
                "db_type": ctx.db_type,
                "has_document": bool(ctx.document_content),
                "uploaded_filename": ctx.uploaded_filename,
                "analysis_done": ctx.analysis_done,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """删除聊天会话"""
    try:
        if session_id not in chat_agent.sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        del chat_agent.sessions[session_id]
        logger.info(f"Deleted session: {session_id}")

        return {"status": "deleted", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
