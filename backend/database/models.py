"""
Database Models for MailMerge System
SQLAlchemy ORM models based on database.md design
"""
from sqlalchemy import (
    Column, BigInteger, Integer, String, DateTime, Boolean, 
    ForeignKey, Text, Enum as SQLEnum, JSON, CheckConstraint,
    UniqueConstraint, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from backend.utils import get_utc_now

Base = declarative_base()


class EmailStatus(enum.Enum):
    """Email sending status"""
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class TaskStatus(enum.Enum):
    """Collection task status"""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    AGGREGATED = "AGGREGATED"
    NEEDS_REAGGREGATION = "NEEDS_REAGGREGATION"


# Table Models
class Department(Base):
    """院系表"""
    __tablename__ = 'department'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='院系唯一ID')
    name = Column(String(100), nullable=False, unique=True, comment='院系名称')
    extra = Column(JSON, nullable=True, comment='扩展描述')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, 
                       onupdate=get_utc_now, comment='更新时间')

    # Relationships
    teachers = relationship("Teacher", back_populates="department")
    secretaries = relationship("Secretary", back_populates="department")

    __table_args__ = (
        Index('idx_department_name', 'name', unique=True),
    )


class Teacher(Base):
    """教师表"""
    __tablename__ = 'teacher'

    id = Column(BigInteger, primary_key=True, autoincrement=False, comment='教师唯一工号')
    name = Column(String(50), nullable=False, comment='教师姓名')
    department_id = Column(BigInteger, ForeignKey('department.id'), nullable=False, comment='所属院系')
    email = Column(String(150), nullable=False, unique=True, comment='教师邮箱')
    phone = Column(String(30), nullable=True, comment='手机')
    title = Column(String(50), nullable=True, comment='职称')
    office = Column(String(100), nullable=True, comment='办公地点')
    extra = Column(JSON, nullable=True, comment='扩展信息')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    # Relationships
    department = relationship("Department", back_populates="teachers")
    sent_emails_received = relationship("SentEmail", back_populates="teacher")
    received_emails_sent = relationship("ReceivedEmail", back_populates="teacher")
    task_targets = relationship("CollectTaskTarget", back_populates="teacher")

    __table_args__ = (
        Index('idx_teacher_department', 'department_id'),
        Index('idx_teacher_email', 'email', unique=True),
    )


class Secretary(Base):
    """科研秘书表"""
    __tablename__ = 'secretary'

    id = Column(BigInteger, primary_key=True, autoincrement=False, comment='秘书唯一工号')
    name = Column(String(50), nullable=False, comment='姓名')
    department_id = Column(BigInteger, ForeignKey('department.id'), nullable=False, comment='所属院系')
    username = Column(String(50), nullable=False, unique=True, comment='登录用户名')
    account = Column(String(100), nullable=False, unique=True, comment='登录账号')
    password_hash = Column(String(255), nullable=False, comment='密码哈希')
    email = Column(String(150), nullable=False, unique=True, comment='秘书邮箱')
    mail_auth_code = Column(String(255), nullable=True, comment='邮箱授权码(加密)')
    phone = Column(String(30), nullable=True, comment='手机')
    teacher_id = Column(BigInteger, ForeignKey('teacher.id'), nullable=True, comment='若秘书也是教师')
    extra = Column(JSON, nullable=True, comment='备注信息')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    # Relationships
    department = relationship("Department", back_populates="secretaries")
    teacher = relationship("Teacher", foreign_keys=[teacher_id])
    templates_created = relationship("TemplateForm", back_populates="creator")
    tasks_created = relationship("CollectTask", back_populates="creator")
    sent_emails = relationship("SentEmail", back_populates="secretary")
    received_emails = relationship("ReceivedEmail", back_populates="secretary")
    aggregations = relationship("Aggregation", back_populates="generator")
    chat_sessions = relationship("ChatSession", back_populates="secretary")

    __table_args__ = (
        Index('idx_secretary_department', 'department_id'),
        Index('idx_secretary_username', 'username', unique=True),
        Index('idx_secretary_account', 'account', unique=True),
        Index('idx_secretary_email', 'email', unique=True),
    )


