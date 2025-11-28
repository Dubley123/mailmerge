"""
秘书相关 API 路由
处理秘书信息更新、密码修改等操作
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import hashlib

from backend.database.db_config import get_db_session
from backend.database.models import Secretary, Department
from backend.api.auth import get_current_user, hash_password, verify_password

router = APIRouter()


# ==================== Pydantic 模型 ====================

class UpdateProfileRequest(BaseModel):
    """更新个人资料请求"""
    name: str = Field(..., min_length=1, max_length=50, description="姓名")
    email: EmailStr = Field(..., description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")


class UpdateProfileResponse(BaseModel):
    """更新个人资料响应"""
    success: bool
    message: str
    data: Optional[dict] = None


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., min_length=6, description="新密码")


class ChangePasswordResponse(BaseModel):
    """修改密码响应"""
    success: bool
    message: str


# ==================== API 路由 ====================

@router.put("/profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    更新秘书个人资料
    可以更新：姓名、邮箱、手机号
    """
    try:
        # 检查邮箱是否已被其他用户使用
        if request.email != current_user.email:
            existing_email = db.query(Secretary).filter(
                Secretary.email == request.email,
                Secretary.id != current_user.id
            ).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被其他用户使用"
                )
        
        # 更新用户信息
        current_user.name = request.name
        current_user.email = request.email
        current_user.phone = request.phone
        
        db.commit()
        db.refresh(current_user)
        
        # 获取部门信息
        department = db.query(Department).filter(Department.id == current_user.department_id).first()
        
        return UpdateProfileResponse(
            success=True,
            message="个人资料更新成功",
            data={
                "id": current_user.id,
                "name": current_user.name,
                "username": current_user.username,
                "email": current_user.email,
                "phone": current_user.phone,
                "department": department.name if department else None
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败：{str(e)}"
        )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    修改秘书密码
    需要提供旧密码进行验证
    """
    try:
        # 验证旧密码
        if not verify_password(request.old_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前密码错误"
            )
        
        # 检查新密码是否与旧密码相同
        if request.old_password == request.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新密码不能与当前密码相同"
            )
        
        # 更新密码
        current_user.password_hash = hash_password(request.new_password)
        
        db.commit()
        
        return ChangePasswordResponse(
            success=True,
            message="密码修改成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"修改失败：{str(e)}"
        )
