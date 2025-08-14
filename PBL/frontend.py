import gradio as gr
import requests
import json
import datetime
import os
import logging
from typing import List, Any, Dict, Tuple, Optional
import mimetypes
from collections import defaultdict
import pandas as pd

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# FastAPI 后端 URL
API_URL = "http://127.0.0.1:8000"

MAX_FILE_SIZE_MB = 3
ALLOWED_FILE_TYPES = ['.pdf', '.docx', '.txt', '.md', '.ipynb']
CUSTOM_MIME_TYPES = {
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.ipynb': 'application/x-ipynb+json',
    '.md': 'text/markdown',
}

# 全局状态变量
current_session_id_state = None
all_sessions_cache = {}

# 用户管理认证
access_token: Optional[str] = None
current_user_role: Optional[str] = None
current_username: Optional[str] = None

def get_content_type(filename):
    """根据文件名获取 MIME 类型"""
    ext = os.path.splitext(filename)[1].lower()
    return CUSTOM_MIME_TYPES.get(ext, mimetypes.guess_type(filename)[0] or 'application/octet-stream')

def login_handler(username, password):
    """处理用户登录"""
    global access_token, current_user_role, current_username
    try:
        response = requests.post(f"{API_URL}/login", data={"username": username, "password": password})
        response.raise_for_status()

        token_data = response.json()
        access_token = token_data['access_token']
        current_username = username

        # 获取用户信息以确定角色
        user_response = requests.get(f"{API_URL}/me", headers={"Authorization": f"Bearer {access_token}"})
        user_response.raise_for_status()
        user_data = user_response.json()
        current_user_role = user_data['role']

        gr.Info(f"登陆成功！欢迎, {username}!")

        # 登录成功后，根据角色返回界面状态
        if current_user_role == 'admin':
            # 隐藏主界面，仅显示管理员界面
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)
        else:
            # 普通用户显示主界面
            return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
    
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.json().get("detail", "未知错误")
        gr.Warning(f"登陆失败: {error_detail}")
        return gr.update(visible=True), gr.update(visible=False)
    except requests.exceptions.RequestException as e:
        gr.Warning(f"无法连接到后端服务: {e}")
        return gr.update(visible=True), gr.update(visible=False)
    except Exception as e:
        gr.Warning(f"登陆失败: {e}")
        return gr.update(visible=True), gr.update(visible=False)

def register_handler(username, password, confirm_password):
    """处理用户注册，并返回界面更新命令"""
    if password != confirm_password:
        gr.Warning("两次输入的密码不一致！")
        return gr.update(visible=True) # 注册失败，保持表单可见
    try:
        response = requests.post(f"{API_URL}/register", data={"username": username, "password": password})
        response.raise_for_status()

        # 注册成功
        gr.Info("注册成功！请登录。")
        return gr.update(visible=False) # 注册成功，隐藏表单
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.json().get("detail", "未知错误")
        gr.Warning(f"注册失败: {error_detail}")
        return gr.update(visible=True) # 注册失败，保持表单可见
    except requests.exceptions.RequestException as e:
        gr.Warning(f"无法连接到后端服务: {e}")
        return gr.update(visible=True) # 注册失败，保持表单可见
    except Exception as e:
        gr.Warning(f"注册失败: {e}")
        return gr.update(visible=True) # 注册失败，保持表单可见

