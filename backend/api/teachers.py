"""
教师相关 API 路由
处理教师列表查询等操作
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from backend.database.db_config import get_db_session
from backend.database.models import Teacher, Secretary
from backend.api.auth import get_current_user

router = APIRouter()


# ==================== Pydantic 模型 ====================

class TeacherResponse(BaseModel):
    """教师响应"""
    id: int
    name: str
    email: str
    department_id: int


# ==================== API 路由 ====================

@router.get("/list", response_model=List[TeacherResponse])
async def get_teachers(
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取当前用户所在院系的所有教师
    """
    teachers = db.query(Teacher).filter(
        Teacher.department_id == current_user.department_id
    ).all()
    
    return [
        TeacherResponse(
            id=teacher.id,
            name=teacher.name,
            email=teacher.email,
            department_id=teacher.department_id
        )
        for teacher in teachers
    ]
