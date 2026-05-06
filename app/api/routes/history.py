from fastapi import APIRouter, HTTPException
from typing import Optional

from app.models import AnalysisHistoryResponse, AnalysisHistoryItem
from datetime import datetime

router = APIRouter(prefix="/api/analysis", tags=["history"])

# 临时存储历史记录（实际应该用数据库）
history_data = {}


@router.get("/history", response_model=AnalysisHistoryResponse)
async def get_history(db_type: Optional[str] = None, skip: int = 0, limit: int = 20):
    """获取历史分析记录"""
    items = []

    for analysis_id, record in history_data.items():
        if db_type and record.get("db_type") != db_type:
            continue

        items.append(
            AnalysisHistoryItem(
                analysis_id=analysis_id,
                filename=record.get("filename", "unknown"),
                db_type=record.get("db_type", "unknown"),
                created_at=record.get("created_at", datetime.now()),
                primary_root_cause=record.get("primary_root_cause"),
                status=record.get("status", "unknown"),
            )
        )

    # 排序：最新优先
    items.sort(key=lambda x: x.created_at, reverse=True)

    # 分页
    paginated_items = items[skip : skip + limit]

    return AnalysisHistoryResponse(items=paginated_items, total=len(items))


@router.delete("/history/{analysis_id}")
async def delete_history(analysis_id: str):
    """删除历史记录"""
    if analysis_id in history_data:
        del history_data[analysis_id]
        return {"message": "History deleted successfully"}

    raise HTTPException(status_code=404, detail="History not found")
