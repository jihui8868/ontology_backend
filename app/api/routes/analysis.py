from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import uuid
import asyncio
from typing import Optional
import json
import logging

from app.models import (
    AnalysisUploadResponse,
    AnalysisStatus,
    ReportResponse,
)
from app.core.storage import storage_manager
from app.agents.pipeline import analysis_pipeline
from app.services.analysis_service import analysis_service
from app.api.routes.history import history_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# 存储正在进行的分析任务（临时，实际应该用数据库）
analysis_tasks = {}

# 存储进度事件队列（用于 SSE 推送）
progress_queues = {}


async def run_analysis_background(analysis_id: str, log_content: str, db_type: str):
    """后台运行分析任务"""
    try:
        logger.info(f"Starting analysis {analysis_id} for {db_type}")

        # 创建进度队列
        progress_queue = asyncio.Queue()
        progress_queues[analysis_id] = progress_queue

        # 执行分析流水线
        result = await analysis_pipeline.analyze_with_streaming(
            log_content=log_content,
            db_type=db_type,
            progress_queue=progress_queue,
        )

        # 更新任务状态
        if result.get("status") == "completed":
            analysis_tasks[analysis_id] = {
                "status": "completed",
                "db_type": db_type,
                "progress": 100,
                "message": "分析完成",
                "result": result,
            }

            # 保存到历史记录
            primary_cause = result.get("primary_cause", "Unknown")
            history_data[analysis_id] = {
                "filename": analysis_tasks[analysis_id].get("filename", "unknown"),
                "db_type": db_type,
                "created_at": result.get("analysis_metadata", {}).get("completed_at"),
                "primary_root_cause": primary_cause,
                "status": "completed",
            }

            logger.info(f"Analysis {analysis_id} completed successfully")
        else:
            analysis_tasks[analysis_id] = {
                "status": "failed",
                "db_type": db_type,
                "progress": 0,
                "message": result.get("error", "Unknown error"),
            }

            logger.error(f"Analysis {analysis_id} failed: {result.get('error')}")

    except Exception as e:
        logger.error(f"Background analysis failed: {e}", exc_info=True)
        analysis_tasks[analysis_id] = {
            "status": "failed",
            "db_type": db_type,
            "progress": 0,
            "message": f"分析失败: {str(e)}",
        }
    finally:
        # 清理进度队列
        if analysis_id in progress_queues:
            del progress_queues[analysis_id]


@router.post("/upload", response_model=AnalysisUploadResponse)
async def upload_log(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """上传日志文件并触发分析"""
    try:
        # 生成分析 ID
        analysis_id = str(uuid.uuid4())

        # 检查文件大小
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)
        if file_size_mb > 50:
            raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

        # 解码内容
        try:
            log_content = content.decode("utf-8")
        except UnicodeDecodeError:
            log_content = content.decode("utf-8", errors="ignore")

        # 自动检测数据库类型
        db_type = await analysis_service.detect_db_type(log_content)

        # 保存文件
        filepath = await storage_manager.save_upload(file, analysis_id)

        # 初始化分析任务
        analysis_tasks[analysis_id] = {
            "status": "queued",
            "db_type": db_type,
            "progress": 0,
            "message": "分析任务已创建，等待处理...",
            "filepath": filepath,
            "filename": file.filename,
        }

        # 后台运行分析
        background_tasks.add_task(
            run_analysis_background, analysis_id, log_content, db_type
        )

        logger.info(f"Upload completed: {analysis_id} ({db_type})")

        return AnalysisUploadResponse(
            analysis_id=analysis_id,
            status="queued",
            db_type=db_type,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{analysis_id}/status")
async def get_analysis_status(analysis_id: str):
    """获取分析状态（SSE 流式推送）"""
    if analysis_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Analysis not found")

    async def event_generator():
        """SSE 事件生成器"""
        try:
            # 首先发送当前状态
            task = analysis_tasks[analysis_id]
            yield f'event: status\ndata: {json.dumps(task)}\n\n'

            # 如果有进度队列，监听进度更新
            if analysis_id in progress_queues:
                progress_queue = progress_queues[analysis_id]
                timeout = 0  # 非阻塞模式

                while True:
                    try:
                        # 尝试从队列获取进度更新（非阻塞）
                        progress_update = progress_queue.get_nowait()
                        yield f'event: progress\ndata: {json.dumps(progress_update)}\n\n'
                    except asyncio.QueueEmpty:
                        # 检查是否完成
                        current_task = analysis_tasks.get(analysis_id, {})
                        if current_task.get("status") in ["completed", "failed"]:
                            yield f'event: {current_task.get("status")}\ndata: {json.dumps(current_task)}\n\n'
                            break
                        else:
                            # 等待一段时间后重试
                            await asyncio.sleep(0.5)
            else:
                # 没有进度队列，定期检查状态
                max_iterations = 120  # 最多等待 60 秒
                for _ in range(max_iterations):
                    current_task = analysis_tasks.get(analysis_id, {})
                    if current_task.get("status") in ["completed", "failed"]:
                        yield f'event: {current_task.get("status")}\ndata: {json.dumps(current_task)}\n\n'
                        break
                    await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"SSE generator error: {e}")
            yield f'event: error\ndata: {json.dumps({"error": str(e)})}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{analysis_id}/report")
async def get_report(analysis_id: str):
    """获取分析报告"""
    if analysis_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="Analysis not found")

    task = analysis_tasks[analysis_id]

    if task["status"] == "completed":
        result = task.get("result", {})
        return {
            "analysis_id": analysis_id,
            "db_type": task.get("db_type", "unknown"),
            "created_at": result.get("analysis_metadata", {}).get("completed_at"),
            "root_causes": result.get("root_causes", []),
            "similar_cases": result.get("analysis_metadata", {}).get(
                "similar_cases_count", 0
            ),
            "resolutions": [],
            "report_markdown": result.get("report", ""),
        }
    elif task["status"] == "failed":
        raise HTTPException(
            status_code=400, detail=f"Analysis failed: {task.get('message', '')}"
        )
    else:
        raise HTTPException(
            status_code=202,
            detail=f"Analysis still in progress: {task.get('message', '')}",
        )
