import os
from io import BytesIO
import uvicorn
import json
import datetime
import hashlib
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from RAG_system import RAGSystem, chatbot
from intent_recognition import identify_intent
from passlib.context import CryptContext
import secrets
import uuid

# 日志
logging.basicConfig(level=logging.DEBUG)

# 常量
MAX_FILE_SIZE_MB = 3
ALLOWED_FILE_TYPES = ['.pdf', '.docx', '.txt', '.md', '.ipynb']
HISTORY_FILE_PATH = "chat_history.json"
USER_FILE_PATH = "users.json"
ADMIN_FOLDER = "admin_chat_history"

# 临时令牌存储(生产环境应使用数据库)
ACTIVE_TOKENS: Dict[str, str] = {}

# 加载课程相关知识库
try:
    with open("D:\AIMaster\PBL\knowledge_base\course_data.json", "r", encoding="utf-8") as f:
        COURSE_INFO = json.load(f)
except FileNotFoundError:
    logging.error("无法加载课程知识库，请检查文件路径。")
    COURSE_INFO = {}

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# FastAPI 应用实例
app = FastAPI()

# 允许 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RAG 系统和 LLM 实例
rag_system_instance = RAGSystem()

# --- Pydantic 模型，用于定义API请求和响应的数据结构 ---
class MessageRequest(BaseModel):
    message: str
    session_id: str

class MessageResponse(BaseModel):
    answer: str
    history: List[Dict[str, str]]
    recommended_questions: List[str] = Field(default_factory=list)

class SessionInfo(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str
    messages: List[Dict[str, str]] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)

class FileUploadResponse(BaseModel):
    status: str
    message: str
    uploaded_files: List[str]

class User(BaseModel):
    id: str
    username: str
    role: str = "user"

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: str
    username: str
    role: str

class UserRoleUpdate(BaseModel):
    user_id: str
    role: str

# OAuth2 依赖
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# --- 用户数据管理 ---
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def load_users() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(USER_FILE_PATH):
        with open(USER_FILE_PATH, 'r', encoding='utf-8') as f:
            try:
                users = json.load(f)
                return {username: UserInDB(**data).dict() for username, data in users.items()}
            except json.JSONDecodeError:
                logging.warning("警告： 用户文件格式错误， 已创建新的空用户列表。")
                return {}
    return {}

