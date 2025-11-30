# 1. Department（院系）

## 字段设计

| 字段名     | 类型         | 约束                                                         | 说明       |
| ---------- | ------------ | ------------------------------------------------------------ | ---------- |
| id         | BIGINT       | PRIMARY KEY, AUTO_INCREMENT                                  | 院系唯一ID |
| name       | VARCHAR(100) | NOT NULL, UNIQUE                                             | 院系名称   |
| extra      | JSONB        | NULL                                                         | 扩展描述   |
| created_at | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 创建时间   |
| updated_at | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间   |

## 必要索引

- UNIQUE(name)

------

# 2. Teacher（教师）

## 字段设计

| 字段名        | 类型         | 约束                                                         | 说明                                    |
| ------------- | ------------ | ------------------------------------------------------------ | --------------------------------------- |
| id            | BIGINT       | PRIMARY KEY                                  | 教师唯一工号                            |
| name          | VARCHAR(50)  | NOT NULL                                                     | 教师姓名                                |
| department_id | BIGINT       | NOT NULL, FOREIGN KEY → Department(id)                       | 所属院系                                |
| email         | VARCHAR(150) | NOT NULL, UNIQUE                                             | 教师邮箱（必须唯一，用于发送&识别汇总） |
| phone         | VARCHAR(30)  | NULL                                                         | 手机                                    |
| title         | VARCHAR(50)  | NULL                                                         | 职称                                    |
| office        | VARCHAR(100) | NULL                                                         | 办公地点                                |
| extra         | JSONB        | NULL                                                         | 扩展信息                                |
| created_at    | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          |                                         |
| updated_at    | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP |                                         |

## 必要索引

- INDEX(department_id)
- UNIQUE(email)

------

# 3. Secretary（科研秘书）

## 字段设计

| 字段名        | 类型         | 约束                                                         | 说明                         |
| ------------- | ------------ | ------------------------------------------------------------ | ---------------------------- |
| id            | BIGINT       | PRIMARY KEY                                  | 秘书唯一工号                 |
| name          | VARCHAR(50)  | NOT NULL                                                     | 姓名                         |
| department_id | BIGINT       | NOT NULL, FOREIGN KEY → Department(id)                       | 所属院系                     |
| username      | VARCHAR(50)  | NOT NULL, UNIQUE                                             | 登录用户名（系统显示昵称）   |
| account       | VARCHAR(100) | NOT NULL, UNIQUE                                             | 登录账号（登录凭据）         |
| password_hash | VARCHAR(255) | NOT NULL                                                     | 密码哈希（bcrypt/argon2）    |
| email         | VARCHAR(150) | NOT NULL, UNIQUE                                             | 秘书邮箱（任务执行非常重要） |
| mail_auth_code| VARCHAR(255) | NULL                                                         | 邮箱授权码（加密存储）       |
| phone         | VARCHAR(30)  | NULL                                                         | 手机                         |
| teacher_id    | BIGINT       | NULL, FOREIGN KEY → Teacher(id)                              | 若秘书也是教师               |
| extra         | JSONB        | NULL                                                         | 备注信息                     |
| created_at    | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          |                              |
| updated_at    | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP |                              |

## 必要索引

- INDEX(department_id)
- UNIQUE(username)
- UNIQUE(account)
- UNIQUE(email)

# 4. TemplateForm（模板表）

## 字段设计

| 字段名      | 类型         | 约束                                                         | 含义说明    |
| ----------- | ------------ | ------------------------------------------------------------ | ----------- |
| id          | BIGINT       | PRIMARY KEY                                                  | 模板唯一 ID |
| name        | VARCHAR(100) | NOT NULL, UNIQUE                                             | 模板名称    |
| description | TEXT         | NULL                                                         | 模板描述    |
| created_by  | BIGINT       | NULL, FOREIGN KEY → Secretary(id)                            | 创建秘书ID  |
| extra       | JSON         | NULL                                                         | 扩展字段（预留，默认NULL）    |
| created_at  | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 创建时间    |
| updated_at  | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间    |

## 必要索引

- INDEX(name)

------

# 5. TemplateFormField（模板表字段）

## 字段设计

| 字段名       | 类型                                                         | 约束                                                         | 含义说明                                |
| ------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | --------------------------------------- |
| id           | BIGINT                                                       | PRIMARY KEY                                                  | 字段唯一 ID                             |
| form_id      | BIGINT                                                       | NOT NULL, FOREIGN KEY → TemplateForm(id)                     | 关联模板 ID                             |
| ord          | INT                                                          | NOT NULL, DEFAULT 0                                          | 字段顺序，用于生成表格的列顺序          |
| display_name | VARCHAR(100)                                                 | NOT NULL                                                     | Excel 上展示的名称                      |
| validation_rule | JSON                                                    | NULL                                                         | 字段校验规则，JSON 格式，统一描述字段的 required/type/constraints |
| extra        | JSON                                                         | NULL                                                         | 扩展字段                                |
| created_at   | DATETIME                                                     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 创建时间                                |
| updated_at   | DATETIME                                                     | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间                                |

