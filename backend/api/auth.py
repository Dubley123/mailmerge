"""
认证相关 API 路由
处理用户登录、注册、登出等操作
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import hashlib
import jwt
from datetime import datetime, timedelta
import os

from backend.database.db_config import get_db_session
from backend.database.models import Secretary, Department

router = APIRouter()
security = HTTPBearer()

# JWT 配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时


# ==================== Pydantic 模型 ====================

class LoginRequest(BaseModel):
    """登录请求"""
    account: str = Field(..., description="登录账号（支持账号/用户名/邮箱）")
    password: str = Field(..., description="登录密码")


class RegisterRequest(BaseModel):
    """注册请求"""
    employee_id: int = Field(..., description="工号（教职工号）")
    name: str = Field(..., min_length=1, max_length=50, description="姓名")
    department_id: int = Field(..., description="所属院系ID")
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")
    password: str = Field(..., min_length=6, description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    success: bool
    token: str
    user: dict


class RegisterResponse(BaseModel):
    """注册响应"""
    success: bool
    message: str


class DepartmentResponse(BaseModel):
    """院系响应"""
    id: int
    name: str


# ==================== 工具函数 ====================

def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return hash_password(plain_password) == hashed_password


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建 JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db_session)
):
    """获取当前登录用户"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证凭证"
            )
        # 将字符串转换回整数
        user_id = int(user_id_str)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )
    
    user = db.query(Secretary).filter(Secretary.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )
    return user


# ==================== API 路由 ====================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db_session)):
    """
    用户登录
    支持通过账号(account)、用户名(username)或邮箱(email)登录
    验证密码，返回 JWT token
    """
    from sqlalchemy import or_
    
    # 查询用户 - 支持账号、用户名、邮箱三种方式
    user = db.query(Secretary).filter(
        or_(
            Secretary.account == request.account,
            Secretary.username == request.account,
            Secretary.email == request.account
        )
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误"
        )
    
    # 验证密码
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误"
        )
    
    # 创建 token（sub 必须是字符串）
    access_token = create_access_token(data={"sub": str(user.id)})
    
    # 获取部门信息
    department = db.query(Department).filter(Department.id == user.department_id).first()
    
    return LoginResponse(
        success=True,
        token=access_token,
        user={
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "department": department.name if department else None
        }
    )


@router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db_session)):
    """
    用户注册
    创建新的 Secretary 记录
    """
    # 检查工号是否已存在
    existing_id = db.query(Secretary).filter(Secretary.id == request.employee_id).first()
    if existing_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="工号已被注册"
        )
    
    # 检查用户名是否已存在
    existing_username = db.query(Secretary).filter(Secretary.username == request.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查账号是否已存在（使用用户名作为账号）
    existing_account = db.query(Secretary).filter(Secretary.account == request.username).first()
    if existing_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账号已存在"
        )
    
    # 检查邮箱是否已存在（如果提供了邮箱）
    if request.email:
        existing_email = db.query(Secretary).filter(Secretary.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )
    
    # 验证院系是否存在
    department = db.query(Department).filter(Department.id == request.department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="院系不存在"
        )
    
    # 创建新用户（使用工号作为id）
    new_user = Secretary(
        id=request.employee_id,  # 使用工号作为主键
        name=request.name,
        department_id=request.department_id,
        username=request.username,
        account=request.username,  # 使用用户名作为账号
        password_hash=hash_password(request.password),
        email=request.email,
        phone=request.phone
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败：{str(e)}"
        )
    
    return RegisterResponse(
        success=True,
        message="注册成功"
    )


@router.get("/departments", response_model=list[DepartmentResponse])
async def get_departments(db: Session = Depends(get_db_session)):
    """
    获取所有院系列表
    用于注册页面的下拉选择
    """
    departments = db.query(Department).all()
    return [
        DepartmentResponse(id=dept.id, name=dept.name)
        for dept in departments
    ]


@router.get("/me")
async def get_current_user_info(
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取当前登录用户信息
    """
    # 获取部门信息
    department = db.query(Department).filter(Department.id == current_user.department_id).first()
    
    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "name": current_user.name,
            "username": current_user.username,
            "email": current_user.email,
            "phone": current_user.phone,
            "department": department.name if department else None
        }
    }


@router.post("/logout")
async def logout():
    """
    登出（前端删除 token 即可）
    """
    return {"success": True, "message": "登出成功"}
