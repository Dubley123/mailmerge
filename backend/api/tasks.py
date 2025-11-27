"""
任务相关 API 路由
处理收集任务的创建、查看、更新等操作
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from backend.database.db_config import get_db_session
from backend.database.models import (
    CollectTask, CollectTaskTarget, Secretary, Teacher,
    TemplateForm, ReceivedEmail, TaskStatus, TemplateFormField
)
from backend.api.auth import get_current_user
from backend.storage_service import storage
import pandas as pd
import tempfile
import os
import shutil
from backend.database.models import ReceivedAttachment, Aggregation

router = APIRouter()


# ==================== Pydantic 模型 ====================

class TaskListItem(BaseModel):
    """任务列表项"""
    id: int
    name: str
    started_time: Optional[datetime]
    deadline: Optional[datetime]
    template_name: str
    replied_count: int
    total_count: int
    status: str
    created_at: datetime


class TeacherDetail(BaseModel):
    """教师详情"""
    id: int
    name: str
    email: str
    has_replied: bool


class TaskDetailResponse(BaseModel):
    """任务详情响应"""
    id: int
    name: str
    description: Optional[str]
    started_time: Optional[datetime]
    deadline: Optional[datetime]
    template_id: int
    template_name: str
    mail_subject: Optional[str]
    mail_content: Optional[str]
    status: str
    teachers: List[TeacherDetail]


class CreateTaskRequest(BaseModel):
    """创建任务请求"""
    name: str = Field(..., min_length=1, max_length=255, description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    deadline: datetime = Field(..., description="截止时间")
    started_time: Optional[datetime] = Field(None, description="发布时间，None表示立即发布")
    template_id: int = Field(..., description="表单模板ID")
    mail_subject: str = Field(..., description="邮件标题")
    mail_content: str = Field(..., description="邮件正文")
    teacher_ids: List[int] = Field(..., min_items=1, description="目标教师ID列表")


class UpdateTaskRequest(BaseModel):
    """更新任务请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    started_time: Optional[datetime] = None
    template_id: Optional[int] = None
    mail_subject: Optional[str] = None
    mail_content: Optional[str] = None
    teacher_ids: Optional[List[int]] = None


# ==================== API 路由 ====================

