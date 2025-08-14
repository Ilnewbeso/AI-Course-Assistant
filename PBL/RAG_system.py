import os
import logging
import nbformat
import requests
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFDirectoryLoader, DirectoryLoader
from langchain_community.vectorstores import Chroma
from langchain.prompts import PromptTemplate
from docx import Document as DocxDocument
from PyPDF2 import PdfReader
from langchain.embeddings import HuggingFaceBgeEmbeddings
from sentence_transformers import SentenceTransformer
from fastapi import HTTPException
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 1. 配置Deppseek LLM
load_dotenv("D:/AIMaster/.env")

class DeepSeekLLM():
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置")
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.system_message = "你是一个知识渊博，乐于助人，且耐心认真帮助用户的课程问答助手"

    def chat(self, text: str, history: List[Dict[str, str]] = None, role: str = "user", context: Optional[str] = None):
        messages = []

        # 如果有Context，将其作为系统消息的一部分
        if context:
            rag_system_message = f"{self.system_message}\n\n以下是参考资料: \n{context}\n\n请根据以上资料和对话历史进行回答。"
            messages.append({"role": "system", "content": rag_system_message})
        else:
            messages.append({"role": "system", "content": self.system_message})
        
        if history:
            # 过滤掉RAG检索前用户添加的最新消息，将其视为单独的text传入
            messages.extend(history)

        messages.append({"role": role, "content": text})

        payload ={
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                self.api_url, headers=self.headers,
                json=payload, timeout=200
            )

            response.raise_for_status() #检查HTTP错误
            reply = response.json()["choices"][0]["message"]["content"]
            return reply
        except requests.exceptions.RequestException as e:
            print(f"Error duringAPI call: {e}")
            raise HTTPException(status_code=500, detail="AI通信出现错误")
        except Exception as e:
            print(f"无法响应解析：{response.text}")
            raise HTTPException(status_code=500, detail="AI返回了无法解析的响应")

# 全局 chatbot 实例
chatbot = DeepSeekLLM()

# 2. 配置可用embedding模型
embeddings = HuggingFaceBgeEmbeddings(
    model_name="C:\\Users\\hlw20\\bge-large-zh-v1.5-local",
    model_kwargs={"device": "cpu"}
)

# 3. 文本分割和提取
def extract_text(file):
    filename = file.name.lower()
    file.seek(0)
    try:
        if filename.endswith('.pdf'):
            reader = PdfReader(file)
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        elif filename.endswith('.docx'):
            doc = DocxDocument(file)
            return "\n".join([para.text for para in doc.paragraphs])
        elif filename.endswith('.txt') or filename.endswith('.md'):
            return file.read().decode('utf-8')
        elif filename.endswith('.ipynb'):
            nb = nbformat.read(file, as_version=4)
            texts = []
            for cell in nb.cells:
                if cell.cell_type in ['markdown', 'code']:
                    texts.append(cell.source)
            return "\n".join(texts)
        else:
            return "暂不支持该类型文件"
    except Exception as e:
        print(f"文件解析错误: {e}")
        return ""

class RAGSystem:
    def __init__(self, persist_directory="D:/AIMaster/PBL/chroma_db"):
        self.persist_directory = persist_directory
        self.vectorstore = None
        self.embeddings = embeddings
        self._load_or_create_vectorstore()

    def _load_or_create_vectorstore(self):
        if os.path.exists(self.persist_directory) and os.listdir(self.persist_directory):
            print("正在加载已存在的向量数据库...")
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
            )
        else:
            print("未找到向量数据库，将创建一个新的。")

    # 构建向量数据库
    def build_vectorstore(self, files: List[Any]):
        if not files:
            print("没有文件可供处理")
            return

        all_docs = []
        for file in files:
            text = extract_text(file)
            if not text or "暂不支持" in text:
                print(f"文件 '{os.path.basename(file.name)}' 解析失败或不支持")
                continue

            splitter = RecursiveCharacterTextSplitter(chunk_size=1024, chunk_overlap=128)
            docs_from_file = splitter.create_documents([text])
            for doc in docs_from_file:
                doc.metadata["source"] = os.path.basename(file.name)
            all_docs.extend(docs_from_file)

        if not all_docs:
            print("所有文件解析失败或者没有可提取的文本内容")
            return

        if self.vectorstore:
            print(f"正在向现有数据库添加 {len(all_docs)} 个文档...")
            self.vectorstore.add_documents(all_docs)
        else:
            self.vectorstore = Chroma.from_documents(
                documents=all_docs,
                embedding=self.embeddings,
                persist_directory=self.persist_directory
            )
            print(f"向量数据库已创建，包含 {len(all_docs)} 个新文档块")

    # RAG问答作用
    def rag_qa(self, query: str, history: List[Dict[str, str]]) -> Tuple[str, List[str]]:
        """
        RAG问答流程。
        从向量数据库检索上下文，并使用LLM生成答案和推荐问题。
        返回：
        - answer (str): LLM生成的答案。
        - recommended_questions (List[str]): 推荐问题列表。
        """
        
        if not self.vectorstore:
            return "请先上传文件并等待向量数据库构建完成", []

        docs = self.vectorstore.similarity_search(query, k=5)
        context = "\n\n".join([doc.page_content for doc in docs])
        
        print("检索到的内容:")
        for doc in docs:
            print(f"- From {doc.metadata.get('source', 'unknown')}: {doc.page_content[:100]}...")

        try:
            # 1.生成推荐问题
            questions_prompt = f"""
            你是一个问题推荐生成器。根据以下提供的资料，提取出与资料内容相关但用户可能还未询问的3-5个问题。只列出问题，不要给出答案。
            参考资料：{context}
            用户问题：{query}
            """.strip()

            questions_response = chatbot.chat(questions_prompt)

            recommended_questions = []
            if questions_response:
                # 使用换行符分割，并清理序号
                recommended_questions = [
                    q.strip().lstrip('01234. ') for q in questions_response.split('\n') if q.strip()
                ]
            # 2.生成最终答案，并保留多轮对话和记忆
            answer =chatbot.chat(text=query, history=history, context=context)

            return answer, recommended_questions
        
        except Exception as e:
            logging.error(f"RAG问答失败: {e}")
            return "对不起，处理您的请求时出现错误。请稍后重试。", []

# 创建实例
rag_system_instance = RAGSystem()