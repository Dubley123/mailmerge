import openpyxl
import os
import tempfile
from sqlalchemy.orm import Session
from backend.database.models import TemplateForm, TemplateFormField

def generate_template_excel(db: Session, template_id: int, filename: str = None) -> str:
    """
    Generates an Excel template for the given form.
    Returns the path to the temporary file.
    """
    template = db.query(TemplateForm).filter(TemplateForm.id == template_id).first()
    if not template:
        raise ValueError(f"Template with id {template_id} not found")

    fields = db.query(TemplateFormField).filter(
        TemplateFormField.form_id == template_id
    ).order_by(TemplateFormField.ord).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = template.name[:30]  # Excel sheet name limit

    # Write headers
    headers = [f.display_name for f in fields]
    ws.append(headers)

    # Add a few empty rows (e.g., 5)
    for _ in range(5):
        ws.append([None] * len(headers))

    # Save to temp file
    if filename:
        temp_dir = tempfile.gettempdir()
        path = os.path.join(temp_dir, filename)
        wb.save(path)
    else:
        fd, path = tempfile.mkstemp(suffix='.xlsx')
        os.close(fd)
        wb.save(path)
    
    return path
