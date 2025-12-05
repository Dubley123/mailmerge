from typing import Dict, Any, List
from .utils import fetch_teachers_for_secretary


def generate_send_email_prompt(user_id: int = None, teacher_list: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generate system prompt and tool definition for send_email action.

    The prompt embeds a short list of candidate teachers (from the same department as
    the secretary identified by `user_id`) and instructs the LLM to produce a JSON
    containing `subject`, `body`, and `recipients` (list of teacher ids or emails).
    """
    if teacher_list is None and user_id is not None:
        teacher_list = fetch_teachers_for_secretary(user_id)
    elif teacher_list is None:
        teacher_list = []

    # Build a compact representation of teachers for embedding into the prompt
    teacher_lines = []
    for t in teacher_list:
        teacher_lines.append(f"- id:{t['id']} | 工号:{t['employee_id']} | 姓名:{t['name']} | 邮箱:{t['email']} | 手机:{t.get('phone','')} | 职称:{t.get('title','')} | 办公:{t.get('office','')}")

    teachers_text = "\n".join(teacher_lines) if teacher_lines else "(未找到本部门教师列表)"

    system_prompt = f"""你是邮件撰写助手，负责将用户的自然语言意图转换成正式邮件。

规则：
1) 只生成邮件的 `subject` 和 `body`（中文场景下请使用恰当的礼貌用语），保证语气与用户要求一致。
2) 不要添加附件。如果用户明确要求附件，拒绝执行并在结果中返回错误说明。
3) 接收者(`recipients`)必须从下面提供的候选教师列表中选择（可选多个）。候选教师列表：\n{teachers_text}\n
4) 如果用户无法明确指定接收者，或者候选列表为空，请拒绝执行并说明原因（例如：‘无法推断目标教师，请手动选择或提供老师列表’）。
5) 一次发送操作使用一份邮件内容发送给所有选定接收者。
6) 返回格式必须为一次性工具调用 `send_email`，并且 `arguments` 字段为 JSON 对象，包含：
   - `subject`: 字符串
   - `body`: 字符串
   - `recipients`: 列表（每项为教师的 `id` 或 `email`）
   - `attachments`: 可选（不支持，若非空应被视为错误）

示例返回（工具调用形式）：
send_email(subject="...", body="...", recipients=["1","2"])

请严格按照上述要求只返回工具调用，不要输出任何额外解释。"""

    tools = [
        {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": "生成邮件并返回要发送的内容和接收者列表（不负责实际发送，handler负责发送）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "recipients": {"type": "array", "items": {"type": "string"}},
                        "attachments": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["subject", "body", "recipients"]
                }
            }
        }
    ]

    return {"system_prompt": system_prompt, "tools": tools}
