"""
模板创建/更新的核心业务逻辑
供 API 路由和 Agent Service 共享使用
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.database.models import TemplateForm, TemplateFormField
from backend.logger import get_logger

logger = get_logger(__name__)

# 允许的字段类型
ALLOWED_TYPES = {'TEXT', 'INTEGER', 'FLOAT', 'DATE', 'DATETIME', 'BOOLEAN', 'EMAIL', 'PHONE', 'ID_CARD', 'EMPLOYEE_ID'}


class TemplateCreationError(Exception):
    """模板创建相关异常"""
    pass


def validate_field_data(field_data: dict) -> tuple[bool, str]:
    """验证单个字段的数据格式
    
    Args:
        field_data: 字段数据，包含 display_name, validation_rule, ord
        
    Returns:
        (is_valid, error_message): (是否有效, 错误信息或"OK")
    """
    # 检查必填字段
    if 'display_name' not in field_data:
        return False, "字段缺少 display_name"
    
    if not isinstance(field_data['display_name'], str) or not field_data['display_name'].strip():
        return False, "display_name 必须是非空字符串"
    
    if len(field_data['display_name']) > 100:
        return False, "display_name 长度不能超过100个字符"
    
    if 'ord' not in field_data:
        return False, "字段缺少 ord"
    
    if not isinstance(field_data['ord'], int) or field_data['ord'] < 0:
        return False, "ord 必须是非负整数"
    
    # 检查 validation_rule
    if 'validation_rule' in field_data and field_data['validation_rule'] is not None:
        validation_rule = field_data['validation_rule']
        
        if not isinstance(validation_rule, dict):
            return False, "validation_rule 必须是对象"
        
        # 检查 type 字段
        if 'type' in validation_rule:
            vtype = validation_rule['type']
            
            if not isinstance(vtype, str):
                return False, "validation_rule.type 必须是字符串"
            
            vtype_upper = vtype.upper()
            if vtype_upper not in ALLOWED_TYPES:
                return False, f"validation_rule.type '{vtype}' 不在允许的类型中: {ALLOWED_TYPES}"
            
            # 验证类型特定的属性
            is_valid, msg = validate_type_specific_attrs(vtype_upper, validation_rule)
            if not is_valid:
                return False, msg
    
    return True, "OK"


def validate_type_specific_attrs(field_type: str, validation_rule: dict) -> tuple[bool, str]:
    """验证类型特定的属性
    
    Args:
        field_type: 字段类型（大写）
        validation_rule: 验证规则字典
        
    Returns:
        (is_valid, error_message)
    """
    # TEXT 类型：min_length, max_length
    if field_type == 'TEXT':
        if 'min_length' in validation_rule:
            if not isinstance(validation_rule['min_length'], int) or validation_rule['min_length'] < 0:
                return False, "TEXT 类型的 min_length 必须是非负整数"
        
        if 'max_length' in validation_rule:
            if not isinstance(validation_rule['max_length'], int) or validation_rule['max_length'] < 1:
                return False, "TEXT 类型的 max_length 必须是正整数"
        
        # 检查 min_length <= max_length
        if 'min_length' in validation_rule and 'max_length' in validation_rule:
            if validation_rule['min_length'] > validation_rule['max_length']:
                return False, "TEXT 类型的 min_length 不能大于 max_length"
    
    # INTEGER 和 FLOAT 类型：min, max
    elif field_type in ('INTEGER', 'FLOAT'):
        if 'min' in validation_rule:
            if not isinstance(validation_rule['min'], (int, float)):
                return False, f"{field_type} 类型的 min 必须是数字"
        
        if 'max' in validation_rule:
            if not isinstance(validation_rule['max'], (int, float)):
                return False, f"{field_type} 类型的 max 必须是数字"
        
        # 检查 min <= max
        if 'min' in validation_rule and 'max' in validation_rule:
            if validation_rule['min'] > validation_rule['max']:
                return False, f"{field_type} 类型的 min 不能大于 max"
    
    return True, "OK"


def create_template_core(
    name: str,
    fields: List[dict],
    description: Optional[str],
    created_by: int,
    db: Session
) -> Dict[str, Any]:
    """创建模板的核心逻辑（不包含 HTTP 相关处理）
    
    Args:
        name: 模板名称
        fields: 字段列表，每个元素包含 display_name, validation_rule, ord
        description: 模板描述
        created_by: 创建者ID
        db: 数据库 Session
        
    Returns:
        {
            "success": True/False,
            "message": str,
            "data": {"template_id": int} | None
        }
        
    Raises:
        TemplateCreationError: 创建失败时抛出
    """
    try:
        # 1. 验证模板名称
        if not name or not isinstance(name, str):
            raise TemplateCreationError("模板名称不能为空")
        
        if len(name) > 100:
            raise TemplateCreationError("模板名称长度不能超过100个字符")
        
        # 2. 检查模板名称是否已存在
        existing = db.query(TemplateForm).filter(
            TemplateForm.name == name,
            TemplateForm.created_by == created_by
        ).first()
        
        if existing:
            raise TemplateCreationError(f"模板名称 '{name}' 已存在")
        
        # 3. 验证字段列表
        if not fields or not isinstance(fields, list):
            raise TemplateCreationError("字段列表不能为空")
        
        if len(fields) == 0:
            raise TemplateCreationError("至少需要一个字段")
        
        # 4. 验证每个字段
        for idx, field_data in enumerate(fields):
            if not isinstance(field_data, dict):
                raise TemplateCreationError(f"第 {idx + 1} 个字段格式错误：必须是对象")
            
            is_valid, error_msg = validate_field_data(field_data)
            if not is_valid:
                raise TemplateCreationError(f"第 {idx + 1} 个字段验证失败：{error_msg}")
        
        # 5. 创建模板
        new_template = TemplateForm(
            name=name,
            description=description,
            created_by=created_by,
            extra=None
        )
        
        db.add(new_template)
        db.flush()  # 获取 template_id
        
        # 6. 创建字段
        for field_data in fields:
            new_field = TemplateFormField(
                form_id=new_template.id,
                display_name=field_data['display_name'],
                validation_rule=field_data.get('validation_rule'),
                ord=field_data['ord']
            )
            db.add(new_field)
        
        # 7. 提交事务
        db.commit()
        
        logger.info(f"Template created successfully: id={new_template.id}, name={name}, created_by={created_by}")
        
        return {
            "success": True,
            "message": "模板创建成功",
            "data": {"template_id": new_template.id}
        }
    
    except TemplateCreationError as e:
        db.rollback()
        logger.warning(f"Template creation validation failed: {str(e)}")
        return {
            "success": False,
            "message": str(e),
            "data": None
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Template creation failed with exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "message": f"创建模板时发生错误：{str(e)}",
            "data": None
        }


def update_template_core(
    template_id: int,
    name: Optional[str],
    fields: Optional[List[dict]],
    description: Optional[str],
    user_id: int,
    db: Session
) -> Dict[str, Any]:
    """更新模板的核心逻辑（不包含 HTTP 相关处理）
    
    Args:
        template_id: 模板ID
        name: 新模板名称（可选）
        fields: 新字段列表（可选）
        description: 新描述（可选）
        user_id: 用户ID（用于权限检查）
        db: 数据库 Session
        
    Returns:
        {
            "success": True/False,
            "message": str,
            "data": None
        }
    """
    try:
        # 1. 查找模板
        template = db.query(TemplateForm).filter(
            TemplateForm.id == template_id,
            TemplateForm.created_by == user_id
        ).first()
        
        if not template:
            raise TemplateCreationError("模板不存在或无权访问")
        
        # 2. 更新名称
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise TemplateCreationError("模板名称不能为空")
            
            if len(name) > 100:
                raise TemplateCreationError("模板名称长度不能超过100个字符")
            
            # 检查名称是否重复
            existing = db.query(TemplateForm).filter(
                TemplateForm.name == name,
                TemplateForm.created_by == user_id,
                TemplateForm.id != template_id
            ).first()
            
            if existing:
                raise TemplateCreationError(f"模板名称 '{name}' 已存在")
            
            template.name = name
        
        # 3. 更新描述
        if description is not None:
            template.description = description
        
        # 4. 更新字段
        if fields is not None:
            if not isinstance(fields, list):
                raise TemplateCreationError("字段列表格式错误")
            
            # 验证每个字段
            for idx, field_data in enumerate(fields):
                if not isinstance(field_data, dict):
                    raise TemplateCreationError(f"第 {idx + 1} 个字段格式错误：必须是对象")
                
                is_valid, error_msg = validate_field_data(field_data)
                if not is_valid:
                    raise TemplateCreationError(f"第 {idx + 1} 个字段验证失败：{error_msg}")
            
            # 删除旧字段
            db.query(TemplateFormField).filter(
                TemplateFormField.form_id == template_id
            ).delete()
            
            # 添加新字段
            for field_data in fields:
                new_field = TemplateFormField(
                    form_id=template_id,
                    display_name=field_data['display_name'],
                    validation_rule=field_data.get('validation_rule'),
                    ord=field_data['ord']
                )
                db.add(new_field)
        
        # 5. 提交事务
        db.commit()
        
        logger.info(f"Template updated successfully: id={template_id}")
        
        return {
            "success": True,
            "message": "模板更新成功",
            "data": None
        }
    
    except TemplateCreationError as e:
        db.rollback()
        logger.warning(f"Template update validation failed: {str(e)}")
        return {
            "success": False,
            "message": str(e),
            "data": None
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Template update failed with exception: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "message": f"更新模板时发生错误：{str(e)}",
            "data": None
        }
