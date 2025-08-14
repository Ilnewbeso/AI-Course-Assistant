# 智能课程咨询助手 API 接口文档

## 📋 概述

智能课程咨询助手提供基于FastAPI的RESTful API服务，支持会话管理、文件上传、智能问答等功能。API采用JSON格式进行数据交换，支持CORS跨域请求。

### 基础信息

- **API基础URL**: `http://127.0.0.1:8000`
- **协议**: HTTP/HTTPS
- **数据格式**: JSON
- **字符编码**: UTF-8
- **API版本**: v1.0

### 技术栈

- **框架**: FastAPI
- **异步支持**: 完全异步处理
- **文档**: 自动生成OpenAPI文档
- **验证**: Pydantic模型验证

## 🔐 认证与授权

当前版本API无需身份认证，支持匿名访问。未来版本可能会添加API密钥或JWT认证。

## 📊 响应格式

### 标准HTTP状态码

| 状态码 | 说明 | 使用场景 |
|-------|------|----------|
| `200` | 成功 | 请求成功处理 |
| `201` | 创建成功 | 新资源创建成功 |
| `400` | 请求错误 | 参数错误或格式不正确 |
| `404` | 资源不存在 | 会话ID不存在 |
| `422` | 验证错误 | 请求数据验证失败 |
| `500` | 服务器错误 | 内部服务器错误 |

### 错误响应格式

```json
{
  "detail": "错误描述信息"
}
```

## 🔗 API端点详细说明

### 1. 会话管理

#### 1.1 获取所有会话列表

```http
GET /sessions
```

**功能描述**: 获取系统中所有会话的基本信息，按创建时间倒序排列。

**请求参数**: 无

**响应数据**:

```json
[
  {
    "id": "abc12345",
    "title": "会话1",
    "created_at": "2024-01-15T10:30:00.123456",
    "messages": [
      {
        "role": "user",
        "content": "用户消息内容"
      },
      {
        "role": "assistant", 
        "content": "助手回复内容"
      }
    ]
  }
]
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 会话唯一标识符（8位哈希值） |
| `title` | string | 会话标题（如："会话1", "会话2"） |
| `created_at` | string | 会话创建时间（ISO格式） |
| `messages` | array | 完整的消息历史记录 |

**请求示例**:

```bash
curl -X GET "http://127.0.0.1:8000/sessions" \
     -H "accept: application/json"
```

**响应示例**:

```json
[
  {
    "id": "a1b2c3d4",
    "title": "会话1",
    "created_at": "2024-01-15T14:30:25.123456",
    "messages": [
      {
        "role": "user",
        "content": "你好，请介绍一下RAG系统"
      },
      {
        "role": "assistant",
        "content": "RAG（检索增强生成）是一种结合了信息检索和文本生成的AI技术..."
      }
    ]
  }
]
```

---

#### 1.2 创建新会话

```http
POST /sessions/new
```

**功能描述**: 创建一个新的对话会话，自动生成唯一ID和标题。

**请求参数**: 无

**响应数据**:

```json
{
  "id": "def67890",
  "title": "会话2", 
  "created_at": "2024-01-15T14:35:00.654321",
  "messages": []
}
```

**业务逻辑**:
1. 自动分析现有会话，生成递增的会话编号
2. 使用当前时间戳生成8位哈希ID
3. 初始化空的消息历史记录
4. 持久化保存到本地JSON文件

**请求示例**:

```bash
curl -X POST "http://127.0.0.1:8000/sessions/new" \
     -H "accept: application/json"
```

**响应示例**:

```json
{
  "id": "x9y8z7w6",
  "title": "会话3",
  "created_at": "2024-01-15T14:35:12.789012",
  "messages": []
}
```

---

#### 1.3 获取指定会话详情

```http
GET /sessions/{session_id}
```

**功能描述**: 根据会话ID获取指定会话的完整信息，包括消息历史和文件列表。

**路径参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `session_id` | string | 是 | 会话唯一标识符 |

**响应数据**:

```json
{
  "id": "abc12345",
  "title": "会话1",
  "created_at": "2024-01-15T10:30:00.123456", 
  "messages": [
    {
      "role": "user",
      "content": "请分析这份文档"
    },
    {
      "role": "assistant", 
      "content": "根据您上传的文档，我分析到以下要点..."
    }
  ]
}
```

**错误响应**:

```json
{
  "detail": "Session not found"
}
```

**请求示例**:

```bash
curl -X GET "http://127.0.0.1:8000/sessions/abc12345" \
     -H "accept: application/json"
