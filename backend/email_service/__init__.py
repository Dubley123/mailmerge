"""
邮件服务模块
提供邮件发送和接收功能
"""

from .email_service import send_email, fetch_email, EmailService

__all__ = ["send_email", "fetch_email", "EmailService"]
