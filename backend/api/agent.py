from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Union, Dict
from pydantic import BaseModel, field_validator
from datetime import datetime
import json

from backend.database.db_config import get_db_session
from backend.database.models import ChatSession, SessionMessage, Secretary
from backend.api.auth import get_current_user
from backend.agent_service import process_user_query
from backend.agent_service.schemas import AgentResponse
from backend.utils import get_utc_now
from backend.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Pydantic Models
class SessionCreate(BaseModel):
    title: Optional[str] = "新对话"

class SessionUpdate(BaseModel):
    title: str

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: int
    role: str
    content: Any
    created_at: datetime

    @field_validator('content', mode='before')
    def parse_content(cls, v):
        if isinstance(v, str):
            # 尝试解析JSON字符串
            # 我们的结构化响应是一个包含 "items" 键的 JSON 对象
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict) and "items" in parsed:
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
        return v

    class Config:
        from_attributes = True

class SessionResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Routes
@router.post("/sessions", response_model=SessionResponse)
def create_session(
    session_in: SessionCreate,
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """创建新的对话会话"""
    # 如果标题是默认值 "新对话"，则自动生成带序号的标题
    title = session_in.title
    if title == "新对话":
        # 查询当前用户的会话数量
        count = db.query(ChatSession).filter(
            ChatSession.secretary_id == current_user.id
        ).count()
        title = f"新对话{count + 1}"

    new_session = ChatSession(
        secretary_id=current_user.id,
        title=title
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """获取当前用户的所有会话列表"""
    sessions = db.query(ChatSession).filter(
        ChatSession.secretary_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    return sessions

@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
def get_messages(
    session_id: int,
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """获取指定会话的所有消息"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.secretary_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 按时间正序排列消息
    messages = db.query(SessionMessage).filter(
        SessionMessage.session_id == session.id
    ).order_by(SessionMessage.created_at.asc()).all()
    
    return messages

@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
def send_message(
    session_id: int,
    message_in: MessageCreate,
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """发送消息给Agent并获取回复"""
    logger.info(f"收到发送消息请求: session_id={session_id}, content={message_in.content}")
    
    # 1. Verify session ownership
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.secretary_id == current_user.id
    ).first()
    if not session:
        logger.warning(f"会话不存在或无权访问: session_id={session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 2. Save user message
    user_msg = SessionMessage(
        session_id=session.id,
        role="user",
        content=message_in.content
    )
    db.add(user_msg)
    db.commit() # Commit user message first so it's saved even if agent fails
    
    # 3. Call Agent Service
    try:
        logger.info("正在调用 Agent Service 处理请求...")
        # Pass user_id for permission control
        agent_response = process_user_query(
            user_input=message_in.content,
            user_id=current_user.id
        )
        
        # Serialize AgentResponse to JSON string for storage
        if isinstance(agent_response, AgentResponse):
            agent_response_text = agent_response.model_dump_json()
        else:
            # Fallback if it returns string (should not happen with new code)
            agent_response_text = str(agent_response)
            
        logger.info("Agent Service 处理完成")
    except Exception as e:
        logger.error(f"Agent Service 处理失败: {e}", exc_info=True)
        # Create an error response in the new format
        error_response = AgentResponse(items=[
            {"format": "text", "content": f"处理请求时发生错误: {str(e)}"}
        ])
        agent_response_text = error_response.model_dump_json()
    
    # 4. Save assistant message
    assistant_msg = SessionMessage(
        session_id=session.id,
        role="assistant",
        content=agent_response_text
    )
    db.add(assistant_msg)
    
    # 5. Update session timestamp
    session.updated_at = get_utc_now()
    
    db.commit()
    db.refresh(assistant_msg)
    
    return assistant_msg

@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """删除会话"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.secretary_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(session)
    db.commit()
    return {"status": "success"}

@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: int,
    session_in: SessionUpdate,
    db: Session = Depends(get_db_session),
    current_user: Secretary = Depends(get_current_user)
):
    """更新会话标题"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.secretary_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.title = session_in.title
    db.commit()
    db.refresh(session)
    return session