```

---

### 2. 文件管理

#### 2.1 上传文件到会话

```http
POST /sessions/{session_id}/files
```

**功能描述**: 向指定会话上传一个或多个文件，自动解析文档内容并更新向量知识库。

**路径参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `session_id` | string | 是 | 目标会话ID |

**请求体**: `multipart/form-data`

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `files` | file[] | 是 | 要上传的文件列表 |

**文件限制**:

| 属性 | 限制 | 说明 |
|------|------|------|
| **大小** | 3MB | 单文件最大限制 |
| **格式** | .pdf, .docx, .txt, .md, .ipynb | 支持的文件类型 |
| **编码** | UTF-8 | 文本文件编码要求 |

**响应数据**:

```json
{
  "status": "success",
  "message": "文件已上传成功！已更新知识库。",
  "uploaded_files": [
    "document1.pdf",
    "notes.txt",
    "analysis.ipynb"
  ]
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 处理状态（success/error） |
| `message` | string | 处理结果描述 |
| `uploaded_files` | array | 成功上传的文件名列表 |

**处理流程**:
1. 验证会话存在性
2. 检查文件格式和大小
3. 解析文档内容（PDF、Word、文本等）
4. 文本分块处理（chunk_size=1024）
5. 生成向量嵌入
6. 更新Chroma向量数据库
7. 保存文件记录到会话

**请求示例**:

```bash
curl -X POST "http://127.0.0.1:8000/sessions/abc12345/files" \
     -H "accept: application/json" \
     -F "files=@document.pdf" \
     -F "files=@notes.txt"
```

**错误示例**:

```json
{
  "detail": "不支持该文件格式: image.jpg"
}
```

```json
{
  "detail": "Session not found"
}
```

---

### 3. 消息处理

#### 3.1 发送消息并获取回复

```http
POST /sessions/{session_id}/message
```

**功能描述**: 向指定会话发送用户消息，系统会自动识别意图并返回相应回复和推荐问题。

**路径参数**:

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `session_id` | string | 是 | 目标会话ID |

**请求体**: `application/json`

```json
{
  "message": "根据刚才上传的PDF文档，请总结主要内容",
  "session_id": "abc12345"
}
```

**请求参数**:

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `message` | string | 是 | 用户输入的消息内容 |
| `session_id` | string | 是 | 会话ID（与路径参数一致） |

**响应数据**:

```json
{
  "answer": "根据您上传的PDF文档，主要内容包括：1. 人工智能的发展历程...",
  "history": [
    {
      "role": "user", 
      "content": "根据刚才上传的PDF文档，请总结主要内容"
    },
    {
      "role": "assistant",
      "content": "根据您上传的PDF文档，主要内容包括：1. 人工智能的发展历程..."
    }
  ],
  "recommended_questions": [
    "文档中提到的关键技术有哪些？",
    "这些技术的应用场景是什么？", 
    "文档中有没有提到发展趋势？"
  ]
}
```

**字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer` | string | AI助手的回复内容 |
| `history` | array | 更新后的完整对话历史 |
| `recommended_questions` | array | 基于上下文生成的推荐问题 |

**智能意图识别**:

系统会自动识别用户意图并路由到相应处理逻辑：

| 意图类型 | 触发条件 | 处理方式 | 示例 |
|---------|---------|---------|------|
| **RAG_QA** | 询问文档具体内容 | 向量检索+LLM生成 | "根据文档，第三章讲了什么？" |
| **GENERAL_QA** | 通用知识问答 | 直接LLM对话 | "什么是机器学习？" |
| **COURSE_MANAGEMENT** | 课程相关询问 | 结构化数据查询 | "第二周的课程内容是什么？" |
| **SYSTEM_ACTION** | 系统操作指导 | 操作引导回复 | "如何上传文件？" |

**请求示例**:

```bash
curl -X POST "http://127.0.0.1:8000/sessions/abc12345/message" \
     -H "accept: application/json" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "请解释一下RAG技术的工作原理",
       "session_id": "abc12345"
     }'
```

**RAG问答示例响应**:

```json
{
  "answer": "RAG（检索增强生成）技术的工作原理分为两个阶段：\n\n1. **检索阶段**：根据用户问题，在向量数据库中检索相关文档片段\n2. **生成阶段**：将检索到的上下文与问题一起输入LLM生成回答\n\n这种方式能够有效提高回答的准确性和相关性。",
  "history": [
    {
      "role": "user",
      "content": "请解释一下RAG技术的工作原理"
    },
    {
      "role": "assistant", 
      "content": "RAG（检索增强生成）技术的工作原理分为两个阶段..."
    }
  ],
  "recommended_questions": [
    "RAG与传统问答系统有什么区别？",
    "如何优化RAG系统的检索效果？",
    "向量数据库在RAG中起什么作用？"
  ]
}
```

---

## 🔧 数据模型定义

### SessionInfo 模型

```python
{
  "id": "string",           # 会话唯一标识符
  "title": "string",        # 会话标题
  "created_at": "string",   # 创建时间（ISO格式）
  "messages": [             # 消息历史
    {
      "role": "user|assistant",
      "content": "string"
    }
  ]
}
```

### MessageRequest 模型

```python
{
  "message": "string",      # 用户消息内容（必需）
  "session_id": "string"    # 会话ID（必需）
}
```

### MessageResponse 模型

```python
{
  "answer": "string",       # AI回复内容
  "history": [              # 更新后的对话历史
    {
      "role": "string",
      "content": "string"
    }
  ],
  "recommended_questions": ["string"]  # 推荐问题列表
}
```

### FileUploadResponse 模型

```python
{
  "status": "success|error",    # 处理状态
  "message": "string",          # 处理结果描述
  "uploaded_files": ["string"]  # 上传成功的文件列表
}
```

---

## 🧪 测试示例

### 完整使用流程测试

#### 1. 创建新会话

```bash
# 创建会话
SESSION_RESPONSE=$(curl -s -X POST "http://127.0.0.1:8000/sessions/new")
SESSION_ID=$(echo $SESSION_RESPONSE | jq -r '.id')
echo "创建的会话ID: $SESSION_ID"
```

#### 2. 上传文件

```bash
# 上传文档
curl -X POST "http://127.0.0.1:8000/sessions/$SESSION_ID/files" \
     -F "files=@test_document.pdf" \
     -F "files=@notes.txt"