class TemplateForm(Base):
    """模板表"""
    __tablename__ = 'template_form'

    id = Column(BigInteger, primary_key=True, comment='模板唯一 ID')
    name = Column(String(100), nullable=False, comment='模板名称')
    description = Column(Text, nullable=True, comment='模板描述')
    created_by = Column(BigInteger, ForeignKey('secretary.id'), nullable=True, comment='创建秘书ID')
    extra = Column(JSON, nullable=True, comment='扩展字段')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, 
                       onupdate=get_utc_now, comment='更新时间')

    # Relationships
    creator = relationship("Secretary", back_populates="templates_created")
    fields = relationship("TemplateFormField", back_populates="form", cascade="all, delete-orphan")
    tasks = relationship("CollectTask", back_populates="template")

    __table_args__ = (
        Index('idx_template_name', 'name'),
    )


class TemplateFormField(Base):
    """模板表字段"""
    __tablename__ = 'template_form_field'

    id = Column(BigInteger, primary_key=True, comment='字段唯一 ID')
    form_id = Column(BigInteger, ForeignKey('template_form.id'), nullable=False, comment='关联模板 ID')
    ord = Column(Integer, nullable=False, default=0, comment='字段顺序')
    display_name = Column(String(100), nullable=False, comment='Excel 上展示的名称')
    # Note: use `validation_rule` JSON to store unified validation rules for the field
    # Example:
    # {
    #   "required": true,
    #   "type": "TEXT|INTEGER|FLOAT|DATE|DATETIME|BOOLEAN|EMAIL|PHONE|ID_CARD|EMPLOYEE_ID",
    #   "min": 0,
    #   "max": 100,
    #   "min_length": 1,
    #   "max_length": 100,
    # }
    validation_rule = Column(JSON, nullable=True, comment='字段校验规则，JSON 格式')
    extra = Column(JSON, nullable=True, comment='扩展字段')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, 
                       onupdate=get_utc_now, comment='更新时间')

    # Relationships
    form = relationship("TemplateForm", back_populates="fields")

    __table_args__ = (
        UniqueConstraint('form_id', 'display_name', name='uq_form_field_name'),
        Index('idx_template_field_form', 'form_id'),
    )


class CollectTask(Base):
    """收集任务表"""
    __tablename__ = 'collect_task'

    id = Column(BigInteger, primary_key=True, comment='唯一 ID')
    name = Column(String(255), nullable=False, comment='任务名称')
    description = Column(Text, nullable=True, comment='任务描述')
    started_time = Column(DateTime(timezone=True), nullable=True, comment='任务实际开始的时间')
    deadline = Column(DateTime(timezone=True), nullable=True, comment='任务计划结束时间')
    template_id = Column(BigInteger, ForeignKey('template_form.id'), nullable=False, comment='对应的表单模板 ID')
    mail_content_template = Column(JSON, nullable=True, comment='邮件所有内容模板')
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.DRAFT, comment='任务状态')
    created_by = Column(BigInteger, ForeignKey('secretary.id'), nullable=False, comment='创建者 ID')
    extra = Column(JSON, nullable=True, comment='扩展字段')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, 
                       onupdate=get_utc_now, comment='更新时间')

    # Relationships
    creator = relationship("Secretary", back_populates="tasks_created")
    template = relationship("TemplateForm", back_populates="tasks")
    targets = relationship("CollectTaskTarget", back_populates="task")
    sent_emails = relationship("SentEmail", back_populates="task")
    received_emails = relationship("ReceivedEmail", back_populates="task")
    aggregations = relationship("Aggregation", back_populates="task")

    __table_args__ = (
        CheckConstraint('deadline > started_time OR deadline IS NULL OR started_time IS NULL', 
                       name='chk_task_deadline'),
        Index('idx_task_status', 'status'),
        Index('idx_task_creator', 'created_by'),
        Index('idx_task_name', 'name'),
    )


class CollectTaskTarget(Base):
    """收集任务目标教师表"""
    __tablename__ = 'collect_task_target'

    task_id = Column(BigInteger, ForeignKey('collect_task.id'), primary_key=True, comment='任务 ID')
    teacher_id = Column(BigInteger, ForeignKey('teacher.id'), primary_key=True, comment='教师 ID')

    # Relationships
    task = relationship("CollectTask", back_populates="targets")
    teacher = relationship("Teacher", back_populates="task_targets")

    __table_args__ = (
        Index('idx_task_target_task', 'task_id'),
        Index('idx_task_target_teacher', 'teacher_id'),
    )


