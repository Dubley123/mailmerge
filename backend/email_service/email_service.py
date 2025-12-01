"""
邮件收发服务模块
提供邮件发送和接收功能
"""
import os
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.header import decode_header
from email.utils import make_msgid
from typing import List, Dict, Optional
import tempfile
import json
from backend.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """邮件服务类"""
    
    def __init__(self):
        """初始化邮件服务"""
        pass
    
    @staticmethod
    def _validate_absolute_path(path: str) -> bool:
        """验证路径是否为绝对路径"""
        return os.path.isabs(path)
    
    @staticmethod
    def _decode_mime_header(header_value):
        """解码邮件头部信息"""
        if header_value is None:
            return ""
        
        decoded_parts = decode_header(header_value)
        header_str = ""
        for content, encoding in decoded_parts:
            if isinstance(content, bytes):
                header_str += content.decode(encoding or 'utf-8', errors='ignore')
            else:
                header_str += content
        return header_str
    
    def send_email(
        self,
        sender_email: str,
        sender_password: str,
        receiver_email: str,
        email_content: Dict,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587
    ) -> Dict:
        """
        发送邮件
        
        Args:
            sender_email: 发送方邮箱地址
            sender_password: 发送方邮箱密码（或应用专用密码）
            receiver_email: 接收方邮箱地址
            email_content: 邮件内容（JSON格式），包含：
                - subject: 邮件标题
                - body: 邮件正文
                - attachments: 附件路径列表（可选）
            smtp_server: SMTP服务器地址
            smtp_port: SMTP服务器端口
        
        Returns:
            Dict: 包含发送结果的字典
        
        Raises:
            ValueError: 如果附件路径不是绝对路径
            FileNotFoundError: 如果附件文件不存在
        """
        try:
            # 验证必需的参数
            if not all([sender_email, sender_password, receiver_email]):
                raise ValueError("发送方邮箱、密码和接收方邮箱不能为空")
            
            # 验证邮件内容格式
            if not isinstance(email_content, dict):
                raise ValueError("email_content必须是字典格式")
            
            subject = email_content.get("subject", "")
            body = email_content.get("body", "")
            attachments = email_content.get("attachments", [])
            
            # 创建邮件对象
            message = MIMEMultipart()
            message["From"] = sender_email
            message["To"] = receiver_email
            message["Subject"] = subject
            
            # Generate Message-ID
            msg_id = make_msgid(domain=sender_email.split('@')[-1])
            message["Message-ID"] = msg_id
            
            # 添加邮件正文
            message.attach(MIMEText(body, "plain", "utf-8"))
            
            # 处理附件
            if attachments:
                if not isinstance(attachments, list):
                    attachments = [attachments]
                
                for attachment_path in attachments:
                    # 验证是否为绝对路径
                    if not self._validate_absolute_path(attachment_path):
                        raise ValueError(f"附件路径必须是绝对路径: {attachment_path}")
                    
                    # 验证文件是否存在
                    if not os.path.exists(attachment_path):
                        raise FileNotFoundError(f"附件文件不存在: {attachment_path}")
                    
                    # 读取并添加附件
                    with open(attachment_path, "rb") as f:
                        attachment = MIMEApplication(f.read())
                        filename = os.path.basename(attachment_path)
                        # Use add_header with keyword arguments to handle non-ASCII filenames (RFC 2231)
                        attachment.add_header(
                            "Content-Disposition",
                            "attachment",
                            filename=filename
                        )
                        message.attach(attachment)
            
            # 连接SMTP服务器并发送邮件
            if smtp_port == 465:
                # 使用SSL连接（适用于163, sina等）
                with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                    server.login(sender_email, sender_password)
                    server.send_message(message)
            else:
                # 使用TLS连接（适用于Gmail, QQ, Outlook等）
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()  # 启用TLS加密
                    server.login(sender_email, sender_password)
                    server.send_message(message)
            
            return {
                "success": True,
                "message": "邮件发送成功",
                "sender": sender_email,
                "receiver": receiver_email,
                "subject": subject,
                "message_id": msg_id
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"邮件发送失败: {str(e)}",
                "error": str(e)
            }
    
    def fetch_email(
        self,
        email_address: str,
        email_password: str,
        imap_server: str = "imap.gmail.com",
        imap_port: int = 993,
        only_unread: bool = True,
        download_dir: Optional[str] = None
    ) -> Dict:
        """
        获取邮件
        
        Args:
            email_address: 邮箱地址
            email_password: 邮箱密码（或应用专用密码）
            imap_server: IMAP服务器地址
            imap_port: IMAP服务器端口
            only_unread: 是否只获取未读邮件
            download_dir: 附件下载目录（默认使用临时目录）
        
        Returns:
            Dict: 包含邮件列表和状态信息的字典
        """
        try:
            # 验证必需的参数
            if not all([email_address, email_password]):
                raise ValueError("邮箱地址和密码不能为空")
            
            # 如果没有指定下载目录，使用临时目录
            if download_dir is None:
                download_dir = tempfile.mkdtemp(prefix="email_attachments_")
            else:
                os.makedirs(download_dir, exist_ok=True)
            
            # 连接IMAP服务器
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(email_address, email_password)
            
            # Send ID command (RFC 2971) - Required by some providers like 163 to avoid "Unsafe Login"
            try:
                # Using xatom to send ID command
                mail.xatom('ID', '("name" "MailMerge" "version" "1.0.0")')
            except Exception as e:
                logger.warning(f"IMAP ID command failed (ignoring): {e}")

            typ, data = mail.select("INBOX")
            if typ != 'OK':
                raise Exception(f"Could not select INBOX: {data}")
            
            # 搜索邮件
            search_criteria = "UNSEEN" if only_unread else "ALL"
            status, message_ids = mail.search(None, search_criteria)
            
            if status != "OK":
                raise Exception("邮件搜索失败")
            
            # 获取邮件ID列表
            email_ids = message_ids[0].split()
            
            if not email_ids:
                return {
                    "success": True,
                    "message": "没有未读邮件" if only_unread else "没有邮件",
                    "emails": [],
                    "count": 0
                }
            
            # 解析邮件
            emails = []
            for email_id in email_ids:
                try:
                    # 获取邮件内容
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    
                    if status != "OK":
                        continue
                    
                    # 解析邮件
                    raw_email = msg_data[0][1]
                    email_message = email.message_from_bytes(raw_email)
                    
                    # 解析邮件头部
                    subject = self._decode_mime_header(email_message.get("Subject", ""))
                    from_addr = self._decode_mime_header(email_message.get("From", ""))
                    date = email_message.get("Date", "")
                    message_id = email_message.get("Message-ID", "")
                    in_reply_to = email_message.get("In-Reply-To", "")
                    
                    # 解析邮件正文
                    body = ""
                    attachments = []
                    
                    # 为每封邮件创建独立的附件目录，防止重名冲突
                    email_uid = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                    safe_uid = "".join(c for c in email_uid if c.isalnum() or c in ('_', '-'))
                    email_attach_dir = os.path.join(download_dir, safe_uid)
                    os.makedirs(email_attach_dir, exist_ok=True)
                    
                    if email_message.is_multipart():
                        for part in email_message.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition", ""))
                            
                            # 获取邮件正文
                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                try:
                                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                except:
                                    body = part.get_payload(decode=True).decode("gbk", errors="ignore")
                            
                            # 处理附件
                            elif "attachment" in content_disposition:
                                filename = part.get_filename()
                                if filename:
                                    filename = self._decode_mime_header(filename)
                                    # 保存附件
                                    filepath = os.path.join(email_attach_dir, filename)
                                    with open(filepath, "wb") as f:
                                        f.write(part.get_payload(decode=True))
                                    attachments.append(filepath)
                    else:
                        # 非multipart邮件
                        try:
                            body = email_message.get_payload(decode=True).decode("utf-8", errors="ignore")
                        except:
                            body = email_message.get_payload(decode=True).decode("gbk", errors="ignore")
                    
                    # 构建邮件信息
                    email_info = {
                        "id": email_id.decode(),
                        "subject": subject,
                        "from": from_addr,
                        "date": date,
                        "message_id": message_id,
                        "in_reply_to": in_reply_to,
                        "body": body.strip(),
                        "attachments": attachments
                    }
                    
                    emails.append(email_info)
                    
                except Exception as e:
                    # 单个邮件解析失败，继续处理其他邮件
                    logger.error(f"Failed to parse email {email_id}: {str(e)}")
                    continue
            
            # 关闭连接
            mail.close()
            mail.logout()
            
            return {
                "success": True,
                "message": f"成功获取 {len(emails)} 封邮件",
                "emails": emails,
                "count": len(emails),
                "download_dir": download_dir
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"获取邮件失败: {str(e)}",
                "error": str(e),
                "emails": [],
                "count": 0
            }


