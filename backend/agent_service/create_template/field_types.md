# 模板字段类型规范文档

本文档定义了创建数据收集模板时支持的所有字段类型及其验证规则。

## 支持的字段类型

| 类型 | 说明 | 必填属性 | 可选属性 | 示例值 |
|------|------|---------|---------|--------|
| **TEXT** | 文本字段 | `type`: "TEXT" | `required`: 是否必填<br>`min_length`: 最小长度<br>`max_length`: 最大长度 | "张三"<br>"备注信息" |
| **INTEGER** | 整数字段 | `type`: "INTEGER" | `required`: 是否必填<br>`min`: 最小值<br>`max`: 最大值 | 25<br>100 |
| **FLOAT** | 浮点数字段 | `type`: "FLOAT" | `required`: 是否必填<br>`min`: 最小值<br>`max`: 最大值 | 85.5<br>3.14 |
| **DATE** | 日期字段 | `type`: "DATE" | `required`: 是否必填 | "2025-01-15"<br>"2025/01/15" |
| **DATETIME** | 日期时间字段 | `type`: "DATETIME" | `required`: 是否必填 | "2025-01-15 10:30:00" |
| **BOOLEAN** | 布尔字段 | `type`: "BOOLEAN" | `required`: 是否必填 | true/false<br>"是"/"否"<br>1/0 |
| **EMAIL** | 邮箱地址 | `type`: "EMAIL" | `required`: 是否必填 | "user@example.com" |
| **PHONE** | 手机号码 | `type`: "PHONE" | `required`: 是否必填 | "13800138000" |
| **ID_CARD** | 身份证号 | `type`: "ID_CARD" | `required`: 是否必填 | "110101199001011234" |
| **EMPLOYEE_ID** | 工号 | `type`: "EMPLOYEE_ID" | `required`: 是否必填 | "2021001234" |

## validation_rule 结构说明

每个字段的 `validation_rule` 是一个 JSON 对象，格式为：

### 基础属性

```json
{
  "type": "字段类型",  // 必填，从上表中选择
  "required": true/false,  // 是否必填，可选，默认false
  // ... 其他类型特定属性
}
```

### 类型特定属性

#### TEXT 类型
- `min_length`: 最小长度，可选
- `max_length`: 最大长度，可选

**示例**：
- 姓名字段：`{"type": "TEXT", "required": true, "min_length": 2, "max_length": 20}`
- 备注字段：`{"type": "TEXT", "max_length": 200}`

#### INTEGER 类型
- `min`: 最小值，可选
- `max`: 最大值，可选

**示例**：
- 年龄字段：`{"type": "INTEGER", "required": true, "min": 18, "max": 65}`
- 数量字段：`{"type": "INTEGER", "min": 0}`

#### FLOAT 类型
- `min`: 最小值，可选
- `max`: 最大值，可选

**示例**：
- 成绩字段：`{"type": "FLOAT", "required": true, "min": 0, "max": 100}`
- 体重字段：`{"type": "FLOAT", "min": 30.0, "max": 200.0}`

#### DATE 类型
无额外属性。支持格式：`YYYY-MM-DD` 或 `YYYY/MM/DD`

**示例**：
- 出生日期：`{"type": "DATE", "required": true}`

#### DATETIME 类型
无额外属性。格式：`YYYY-MM-DD HH:MM:SS`

**示例**：
- 入职时间：`{"type": "DATETIME", "required": true}`

#### BOOLEAN 类型
无额外属性。支持的值：true、false、"是"、"否"、"yes"、"no"、1、0

**示例**：
- 是否党员：`{"type": "BOOLEAN"}`
- 是否在职：`{"type": "BOOLEAN", "required": true}`

#### EMAIL 类型
无额外属性。验证规则：必须包含 @ 符号，格式为 xxx@xxx.xxx

**示例**：
- 邮箱地址：`{"type": "EMAIL", "required": true}`

#### PHONE 类型
无额外属性。验证规则：11位数字，以1开头，第二位为3-9

**示例**：
- 联系电话：`{"type": "PHONE", "required": true}`

#### ID_CARD 类型
无额外属性。验证规则：15位或18位数字（最后一位可以是X）

**示例**：
- 身份证号：`{"type": "ID_CARD", "required": true}`

#### EMPLOYEE_ID 类型
无额外属性。验证规则：10位数字

**示例**：
- 工号：`{"type": "EMPLOYEE_ID", "required": true}`

## 完整示例

### 示例1：学生信息收集模板

```json
{
  "name": "学生基本信息",
  "description": "收集新生入学信息",
  "fields": [
    {
      "display_name": "姓名",
      "validation_rule": {
        "type": "TEXT",
        "required": true,
        "min_length": 2,
        "max_length": 20
      },
      "ord": 0
    },
    {
      "display_name": "学号",
      "validation_rule": {
        "type": "EMPLOYEE_ID",
        "required": true
      },
      "ord": 1
    },
    {
      "display_name": "性别",
      "validation_rule": {
        "type": "TEXT",
        "required": true,
        "max_length": 10
      },
      "ord": 2
    },
    {
      "display_name": "出生日期",
      "validation_rule": {
        "type": "DATE",
        "required": true
      },
      "ord": 3
    },
    {
      "display_name": "联系电话",
      "validation_rule": {
        "type": "PHONE",
        "required": true
      },
      "ord": 4
    },
    {
      "display_name": "邮箱",
      "validation_rule": {
        "type": "EMAIL",
        "required": true
      },
      "ord": 5
    }
  ]
}
```

### 示例2：员工考勤统计模板

```json
{
  "name": "月度考勤统计",
  "description": "记录员工月度考勤情况",
  "fields": [
    {
      "display_name": "工号",
      "validation_rule": {
        "type": "EMPLOYEE_ID",
        "required": true
      },
      "ord": 0
    },
    {
      "display_name": "姓名",
      "validation_rule": {
        "type": "TEXT",
        "required": true
      },
      "ord": 1
    },
    {
      "display_name": "出勤天数",
      "validation_rule": {
        "type": "INTEGER",
        "required": true,
        "min": 0,
        "max": 31
      },
      "ord": 2
    },
    {
      "display_name": "迟到次数",
      "validation_rule": {
        "type": "INTEGER",
        "min": 0
      },
      "ord": 3
    },
    {
      "display_name": "是否全勤",
      "validation_rule": {
        "type": "BOOLEAN"
      },
      "ord": 4
    }
  ]
}
```

## 验证错误类型

当数据不符合验证规则时，会产生以下错误：

| 错误类型 | 说明 | 示例 |
|---------|------|------|
| **MISSING** | 必填项为空 | required=true 但值为空 |
| **INVALID** | 格式/类型错误 | 邮箱格式错误、手机号不符合规则等 |