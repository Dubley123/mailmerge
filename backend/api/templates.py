"""
模板相关 API 路由
处理表单模板的创建、查看、编辑等操作
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import openpyxl
from openpyxl.cell import Cell
import io
from backend.utils import ensure_utc

from backend.database.db_config import get_db_session
from backend.database.models import TemplateForm, TemplateFormField, Secretary, DataType
from backend.api.auth import get_current_user

router = APIRouter()


# ==================== Pydantic 模型 ====================

class FieldRequest(BaseModel):
    """字段请求"""
    display_name: str = Field(..., min_length=1, max_length=100)
    data_type: str = Field(..., description="字段类型：TEXT/NUMBER/DATE/TIME/BOOLEAN/RADIO/CHECKBOX")
    required: bool = False
    ord: int = Field(..., ge=0, description="字段顺序")


class FieldResponse(BaseModel):
    """字段响应"""
    id: int
    display_name: str
    data_type: str
    required: bool
    ord: int


class TemplateResponse(BaseModel):
    """模板响应"""
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    field_count: int = 0


class TemplateDetailResponse(BaseModel):
    """模板详情响应"""
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    fields: List[FieldResponse]


class CreateTemplateRequest(BaseModel):
    """创建模板请求"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    fields: List[FieldRequest] = Field(..., min_items=1, description="至少包含一个字段")


class UpdateTemplateRequest(BaseModel):
    """更新模板请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    fields: Optional[List[FieldRequest]] = None


# ==================== API 路由 ====================

@router.get("/", response_model=List[TemplateResponse])
async def get_templates(
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取当前用户创建的所有模板
    """
    templates = db.query(TemplateForm).filter(
        TemplateForm.created_by == current_user.id
    ).all()
    
    result = []
    for template in templates:
        field_count = db.query(TemplateFormField).filter(
            TemplateFormField.form_id == template.id
        ).count()
        
        result.append(TemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            created_at=ensure_utc(template.created_at),
            field_count=field_count
        ))
    
    return result


@router.get("/list", response_model=List[TemplateResponse])
async def get_templates_list(
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取当前用户创建的所有模板（别名路由）
    """
    return await get_templates(current_user, db)


@router.get("/{template_id}", response_model=TemplateDetailResponse)
async def get_template_detail(
    template_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    获取模板详情，包含所有字段
    """
    template = db.query(TemplateForm).filter(
        TemplateForm.id == template_id,
        TemplateForm.created_by == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在或无权访问"
        )
    
    fields = db.query(TemplateFormField).filter(
        TemplateFormField.form_id == template_id
    ).order_by(TemplateFormField.ord).all()
    
    return TemplateDetailResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        created_at=ensure_utc(template.created_at),
        fields=[
            FieldResponse(
                id=field.id,
                display_name=field.display_name,
                data_type=field.data_type.value,
                required=field.required,
                ord=field.ord
            )
            for field in fields
        ]
    )


@router.post("/create")
async def create_template(
    request: CreateTemplateRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    创建新模板
    """
    try:
        # 检查模板名称是否已存在
        existing = db.query(TemplateForm).filter(
            TemplateForm.name == request.name,
            TemplateForm.created_by == current_user.id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="模板名称已存在"
            )
        
        # 创建模板
        new_template = TemplateForm(
            name=request.name,
            description=request.description,
            created_by=current_user.id,
            extra=None
        )
        
        db.add(new_template)
        db.flush()
        
        # 创建字段
        for field_data in request.fields:
            try:
                data_type_enum = DataType(field_data.data_type.upper())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的字段类型: {field_data.data_type}"
                )
            
            new_field = TemplateFormField(
                form_id=new_template.id,
                display_name=field_data.display_name,
                data_type=data_type_enum,
                required=field_data.required,
                ord=field_data.ord
            )
            db.add(new_field)
        
        db.commit()
        
        return {
            "success": True,
            "message": "模板创建成功",
            "data": {"template_id": new_template.id}
        }
    
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print(f"[ERROR] 创建模板失败: {str(e)}")
        print(f"[ERROR] 请求数据: name={request.name}, fields={request.fields}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建模板失败：{str(e)}"
        )


@router.put("/{template_id}")
async def update_template(
    template_id: int,
    request: UpdateTemplateRequest,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    更新模板
    """
    template = db.query(TemplateForm).filter(
        TemplateForm.id == template_id,
        TemplateForm.created_by == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在或无权访问"
        )
    
    try:
        # 更新模板名称
        if request.name is not None:
            # 检查名称是否重复
            existing = db.query(TemplateForm).filter(
                TemplateForm.name == request.name,
                TemplateForm.created_by == current_user.id,
                TemplateForm.id != template_id
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="模板名称已存在"
                )
            
            template.name = request.name
        
        # 更新描述
        if request.description is not None:
            template.description = request.description
        
        # 更新字段
        if request.fields is not None:
            # 删除旧字段
            db.query(TemplateFormField).filter(
                TemplateFormField.form_id == template_id
            ).delete()
            
            # 添加新字段
            for field_data in request.fields:
                try:
                    data_type_enum = DataType(field_data.data_type.upper())
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"无效的字段类型: {field_data.data_type}"
                    )
                
                new_field = TemplateFormField(
                    form_id=template_id,
                    display_name=field_data.display_name,
                    data_type=data_type_enum,
                    required=field_data.required,
                    ord=field_data.ord
                )
                db.add(new_field)
        
        db.commit()
        
        return {
            "success": True,
            "message": "模板更新成功"
        }
    
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新模板失败：{str(e)}"
        )