# 对外暴露的便捷函数
_email_service = EmailService()


def send_email(
    sender_email: str,
    sender_password: str,
    receiver_email: str,
    email_content: Dict,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587
) -> Dict:
    """
    发送邮件的便捷函数
    
    Args:
        sender_email: 发送方邮箱地址
        sender_password: 发送方邮箱密码
        receiver_email: 接收方邮箱地址
        email_content: 邮件内容，包含：
            - subject: 邮件标题
            - body: 邮件正文
            - attachments: 附件路径列表（必须是绝对路径）
        smtp_server: SMTP服务器地址
        smtp_port: SMTP服务器端口
    
    Returns:
        Dict: 发送结果
    """
    return _email_service.send_email(
        sender_email,
        sender_password,
        receiver_email,
        email_content,
        smtp_server,
        smtp_port
    )


def fetch_email(
    email_address: str,
    email_password: str,
    imap_server: str = "imap.gmail.com",
    imap_port: int = 993,
    only_unread: bool = True,
    download_dir: Optional[str] = None
) -> Dict:
    """
    获取邮件的便捷函数
    
    Args:
        email_address: 邮箱地址
        email_password: 邮箱密码
        imap_server: IMAP服务器地址
        imap_port: IMAP服务器端口
        only_unread: 是否只获取未读邮件
        download_dir: 附件下载目录
    
    Returns:
        Dict: 包含邮件列表的结果
    """
    return _email_service.fetch_email(
        email_address,
        email_password,
        imap_server,
        imap_port,
        only_unread,
        download_dir
    )
