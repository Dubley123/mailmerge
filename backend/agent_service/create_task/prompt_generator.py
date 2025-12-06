from typing import Dict, Any, List
from datetime import datetime

def generate_create_task_prompt(user_id: int, templates: List[Dict[str, Any]], teachers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成创建任务的Prompt"""
    
    # 格式化模板列表
    templates_str = "可用的表单模板列表：\n"
    if not templates:
        templates_str += "（暂无可用模板）\n"
    else:
        for t in templates:
            fields_str = ", ".join(t['fields'])
            templates_str += f"- ID: {t['id']}, 名称: {t['name']}, 包含字段: [{fields_str}]\n"
            
    # 格式化教师列表
    teachers_str = "可用的教师列表：\n"
    if not teachers:
        teachers_str += "（暂无教师信息）\n"
    else:
        for t in teachers:
            teachers_str += f"- ID: {t['id']}, 姓名: {t['name']}, 邮箱: {t['email']}, 职称: {t['title'] or '无'}\n"

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_weekday = datetime.now().isoweekday()

    system_prompt = f"""你是一个智能任务创建助手。你的目标是根据用户的自然语言描述，提取创建收集任务所需的信息。

当前时间：{current_time}
当前星期：{current_weekday}

{templates_str}
{teachers_str}

请遵循以下规则：
1. **必须**从上述“可用的表单模板列表”中选择一个最匹配的模板ID。如果用户指定的模板不存在，或者用户想要创建新模板，请**拒绝**并告知用户先创建模板。
2. **必须**从上述“可用的教师列表”中选择目标教师ID列表。如果用户未指定具体教师，你可以根据上下文推断（例如“所有教授”），如果无法推断，请拒绝。
3. 任务名称（name）如果用户未指定，请根据模板名称和当前时间自动生成一个合理的名称（例如“2023年12月教师信息收集”）。
4. 截止时间（deadline）如果用户未指定，请不要填写该字段，系统将自动设置为开始时间后7天。
5. 开始时间（started_time）如果用户未指定，请不要填写该字段，系统将自动设置为5分钟后。
6. 邮件标题（mail_subject）和邮件正文（mail_content）如果用户未指定，请根据任务内容自动生成礼貌、专业的通知邮件内容。
7. 每次只允许创建一个任务。

你需要提取以下字段并调用 `create_task` 工具：
- name: 任务名称 (string)
- description: 任务描述 (string, 可选)
- deadline: 截止时间 (string, ISO8601格式, 可选)
- started_time: 开始时间 (string, ISO8601格式, 可选)
- template_id: 模板ID (integer)
- mail_subject: 邮件标题 (string)
- mail_content: 邮件正文 (string)
- teacher_ids: 目标教师ID列表 (array of integers)
"""

    tools = [
        {
            "type": "function",
            "function": {
                "name": "create_task",
                "description": "创建一个新的数据收集任务",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "任务名称"
                        },
                        "description": {
                            "type": "string",
                            "description": "任务描述"
                        },
                        "deadline": {
                            "type": "string",
                            "description": "截止时间 (ISO8601格式)"
                        },
                        "started_time": {
                            "type": "string",
                            "description": "开始时间 (ISO8601格式)"
                        },
                        "template_id": {
                            "type": "integer",
                            "description": "使用的表单模板ID"
                        },
                        "mail_subject": {
                            "type": "string",
                            "description": "通知邮件的标题"
                        },
                        "mail_content": {
                            "type": "string",
                            "description": "通知邮件的正文内容"
                        },
                        "teacher_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "目标教师的ID列表"
                        }
                    },
                    "required": ["name", "template_id", "mail_subject", "mail_content", "teacher_ids"]
                }
            }
        }
    ]

    return {
        "system_prompt": system_prompt,
        "tools": tools
    }