@router.delete("/{template_id}")
async def delete_template(
    template_id: int,
    current_user: Secretary = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """
    删除模板
    """
    template = db.query(TemplateForm).filter(
        TemplateForm.id == template_id,
        TemplateForm.created_by == current_user.id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在或无权访问"
        )
    
    try:
        # 删除所有字段（级联）
        db.query(TemplateFormField).filter(
            TemplateFormField.form_id == template_id
        ).delete()
        
        # 删除模板
        db.delete(template)
        db.commit()
        
        return {
            "success": True,
            "message": "模板删除成功"
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除模板失败：{str(e)}"
        )

@router.post("/parse-excel")
async def parse_excel(
    file: UploadFile = File(...),
    current_user: Secretary = Depends(get_current_user)
):
    """
    解析 Excel 文件，提取表头作为模板字段
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 .xlsx 和 .xls 格式的 Excel 文件"
        )
    
    try:
        # 读取文件内容
        contents = await file.read()
        workbook = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
        
        # 获取第一个工作表
        sheet = workbook.active
        
        # 获取文件名作为模板名称（去除扩展名）
        template_name = file.filename.rsplit('.', 1)[0]
        
        # 读取第一行作为字段名
        first_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=False))
        
        fields = []
        for idx, cell in enumerate(first_row):
            if cell.value is None or str(cell.value).strip() == '':
                continue
                
            field_name = str(cell.value).strip()
            
            # 尝试推断字段类型
            data_type = infer_field_type(sheet, idx + 1)
            
            fields.append({
                'display_name': field_name,
                'data_type': data_type,
                'required': False,
                'ord': idx
            })
        
        if not fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Excel 文件第一行没有有效的列名"
            )
        
        return {
            "template_name": template_name,
            "fields": fields
        }
    
    except openpyxl.utils.exceptions.InvalidFileException:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的 Excel 文件格式"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析 Excel 失败：{str(e)}"
        )


def infer_field_type(sheet, column_index: int) -> str:
    """
    根据列的数据推断字段类型
    检查前10行数据（跳过表头）
    """
    # 默认类型
    default_type = 'TEXT'
    
    # 收集样本数据
    samples = []
    for row in sheet.iter_rows(min_row=2, max_row=11, min_col=column_index, max_col=column_index):
        cell = row[0]
        if cell.value is not None and str(cell.value).strip():
            samples.append(cell)
    
    if not samples:
        return default_type
    
    # 检查是否所有样本都是数字
    all_numbers = all(_is_number(cell.value) for cell in samples)
    if all_numbers:
        return 'NUMBER'
    
    # 检查是否有日期格式
    has_date = any(_is_date_cell(cell) for cell in samples)
    if has_date:
        return 'DATE'
    
    # 检查是否有时间格式
    has_time = any(_is_time_cell(cell) for cell in samples)
    if has_time:
        return 'TIME'
    
    # 检查是否是布尔值
    all_boolean = all(_is_boolean(cell.value) for cell in samples)
    if all_boolean:
        return 'BOOLEAN'
    
    # 检查是否是选项（重复值较少）
    unique_values = set(str(cell.value).strip() for cell in samples)
    if len(unique_values) <= 5 and len(samples) >= 5:
        # 如果唯一值较少，可能是单选或多选
        return 'RADIO'
    
    return default_type


def _is_number(value) -> bool:
    """判断是否为数字"""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def _is_date_cell(cell: Cell) -> bool:
    """判断是否为日期单元格"""
    if cell.is_date:
        return True
    
    # 检查格式代码
    if cell.number_format:
        date_formats = ['yyyy', 'yy', 'mm', 'dd', 'd/m', 'm/d']
        format_lower = cell.number_format.lower()
        return any(fmt in format_lower for fmt in date_formats)
    
    return False


def _is_time_cell(cell: Cell) -> bool:
    """判断是否为时间单元格"""
    if cell.number_format:
        time_formats = ['h:mm', 'hh:mm', 'h:mm:ss']
        format_lower = cell.number_format.lower()
        return any(fmt in format_lower for fmt in time_formats)
    
    return False


def _is_boolean(value) -> bool:
    """判断是否为布尔值"""
    if isinstance(value, bool):
        return True
    
    if isinstance(value, str):
        value_lower = value.lower().strip()
        return value_lower in ['true', 'false', 'yes', 'no', '是', '否', '对', '错', '1', '0']
    
    return False