```

#### 3. 发送问题

```bash
# 询问文档内容
curl -X POST "http://127.0.0.1:8000/sessions/$SESSION_ID/message" \
     -H "Content-Type: application/json" \
     -d "{
       \"message\": \"请总结刚才上传文档的主要内容\",
       \"session_id\": \"$SESSION_ID\"
     }"
```

#### 4. 查看会话历史

```bash
# 获取会话详情
curl -X GET "http://127.0.0.1:8000/sessions/$SESSION_ID"
```

---

## ⚠️ 错误处理

### 常见错误情况

#### 1. 会话不存在 (404)

```json
{
  "detail": "Session not found"
}
```

**原因**: 使用了不存在的session_id

**解决方案**: 
- 通过 `GET /sessions` 获取有效的会话ID列表
- 或者创建新会话 `POST /sessions/new`

#### 2. 文件格式不支持 (400)

```json
{
  "detail": "不支持该文件格式: image.png"
}
```

**原因**: 上传了不支持的文件格式

**解决方案**: 
- 只上传支持的格式：.pdf, .docx, .txt, .md, .ipynb
- 检查文件扩展名是否正确

#### 3. 文件过大 (413)

```json
{
  "detail": "文件大小超出限制"
}
```

**原因**: 单个文件超过3MB限制

**解决方案**: 
- 压缩文件或分割大文件
- 选择更小的文件进行上传

#### 4. API调用失败 (500)

```json
{
  "detail": "AI通信出现错误"
}
```

**原因**: DeepSeek API调用失败

**解决方案**: 
- 检查网络连接
- 验证API密钥是否正确
- 检查API额度是否充足

---

## 📊 性能和限制

### API限制

| 项目 | 限制值 | 说明 |
|------|-------|------|
| **并发连接** | 100 | 最大同时连接数 |
| **请求频率** | 无限制 | 当前版本无频率限制 |
| **文件大小** | 3MB | 单文件上传限制 |
| **会话数量** | 无限制 | 理论上无限制 |
| **消息历史** | 无限制 | 全量保存对话记录 |

### 性能优化建议

1. **文件上传优化**
   - 建议文件大小控制在1MB以内获得最佳处理速度
   - PDF文件页数建议控制在50页以内

2. **检索优化** 
   - 系统默认检索Top-5相关文档片段
   - 可通过调整相似度阈值优化检索精度

3. **响应时间**
   - 文档检索：通常100-500ms
   - LLM生成：通常2-8秒
   - 文件上传处理：根据文件大小1-10秒

---

## 🔗 相关资源

### 自动生成的API文档

FastAPI提供自动生成的交互式API文档：

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **OpenAPI JSON**: http://127.0.0.1:8000/openapi.json

### 开发工具推荐

- **API测试**: [Postman](https://www.postman.com/), [Insomnia](https://insomnia.rest/)
- **命令行工具**: [HTTPie](https://httpie.io/), [curl](https://curl.se/)
- **SDK生成**: 可基于OpenAPI规范生成各语言SDK

---

## 📝 更新日志

### v1.0.0 (2024-01-15)

- ✅ 实现基础会话管理API
- ✅ 支持多格式文件上传和解析
- ✅ 集成RAG检索问答功能
- ✅ 添加智能意图识别
- ✅ 实现推荐问题生成
- ✅ 支持CORS跨域请求

### 计划中的功能

- 🔄 API认证和授权机制
- 📊 使用统计和分析接口
- 🔍 高级搜索和过滤功能
- 📱 WebSocket实时通信支持

---

## 🆘 技术支持

如果在使用API过程中遇到问题：

1. 查看自动生成的API文档：http://127.0.0.1:8000/docs
2. 检查后端日志输出获取详细错误信息
3. 参考本文档的错误处理章节
4. 提交GitHub Issue或联系开发团队

**祝您使用愉快！** 🎉