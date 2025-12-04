"""
Create Template Prompt Generator
负责生成创建模板相关的Prompt和工具定义
"""
from typing import Dict, Any
from pathlib import Path


def generate_create_template_prompt() -> Dict[str, Any]:
    """生成创建模板的Prompt和工具定义
    
    Returns:
        {
            "system_prompt": str,   # 系统提示词
            "tools": List[Dict]     # 工具定义（Tool Calling）
        }
    """
    # 加载字段类型文档
    field_types_doc = _load_field_types_doc()
    
    system_prompt = f"""你是一个专业的数据收集模板创建助手，负责根据用户需求设计规范的表单模板。

## 你的职责
1. 理解用户想要收集什么类型的数据
2. 根据字段类型规范设计合理的表单字段
3. 生成符合API格式要求的模板定义
4. 使用create_template工具提交创建请求

## 支持的字段类型规范

{field_types_doc}

## 工作流程
1. 分析用户需求，确定需要收集的信息项
2. 为每个信息项选择合适的字段类型
3. 设置字段的验证规则（type、required、min/max等）
4. 按照逻辑顺序排列字段（ord从0开始）
5. 使用create_template工具提交完整的模板定义

## 字段设计原则
- 姓名类字段：使用TEXT类型，required=true，min_length=2，max_length=20
- 学号/工号：使用EMPLOYEE_ID类型，required=true
- 性别：使用TEXT类型配合options=["男","女"]
- 年龄：使用INTEGER类型，设置合理的min/max范围
- 日期：使用DATE或DATETIME类型
- 邮箱：使用EMAIL类型
- 手机：使用PHONE类型
- 身份证：使用ID_CARD类型
- 是否类字段：使用BOOLEAN类型
- 数值类：使用INTEGER或FLOAT，设置合理范围

## 重要提示
1. validation_rule中的type必须大写（TEXT、INTEGER、FLOAT等）
2. 必须设置ord字段（从0开始的顺序）
3. 字段名称（display_name）应简洁明确
4. 合理使用required标记必填项
5. 为数值型字段设置合理的min/max范围

## 示例

### 示例1：学生信息收集
用户: "创建一个收集学生基本信息的模板，包括姓名、学号、性别、出生日期、联系电话"

create_template({{
  "name": "学生基本信息",
  "description": "收集学生入学信息",
  "fields": [
    {{
      "display_name": "姓名",
      "validation_rule": {{"type": "TEXT", "required": true, "min_length": 2, "max_length": 20}},
      "ord": 0
    }},
    {{
      "display_name": "学号",
      "validation_rule": {{"type": "EMPLOYEE_ID", "required": true}},
      "ord": 1
    }},
    {{
      "display_name": "性别",
      "validation_rule": {{"type": "TEXT", "required": true, "options": ["男", "女"]}},
      "ord": 2
    }},
    {{
      "display_name": "出生日期",
      "validation_rule": {{"type": "DATE", "required": true}},
      "ord": 3
    }},
    {{
      "display_name": "联系电话",
      "validation_rule": {{"type": "PHONE", "required": true}},
      "ord": 4
    }}
  ]
}})

### 示例2：考勤统计
用户: "创建月度考勤统计模板"

create_template({{
  "name": "月度考勤统计",
  "description": "记录员工考勤情况",
  "fields": [
    {{
      "display_name": "工号",
      "validation_rule": {{"type": "EMPLOYEE_ID", "required": true}},
      "ord": 0
    }},
    {{
      "display_name": "姓名",
      "validation_rule": {{"type": "TEXT", "required": true}},
      "ord": 1
    }},
    {{
      "display_name": "出勤天数",
      "validation_rule": {{"type": "INTEGER", "required": true, "min": 0, "max": 31}},
      "ord": 2
    }},
    {{
      "display_name": "是否全勤",
      "validation_rule": {{"type": "BOOLEAN"}},
      "ord": 3
    }}
  ]
}})
"""

    # 定义工具（符合API接口格式）
    tools = [
        {
            "type": "function",
            "function": {
                "name": "create_template",
                "description": "创建数据收集模板，提交到后端API",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "模板名称，1-100字符"
                        },
                        "description": {
                            "type": "string",
                            "description": "模板描述（可选）"
                        },
                        "fields": {
                            "type": "array",
                            "description": "字段列表，至少包含一个字段",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "display_name": {
                                        "type": "string",
                                        "description": "字段显示名称"
                                    },
                                    "validation_rule": {
                                        "type": "object",
                                        "description": "验证规则JSON对象，必须包含type字段",
                                        "properties": {
                                            "type": {
                                                "type": "string",
                                                "enum": ["TEXT", "INTEGER", "FLOAT", "DATE", "DATETIME", "BOOLEAN", "EMAIL", "PHONE", "ID_CARD", "EMPLOYEE_ID"],
                                                "description": "字段类型（必填）"
                                            },
                                            "required": {
                                                "type": "boolean",
                                                "description": "是否必填（可选）"
                                            },
                                            "min_length": {
                                                "type": "integer",
                                                "description": "最小长度（TEXT类型可选）"
                                            },
                                            "max_length": {
                                                "type": "integer",
                                                "description": "最大长度（TEXT类型可选）"
                                            },
                                            "min": {
                                                "type": "number",
                                                "description": "最小值（INTEGER/FLOAT类型可选）"
                                            },
                                            "max": {
                                                "type": "number",
                                                "description": "最大值（INTEGER/FLOAT类型可选）"
                                            },
                                            "options": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                                "description": "可选项列表（TEXT类型可选）"
                                            },
                                            "regex": {
                                                "type": "string",
                                                "description": "正则表达式（TEXT类型可选）"
                                            }
                                        },
                                        "required": ["type"]
                                    },
                                    "ord": {
                                        "type": "integer",
                                        "description": "字段顺序，从0开始"
                                    }
                                },
                                "required": ["display_name", "validation_rule", "ord"]
                            }
                        }
                    },
                    "required": ["name", "fields"]
                }
            }
        }
    ]
    
    return {
        "system_prompt": system_prompt,
        "tools": tools
    }


def _load_field_types_doc() -> str:
    """加载字段类型文档
    
    Returns:
        str: 字段类型文档内容（主要部分）
    """
    doc_path = Path(__file__).parent / "field_types.md"
    
    if not doc_path.exists():
        return "## 字段类型文档未找到\n请检查 field_types.md 文件是否存在"
    
    try:
        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 提取核心表格和规则部分（去掉完整示例）
        # 只保留类型表格和validation_rule结构说明
        lines = content.split('\n')
        core_content = []
        skip_section = False
        
        for line in lines:
            # 跳过完整示例部分
            if line.startswith('## 完整示例'):
                skip_section = True
            elif line.startswith('## 验证错误类型'):
                skip_section = False
            elif line.startswith('## API 接口格式'):
                break
            
            if not skip_section:
                core_content.append(line)
        
        return '\n'.join(core_content[:200])  # 限制长度，避免Prompt过长
        
    except Exception as e:
        return f"## 加载字段类型文档失败\n错误: {str(e)}"