@router.get("/list", response_model=List[TaskListItem])
async def get_task_list(
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取任务列表
    包含：任务基本信息、模板名称、回复统计
    """
    tasks = db.query(CollectTask).filter(
        CollectTask.created_by == current_user.id
    ).order_by(CollectTask.created_at.desc()).all()

    result = []
    for task in tasks:
        # 获取模板名称
        template = db.query(TemplateForm).filter(
            TemplateForm.id == task.template_id
        ).first()

        # 统计总教师数
        total_count = db.query(CollectTaskTarget).filter(
            CollectTaskTarget.task_id == task.id
        ).count()

        # 统计已回复人数（根据 ReceivedEmail 表，按 from_tea_id 去重）
        replied_count = db.query(func.count(func.distinct(ReceivedEmail.from_tea_id))).filter(
            ReceivedEmail.task_id == task.id
        ).scalar() or 0

        result.append(TaskListItem(
            id=task.id,
            name=task.name,
            started_time=task.started_time,
            deadline=task.deadline,
            template_name=template.name if template else "未知模板",
            replied_count=replied_count,
            total_count=total_count,
            status=task.status.value,
            created_at=task.created_at
        ))

    return result


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task_detail(
    task_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取任务详情
    包含：任务信息、教师列表及回复状态
    """
    # 查询任务
    task = db.query(CollectTask).filter(
        CollectTask.id == task_id,
        CollectTask.created_by == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    # 获取模板信息
    template = db.query(TemplateForm).filter(
        TemplateForm.id == task.template_id
    ).first()

    # 获取目标教师列表
    target_teacher_ids = db.query(CollectTaskTarget.teacher_id).filter(
        CollectTaskTarget.task_id == task_id
    ).all()
    teacher_ids = [t[0] for t in target_teacher_ids]

    # 获取已回复的教师ID
    replied_teacher_ids = set([
        t[0] for t in db.query(ReceivedEmail.from_tea_id).filter(
            ReceivedEmail.task_id == task_id
        ).distinct().all()
    ])

    # 获取教师详细信息
    teachers = db.query(Teacher).filter(Teacher.id.in_(teacher_ids)).all()

    teacher_list = [
        TeacherDetail(
            id=teacher.id,
            name=teacher.name,
            email=teacher.email,
            has_replied=teacher.id in replied_teacher_ids
        )
        for teacher in teachers
    ]

    # 未回复的排在前面
    teacher_list.sort(key=lambda x: (x.has_replied, x.name))

    # 从数据库字段或 mail_content_template 中提取邮件信息
    mail_subject = None
    mail_content = None

    # 优先从 mail_content_template 中读取
    if task.mail_content_template:
        mail_subject = task.mail_content_template.get('subject')
        mail_content = task.mail_content_template.get('content')

    return TaskDetailResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        started_time=task.started_time,
        deadline=task.deadline,
        template_id=task.template_id,
        template_name=template.name if template else "未知模板",
        mail_subject=mail_subject,
        mail_content=mail_content,
        status=task.status.value,
        teachers=teacher_list
    )


@router.post("/create")
async def create_task(
    request: CreateTaskRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    创建新任务
    """
    # 检查任务名称是否已存在
    existing = db.query(CollectTask).filter(
        CollectTask.name == request.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务名称已存在"
        )

    # 检查模板是否存在
    template = db.query(TemplateForm).filter(
        TemplateForm.id == request.template_id
    ).first()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模板不存在"
        )

    # 检查教师是否都存在
    teachers = db.query(Teacher).filter(
        Teacher.id.in_(request.teacher_ids)
    ).all()
    if len(teachers) != len(request.teacher_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="部分教师不存在"
        )

    # 确定任务状态和开始时间
    now = datetime.utcnow()
    if request.started_time is None:
        # 立即发布
        started_time = now
        task_status = TaskStatus.ACTIVE
    else:
        # 移除时区信息以便比较
        started_time = request.started_time.replace(tzinfo=None) if request.started_time.tzinfo else request.started_time
        task_status = TaskStatus.DRAFT if started_time > now else TaskStatus.ACTIVE

    # 移除deadline的时区信息
    deadline = request.deadline.replace(tzinfo=None) if request.deadline.tzinfo else request.deadline

    # 创建任务
    new_task = CollectTask(
        name=request.name,
        description=request.description,
        started_time=started_time,
        deadline=deadline,
        template_id=request.template_id,
        status=task_status,
        created_by=current_user.id,
        mail_content_template={
            'subject': request.mail_subject,
            'content': request.mail_content
        },
        extra=None
    )

    try:
        db.add(new_task)
        db.flush()

        # 创建任务目标教师关联
        for teacher_id in request.teacher_ids:
            target = CollectTaskTarget(
                task_id=new_task.id,
                teacher_id=teacher_id
            )
            db.add(target)

        db.commit()

        return {
            "success": True,
            "message": "任务创建成功",
            "data": {"task_id": new_task.id}
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建任务失败：{str(e)}"
        )


@router.put("/{task_id}")
async def update_task(
    task_id: int,
    request: UpdateTaskRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    更新任务（仅限未发布的任务）
    """
    # 查询任务
    task = db.query(CollectTask).filter(
        CollectTask.id == task_id,
        CollectTask.created_by == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    if task.status != TaskStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能编辑未发布的任务"
        )

    # 更新字段
    if request.name is not None:
        # 检查名称是否重复
        existing = db.query(CollectTask).filter(
            CollectTask.name == request.name,
            CollectTask.id != task_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="任务名称已存在"
            )
        task.name = request.name

    if request.deadline is not None:
        # 移除时区信息
        task.deadline = request.deadline.replace(tzinfo=None) if request.deadline.tzinfo else request.deadline

    # 处理发布时间和状态更新
    # 如果请求中包含 started_time 字段（即使是 None），说明用户修改了发布时间设置
    if 'started_time' in request.model_dump(exclude_unset=True):
        now = datetime.utcnow()
        
        if request.started_time is None:
            # 立即发布：设置当前时间并激活任务
            task.started_time = now
            task.status = TaskStatus.ACTIVE
        else:
            # 自定义发布时间：移除时区信息
            task.started_time = request.started_time.replace(tzinfo=None) if request.started_time.tzinfo else request.started_time
            
            # 根据发布时间决定状态
            if task.started_time <= now:
                # 如果发布时间已到，状态改为 ACTIVE
                task.status = TaskStatus.ACTIVE
            else:
                # 如果是未来时间，保持 DRAFT 状态
                task.status = TaskStatus.DRAFT

    if request.template_id is not None:
        template = db.query(TemplateForm).filter(
            TemplateForm.id == request.template_id
        ).first()
        if not template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="模板不存在"
            )
        task.template_id = request.template_id

    # 更新邮件内容
    if request.mail_subject or request.mail_content:
        if task.mail_content_template is None:
            task.mail_content_template = {}
        if request.mail_subject:
            task.mail_content_template['subject'] = request.mail_subject
        if request.mail_content:
            task.mail_content_template['content'] = request.mail_content

    # 更新描述
    if request.description is not None:
        task.description = request.description

    # 更新教师列表
    if request.teacher_ids is not None:
        # 删除现有关联
        db.query(CollectTaskTarget).filter(
            CollectTaskTarget.task_id == task_id
        ).delete()

        # 添加新关联
        for teacher_id in request.teacher_ids:
            target = CollectTaskTarget(
                task_id=task_id,
                teacher_id=teacher_id
            )
            db.add(target)

    try:
        db.commit()
        return {
            "success": True,
            "message": "任务更新成功"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新任务失败：{str(e)}"
        )


@router.post("/{task_id}/close")
async def close_task(
    task_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    提前关闭任务
    """
    task = db.query(CollectTask).filter(
        CollectTask.id == task_id,
        CollectTask.created_by == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    if task.status not in [TaskStatus.ACTIVE, TaskStatus.EXPIRED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能关闭进行中或已过期的任务"
        )

    task.status = TaskStatus.CLOSED

    try:
        db.commit()
        return {
            "success": True,
            "message": "任务已关闭"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"关闭任务失败：{str(e)}"
        )


@router.post("/{task_id}/publish")
async def publish_task(
    task_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    一键发布任务（将DRAFT状态改为ACTIVE，并设置started_time为当前时间）
    """
    task = db.query(CollectTask).filter(
        CollectTask.id == task_id,
        CollectTask.created_by == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )

    if task.status != TaskStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能发布未发布的任务"
        )

    # 设置发布时间为当前时间，状态改为ACTIVE
    task.started_time = datetime.utcnow()
    task.status = TaskStatus.ACTIVE

    try:
        db.commit()
        return {
            "success": True,
            "message": "任务已发布"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发布任务失败：{str(e)}"
        )


@router.post("/{task_id}/aggregate")
async def aggregate_task(
    task_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """合并任务附件并导出汇总表（仅 Excel）。

    步骤：
    1. 查找属于该任务的 ReceivedEmail，集合其 attachment_id
    2. 读取对应 ReceivedAttachment.file_path（支持本地与 MinIO）
    3. 解析 Excel（只取第一条数据行），并根据模板字段顺序拼接
    4. 生成汇总 Excel，上传到 MinIO（aggregation/{id}/...）并写入 Aggregation 表
    """
    # 检查任务权限
    task = db.query(CollectTask).filter(
        CollectTask.id == task_id,
        CollectTask.created_by == current_user.id
    ).first()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    # 获取模板字段（按 ord 排序）
    template = db.query(TemplateForm).filter(TemplateForm.id == task.template_id).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任务对应模板不存在")

    template_fields = db.query(TemplateFormField).filter(
        TemplateFormField.form_id == template.id
    ).order_by(TemplateFormField.ord).all()
    template_headers = [f.display_name for f in template_fields]

    # 收集收到的邮件及其附件
    received_emails = db.query(ReceivedEmail).filter(
        ReceivedEmail.task_id == task_id,
        ReceivedEmail.attachment_id != None
    ).all()

    if not received_emails:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该任务没有收到任何带附件的回复")

    temp_files = []
    rows = []
    warnings = []
    processed_received_ids = []

    try:
        for r in received_emails:
            if not r.attachment_id:
                continue
            att = db.query(ReceivedAttachment).filter(ReceivedAttachment.id == r.attachment_id).first()
            if not att:
                warnings.append(f"附件记录未找到(id={r.attachment_id})")
                continue

            file_path = att.file_path
            file_name = att.file_name or os.path.basename(file_path or '')
            if not file_path:
                warnings.append(f"附件路径为空(id={att.id})")
                continue

            # 判断是否 Excel
            lower = (file_name or file_path).lower()
            if not (lower.endswith('.xlsx') or lower.endswith('.xls')):
                warnings.append(f"忽略非 Excel 附件: {file_name}")
                continue

            # 下载附件到本地临时文件 (使用新的 storage.download 接口)
            try:
                tmp_fd, local_tmp = tempfile.mkstemp(suffix=os.path.splitext(file_name)[1])
                os.close(tmp_fd)
                temp_files.append(local_tmp)
                
                storage.download(file_path, local_tmp)
            except Exception as e:
                warnings.append(f"下载附件失败(id={att.id}): {e}")
                continue

            # 读取 Excel（使用 pandas）
            try:
                df = pd.read_excel(local_tmp, engine='openpyxl')
            except Exception as e:
                warnings.append(f"解析 Excel 失败(id={att.id}): {e}")
                continue

            if df.shape[0] == 0:
                warnings.append(f"附件无数据(id={att.id}): {file_name}")
                continue

            if df.shape[0] > 1:
                warnings.append(f"附件包含多于一行数据(id={att.id})，仅取第一行: {file_name}")

            # 取第一行数据并按模板字段过滤与重排
            first_row = df.iloc[0]

            # 构建 normalized mapping from excel headers -> column
            col_map = {str(col).strip(): col for col in df.columns}

            row_values = []
            for header in template_headers:
                key = header.strip()
                if key in col_map:
                    val = first_row[col_map[key]]
                    # 将 numpy 值转换为 Python 原生类型
                    try:
                        if pd.isna(val):
                            val = None
                    except Exception:
                        pass
                    row_values.append(val)
                else:
                    # 模板字段在附件头中不存在，留空
                    row_values.append(None)

            rows.append(row_values)
            processed_received_ids.append(r.id)

        if len(rows) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"未找到可合并的 Excel 附件。详情: {warnings}")

        # 构建 DataFrame
        out_df = pd.DataFrame(rows, columns=template_headers)

        # 创建 Aggregation 记录，先写入以获取 id
        safe_task_name = ''.join(c for c in task.name if c.isalnum() or c in (' ', '_', '-')).strip()
        filename = f"{safe_task_name}_汇总表.xlsx"

        agg = Aggregation(
            task_id=task_id,
            name=f"{task.name}_汇总表",
            generated_by=current_user.id,
            record_count=len(out_df),
            file_path=""
        )
        db.add(agg)
        db.flush()

        # 临时保存到本地
        tmp_out_fd, tmp_out_path = tempfile.mkstemp(suffix='.xlsx')
        os.close(tmp_out_fd)
        temp_files.append(tmp_out_path) # 加入清理列表
        
        try:
            out_df.to_excel(tmp_out_path, index=False)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"生成汇总 Excel 失败: {e}")

        # 保存文件 (使用新的 storage.upload 接口)
        # 目标路径: minio://mailmerge/aggregation/{agg.id}/{filename}
        target_path = f"minio://mailmerge/aggregation/{agg.id}/{filename}"
        try:
            uploaded_path = storage.upload(tmp_out_path, target_path)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"保存汇总文件失败: {e}")

        # 更新 Aggregation.file_path
        agg.file_path = uploaded_path
        db.commit()

        # 标记已合并的 ReceivedEmail（可选）
        if processed_received_ids:
            db.query(ReceivedEmail).filter(ReceivedEmail.id.in_(processed_received_ids)).update({"is_aggregated": True}, synchronize_session=False)
            db.commit()

        return {
            "success": True,
            "message": "合并并导出成功",
            "data": {
                "aggregation_id": agg.id,
                "file_path": uploaded_path,
                "warnings": warnings
            }
        }

    finally:
        for f in temp_files:
            try:
                if f and os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