------

## 表级约束

- UNIQUE(form_id, display_name)  # 同一个模板中字段名称不能重复

## 必要索引

- INDEX(form_id)

------

# 6. SentEmail（邮件发送记录表）

## 字段设计

| 字段名        | 类型                           | 约束                                                         | 含义说明                      |
| ------------- | ------------------------------ | ------------------------------------------------------------ | ----------------------------- |
| id            | BIGINT                         | PRIMARY KEY                                                  | 唯一 ID                       |
| task_id       | BIGINT                         | NOT NULL, FOREIGN KEY → CollectTask(id)                      | 对应 CollectTask 表任务 ID    |
| from_sec_id   | BIGINT                         | NOT NULL, FOREIGN KEY → Secretary(id)                        | 发送秘书 ID                   |
| to_tea_id     | BIGINT                         | NOT NULL, FOREIGN KEY → Teacher(id)                          | 接收教师 ID                   |
| sent_at       | DATETIME                       | NULL                                                         | 实际发送时间                  |
| status        | ENUM('queued','sent','failed') | NOT NULL, DEFAULT 'queued'                                   | 邮件发送状态                  |
| retry_count   | INT                            | NOT NULL, DEFAULT 0                                          | 重试次数                      |
| message_id    | VARCHAR(255)                   | NULL                                                         | 邮件服务返回的消息 ID         |
| mail_content  | JSON                           | NULL                                                         | 邮件正文解析内容（JSON 格式） |
| attachment_id | BIGINT                         | NULL, FOREIGN KEY → SentAttachment(id)                       | 对应发送附件表 ID             |
| extra         | JSON                           | NULL                                                         | 扩展字段                      |
| created_at    | DATETIME                       | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 创建时间                      |
| updated_at    | DATETIME                       | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间                      |

## 必要索引

- INDEX(task_id)
- INDEX(from_sec_id)
- INDEX(to_tea_id)
- INDEX(sent_at)

------

# 7. ReceivedEmail（邮件接收记录表）

## 字段设计

| 字段名        | 类型         | 约束                                                         | 含义说明                      |
| ------------- | ------------ | ------------------------------------------------------------ | ----------------------------- |
| id            | BIGINT       | PRIMARY KEY                                                  | 唯一 ID                       |
| task_id       | BIGINT       | NULL, FOREIGN KEY → CollectTask(id)                          | 对应 CollectTask 表任务 ID    |
| from_tea_id   | BIGINT       | NOT NULL, FOREIGN KEY → Teacher(id)                          | 发件教师 ID                   |
| to_sec_id     | BIGINT       | NOT NULL, FOREIGN KEY → Secretary(id)                        | 收件秘书 ID                   |
| received_at   | DATETIME     | NOT NULL                                                     | 邮件接收时间                  |
| message_id    | VARCHAR(255) | NULL                                                         | 邮件服务返回的消息 ID         |
| mail_content  | JSON         | NULL                                                         | 邮件正文解析内容（JSON 格式） |
| attachment_id | BIGINT       | NULL, FOREIGN KEY → ReceivedAttachment(id)                   | 对应接收附件表 ID             |
| is_aggregated | BOOLEAN      | NOT NULL, DEFAULT FALSE                                      | 是否已被合并                  |
| extra         | JSON         | NULL                                                         | 扩展字段                      |
| created_at    | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 创建时间                      |
| updated_at    | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间                      |

## 必要索引

- INDEX(task_id)
- INDEX(from_tea_id)
- INDEX(to_sec_id)
- INDEX(received_at)

------

# 8. SentAttachment（发送邮件附件表）

## 字段设计

| 字段名       | 类型         | 约束                                                         | 含义说明                         |
| ------------ | ------------ | ------------------------------------------------------------ | -------------------------------- |
| id           | BIGINT       | PRIMARY KEY                                                  | 唯一 ID                          |
| file_path    | TEXT         | NOT NULL                                                     | 附件路径（可以是 S3 等远程路径） |
| file_name    | VARCHAR(255) | NULL                                                         | 文件名                           |
| content_type | VARCHAR(255) | NULL                                                         | MIME 类型，标识附件文件类型      |
| file_size    | BIGINT       | NULL                                                         | 文件大小（字节）                 |
| extra        | JSON         | NULL                                                         | 扩展字段，例如加密信息、哈希等   |
| uploaded_at  | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 上传时间                         |
| updated_at   | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间                         |

## 必要索引

- INDEX(email_id)
- INDEX(file_path)

------

