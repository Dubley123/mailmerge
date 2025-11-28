"""
已汇总表单 API
提供汇总表的查询、下载等功能
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database.db_config import get_db_session
from backend.database.models import Aggregation, CollectTask, Secretary
from backend.api.auth import get_current_user
import os
import tempfile

router = APIRouter()


# ===================== Pydantic Schemas =====================

class AggregationItem(BaseModel):
    """汇总表列表项"""
    id: int
    name: str
    task_id: int
    task_name: str
    generated_at: datetime
    record_count: Optional[int]
    file_path: str
    
    class Config:
        from_attributes = True


class AggregationListResponse(BaseModel):
    """汇总表列表响应"""
    success: bool
    data: List[AggregationItem]
    total: int
    message: Optional[str] = None


class AggregationDownloadResponse(BaseModel):
    """下载响应"""
    success: bool
    download_url: Optional[str] = None
    filename: Optional[str] = None
    message: Optional[str] = None


# ===================== API Endpoints =====================

@router.get("/list")
def get_aggregation_list(
    task_id: Optional[int] = Query(None, description="按任务ID过滤"),
    task_name: Optional[str] = Query(None, description="按任务名称模糊查询"),
    start_date: Optional[str] = Query(None, description="开始日期(YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期(YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    sort_by: str = Query("generated_at", description="排序字段: generated_at, task_name"),
    sort_order: str = Query("desc", description="排序顺序: asc, desc"),
    current_secretary: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取汇总表列表
    - 支持按任务ID过滤
    - 支持按时间范围过滤
    - 支持分页
    - 支持排序
    """
    try:
        # 基础查询：仅查询当前教秘生成的汇总表
        query = db.query(Aggregation).filter(
            Aggregation.generated_by == current_secretary.id
        )
        joined_task = False
        
        # 过滤条件
        if task_id:
            query = query.filter(Aggregation.task_id == task_id)
        
        if task_name:
            query = query.join(CollectTask, Aggregation.task_id == CollectTask.id)
            joined_task = True
            query = query.filter(CollectTask.name.ilike(f"%{task_name}%"))
        
        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                query = query.filter(Aggregation.generated_at >= start_dt)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_dt = datetime.strptime(end_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
                query = query.filter(Aggregation.generated_at <= end_dt)
            except ValueError:
                pass
        
        # 获取总数
        total = query.count()
        
        # 排序
        if sort_by == "task_name":
            # 需要 join CollectTask 表
            if not joined_task:
                query = query.join(CollectTask, Aggregation.task_id == CollectTask.id)
                joined_task = True
            if sort_order == "asc":
                query = query.order_by(CollectTask.name.asc())
            else:
                query = query.order_by(CollectTask.name.desc())
        else:  # 默认按 generated_at 排序
            if sort_order == "asc":
                query = query.order_by(Aggregation.generated_at.asc())
            else:
                query = query.order_by(Aggregation.generated_at.desc())
        
        # 分页
        offset = (page - 1) * page_size
        aggregations = query.offset(offset).limit(page_size).all()
        
        # 构建返回数据
        items = []
        for agg in aggregations:
            task = db.query(CollectTask).filter(CollectTask.id == agg.task_id).first()
            items.append({
                "id": agg.id,
                "name": agg.name,
                "task_id": agg.task_id,
                "task_name": task.name if task else "未知任务",
                "generated_at": agg.generated_at.isoformat(),
                "record_count": agg.record_count,
                "file_path": agg.file_path
            })
        
        # 返回数据和总数（CommonAPI会自动包装success: true）
        return {
            "data": items,
            "total": total
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取汇总表列表失败: {str(e)}")


@router.get("/{aggregation_id}/download")
def download_aggregation(
    aggregation_id: int,
    current_secretary: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    下载汇总表文件
    - 验证权限（仅本人生成的汇总表可下载）
    - 从存储服务下载文件
    - 返回文件流
    """
    try:
        # 查询汇总表记录
        agg = db.query(Aggregation).filter(Aggregation.id == aggregation_id).first()
        if not agg:
            raise HTTPException(status_code=404, detail="汇总表不存在")
        
        # 权限验证：仅本人生成的汇总表可下载
        if agg.generated_by != current_secretary.id:
            raise HTTPException(status_code=403, detail="无权限下载此汇总表")
        
        # 从存储服务下载文件
        # file_path 格式: minio://mailmerge/aggregation/{id}/filename.xlsx
        source_path = agg.file_path
        
        # 创建临时文件
        original_filename = os.path.basename(source_path)
        file_extension = os.path.splitext(original_filename)[1]  # 获取文件扩展名 .xlsx
        temp_dir = tempfile.gettempdir()
        local_file_path = os.path.join(temp_dir, f"agg_{aggregation_id}_{original_filename}")
        
        # 下载到本地临时文件
        from backend.storage_service import download
        downloaded_path = download(source_path, local_file_path)
        
        # 使用汇总表名称作为下载文件名
        download_filename = f"{agg.name}{file_extension}"
        
        # 返回文件下载响应
        from fastapi.responses import FileResponse
        from urllib.parse import quote
        
        # 对文件名进行URL编码以支持中文
        encoded_filename = quote(download_filename.encode('utf-8'))
        
        response = FileResponse(
            path=downloaded_path,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=download_filename
        )
        
        # 设置 Content-Disposition 头，同时支持旧版和新版浏览器
        # filename: ASCII回退，filename*: UTF-8编码（RFC 5987）
        response.headers["Content-Disposition"] = (
            f'attachment; '
            f'filename="{download_filename.encode("ascii", "ignore").decode()}"; '
            f"filename*=utf-8''{encoded_filename}"
        )
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")


@router.get("/{aggregation_id}/info")
def get_aggregation_info(
    aggregation_id: int,
    current_secretary: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取汇总表详细信息
    """
    try:
        agg = db.query(Aggregation).filter(Aggregation.id == aggregation_id).first()
        if not agg:
            raise HTTPException(status_code=404, detail="汇总表不存在")
        
        # 权限验证
        if agg.generated_by != current_secretary.id:
            raise HTTPException(status_code=403, detail="无权限查看此汇总表")
        
        task = db.query(CollectTask).filter(CollectTask.id == agg.task_id).first()
        
        return {
            "success": True,
            "data": {
                "id": agg.id,
                "name": agg.name,
                "task_id": agg.task_id,
                "task_name": task.name if task else "未知任务",
                "generated_at": agg.generated_at.isoformat(),
                "record_count": agg.record_count,
                "file_path": agg.file_path,
                "extra": agg.extra
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取详情失败: {str(e)}")
