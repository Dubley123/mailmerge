# Agent Service - 智能助手服务

## 概述

`agent_service` 是一个基于大语言模型（LLM）的智能助手服务，采用**解耦式多ACTION架构**，通过统一的LLM交互接口和独立的ACTION子目录实现清晰的职责分离。

## 核心设计理念

### 解耦式架构

```
用户输入
  ↓
process_user_query (统一入口)
  ↓
ActionRouter (识别意图)
  ↓
对应的ACTION子目录 (完全接管处理)
  ├─ 自行生成Prompt
  ├─ 调用统一的LLM Client
  ├─ 处理业务逻辑
  └─ 返回结构化结果
  ↓
process_user_query (包装成自然语言)
  ↓
返回给用户
```

### 职责分离

| 组件 | 职责 | 特点 |
|------|------|------|
| **agent_service.py** | 统一入口，调度分发 | 唯一外部接口 |
| **action_router.py** | 识别用户意图 | 独立的ACTION识别器 |
| **llm_client.py** | LLM交互接口 | 统一的LLM调用标准 |
| **sql_query/** | SQL查询子模块 | 完全自治的处理逻辑 |
| **create_template/** | 模板创建子模块 | 完全自治的处理逻辑 |

## 目录结构

```
backend/agent_service/
├── __init__.py              # 统一导出
├── config.py                # 配置管理
├── agent_service.py         # 统一入口 (process_user_query)
├── action_router.py         # ACTION识别器
├── llm_client.py           # 统一LLM交互接口
│
├── sql_query/               # SQL查询ACTION子目录
│   ├── __init__.py
│   ├── handler.py           # 入口函数: handle_sql_query()
│   ├── prompt_generator.py  # 生成SQL查询Prompt
│   ├── sql_validator.py     # SQL安全校验
│   └── sql_executor.py      # SQL执行器
│
└── create_template/         # 创建模板ACTION子目录
    ├── __init__.py
    ├── handler.py           # 入口函数: handle_create_template()
    ├── prompt_generator.py  # 生成模板创建Prompt
    └── field_types.md       # 字段类型规范文档
```

## 核心组件详解

### 1. 统一入口 (agent_service.py)

**唯一外部接口**：`process_user_query(user_input, config=None)`

**职责**：
- 接收用户自然语言输入
- 调用ActionRouter识别意图
- 分发到对应ACTION子目录的handler
- 将结构化结果包装成自然语言返回

**示例**：
```python
from backend.agent_service import process_user_query

result = process_user_query("查询所有院系")
print(result)  # 自然语言形式的结果
```

### 2. ACTION识别器 (action_router.py)

**职责**：识别用户输入属于哪种ACTION类型

**支持的ACTION**：
- `SQL_QUERY`: 数据库查询
- `CREATE_TEMPLATE`: 创建模板
- `UNKNOWN`: 无法识别

**特点**：
- 使用LLM进行意图识别
- 返回ActionType枚举值
- 完全独立的模块

### 3. 统一LLM客户端 (llm_client.py)

**提供标准化的LLM交互接口**：

```python
from backend.agent_service.llm_client import LLMClient

client = LLMClient(config)

# 基础对话
response = client.chat(
    system_prompt="你是助手",
    user_message="用户问题",
    tools=[...],  # 可选的Tool Calling
    temperature=0.1
)

# 带历史的对话
response = client.chat_with_history(
    messages=[...],
    tools=[...],
    temperature=0.1
)
```

**返回格式**：
```python
{
    "type": "text" | "tool_call",
    "content": "文本内容",  # type=text时
    "tool_calls": [...],    # type=tool_call时
    "raw_response": {...}
}
```

### 4. ACTION子目录架构

每个ACTION子目录都是**完全自治**的，包含：

#### handler.py - 入口函数
```python
def handle_xxx(user_input: str, config: Config) -> Dict[str, Any]:
    """
    返回结构化结果：
    {
        "status": "success" | "error",
        "data": {...}
    }
    """
```

#### prompt_generator.py - Prompt生成
- 自行负责Prompt设计
- 返回system_prompt、tools等
- 不依赖外部Prompt生成器

#### 其他模块 - 业务逻辑
- 校验器、执行器等独立模块
- 清晰的职责划分
- 易于测试和维护

## SQL Query 子模块详解

### 工作流程

```
handle_sql_query()
  ↓
1. generate_sql_query_prompt() - 生成Prompt和工具定义
  ↓
2. LLMClient.chat_with_history() - 调用LLM生成SQL
  ↓
3. SQLValidator.validate() - 校验SQL安全性
  ↓
4. SQLExecutor.execute() - 执行SQL查询
  ↓
5. 失败则反馈给LLM重试，成功则返回结果
```

### 安全机制

| 校验项 | 说明 |
|--------|------|
| SELECTOnly | 仅允许SELECT，禁止DDL/DML |
| 表名白名单 | 仅查询database.md中的表 |
| 单语句 | 防止SQL注入 |
| 危险函数 | 禁止pg_sleep等系统函数 |
| sqlglot解析 | 专业的SQL语法检查 |

### 重试机制

- 最多重试N次（config.MAX_RETRY）
- 每次失败后反馈错误给LLM
- 保留完整的对话历史
- LLM根据错误信息自动修正

## CREATE_TEMPLATE 子模块详解

### 工作流程

```
handle_create_template()
  ↓
1. generate_create_template_prompt() - 生成Prompt和工具定义（包含field_types.md）
  ↓
2. LLMClient.chat_with_history() - 调用LLM生成模板JSON
  ↓
3. create_template_core() - 调用共享业务逻辑创建模板
  ↓
4. 失败则反馈给LLM重试，成功则返回template_id
```

### 核心特性

| 特性 | 说明 |
|------|------|
| **共享业务逻辑** | 使用 `backend/utils/template_utils.py` 中的 `create_template_core()` |
| **离线操作** | 无需HTTP调用，直接访问数据库 |
| **字段类型支持** | 10种类型：TEXT, INTEGER, FLOAT, DATE, DATETIME, BOOLEAN, EMAIL, PHONE, ID_CARD, EMPLOYEE_ID |
| **完整文档** | `field_types.md` 提供详细的字段规范和示例 |
| **验证机制** | 自动验证字段格式、类型合法性、必填项等 |

### 字段类型说明

完整的字段类型规范请参考 [field_types.md](create_template/field_types.md)

**支持的字段类型**：
- **TEXT**: 文本字段，支持 min_length, max_length
- **INTEGER**: 整数字段，支持 min, max
- **FLOAT**: 浮点数字段，支持 min, max
# 创建模板
result = process_user_query("创建一个收集学生信息的模板", user_id=1)
print(result)
# 输出: "模板创建成功！\n模板名称：学生信息\n您可以在模板管理页面查看和使用该模板。"
- **PHONE**: 手机号码（11位，自动验证）
- **ID_CARD**: 身份证号（15/18位，自动验证）
- **EMPLOYEE_ID**: 工号（10位数字）

### 与API路由共享逻辑

CREATE_TEMPLATE 功能采用**逻辑共享**设计：

```
backend/utils/template_utils.py
  ├─ create_template_core()      # 核心创建逻辑
  └─ update_template_core()      # 核心更新逻辑
       ↑                  ↑
       │                  │
   调用共享逻辑        调用共享逻辑
       │                  │
backend/api/templates.py   backend/agent_service/create_template/
  POST /api/templates/create       handler.py
  (处理HTTP请求)                  (LLM生成 + 调用核心逻辑)
```

**优势**：
- ✅ 逻辑统一，避免重复代码
- ✅ 离线操作，无需HTTP调用
- ✅ 易于测试和维护
- ✅ API和Agent共享相同的验证规则

## 配置说明

在项目根目录创建 `.env` 文件：

```bash
# LLM配置（OpenAI兼容接口）
DASHSCOPE_API_KEY=your_api_key
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-plus
MAX_RETRY=3
LLM_TIMEOUT=60

# 数据库配置（由backend/database/db_config.py统一管理）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mailmerge
DB_USER=postgres
DB_PASSWORD=your_password
```

**注意**：agent_service 使用 `backend.database.db_config` 统一管理数据库连接，确保与项目其他部分保持一致。

## 使用示例

### 基础使用

```python
from backend.agent_service import process_user_query

# SQL查询
result = process_user_query("查询所有院系的名称")
print(result)
# 输出: "查询成功！共找到 5 条记录。\n列名: id, name\n..."

# 创建模板（开发中）
result = process_user_query("创建一个收集学生信息的模板")
print(result)
# 输出: "模板创建失败：CREATE_TEMPLATE 功能正在开发中"
```

### 自定义配置

```python
from backend.agent_service import process_user_query, Config

config = Config(
    API_KEY="custom_key",
    MODEL_NAME="qwen-max",
    MAX_RETRY=5
)

# SQL查询
result = process_user_query("查询教师信息", config=config)

# 创建模板（需要user_id）
result = process_user_query(
    "创建一个考勤统计模板",
    config=config,
    user_id=1  # 必须提供用户ID
)
```

### 测试示例

```bash
# 测试CREATE_TEMPLATE功能
cd backend/agent_service
python test_create_template.py
```

## 扩展新ACTION

### 1. 创建子目录

```bash
mkdir backend/agent_service/new_action
```

### 2. 实现handler.py

```python
def handle_new_action(user_input: str, config: Config) -> Dict[str, Any]:
    """
    Returns:
        {
            "status": "success" | "error",
            "data": {...}
        }
    """
    # 你的处理逻辑
    pass
```

### 3. 创建prompt_generator.py

```python
def generate_new_action_prompt() -> Dict[str, Any]:
    return {
        "system_prompt": "...",
        "tools": [...]
    }
```

### 4. 更新action_router.py

```python
class ActionType(Enum):
    NEW_ACTION = "NEW_ACTION"
```

### 5. 更新agent_service.py

```python
from .new_action.handler import handle_new_action

def process_user_query(...):
    if action == ActionType.NEW_ACTION:
        result = handle_new_action(user_input, cfg)
        return _format_new_action_result(result)
```

## 测试

```bash
# 运行测试
python tests/test_agent_basic.py
python tests/test_agent_complete.py
```

## 依赖

```bash
pip install openai sqlalchemy psycopg2-binary sqlglot python-dotenv
```

## 设计优势

### ✅ 解耦合
- 每个ACTION完全独立
- LLM交互统一标准
- 易于单元测试

### ✅ 可扩展
- 新增ACTION只需创建子目录
- 不影响现有功能
- 清晰的扩展流程

### ✅ 易维护
- 职责清晰
- 代码组织规范
- 每个模块可独立修改

### ✅ 标准化
- 统一的LLM接口
- 统一的返回格式
- 统一的配置管理

## 常见问题

### Q: 为什么不用统一的Prompt生成器？

A: 每个ACTION的Prompt需求差异大，统一生成器会导致耦合。让每个子目录自行管理Prompt更灵活。

### Q: LLMClient和各子目录是什么关系？

A: LLMClient提供标准接口，各子目录调用它。这样LLM调用逻辑统一，易于升级和维护。

### Q: 如何调试某个ACTION？

A: 直接调用子目录的handler函数，传入测试数据即可：
```python
from backend.agent_service.sql_query import handle_sql_query
result = handle_sql_query("测试查询", config)
```

### Q: 返回格式为什么不统一？

A: handler返回结构化数据（Dict），process_user_query负责转换成自然语言，职责分离。

## 版本信息

**当前版本**: 2.0.0

**架构**: 解耦式多ACTION设计

## 许可证

与主项目保持一致。
