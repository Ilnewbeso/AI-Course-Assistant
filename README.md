# 智能课程咨询助手 + 专业知识顾问

一个基于RAG（检索增强生成）技术的智能课程咨询系统，集成了文档上传、向量检索、意图识别和多轮对话功能。支持多种文档格式，提供智能问答推荐，是您的专业学习助手。

## 项目特性

- **智能意图识别**：自动识别用户意图（RAG问答、通用问答、课程管理、系统操作）
- **RAG文档检索**：支持PDF、DOCX、TXT、MD、IPYNB等格式文档的智能检索问答
- **多轮对话**：支持上下文记忆的多轮对话功能，智能推荐相关问题
- **会话管理**：支持创建、切换和管理多个对话会话，按时间自动分类
- **文件管理**：支持多文件同时上传并自动构建向量知识库
- **现代化界面**：基于Gradio的响应式深色主题界面，用户体验优良
- **实时更新**：文档上传后即时更新知识库，无需重启服务

## 系统架构

```
智能课程咨询助手/
├── frontend.py              # Gradio前端界面 - 用户交互层
├── rag_api.py              # FastAPI后端服务 - 核心API层
├── RAG_system.py           # RAG检索系统 - 文档处理与向量检索
├── intent_recognition.py   # 意图识别模块 - 智能路由分发
├── knowledge_base/         # 课程知识库目录
│   └── course_data.json   # 课程结构化数据配置
├── uploaded_files/         # 用户上传文件存储（运行时创建）
├── chroma_db/             # Chroma向量数据库（运行时创建）
├── chat_history.json      # 对话历史记录（运行时创建）
├── .env                   # 环境配置文件
├── requirements.txt       # 项目依赖
└── README.md             # 项目文档
```

## 技术栈

|组件|技术选型|版本要求|说明|
|---|---|---|---|
|**后端框架**|FastAPI|>=0.100.0|高性能异步API框架|
|**前端界面**|Gradio|>=4.0.0|机器学习应用界面|
|**LLM模型**|DeepSeek API|-|大语言模型服务|
|**向量数据库**|Chroma|>=0.4.0|向量存储与检索|
|**嵌入模型**|BGE-large-zh|v1.5|中文文本向量化|
|**文档处理**|LangChain|>=0.1.0|文档加载与分割|
|**文档解析**|PyPDF2, python-docx|-|多格式文档支持|

## 快速开始

### 环境要求

- Python 3.8+
- 内存：建议4GB以上
- 磁盘：预留2GB存储空间
- 网络：需要访问DeepSeek API

### 1. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 环境配置

创建 `.env` 文件并配置API密钥：

```env
# DeepSeek API配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 可选：其他配置
CHROMA_DB_PATH=./chroma_db
UPLOAD_PATH=./uploaded_files
```

