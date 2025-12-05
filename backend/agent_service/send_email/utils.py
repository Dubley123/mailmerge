from typing import List, Dict, Any
from backend.database.db_config import get_session_factory
from backend.database.models import Secretary, Teacher


def fetch_teachers_for_secretary(secretary_id: int) -> List[Dict[str, Any]]:
    """Query DB and return a list of teachers in the secretary's department.

    Returns minimal teacher info: id, employee id (工号), name, email, phone, title, office
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        sec = db.query(Secretary).filter(Secretary.id == secretary_id).first()
        if not sec:
            return []
        dept_id = sec.department_id
        teachers = db.query(Teacher).filter(Teacher.department_id == dept_id).all()
        result = []
        for t in teachers:
            result.append({
                "id": t.id,
                "employee_id": t.id,
                "name": t.name,
                "email": t.email,
                "phone": t.phone,
                "title": t.title,
                "office": t.office
            })
        return result
    finally:
        db.close()
