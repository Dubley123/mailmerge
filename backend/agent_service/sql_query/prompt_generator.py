"""
SQL Query Prompt Generator
负责生成SQL查询相关的Prompt和工具定义
"""
from typing import Dict, Any, List
from pathlib import Path
import re


def generate_sql_query_prompt(user_id: int = None) -> Dict[str, Any]:
    """生成SQL查询的Prompt和工具定义
    
    Args:
        user_id: 当前用户的ID（secretary表的主键），用于权限控制
        
    Returns:
        {
            "system_prompt": str,        # 系统提示词
            "tools": List[Dict],          # 工具定义（Tool Calling）
            "allowed_tables": List[str]   # 允许查询的表名列表
        }
    """
    # 加载数据库Schema
    schema_text = _load_database_schema()
    allowed_tables = _extract_table_names(schema_text)
    
    # 构建权限控制说明
    permission_instruction = ""
    if user_id is not None:
        permission_instruction = f"""
## 权限控制规则（必须严格遵守）
当前用户的ID (secretary_id) 为: {user_id}

你必须根据以下规则限制查询范围：

1. **公开数据（无限制）**：
   - 表：`department`, `secretary`, `teacher`
   - 规则：允许查询所有数据，不需要添加权限过滤条件。

2. **私有数据（仅限本人）**：
   - 表：除上述公开表之外的所有表（如 `collect_task`, `template_form`, `sent_email` 等）
   - 规则：必须在 WHERE 子句中添加过滤条件，确保只查询当前用户创建或相关的数据。
   - 示例：
     - 查询任务：`WHERE created_by = {user_id}`
     - 查询模板：`WHERE created_by = {user_id}`
     - 查询发送邮件：`WHERE from_sec_id = {user_id}`
     - 查询接收邮件：`WHERE to_sec_id = {user_id}`
     - 查询关联表（如 `template_form_field`）：必须通过 JOIN 确保主表（`template_form`）是当前用户创建的。

3. **越权请求处理**：
   - 如果用户显式要求查询超出其权限范围的数据（例如"查询所有人的任务"），你必须**拒绝**该越权请求，仍然强制加上 `WHERE created_by = {user_id}` 等限制条件。
   - 同时，你必须在 `run_sql` 工具的 `permission_warning` 字段中说明情况。
"""
    else:
        permission_instruction = "\n## 权限控制\n当前未提供用户ID，假设拥有全局查询权限（仅用于测试环境）。"

    # 构建系统提示词
    system_prompt = f"""你是一个专业的SQL查询助手，负责根据用户的自然语言需求生成PostgreSQL查询语句。

## 你的职责
1. 理解用户的自然语言查询需求
2. 根据数据库Schema生成正确的SQL SELECT查询
3. 严格遵守权限控制规则，确保数据安全
4. 使用run_sql工具返回SQL查询语句

## 数据库Schema
{schema_text}
{permission_instruction}

## 安全规则（必须严格遵守）
1. **仅允许SELECT查询**：不得生成INSERT、UPDATE、DELETE、DROP等修改操作
2. **仅查询允许的表**：只能查询上述Schema中列出的表
3. **单条SQL**：每次只返回一条SQL语句
4. **使用标准语法**：使用PostgreSQL标准语法
5. **避免危险函数**：不得使用pg_sleep、pg_read_file等系统函数

## 工作流程
1. 分析用户需求，确定需要查询的表和字段
2. 判断涉及的表属于"公开数据"还是"私有数据"
3. 如果涉及"私有数据"，必须添加基于 `secretary_id={user_id}` 的过滤条件
4. 生成符合PostgreSQL语法的SELECT查询
5. 使用run_sql工具返回SQL，如果有越权请求，填写 `permission_warning` 字段

## 示例
假设当前用户ID为 100

用户: "查询所有院系的名称"
返回: run_sql(sql="SELECT name FROM department;")  <-- 公开表，无限制

用户: "查询我创建的所有任务"
返回: run_sql(sql="SELECT * FROM collect_task WHERE created_by = 100;") <-- 私有表，添加限制

用户: "查询所有人的任务"
返回: run_sql(
    sql="SELECT * FROM collect_task WHERE created_by = 100;",  <-- 强制添加限制
    permission_warning="根据权限规则，您只能查看自己创建的任务。已为您过滤显示本人的任务数据。"
)
"""

    # 定义工具（Tool Calling）
    tools = [
        {
            "type": "function",
            "function": {
                "name": "run_sql",
                "description": "执行SQL查询并返回结果",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "要执行的SQL SELECT查询语句"
                        },
                        "permission_warning": {
                            "type": "string",
                            "description": "如果用户的请求超出了权限范围（例如请求查看他人的私有数据），在此字段中说明原因。如果未越权，则留空。"
                        }
                    },
                    "required": ["sql"]
                }
            }
        }
    ]
    
    return {
        "system_prompt": system_prompt,
        "tools": tools,
        "allowed_tables": allowed_tables
    }


def _load_database_schema() -> str:
    """从database.md加载数据库Schema
    
    Returns:
        str: Schema文本
    """
    # 默认路径：项目根目录下的database.md
    db_schema_path = Path(__file__).parent.parent.parent.parent / "database.md"
    
    if not db_schema_path.exists():
        return "## 数据库Schema未找到\n请确保database.md文件存在"
    
    try:
        with open(db_schema_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"## 读取数据库Schema失败\n错误: {str(e)}"


def _extract_table_names(schema_text: str) -> List[str]:
    """从Schema文本中提取表名列表
    
    Args:
        schema_text: database.md的内容
        
    Returns:
        List[str]: 表名列表
    """
    # 匹配表名（支持多种格式）
    # 格式1: ### 表名: xxx
    # 格式2: ## xxx 表
    # 格式3: CREATE TABLE xxx
    
    tables = set()
    
    # 匹配 ### 表名: xxx
    pattern1 = r'###\s*表名[:：]\s*`?(\w+)`?'
    tables.update(re.findall(pattern1, schema_text))
    
    # 匹配 ## xxx 表
    pattern2 = r'##\s+(\w+)\s*表'
    tables.update(re.findall(pattern2, schema_text))
    
    # 匹配 CREATE TABLE xxx
    pattern3 = r'CREATE TABLE\s+`?(\w+)`?'
    tables.update(re.findall(pattern3, schema_text, re.IGNORECASE))
    
    return sorted(list(tables))
