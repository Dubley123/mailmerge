from typing import Dict, Any
from ..config import Config
from ..llm_client import LLMClient
from .prompt_generator import generate_send_email_prompt
from .utils import fetch_teachers_for_secretary
from backend.logger import get_logger
from backend.database.db_config import get_session_factory
from backend.utils.encryption import decrypt_value
from backend.email_service.email_publisher import get_smtp_config
from backend.email_service import send_email as send_email_func
from backend.database.models import Secretary, Teacher, SentEmail, EmailStatus
from backend.utils import get_utc_now

logger = get_logger(__name__)


def handle_send_email(user_input: str, user_id: int = None) -> Dict[str, Any]:
    """Handle send_email action: ask LLM to produce subject/body/recipients, then send.

    Returns structure similar to other handlers:
    {"status": "success"|"error", "data": {...}}
    """
    if user_id is None:
        return {"status": "error", "data": {"message": "缺少 user_id，无法发送邮件"}}

    config = Config.from_env()
    llm_client = LLMClient()
    SessionLocal = get_session_factory()

    # Fetch teachers once
    teacher_list = fetch_teachers_for_secretary(user_id)
    logger.info(f"Fetched {len(teacher_list)} teachers for secretary ID {user_id}")
    logger.info(f"Teacher list:\n{chr(10).join([str(t) for t in teacher_list])}")
    
    
    # Generate prompt (embedding teacher list)
    prompt_data = generate_send_email_prompt(user_id=user_id, teacher_list=teacher_list)
    system_prompt = prompt_data["system_prompt"]
    tools = prompt_data["tools"]

    conversation_history = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    max_retries = config.MAX_RETRY
    for attempt in range(1, max_retries + 1):
        logger.info(f"发送邮件尝试 {attempt}/{max_retries}")
        try:
            llm_response = llm_client.chat_with_history(
                messages=conversation_history,
                tools=tools,
                temperature=0.2
            )

            if llm_response["type"] != "tool_call":
                logger.error("LLM未返回send_email工具调用")
                conversation_history.append({"role": "assistant", "content": llm_response.get("content")})
                conversation_history.append({"role": "user", "content": "请使用send_email工具返回邮件字段和接收者列表"})
                continue

            tool_call = llm_response["tool_calls"][0]
            if tool_call["name"] != "send_email":
                logger.error(f"LLM调用了错误的工具: {tool_call['name']}")
                continue

            args = tool_call.get("arguments", {})
            subject = args.get("subject", "").strip()
            body = args.get("body", "").strip()
            recipients = args.get("recipients", [])
            attachments = args.get("attachments", [])

            # Validation
            if attachments:
                return {"status": "error", "data": {"message": "当前不支持附件发送，请移除附件后重试"}}

            if not recipients:
                return {"status": "error", "data": {"message": "未能推断出目标收件人，请提供明确的教师列表或联系方式"}}

            # Normalize recipients to emails and validate they are within department
            # Use the already fetched teacher_list for validation
            allowed_emails = {t['email']: t for t in teacher_list if t.get('email')}
            allowed_ids = {str(t['id']): t for t in teacher_list}

            final_recipients = []
            recipient_teacher_ids = []
            
            for r in recipients:
                r_str = str(r).strip()
                if r_str in allowed_ids:
                    t = allowed_ids[r_str]
                    if t.get('email'):
                        final_recipients.append(t['email'])
                        recipient_teacher_ids.append(t['id'])
                elif r_str in allowed_emails:
                    final_recipients.append(r_str)
                    recipient_teacher_ids.append(allowed_emails[r_str]['id'])
                else:
                    # Not in allowed list -> reject
                    return {"status": "error", "data": {"message": f"收件人 {r_str} 不在当前秘书的院系教师列表中，已拒绝"}}

            if not final_recipients:
                return {"status": "error", "data": {"message": "没有有效的收件人邮箱，操作终止"}}

            # Send emails
            db = SessionLocal()
            try:
                sec = db.query(Secretary).filter(Secretary.id == user_id).first()
                if not sec:
                    return {"status": "error", "data": {"message": "未找到当前秘书信息"}}

                # Decrypt secretary auth code for SMTP
                if not sec.mail_auth_code:
                    return {"status": "error", "data": {"message": "当前秘书未配置邮箱授权码，无法发送邮件"}}

                try:
                    auth_code = decrypt_value(sec.mail_auth_code)
                except Exception as e:
                    logger.error(f"解密邮箱授权码失败: {e}")
                    return {"status": "error", "data": {"message": "解密邮箱授权码失败，无法发送邮件"}}

                smtp_cfg = get_smtp_config(sec.email)

                # Only send once for all recipients using same content
                results = []
                for idx, to_email in enumerate(final_recipients):
                    result = send_email_func(
                        sender_email=sec.email,
                        sender_password=auth_code,
                        receiver_email=to_email,
                        email_content={"subject": subject, "body": body, "attachments": []},
                        smtp_server=smtp_cfg['smtp_server'],
                        smtp_port=smtp_cfg['smtp_port']
                    )

                    # Record to DB
                    status = EmailStatus.SENT if result.get('success') else EmailStatus.FAILED
                    sent_email = SentEmail(
                        task_id=None,
                        from_sec_id=sec.id,
                        to_tea_id=recipient_teacher_ids[idx] if idx < len(recipient_teacher_ids) else None,
                        sent_at=get_utc_now() if result.get('success') else None,
                        status=status,
                        mail_content={"subject": subject, "body": body},
                        attachment_id=None,
                        extra={"error": result.get('message')} if not result.get('success') else None
                    )
                    db.add(sent_email)
                    results.append(result)

                db.commit()

                # Summarize results
                success_count = sum(1 for r in results if r.get('success'))
                return {"status": "success", "data": {"sent": success_count, "total": len(results), "results": results}}

            finally:
                db.close()

        except Exception as e:
            logger.error(f"处理send_email过程中发生异常: {e}", exc_info=True)
            conversation_history.append({"role": "user", "content": f"发生错误：{str(e)}\n请重新生成邮件内容。"})

    return {"status": "error", "data": {"message": f"经过 {max_retries} 次尝试仍未成功生成发送邮件的内容"}}
