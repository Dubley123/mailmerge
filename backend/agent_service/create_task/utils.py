from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.database.db_config import get_session_factory
from backend.database.models import TemplateForm, Teacher, Secretary

def fetch_available_templates(user_id: int) -> List[Dict[str, Any]]:
    """获取当前用户可用的模板列表"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        # 获取当前秘书创建的模板
        templates = db.query(TemplateForm).filter(
            TemplateForm.created_by == user_id
        ).all()
        
        result = []
        for t in templates:
            # 获取模板字段
            fields = [f.display_name for f in t.fields]
            result.append({
                "id": t.id,
                "name": t.name,
                "fields": fields
            })
        return result
    finally:
        db.close()

def fetch_available_teachers(user_id: int) -> List[Dict[str, Any]]:
    """获取当前用户所在院系的教师列表"""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        secretary = db.query(Secretary).filter(Secretary.id == user_id).first()
        if not secretary:
            return []
            
        teachers = db.query(Teacher).filter(
            Teacher.department_id == secretary.department_id
        ).all()
        
        result = []
        for t in teachers:
            result.append({
                "id": t.id,
                "name": t.name,
                "email": t.email,
                "phone": t.phone,
                "title": t.title,
                "office": t.office
            })
        return result
    finally:
        db.close()