# 9. ReceivedAttachment（接收邮件附件表）

## 字段设计

| 字段名       | 类型         | 约束                                                         | 含义说明                         |
| ------------ | ------------ | ------------------------------------------------------------ | -------------------------------- |
| id           | BIGINT       | PRIMARY KEY                                                  | 唯一 ID                          |
| file_path    | TEXT         | NOT NULL                                                     | 附件路径（可以是 S3 等远程路径） |
| file_name    | VARCHAR(255) | NULL                                                         | 文件名                           |
| content_type | VARCHAR(255) | NULL                                                         | MIME 类型，标识附件文件类型      |
| file_size    | BIGINT       | NULL                                                         | 文件大小（字节）                 |
| extra        | JSON         | NULL                                                         | 扩展字段，例如加密信息、哈希等   |
| uploaded_at  | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 上传时间                         |
| updated_at   | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间                         |

## 必要索引

- INDEX(email_id)
- INDEX(file_path)

------

# 10. Aggregation（汇总结果表）

## 字段设计

| 字段名       | 类型         | 约束                                                         | 含义说明                          |
| ------------ | ------------ | ------------------------------------------------------------ | --------------------------------- |
| id           | BIGINT       | PRIMARY KEY                                                  | 唯一 ID                           |
| task_id      | BIGINT       | NOT NULL, FOREIGN KEY → CollectTask(id)                      | 对应的任务 ID                     |
| name         | VARCHAR(255) | NOT NULL                                                     | 汇总表名称                        |
| generated_by | BIGINT       | NULL, FOREIGN KEY → Secretary(id)                            | 执行汇总操作的教秘 ID             |
| generated_at | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 汇总生成时间                      |
| record_count | INT          | NULL                                                         | 本次汇总的记录条数                |
| has_validation_issues | BOOLEAN | NOT NULL, DEFAULT FALSE                                    | 本次汇总是否包含校验失败的记录    |
| validation_errors | JSON      | NULL                                                         | 校验失败详情，JSON 格式（以 teacher_id 为 key） |
| file_path    | TEXT         | NOT NULL                                                     | 汇总生成文件路径（S3 或本地路径） |
| extra        | JSON         | NULL                                                         | 扩展字段，例如备注、描述等        |
| created_at   | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 创建时间                          |
| updated_at   | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间                          |

## 必要索引

- INDEX(task_id)
- INDEX(generated_by)
- INDEX(generated_at)

# 11. CollectTask（收集任务表）

| 字段名                | 类型                                            | 约束                                                         | 含义说明                                          |
| --------------------- | ----------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------- |
| id                    | BIGINT                                          | PRIMARY KEY                                                  | 唯一 ID                                           |
| name                  | VARCHAR(255)                                    | NOT NULL, UNIQUE                                             | 任务名称，用于邮件主题匹配                        |
| description           | TEXT                                            | NULL                                                         | 任务描述                                          |
| started_time          | DATETIME                                        | NULL                                                         | 任务实际开始的时间（教秘任务发布的时间）          |
| deadline              | DATETIME                                        | NULL                                                         | 任务计划结束时间（可为空表示无截止）              |
| template_id           | BIGINT                                          | NOT NULL, FOREIGN KEY → TemplateForm(id)                     | 对应的表单模板 ID                                 |
| mail_content_template | JSON                                            | NULL                                                         | 邮件所有内容模板（主题、正文、附件说明等）        |
| status                | ENUM('DRAFT', 'ACTIVE', 'CLOSED', 'AGGREGATED', 'NEEDS_REAGGREGATION') | NOT NULL, DEFAULT 'DRAFT'                                    | 任务状态，分别为：草稿/进行中/已关闭/已汇总/需重新汇总 |
| created_by            | BIGINT                                          | NOT NULL, FOREIGN KEY → Secretary(id)                        | 创建者 ID（教秘）                                 |
| extra                 | JSON                                            | NULL                                                         | 扩展字段（预留，默认NULL）                        |
| created_at            | DATETIME                                        | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | 创建时间                                          |
| updated_at            | DATETIME                                        | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间                                          |

## 表级约束

- deadline > started_time

## 必要索引

- INDEX(status)
- INDEX(created_by)
- INDEX(name)

# 12. CollectTaskTarget（收集任务目标教师表）

| 字段名      | 类型         | 约束                                       | 含义说明              |
| ----------- | ------------ | ------------------------------------------ | --------------------- |
| task_id     | BIGINT       | NOT NULL, FOREIGN KEY → CollectTask(id)    | 任务 ID               |
| teacher_id  | BIGINT       | NOT NULL, FOREIGN KEY → Teacher(id)        | 教师 ID               |

## 表级约束

- PrimaryKey(task_id, teacher_id)

## 必要索引

- INDEX(task_id)
- INDEX(teacher_id)