class SentAttachment(Base):
    """发送邮件附件表"""
    __tablename__ = 'sent_attachment'

    id = Column(BigInteger, primary_key=True, comment='唯一 ID')
    file_path = Column(Text, nullable=False, comment='附件路径')
    file_name = Column(String(255), nullable=True, comment='文件名')
    content_type = Column(String(255), nullable=True, comment='MIME 类型')
    file_size = Column(BigInteger, nullable=True, comment='文件大小（字节）')
    extra = Column(JSON, nullable=True, comment='扩展字段')
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='上传时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, 
                       onupdate=get_utc_now, comment='更新时间')

    # Relationships
    sent_emails = relationship("SentEmail", back_populates="attachment")

    __table_args__ = (
        Index('idx_sent_attachment_path', 'file_path'),
    )


class SentEmail(Base):
    """邮件发送记录表"""
    __tablename__ = 'sent_email'

    id = Column(BigInteger, primary_key=True, comment='唯一 ID')
    task_id = Column(BigInteger, ForeignKey('collect_task.id'), nullable=False, comment='对应任务 ID')
    from_sec_id = Column(BigInteger, ForeignKey('secretary.id'), nullable=False, comment='发送秘书 ID')
    to_tea_id = Column(BigInteger, ForeignKey('teacher.id'), nullable=False, comment='接收教师 ID')
    sent_at = Column(DateTime(timezone=True), nullable=True, comment='实际发送时间')
    status = Column(SQLEnum(EmailStatus), nullable=False, default=EmailStatus.QUEUED, comment='邮件发送状态')
    retry_count = Column(Integer, nullable=False, default=0, comment='重试次数')
    message_id = Column(String(255), nullable=True, comment='邮件服务返回的消息 ID')
    mail_content = Column(JSON, nullable=True, comment='邮件正文解析内容')
    attachment_id = Column(BigInteger, ForeignKey('sent_attachment.id'), nullable=True, comment='对应发送附件表 ID')
    extra = Column(JSON, nullable=True, comment='扩展字段')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, 
                       onupdate=get_utc_now, comment='更新时间')

    # Relationships
    task = relationship("CollectTask", back_populates="sent_emails")
    secretary = relationship("Secretary", back_populates="sent_emails")
    teacher = relationship("Teacher", back_populates="sent_emails_received")
    attachment = relationship("SentAttachment", back_populates="sent_emails")

    __table_args__ = (
        Index('idx_sent_email_task', 'task_id'),
        Index('idx_sent_email_secretary', 'from_sec_id'),
        Index('idx_sent_email_teacher', 'to_tea_id'),
        Index('idx_sent_email_sent_at', 'sent_at'),
    )


class ReceivedAttachment(Base):
    """接收邮件附件表"""
    __tablename__ = 'received_attachment'

    id = Column(BigInteger, primary_key=True, comment='唯一 ID')
    file_path = Column(Text, nullable=False, comment='附件路径')
    file_name = Column(String(255), nullable=True, comment='文件名')
    content_type = Column(String(255), nullable=True, comment='MIME 类型')
    file_size = Column(BigInteger, nullable=True, comment='文件大小（字节）')
    extra = Column(JSON, nullable=True, comment='扩展字段')
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='上传时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, 
                       onupdate=get_utc_now, comment='更新时间')

    # Relationships
    received_emails = relationship("ReceivedEmail", back_populates="attachment")

    __table_args__ = (
        Index('idx_received_attachment_path', 'file_path'),
    )


class ReceivedEmail(Base):
    """邮件接收记录表"""
    __tablename__ = 'received_email'

    id = Column(BigInteger, primary_key=True, comment='唯一 ID')
    task_id = Column(BigInteger, ForeignKey('collect_task.id'), nullable=True, comment='对应任务 ID')
    from_tea_id = Column(BigInteger, ForeignKey('teacher.id'), nullable=False, comment='发件教师 ID')
    to_sec_id = Column(BigInteger, ForeignKey('secretary.id'), nullable=False, comment='收件秘书 ID')
    received_at = Column(DateTime(timezone=True), nullable=False, comment='邮件接收时间')
    message_id = Column(String(255), nullable=True, comment='邮件服务返回的消息 ID')
    mail_content = Column(JSON, nullable=True, comment='邮件正文解析内容')
    attachment_id = Column(BigInteger, ForeignKey('received_attachment.id'), nullable=True, 
                          comment='对应接收附件表 ID')
    is_aggregated = Column(Boolean, nullable=False, default=False, comment='是否已被合并')
    extra = Column(JSON, nullable=True, comment='扩展字段')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, 
                       onupdate=get_utc_now, comment='更新时间')

    # Relationships
    task = relationship("CollectTask", back_populates="received_emails")
    teacher = relationship("Teacher", back_populates="received_emails_sent")
    secretary = relationship("Secretary", back_populates="received_emails")
    attachment = relationship("ReceivedAttachment", back_populates="received_emails")

    __table_args__ = (
        Index('idx_received_email_task', 'task_id'),
        Index('idx_received_email_teacher', 'from_tea_id'),
        Index('idx_received_email_secretary', 'to_sec_id'),
        Index('idx_received_email_received_at', 'received_at'),
    )