>  **获取API密钥**：访问 [DeepSeek官网](https://platform.deepseek.com/) 注册并获取API密钥

### 4. 配置嵌入模型

**方法一：自动下载（推荐新用户）**

修改 `RAG_system.py` 中的配置：

```python
embeddings = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-large-zh-v1.5",  # 在线下载
    model_kwargs={"device": "cpu"}
)
```

**方法二：使用本地模型（推荐有本地模型的用户）**

```python
embeddings = HuggingFaceBgeEmbeddings(
    model_name="C:\\path\\to\\your\\bge-large-zh-v1.5",  # 本地路径
    model_kwargs={"device": "cpu"}
)
```

### 5. 初始化项目结构

```bash
# 创建必要目录
mkdir -p uploaded_files knowledge_base chroma_db

# 初始化课程数据文件
echo '{}' > knowledge_base/course_data.json
```

### 6. 启动系统

**终端1 - 启动后端服务：**

```bash
python rag_api.py
```

看到以下信息表示后端启动成功：

```
INFO:     Started server process [xxxxx]
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**终端2 - 启动前端界面：**

```bash
python frontend.py
```

看到以下信息表示前端启动成功：

```
Running on local URL:  http://127.0.0.1:7860
```

### 7. 访问应用

在浏览器中访问：**http://127.0.0.1:7860**

## 使用指南

### 基础操作流程

1. **开始使用**
    - 点击"新建会话"创建对话
    - 系统自动生成会话标题
2. **上传文档**
    - 拖拽文件到上传区域
    - 或点击上传按钮选择文件
    - 支持同时上传多个文件
3. **智能问答**
    - 在输入框输入问题
    - 点击"发送"或按回车键
    - 系统自动识别意图并回答
4. **推荐问题**
    - 系统自动生成相关问题
    - 点击推荐问题快速提问
5. **会话管理**
    - 左侧面板查看历史会话
    - 按时间自动分类显示
    - 点击切换到历史对话
6. 登陆系统
	- 注册为普通用户使用智能助手系统
	- 内置管理员账号登录查看所有历史记录

### 智能意图识别

系统自动识别以下四种用户意图：

| 意图类型        | 触发场景      | 示例问题                                   | 处理方式       |
| ----------- | --------- | -------------------------------------- | ---------- |
| **RAG文档问答** | 询问已上传文档内容 | "根据这份PDF，第三章讲了什么？"<br>"文档中提到的核心概念是什么？" | 向量检索+上下文问答 |
| **通用问答**    | 日常对话和通用知识 | "你好"<br>"什么是机器学习？"<br>"帮我写个Python函数"   | 直接LLM对话    |
| **课程管理**    | 询问课程结构和安排 | "第三周的核心模块是什么？"<br>"意图识别系统怎么实现的？"       | 结构化数据查询    |
| **系统操作**    | 系统功能使用指导  | "如何上传文件？"<br>"怎么新建会话？"                 | 操作指南回复     |

### 支持的文档格式

|格式类型|文件扩展名|大小限制|特殊说明|
|---|---|---|---|
|**PDF文档**|`.pdf`|3MB|提取文本内容，支持多页|
|**Word文档**|`.docx`|3MB|提取段落文本和格式|
|**纯文本**|`.txt`|3MB|UTF-8编码，原始文本|
|**Markdown**|`.md`|3MB|完整Markdown语法支持|
|**Jupyter笔记本**|`.ipynb`|3MB|提取代码和markdown单元格|

### 会话管理功能

- **时间分类**：自动按"今天"、"昨天"、"更早"分类
- **自动保存**：对话内容实时保存到本地
- **无缝切换**：点击历史会话即可切换上下文
- **状态显示**：显示当前会话和已上传文件状态

## 高级配置


### 内置管理员账号

用户名：admin
密码：Admin.20250813

可以使用内置管理员账号密码登陆系统查看所有用户的会话聊天历史

### 自定义课程数据

编辑 `knowledge_base/course_data.json` 添加课程信息：

```json
{
  "第一周": "Python基础语法：变量、数据类型、控制结构。实践项目：计算器程序。",
  "第二周": "面向对象编程：类、对象、继承、多态。项目：学生管理系统。",
  "RAG系统": "检索增强生成技术，结合文档检索和语言生成，提高回答准确性。",
  "意图识别": "NLP任务，通过模式匹配和机器学习识别用户真实意图。",
  "向量数据库": "Chroma数据库用于存储文档向量，支持语义相似度检索。"
}
```

### 性能优化设置

**GPU加速（可选）**

如果有NVIDIA GPU，可以启用GPU加速：

```python
# 在 RAG_system.py 中修改
embeddings = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-large-zh-v1.5",
    model_kwargs={"device": "cuda"}  # 使用GPU
)
```

**内存优化**

对于内存受限环境，可以调整参数：

```python
# 减少检索文档数量
docs = self.vectorstore.similarity_search(query, k=3)  # 默认k=5

# 减少文本分块大小
splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,    # 默认1024
    chunk_overlap=64   # 默认128
)
```

## API接口文档

### 会话管理接口

#### 获取所有会话

```http
GET /sessions
```

**响应示例：**

```json
[
  {
    "id": "abc12345",
    "title": "会话1",
    "created_at": "2024-01-15T10:30:00",
    "messages": []
  }
]
```

#### 创建新会话

```http
POST /sessions/new
```

#### 获取指定会话

```http
GET /sessions/{session_id}
```

### 文件和消息处理

#### 上传文件

```http
POST /sessions/{session_id}/files
Content-Type: multipart/form-data

files: [file1, file2, ...]
```

#### 发送消息

```http
POST /sessions/{session_id}/message
Content-Type: application/json

{
  "message": "你的问题",
  "session_id": "abc12345"
}
```

**响应示例：**

```json
{
  "answer": "AI助手的回答",
  "history": [
    {"role": "user", "content": "用户问题"},
    {"role": "assistant", "content": "AI回答"}
  ],
  "recommended_questions": [
    "相关问题1",
    "相关问题2"
  ]
}
```

## 故障排除

### 常见问题解决

|问题|可能原因|解决方案|
|---|---|---|
|**后端启动失败**|端口8000被占用|`lsof -i :8000` 查看并关闭占用进程|
|**前端无法连接后端**|API_URL配置错误|检查frontend.py中的API_URL设置|
|**文件上传失败**|文件格式不支持或过大|检查文件格式和大小限制|
|**向量检索无结果**|嵌入模型未正确加载|检查模型路径和网络连接|
|**API调用失败**|DeepSeek密钥无效|验证.env文件中的API密钥|

### 调试模式

启用详细日志输出：

```python
# 在各模块顶部添加
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 重置系统

如需重置所有数据：

```bash
# 清理所有生成的文件
rm -rf chroma_db/ uploaded_files/
rm -f chat_history.json

# 重新创建目录
mkdir -p chroma_db uploaded_files
```