def get_session_lists():
    """从API获取当前用户的所有会话，并按时间分组"""
    global all_sessions_cache, access_token
    if not access_token:
        return [], [], []
    try:
        response = requests.get(
            f"{API_URL}/sessions",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        sessions = response.json()
        
        all_sessions_cache = {s['id']: s for s in sessions}

        today = datetime.datetime.now().date()
        yesterday = today - datetime.timedelta(days=1)
        
        sessions_by_date = defaultdict(list)
        
        for session in sorted(sessions, key=lambda s: s['created_at'], reverse=True):
            try:
                session_created_at_dt = datetime.datetime.fromisoformat(session["created_at"])
                session_date = session_created_at_dt.date()
                
                title = session.get("title", f"会话 {session['id'][:4]}")
                
                if session_date == today:
                    sessions_by_date["今天"].append((title, session['id']))
                elif session_date == yesterday:
                    sessions_by_date["昨天"].append((title, session['id']))
                else:
                    sessions_by_date["更早"].append((title, session['id']))
            except (ValueError, KeyError) as e:
                print(f"会话数据格式错误，跳过: {e}")
                continue
                
        return sessions_by_date["今天"], sessions_by_date["昨天"], sessions_by_date["更早"]
    except requests.exceptions.RequestException as e:
        print(f"无法连接到后端API: {e}")
        return [], [], []

def create_new_session_handler():
    """通过API创建新会话，并清空所有状态"""
    global current_session_id_state, access_token
    if not access_token:
        gr.Warning("请先登录！")
        return None, [], "#### 已上传文件: \n- 暂无文件", gr.update(value="请先登录"), [], None, None, None, None
    
    try:
        response = requests.post(
            f"{API_URL}/sessions/new",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        new_session = response.json()
        current_session_id_state = new_session['id']
        
        today_sessions, yesterday_sessions, older_sessions = get_session_lists()
        
        # 确保新会话标题在选项列表中
        today_choices = [s[0] for s in today_sessions]
        if new_session['title'] not in today_choices:
            today_choices.insert(0, new_session['title'])
            
        return (
            new_session['id'],
            [], # 清空聊天界面
            "#### 已上传文件: \n- 暂无文件", # 清空文件列表
            gr.update(value=f"当前会话: {new_session['title']}"),
            [], # 清空文件状态
            gr.update(choices=today_choices, value=new_session['title']),
            gr.update(choices=[s[0] for s in yesterday_sessions]),
            gr.update(choices=[s[0] for s in older_sessions]),
            gr.update(visible=False, choices=[], value=None), # 清空并隐藏推荐问题
        )
    except requests.exceptions.RequestException as e:
        print(f"创建新会话失败: {e}")
        gr.Warning(f"创建新会话失败: {e}")
        return None, [], "#### 已上传文件: \n- 暂无文件", gr.update(value="创建新会话失败"), [], None, None, None, None

def select_session_handler(session_name: str):
    """通过API切换到选定的会话，并加载其历史记录"""
    global current_session_id_state, all_sessions_cache, access_token
    if not access_token:
        gr.Warning("请先登录！")
        return current_session_id_state, [], "#### 已上传文件: \n- 暂无文件", gr.update(value="会话加载失败"), [], gr.update(visible=False, choices=[], value=None)
    
    session_id = None
    for sid, data in all_sessions_cache.items():
        if data.get("title") == session_name:
            session_id = sid
            break
    
    if not session_id:
        gr.Warning("会话加载失败，找不到匹配的ID。")
        return current_session_id_state, [], "#### 已上传文件: \n- 暂无文件", gr.update(value="会话加载失败"), [], gr.update(visible=False, choices=[], value=None)

    try:
        response = requests.get(f"{API_URL}/sessions/{session_id}", headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()
        session_data = response.json()
        current_session_id_state = session_id

        # 构造已上传文件的Markdown字符串
        uploaded_files = session_data.get("files", [])
        uploaded_files_md_str = "#### 已上传文件: \n" + "\n".join([f"- {f}" for f in uploaded_files]) if uploaded_files else "#### 已上传文件: \n- 暂无文件"
        
        return (
            session_id,
            session_data['messages'],
            uploaded_files_md_str,
            gr.update(value=f"当前会话: {session_data['title']}"),
            uploaded_files,
            gr.update(visible=False, choices=[], value=None), # 切换会话时隐藏推荐问题
        )
    except requests.exceptions.RequestException as e:
        print(f"加载会话失败: {e}")
        gr.Warning("加载会话失败，请检查后端服务。")
        return current_session_id_state, [], "#### 已上传文件: \n- 暂无文件", gr.update(value="会话加载失败"), [], gr.update(visible=False, choices=[], value=None)

def handle_file_upload_handler(files: List[Any], session_id: str):
    """通过API上传文件并更新知识库"""
    global access_token
    if not access_token:
        gr.Warning("请先登录！")
        return "请先登录", [], "#### 已上传文件: \n- 暂无文件"
    
    if not session_id:
        gr.Warning("请先创建一个新会话或选择一个会话")
        return "请先创建一个新会话或选择一个会话", [], "#### 已上传文件: \n- 暂无文件"
    
    if not files:
        gr.Info("请选择要上传的文件")
        return "请选择要上传的文件", [], "#### 已上传文件: \n- 暂无文件"

    files_to_upload = []

    try:
        for f in files:
            with open(f.name, 'rb') as file_handle:
                filename = os.path.basename(f.name)
                content_type = get_content_type(filename)
                files_to_upload.append(('files', (filename, file_handle.read(), content_type)))
        
        response = requests.post(
            f"{API_URL}/sessions/{session_id}/files",
            files=files_to_upload,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        
        response_data = response.json()
        gr.Info(f"文件上传成功: {response_data['message']}")

        uploaded_files_md_str = "#### 已上传文件: \n" + "\n".join([f"- {f}" for f in response_data['uploaded_files']])
        return response_data['message'], response_data['uploaded_files'], uploaded_files_md_str
    
    except requests.exceptions.RequestException as e:
        print(f"文件上传失败: {e}")
        gr.Warning(f"文件上传失败: {e}")
        return f"文件上传失败: {e}", [], "#### 已上传文件：\n- 暂无文件"
    except Exception as e:
        print(f"文件上传处理异常: {e}")
        gr.Warning(f"文件上传处理异常: {e}")
        return f"文件上传处理异常: {e}", [], "#### 已上传文件：\n- 暂无文件"

def process_message_handler(message: str, history: List[Dict[str, str]], session_id: str):
    """处理用户消息，返回AI回答。"""
    global access_token
    if not access_token:
        error_msg = "请先登录！"
        yield history + [{"role": "user", "content": message}], error_msg, gr.update(visible=False, choices=[], value=None)
        return
    
    if not session_id:
        error_msg = "请先创建一个新会话或选择一个会话。"
        yield history + [{"role": "user", "content": message}], error_msg, gr.update(visible=False, choices=[], value=None)
        return

    if not message.strip():
        yield history, "", gr.update(visible=False, choices=[], value=None)
        return
    
    # 将用户新消息添加到历史记录中
    history = history + [{"role": "user", "content": message}]
    
    # 在前端即时显示用户消息
    yield history, "", gr.update(visible=False, choices=[], value=None)
    
    try:
        payload = {"message": message, "session_id": session_id}
        response = requests.post(
            f"{API_URL}/sessions/{session_id}/message",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        
        response_data = response.json()
        recommended_questions = response_data.get('recommended_questions', [])
        
        # 将后端返回的字典列表转换为 Gradio 的元组列表
        yield response_data['history'], "", gr.update(visible=True, choices=recommended_questions, value=None)
    
    except requests.exceptions.RequestException as e:
        print(f"消息处理失败: {e}")
        error_msg = "对不起，消息处理失败，请稍后再试。"
        # 在前端历史记录中显示错误
        history.append({"role": "assistant", "content": error_msg})
        gr.Warning(error_msg)
        yield history, "", gr.update(visible=False, choices=[], value=None)
    except (KeyError, IndexError) as e:
        print(f"解析后端响应失败: {e}")
        error_msg = "后端返回了无法解析的响应。"
        history.append({"role": "assistant", "content": error_msg})
        gr.Warning(error_msg)
        yield history, "", gr.update(visible=False, choices=[], value=None)

def select_recommended_question(question: str):
    """当用户点击推荐问题时，将问题填充到输入框"""
    if question:
        return question
    return ""

def clear_chat_handler():
    """清空当前聊天记录和文件状态"""
    gr.Info("已清空聊天记录")
    return [], "#### 已上传文件: \n- 暂无文件", [], gr.update(visible=False, choices=[], value=None)

def post_login_init_user_view():
    """在登陆成功后调用， 用于初始化会话列表和界面"""
    global current_session_id_state, access_token

    today_sessions, yesterday_sessions, older_sessions = get_session_lists()

    # 如果有会话，加载最新的一个
    if today_sessions:
        session_name, session_id = today_sessions[0]
        current_session_id_state = session_id
        try:
            response = requests.get(
                f"{API_URL}/sessions/{session_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            session_data = response.json()
        except requests.exceptions.RequestException:
            session_data = {"messages": [], "title": "加载失败", "files": []}
            gr.Warning(f"加载最新会话失败。")

        uploaded_files = session_data.get("files", [])
        uploaded_files_md_str = "#### 已上传文件: \n" + "\n".join([f"- {f}" for f in uploaded_files]) if uploaded_files else "#### 已上传文件: \n- 暂无文件"

        return (
            gr.update(visible=(current_user_role == 'admin')),
            session_data['messages'],
            uploaded_files_md_str,
            f"当前会话: {session_data['title']}",
            uploaded_files,
            gr.update(choices=[s[0] for s in today_sessions], value=session_name),
            gr.update(choices=[s[0] for s in yesterday_sessions]),
            gr.update(choices=[s[0] for s in older_sessions])
        )
    else:
        # 如果没有对话，显示欢迎信息
        return (
            gr.update(visible=True),
            [{"role": "assistant", "content": "您好，很高兴为您服务！请新建一个会话开始。"}],
            "#### 已上传文件: \n- 暂无文件", 
            "当前会话: 无",
            [],
            gr.update(choices=[]),
            gr.update(choices=[]),
            gr.update(choices=[])
        )

def get_all_users_for_admin():
    """管理员获取所有用户列表，并返回一个 Gradio DataFrame"""
    global access_token
    if not access_token:
        gr.Warning("请先登录！")
        return pd.DataFrame()
    
    try:
        response = requests.get(f"{API_URL}/users", headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()
        users = response.json()
        df = pd.DataFrame(users)
        return df
    except requests.exceptions.RequestException as e:
        gr.Warning(f"获取用户列表失败: {e}")
        return pd.DataFrame()
    
def update_user_role_for_admin(user_id: str, new_role: str):
    """管理员修改用户角色"""
    global access_token
    if not access_token:
        gr.Warning("请先登录！")
        return get_all_users_for_admin()
    
    if new_role not in ["admin", "user"]:
        gr.Warning("角色只能是 'admin' 或 'user'。")
        return get_all_users_for_admin()
    
    try:
        payload = {"user_id": user_id, "role": new_role}
        response = requests.put(f"{API_URL}/users/role", data=payload, headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()
        gr.Info(f"用户 {user_id} 的角色已更新为 {new_role}")
    except requests.exceptions.RequestException as e:
        gr.Warning(f"更新角色失败: {e}")
    
    return get_all_users_for_admin()

def get_all_sessions_for_admin():
    """管理员获取所有用户的所有会话（用后端专用接口）"""
    global access_token
    if not access_token:
        gr.Warning("请先登录！")
        return gr.update(choices=[]), gr.update(choices=[]), {}, gr.update(value="")

    try:
        response = requests.get(f"{API_URL}/admin/sessions", headers={"Authorization": f"Bearer {access_token}"})
        response.raise_for_status()
        sessions = response.json()
        # sessions: [{id, user_id, username, title, created_at}]
        user_sessions = {}
        for s in sessions:
            user_sessions.setdefault(s['username'], []).append((s['title'], s['id']))
        user_choices = list(user_sessions.keys())
        return gr.update(choices=user_choices), gr.update(choices=[]), user_sessions, gr.update(value="请选择会话")
    except Exception as e:
        gr.Warning(f"获取所有会话失败: {e}")
        return gr.update(choices=[]), gr.update(choices=[]), {}, gr.update(value="加载失败")

def filter_sessions_by_user(user_name: str, user_sessions: dict):
    """根据选择的用户名，更新会话下拉菜单"""
    if not user_name or user_name not in user_sessions:
        return gr.update(choices=[], value=None), gr.update(value="请选择会话")
    session_titles = [s[0] for s in user_sessions[user_name]]
    if session_titles:
        # 自动选中第一个会话并自动显示聊天记录
        return gr.update(choices=session_titles, value=session_titles[0]), get_admin_session_history(session_titles[0], user_sessions, user_name)
    else:
        return gr.update(choices=[], value=None), gr.update(value="请选择会话")

def get_admin_session_history(session_title: str, user_sessions: dict, user_name: str):
    """管理员获取特定会话的聊天记录"""
    global access_token
    
    print(f"Debug: session_title={session_title}, user_name={user_name}")
    print(f"Debug: user_sessions keys={list(user_sessions.keys())}")
    
    if not session_title or not user_name or user_name not in user_sessions:
        return gr.update(value="请选择会话")
    
    session_id = None
    for title, sid in user_sessions[user_name]:
        if title == session_title:
            session_id = sid
            break
    
    print(f"Debug: found session_id={session_id}")
    
    if not session_id:
        return gr.update(value="会话ID未找到")
    
    try:
        response = requests.get(
            f"{API_URL}/admin/sessions/{session_id}", 
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        session_data = response.json()
        
        print(f"Debug: session_data messages count={len(session_data.get('messages', []))}")
        
        formatted_history = "### 聊天记录\n\n"
        messages = session_data.get('messages', [])
        
        if not messages:
            formatted_history += "**该会话暂无聊天记录**\n\n"
        else:
            for message in messages:  # 去掉了 i, enumerate
                role = "用户" if message['role'] == 'user' else "助手"
                content = message.get('content', '(无内容)')
                formatted_history += f"**{role}**: {content}\n\n"  # 去掉了 ({i+1})
        
        return gr.update(value=formatted_history)
    except Exception as e:
        error_msg = f"获取聊天记录失败: {str(e)}"
        print(f"Debug: {error_msg}")
        gr.Warning(error_msg)
        return gr.update(value=error_msg)


def create_interface():
    """创建 Gradio 用户界面"""
    with gr.Blocks(
        title="智能课程咨询助手",
        theme= gr.themes.Soft(),
        css="""
        .gradio-container {
            width: 100%;
            height: 95vh;
            padding: 10px;
            box-sizing: border-box;
            display: flex;
        }
        .main-content { 
            width: 98vw; 
            height: 97vh; 
            max-width: 1800px; 
            max-height: 980px; 
            min-width: 900px; 
            min-height: 511px; 
            border-radius: 18px;
            display: flex; 
            flex-direction: row; 
            overflow: hidden;
            background: #121212;
        }
        .login-content { 
            width: 100%; 
            height: 100vh; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            background: #181818;
        }
        .login-box {
            width: 45%;
            max-width: 400px;
            max-height: 85vh;   /* 根据需要调整的最大高度 */
            overflow-y: auto;  /* 如果内容超出最大高度，则启用滚动 */
            padding: 10px; 
            background: #1e1e1e; 
            border-radius: 12px; 
            border: 1px solid #333;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); /* 添加阴影效果提升视觉层次 */
            overflow: hidden; /* 防止内容溢出 */
        }
        @media (max-width: 780px) {
            .login-box {
                width: 90%; /* 在小屏幕设备上占据整个宽度 */
                padding: 8px; /* 减少内边距 */
            }
        }
        .left-panel { 
            width: 25% /* 调整为合适的宽度 */
            display: flex; 
            flex-direction: column; 
            padding: 18px 8px;
            background: #1e1e1e;
        }
        .right-panel { 
            width: 75%
            display: flex; 
            flex-direction: column; 
            height: 100%; 
            padding: 18px 18px 12px 18px;
            background: #181818;
        }
        .header { 
            color: #fff; 
            text-align: center; 
            margin-bottom: 18px; 
            font-size: 1.5em; 
            font-weight: 600; 
            letter-spacing: 1px;
        }
        .session-list { 
            flex: 1; 
            overflow-y: auto; 
            margin-bottom: 18px; 
        }
        .session-list h4 { 
            color: #bbb; 
            font-size: 1em; 
            margin: 14px 0 6px 0; 
            font-weight: 500 
        }
        .radio-group label { 
            display: block; 
            padding: 8px 10px; 
            margin: 4px 0; 
            background: #232323; 
            border: 1px solid #333; 
            border-radius: 8px; 
            color: #eee; 
            cursor: pointer; 
            transition: background 0.2s; 
        }
        .radio-group label:hover, 
        .radio-group input[type="radio"]:checked + label { 
            background: #333; 
            color: #fff; 
        }
        .new-session-btn { 
            width: 100%; 
            padding: 10px; 
            margin-bottom: 12px; 
            background: #232323; 
            border: 1px solid #444; 
            border-radius: 8px; 
            color: #fff; 
            font-size: 1em; 
            font-weight: 500; 
            cursor: pointer; 
            transition: background 0.2s;
        }
        .new-session-btn:hover { background: #333; }
        .chat-container { 
            flex: 1; 
            min-height: 0; 
            background: #181818; 
            border-radius: 12px; 
            border: 1px solid #333; 
            padding: 12px; 
            overflow-y: auto; 
            margin-bottom: 8px; 
            color: #eee; 
            width: 100%;
        }
        .input-row { 
            display: flex; 
            gap: 8px; 
            align-items: center;
        }
        .upload_btn {
            height: 120px;
            font-size: 12px;
        }
        .input-area, .upload-status { 
            width: 100%; 
            background: #232323; 
            border: 1px solid #333; 
            border-radius: 8px; 
            color: #fff; 
            padding: 10px; 
            margin-bottom: 8px; 
            font-size: 1em; 
        }
        .send_btn { 
            width: 100%; 
            height: 44px; 
            background: #333; 
            color: #fff; 
            border: none; 
            border-radius: 8px; 
            font-size: 1.1em; 
            font-weight: 600; 
            cursor: pointer; 
            transition: background 0.2s; 
        }
        .send_btn:hover { background: #444; }
        .status-display { 
            background: #232323; 
            color: #bbb; 
            border-radius: 8px; 
            padding: 8px 0; 
            text-align: center; 
            font-size: 0.9em; 
            margin-top: 6px; 
            border: 1px solid #333; 
        }
        .recommended-questions-container {
            margin-top: 10px;
            margin-bottom: 10px;
        }
        .recommended-questions-container h4 {
            color: #ddd;
            margin-bottom: 5px;
        }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-thumb {
            background: #333;
            border-radius: 4px;
        }
        .dataframe-container, .admin-chat-viewer { 
            height: 75vh; 
            overflow-y: auto; 
        }
        .chat-history-output { 
            height: 80vh; 
            overflow-y: auto; 
            background: #1e1e1e; 
            padding: 10px; 
            border-radius: 8px; 
            border: 1px solid #333; 
        }
        .admin-controls {
            padding: 10px;
            background: #1e1e1e;
            border-radius: 8px;
        }
        """
    ) as interface:
        
        # ===== 登录和注册界面 =====
        with gr.Row(visible=True, elem_classes=["login-content"]) as login_row:
            with gr.Column(elem_classes=["login-box"]):
                gr.Markdown("## 登录 / 注册", elem_classes=["header"])
                login_username_input = gr.Textbox(label="用户名")
                login_password_input = gr.Textbox(label="密码", type="password")
                with gr.Row():
                    login_btn = gr.Button("登录", variant="primary")
                    register_btn = gr.Button("注册")
                
                # 注册时显示额外字段
                with gr.Column(visible=False) as register_form:
                    register_confirm_password = gr.Textbox(label="确认密码", type="password")
                    register_submit_btn = gr.Button("提交注册")
                    register_cancel_btn = gr.Button("取消")
        
        # ===== 主聊天界面 =====
        with gr.Row(scale=8, elem_classes=["main-content"], visible=False) as main_row:
            current_session_id_state_gr = gr.State(current_session_id_state)
            uploaded_files_state_gr = gr.State([])
            
            with gr.Column(elem_classes=["left-panel"]):
                gr.Markdown("智能课程咨询助手", elem_classes=["header"])
                new_session_btn = gr.Button("新建会话", variant="primary", elem_classes=["new-session-btn"])

                with gr.Column(scale=1, elem_classes=["session-list"]):
                    today_sessions, yesterday_sessions, older_sessions = get_session_lists()
                    today_radio = gr.Radio(
                        choices=[s[0] for s in today_sessions],
                        label="今天",
                        show_label=True,
                        elem_classes=["radio-group"]
                    )
                    yesterday_radio = gr.Radio(
                        choices=[s[0] for s in yesterday_sessions],
                        label="昨天",
                        show_label=True,
                        elem_classes=['radio-group']
                    )
                    older_radio = gr.Radio(
                        choices=[s[0] for s in older_sessions],
                        label="更早",
                        show_label=True,
                        elem_classes=['radio-group']
                    )

                uploaded_files_md = gr.Markdown(
                    "#### 已上传文件: \n- 暂无文件",
                    elem_classes="status-display"
                )

                upload_status = gr.Textbox(
                    label="上传状态",
                    interactive=False,
                    visible=True,
                    elem_classes=["upload-status"]
                )
                session_status = gr.Textbox(
                    label="当前会话",
                    interactive=False,
                    elem_classes=["status-display"]
                )
            
            with gr.Column(scale=7, elem_classes=["right-panel"]):
                chatbot_ui = gr.Chatbot(
                    value=[{'role': "assistant", "content": "您好！请先登录或注册。"}],
                    elem_classes=["chat-container"],
                    show_label=False,
                    type='messages',
                    scale=7
                )

                recommended_questions_ui = gr.Radio(
                    label="推荐问题",
                    choices=[],
                    visible=False,
                    elem_classes="recommended-questions-container"
                )

                with gr.Row(elem_classes=["input-row"]):
                    upload_btn = gr.File(
                        file_types=ALLOWED_FILE_TYPES,
                        label="",
                        file_count="multiple",
                        scale=1,
                        elem_classes=["upload_btn"]
                    )
                    msg_input = gr.Textbox(
                        placeholder=f"上传的文件不超过{MAX_FILE_SIZE_MB}M，支持格式：'pdf', 'docx', 'txt', 'ipynb'。输入你的消息...",
                        show_label=False,
                        lines=2,
                        elem_classes=["input-area"],
                        scale=5
                    )
                    with gr.Row():
                        send_btn = gr.Button(
                            "发送",
                            variant="primary",
                            elem_classes=["send_btn"],
                            scale=1
                        )
                        clear_btn = gr.Button(
                            "清空聊天",
                            variant="secondary",
                            scale=1
                        )
        # ===== 管理员面板界面 =====
        with gr.Row(visible=False, elem_classes=["admin-main-content"]) as admin_row:
            gr.Markdown("## 管理员面板", elem_classes=["header"])
            with gr.Column(scale=4, min_width=320):
                with gr.Tab("用户管理"):
                    with gr.Row(elem_classes=["admin-controls"]):
                        user_id_input = gr.Textbox(label="输入用户ID")
                        role_input = gr.Dropdown(label="选择新角色", choices=["user", "admin"])
                        update_role_btn = gr.Button("更新用户角色", variant="primary")
                        refresh_users_btn = gr.Button("刷新用户列表")
                    gr.Markdown('### 用户列表', elem_classes=["header"])
                    users_df = gr.DataFrame(
                        headers=["id", "username", "role"],
                        interactive=True,
                        elem_classes=["dataframe-container"]
                    )
                with gr.Tab("聊天记录管理"):
                    gr.Markdown("### 聊天记录浏览", elem_classes=["header"])
                    all_sessions_dict_state = gr.State({})
                    refresh_sessions_btn = gr.Button("刷新会话列表")  # 只定义一次
                    user_dropdown = gr.Dropdown(label="选择用户", choices=[])
                    session_dropdown = gr.Dropdown(label="选择会话", choices=[])
                    view_chat_btn = gr.Button("查看选定会话聊天记录", variant="primary")
            with gr.Column(scale=6, min_width=480):
                chat_history_viewer = gr.Markdown("#### 聊天记录将在此显示", elem_classes=["chat-history-output"])
        
        # ----------------- 登录/注册逻辑 -----------------
        login_btn.click(
            login_handler,
            inputs=[login_username_input, login_password_input],
            outputs=[login_row, main_row, admin_row]
        ).then(
            lambda: post_login_init_user_view() if current_user_role != 'admin' else (
                gr.update(visible=False), [], "", "", [], gr.update(choices=[]), gr.update(choices=[]), gr.update(choices=[])
            ),
            inputs=None,
            outputs=[main_row, chatbot_ui, uploaded_files_md, session_status, uploaded_files_state_gr, today_radio, yesterday_radio, older_radio]
        ).then(
            lambda: get_all_users_for_admin() if current_user_role == 'admin' else pd.DataFrame(),
            inputs=None,
            outputs=[users_df]
        ).then(
            lambda: get_all_sessions_for_admin() if current_user_role == 'admin' else (gr.update(choices=[]), gr.update(choices=[]), {}, gr.update(value="")),
            inputs=None,
            outputs=[user_dropdown, session_dropdown, all_sessions_dict_state, chat_history_viewer]
        )

        register_btn.click(
            lambda: gr.update(visible=True), 
            outputs=[register_form]
        )
        
        register_submit_btn.click(
            register_handler,
            inputs=[login_username_input, login_password_input, register_confirm_password],
            outputs=[register_form]
        )
        
        register_cancel_btn.click(
            lambda: gr.update(visible=False),
            outputs=[register_form]
        )

        # ----------------- 主页面事件绑定 -----------------
        new_session_btn.click(
            create_new_session_handler,
            inputs=[],
            outputs=[
                current_session_id_state_gr,
                chatbot_ui,
                uploaded_files_md,
                session_status,
                uploaded_files_state_gr,
                today_radio,
                yesterday_radio,
                older_radio,
                recommended_questions_ui,
            ]
        )
        
        upload_btn.upload(
            handle_file_upload_handler,
            inputs=[upload_btn, current_session_id_state_gr],
            outputs=[upload_status, uploaded_files_state_gr, uploaded_files_md]
        )

        send_btn.click(
            process_message_handler,
            inputs=[msg_input, chatbot_ui, current_session_id_state_gr],
            outputs=[chatbot_ui, msg_input, recommended_questions_ui]
        )
        
        recommended_questions_ui.change(
            select_recommended_question,
            inputs=[recommended_questions_ui],
            outputs=[msg_input]
        )

        for radio in [today_radio, yesterday_radio, older_radio]:
            radio.change(
                select_session_handler,
                inputs=[radio],
                outputs=[current_session_id_state_gr, chatbot_ui, uploaded_files_md, session_status, uploaded_files_state_gr, recommended_questions_ui]
            )
        
        clear_btn.click(
            clear_chat_handler,
            outputs=[chatbot_ui, uploaded_files_md, uploaded_files_state_gr, recommended_questions_ui]
        )

        # ===== 管理员界面事件绑定 =====
        # 管理员面板事件绑定
        refresh_users_btn.click(
            get_all_users_for_admin,
            inputs=None,
            outputs=[users_df]
        )

        update_role_btn.click(
            update_user_role_for_admin,
            inputs=[user_id_input, role_input],
            outputs=[users_df]
        )

        # 聊天记录管理 - 修复后的事件绑定
        refresh_sessions_btn.click(
            get_all_sessions_for_admin,
            inputs=None,
            outputs=[user_dropdown, session_dropdown, all_sessions_dict_state, chat_history_viewer]
        )

        user_dropdown.change(
            filter_sessions_by_user,
            inputs=[user_dropdown, all_sessions_dict_state],
            outputs=[session_dropdown, chat_history_viewer]
        )

        session_dropdown.change(
            get_admin_session_history,
            inputs=[session_dropdown, all_sessions_dict_state, user_dropdown],
            outputs=[chat_history_viewer]
        )

        view_chat_btn.click(
            get_admin_session_history,
            inputs=[session_dropdown, all_sessions_dict_state, user_dropdown],
            outputs=[chat_history_viewer]
        )

    return interface

if __name__ == "__main__":
    app = create_interface()
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False
    )