def save_users(users: Dict[str, Dict[str, Any]]):
    with open(USER_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

USERS_DB = load_users()

# 为管理员账户生成一个哈希密码
# from passlib.context import CryptContext
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# hashed_password = pwd_context.hash("your-super-strong-admin-password")
# print(hashed_password)
# 内置管理员账户
# 检查并添加内置管理员账户
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = "$2b$12$J1XGV.h9bziC087BlOrc4eMvYPScJtQJbVxpjrHmvo4mCV.flpd7m" # <-- 替换为你自己的哈希值

if ADMIN_USERNAME not in USERS_DB:
    admin_user_data = {
        "id": hashlib.sha256(ADMIN_USERNAME.encode()).hexdigest()[:8],
        "username": ADMIN_USERNAME,
        "hashed_password": ADMIN_PASSWORD_HASH,
        "role": "admin"
    }
    USERS_DB[ADMIN_USERNAME] = admin_user_data
    save_users(USERS_DB)
    logging.info("内置管理员账户已创建或加载。")

def get_user_from_db(username: str) -> Optional[UserInDB]:
    user_data = USERS_DB.get(username)
    if user_data:
        return UserInDB(**user_data)
    return None

def create_token(user: UserInDB) -> str:
    token = secrets.token_urlsafe(32)
    ACTIVE_TOKENS[token] = user.username
    return token

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    username = ACTIVE_TOKENS.get(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_in_db = get_user_from_db(username)
    if not user_in_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return User(id=user_in_db.id, username=user_in_db.username, role=user_in_db.role)

def get_current_admin(current_user: User = Depends(get_current_user)):
    """认证用户是否为管理员"""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，需要管理员权限")
    return current_user

# --- 会话管理逻辑 ---
def load_all_sessions() -> Dict[str, Any]:
    if os.path.exists(HISTORY_FILE_PATH):
        with open(HISTORY_FILE_PATH, "r", encoding="utf-8") as f:
            try:
                sessions_data = json.load(f)
                for sid in sessions_data:
                    if 'files' not in sessions_data[sid]:
                        sessions_data[sid]['files'] = []
                return sessions_data
            except json.JSONDecodeError:
                logging.warning("警告: 历史文件格式错误，已创建新的空历史。")
                return {}
    return {}

def save_all_sessions(sessions: Dict[str, Any]):
    with open(HISTORY_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=4)

def save_chat_history_to_file(session_data: dict):
    """保存单个会话的聊天记录到一个管理员文件夹"""
    os.makedirs(ADMIN_FOLDER, exist_ok=True)
    file_name = f"chat_history_user_{session_data['user_id']}_session_{session_data['id']}.json"
    file_path = os.path.join(ADMIN_FOLDER, file_name)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(session_data, f, ensure_ascii=False, indent=4)

ALL_SESSIONS = load_all_sessions()

# --- API 端点 ---
@app.post("/register")
async def register_user(form_data: OAuth2PasswordRequestForm = Depends()):
    if get_user_from_db(form_data.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    hashed_password = get_password_hash(form_data.password)
    user_id = hashlib.sha256(form_data.username.encode()).hexdigest()[:8]
    new_user = UserInDB(id=user_id, username=form_data.username, hashed_password=hashed_password, role="user")

    USERS_DB[form_data.username] = new_user.dict()
    save_users(USERS_DB)
    return {"message": "用户注册成功"}

@app.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user_in_db = get_user_from_db(form_data.username)
    if not user_in_db or not verify_password(form_data.password, user_in_db.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = create_token(user_in_db)
    return Token(access_token=token)

@app.get("/me", response_model=User)
async def read_current_user(current_user: User = Depends(get_current_user)):
    """获取当前用户"""
    return current_user

@app.get("/users", response_model=List[UserOut])
async def get_all_users(admin: User = Depends(get_current_admin)):
    """获取所有用户列表，仅限管理员访问"""
    return [UserOut(id=user['id'], username=user['username'], role=user['role']) for user in USERS_DB.values()]

@app.put("/users/role", response_model=UserOut)
async def update_user_role(update_data: UserRoleUpdate, admin: User = Depends(get_current_admin)):
    """更新用户的角色，仅限管理员访问"""
    user_to_update = None
    for username, user_data in USERS_DB.items():
        if user_data['id'] == update_data.user_id:
            user_to_update = user_data
            break
    if not user_to_update:
        raise HTTPException(status_code=404, detail="用户未找到")
    
    user_to_update['role'] = update_data.role
    save_users(USERS_DB)
    return UserOut(**user_to_update)

# 管理员专用API端点
@app.get("/admin/sessions")
async def get_all_sessions_for_admin(admin: User = Depends(get_current_admin)):
    sessions_data = load_all_sessions()  # 每次都重新加载
    sessions_list = []
    for session_id, session_data in sessions_data.items():
        session_info = {
            "id": session_id,
            "user_id": session_data["user_id"],
            "username": next((u["username"] for u in USERS_DB.values() if u["id"] == session_data["user_id"]), "未知用户"),
            "title": session_data.get("title", f"会话 {session_id[:4]}"),
            "created_at": session_data.get("created_at", "未知时间")
        }
        sessions_list.append(session_info)
    sessions_list.sort(key=lambda x: x["created_at"], reverse=True)
    return sessions_list

@app.get("/admin/sessions/{session_id}")
async def get_admin_session_detail(session_id: str, admin: User = Depends(get_current_admin)):
    sessions_data = load_all_sessions()  # 每次都重新加载
    session_data = sessions_data.get(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session_data

@app.get("/sessions", response_model=List[SessionInfo])
async def get_all_sessions(current_user: User = Depends(get_current_user)):
    sessions_list = []
    for sid, data in ALL_SESSIONS.items():
        if data.get('user_id') == current_user.id:
            sessions_list.append(SessionInfo(**data))
    return sessions_list

@app.post("/sessions/new", response_model=SessionInfo)
async def create_new_session_api(current_user: User = Depends(get_current_user)):
    all_sessions = ALL_SESSIONS
    max_session_number = 0
    for session_data in all_sessions.values():
        if session_data.get('user_id') == current_user.id and session_data.get('title', '').startswith("会话"):
            try:
                number = int(session_data.get('title', '').replace("会话", "").strip())
                if number > max_session_number:
                    max_session_number = number
            except (ValueError, KeyError):
                continue

    new_session_number = max_session_number + 1
    new_session_title = f"会话{new_session_number}"
    new_session_id = hashlib.sha256(str(datetime.datetime.now()).encode()).hexdigest()[:8]
    new_session_data = SessionInfo(
        id=new_session_id,
        user_id=current_user.id,
        title=new_session_title,
        created_at=str(datetime.datetime.now()),
        messages=[],
        files=[]
    )

    all_sessions[new_session_id] = new_session_data.dict()
    save_all_sessions(all_sessions)

    return new_session_data

@app.get("/sessions/{session_id}", response_model=SessionInfo)
def get_session_by_id(session_id: str, current_user: User = Depends(get_current_user)):
    session_data = ALL_SESSIONS.get(session_id)
    if not session_data or session_data.get('user_id') != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found or not owned by user")
    
    return SessionInfo(**session_data)

@app.post("/sessions/{session_id}/files", response_model=FileUploadResponse)
async def upload_files_api(session_id: str, files: List[UploadFile] = File(...), current_user: User = Depends(get_current_user)):
    if session_id not in ALL_SESSIONS or ALL_SESSIONS[session_id].get('user_id') != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = ALL_SESSIONS[session_id]
    uploaded_files_paths = session_data.get("files", [])
    
    files_to_process = []
    
    try:
        for file in files:
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in ALLOWED_FILE_TYPES:
                raise HTTPException(status_code=400, detail=f"不支持该文件格式: {file.filename}")
            
            file_content = await file.read()
            file_object = BytesIO(file_content)
            file_object.name = file.filename
            files_to_process.append(file_object)
            uploaded_files_paths.append(file.filename)
        
        rag_system_instance.build_vectorstore(files_to_process)
        session_data["files"] = uploaded_files_paths
        save_all_sessions(ALL_SESSIONS)

    except Exception as e:
        logging.error(f"文件处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件处理失败: {e}")
    finally:
        for f in files_to_process:
            f.close()

    return FileUploadResponse(
        status="success",
        message="文件已上传成功！已更新知识库。",
        uploaded_files=uploaded_files_paths
    )

@app.post("/sessions/{session_id}/message", response_model=MessageResponse)
async def process_message_api(session_id: str, request: MessageRequest, current_user: User = Depends(get_current_user)):
    if session_id not in ALL_SESSIONS or ALL_SESSIONS[session_id].get('user_id') != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found or not owned by user")
    
    session_data = ALL_SESSIONS[session_id]
    history = session_data.get("messages", [])
    user_message = request.message
    intent = identify_intent(user_message)
    history.append({"role": "user", "content": user_message})

    answer = ""
    recommended_questions = []

    if intent == "RAG_QA":
        if rag_system_instance.vectorstore:
            answer, recommended_questions = rag_system_instance.rag_qa(user_message, history)
            history.append({"role": "assistant", "content": answer})
        else:
            answer = "您好，知识库中还没有内容，我将进行通用问答。请先上传文件。"
            ai_response = chatbot.chat(user_message, history=history[:-1])
            history.append({"role": "assistant", "content": ai_response})
            answer = ai_response

    elif intent == "GENERAL_QA":
        ai_response = chatbot.chat(user_message, history=history[:-1])
        history.append({"role": "assistant", "content": ai_response})
        answer = ai_response
    
    elif intent == "COURSE_MANAGEMENT":
        found_info = False
        for keyword, info in COURSE_INFO.items():
            if keyword in user_message:
                answer = info
                found_info = True
                break
        if not found_info:
            ai_response = chatbot.chat(user_message, history=history[:-1])
            history.append({"role": "assistant", "content": ai_response})
            answer = ai_response
        if found_info:
            history.append({"role": "assistant", "content": answer})

    elif intent == "SYSTEM_ACTION":
        user_message_lower = user_message.lower()
        if "新建会话" in user_message_lower or "开始新会话" in user_message_lower or "创建新会话" in user_message_lower:
            answer = "好的，请点击左侧的“新建会话”按钮来开始一个新的话题。"
        elif "上传" in user_message_lower or "上传新文件" in user_message_lower:
            answer = "请使用“上传文件”按钮来上传您需要参考的资料。"
        elif "删除" in user_message_lower or "清空" in user_message_lower or "清空聊天记录" in user_message_lower:
            answer = "如果您想清空当前聊天记录，请点击界面下方的“清空聊天”按钮。"
        else:
            answer = "您好，系统操作（例如新建会话、上传文件）需要通过界面按钮完成。请使用相应按钮进行操作。"
        
        history.append({"role": "assistant", "content": answer})
    
    else:
        ai_response = chatbot.chat(user_message, history=history[:-1])
        history.append({"role": "assistant", "content": ai_response})
        answer = ai_response

    session_data["messages"] = history
    # save_all_sessions(ALL_SESSIONS)
    # 为管理员保存聊天记录
    save_chat_history_to_file(session_data)

    return MessageResponse(answer=history[-1]['content'], history=history, recommended_questions=recommended_questions)

if __name__ == "__main__":
    if not os.path.exists("uploaded_files"):
        os.makedirs("uploaded_files")
    if not os.path.exists(ADMIN_FOLDER):
        os.makedirs(ADMIN_FOLDER)
    uvicorn.run(app, host="127.0.0.1", port=8000)