class Aggregation(Base):
    """汇总结果表"""
    __tablename__ = 'aggregation'

    id = Column(BigInteger, primary_key=True, comment='唯一 ID')
    task_id = Column(BigInteger, ForeignKey('collect_task.id'), nullable=False, comment='对应的任务 ID')
    name = Column(String(255), nullable=False, comment='汇总表名称')
    generated_by = Column(BigInteger, ForeignKey('secretary.id'), nullable=True, comment='执行汇总操作的教秘 ID')
    generated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='汇总生成时间')
    record_count = Column(Integer, nullable=True, comment='本次汇总的记录条数')
    # 是否存在校验失败的记录
    has_validation_issues = Column(Boolean, nullable=False, default=False, comment='本次汇总是否包含不合规记录')
    file_path = Column(Text, nullable=False, comment='汇总生成文件路径')
    extra = Column(JSON, nullable=True, comment='扩展字段')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, 
                       onupdate=get_utc_now, comment='更新时间')

    # Relationships
    task = relationship("CollectTask", back_populates="aggregations")
    generator = relationship("Secretary", back_populates="aggregations")
    validation_records = relationship("FieldValidationRecord", back_populates="aggregation", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_aggregation_task', 'task_id'),
        Index('idx_aggregation_generator', 'generated_by'),
        Index('idx_aggregation_generated_at', 'generated_at'),
    )


class FieldValidationRecord(Base):
    """字段校验记录表"""
    __tablename__ = 'field_validation_record'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='唯一 ID')
    aggregation_id = Column(BigInteger, ForeignKey('aggregation.id'), nullable=False, comment='关联汇总表 ID')
    teacher_id = Column(BigInteger, ForeignKey('teacher.id'), nullable=False, comment='关联教师 ID')
    field_name = Column(String(100), nullable=False, comment='字段名称')
    error_type = Column(SQLEnum("MISSING", "INVALID", name="validation_error_type"), nullable=False, comment='错误类型')
    error_description = Column(Text, nullable=True, comment='错误描述')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')

    # Relationships
    aggregation = relationship("Aggregation", back_populates="validation_records")
    teacher = relationship("Teacher")

    __table_args__ = (
        UniqueConstraint('aggregation_id', 'teacher_id', 'field_name', name='uq_agg_teacher_field'),
        Index('idx_validation_agg', 'aggregation_id'),
        Index('idx_validation_teacher', 'teacher_id'),
    )


class ChatSession(Base):
    """对话会话表"""
    __tablename__ = 'chat_session'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='会话唯一ID')
    secretary_id = Column(BigInteger, ForeignKey('secretary.id'), nullable=False, comment='所属秘书ID')
    title = Column(String(255), nullable=True, comment='会话标题')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now, comment='更新时间')

    # Relationships
    secretary = relationship("Secretary", back_populates="chat_sessions")
    messages = relationship("SessionMessage", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_chat_session_secretary', 'secretary_id'),
    )


class SessionMessage(Base):
    """会话消息表"""
    __tablename__ = 'session_message'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='消息唯一ID')
    session_id = Column(BigInteger, ForeignKey('chat_session.id'), nullable=False, comment='所属会话ID')
    role = Column(String(50), nullable=False, comment='角色: user/assistant')
    content = Column(Text, nullable=False, comment='消息内容')
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, comment='创建时间')

    # Relationships
    session = relationship("ChatSession", back_populates="messages")

    __table_args__ = (
        Index('idx_session_message_session', 'session_id'),
    )
