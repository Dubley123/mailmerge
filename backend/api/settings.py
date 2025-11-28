"""
系统设置相关 API 路由
处理用户个人资料更新、密码修改等操作
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from sqlalchemy.orm import Session

from backend.database.db_config import get_db_session
from backend.database.models import Secretary, Department
from backend.api.auth import get_current_user, verify_password, hash_password

router = APIRouter()


# ==================== Pydantic 模型 ====================

class UpdateProfileRequest(BaseModel):
    """更新个人资料请求"""
    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, description="新密码")


class UserProfileResponse(BaseModel):
    """用户资料响应"""
    id: int
    name: str
    username: str
    account: str
    email: str
    phone: Optional[str]
    department: Optional[str]


class UpdateProfileResponse(BaseModel):
    """更新个人资料响应"""
    success: bool
    message: str
    data: Optional[UserProfileResponse] = None


class ChangePasswordResponse(BaseModel):
    """修改密码响应"""
    success: bool
    message: str


# ==================== API 路由 ====================

@router.put("/profile", response_model=UpdateProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    更新用户个人资料
    """
    # 检查邮箱是否已被其他用户使用
    existing_email = db.query(Secretary).filter(
        Secretary.email == request.email,
        Secretary.id != current_user.id
    ).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被其他用户使用"
        )
    
    # 检查用户名是否已被其他用户使用
    existing_username = db.query(Secretary).filter(
        Secretary.username == request.username,
        Secretary.id != current_user.id
    ).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被其他用户使用"
        )
    
    try:
        # 更新用户信息
        current_user.username = request.username
        current_user.email = request.email
        current_user.phone = request.phone
        
        db.commit()
        db.refresh(current_user)
        
        # 获取部门信息
        department = db.query(Department).filter(Department.id == current_user.department_id).first()
        
        # 返回更新后的用户信息
        return UpdateProfileResponse(
            success=True,
            message="个人资料更新成功",
            data=UserProfileResponse(
                id=current_user.id,
                name=current_user.name,
                username=current_user.username,
                account=current_user.account,
                email=current_user.email,
                phone=current_user.phone,
                department=department.name if department else None
            )
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败：{str(e)}"
        )


@router.post("/password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    修改用户密码
    """
    # 验证旧密码
    if not verify_password(request.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    try:
        # 更新密码
        current_user.password_hash = hash_password(request.new_password)
        
        db.commit()
        db.refresh(current_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"密码修改失败：{str(e)}"
        )
    
    return ChangePasswordResponse(
        success=True,
        message="密码修改成功"
    )
