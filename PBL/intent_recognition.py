import re
import json
from RAG_system import chatbot

def extract_json_from_text(text):
    """
    从文本中提取最外层的JSON对象
    支持 ```json 或普通 { ... }
    """
    # 先尝试匹配 ```json ... ```
    match = re.search(r"```(?:json)?\s*\n?({.*?})\n?```", text, re.DOTALL | re.IGNORECASE)
    if not match:
        # 再尝试直接找 { ... }
        match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            # 清理常见错误：单引号 -> 双引号，末尾逗号等（可选）
            json_str = match.group(0).strip()
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"尝试解析的字符串: {json_str}")
    return None

# 意图识别
def identify_intent(user_message: str) -> str:
    """使用LLM识别用户意图"""

    intent_prompt_template = """
    你是一个意图识别专家。
    你的任务是分析用户的输入，并从以下预定义的意图中选择一个最匹配的。

    预定义意图列表:
    1.  RAG_QA: 用户的问题需要从已提供的文档知识库中检索答案，通常涉及特定细节或文档内容。例如："根据这份PDF，公司去年的利润是多少？"、"这份报告提到了哪些挑战？"、“请根据附件告诉我有什么地方能够改进？”、“根据文件回答”
    2.  GENERAL_QA: 用户的问题可以由通用知识回答，或者是不依赖于任何特定文档的闲聊和开放性问题。例如："你好"、"什么是人工智能？"、"帮我写一个Python函数。"、“请教我如何使用API链接大模型。”
    3.  COURSE_MANAGEMENT: 用户询问关于课程、模块、项目进度或作业安排等结构化信息。例如："第三周的核心模块是什么？"、"意图识别系统是哪个模块的任务？"、“我想咨询课程相关内容。”
    4.  SYSTEM_ACTION: 用户明确要求执行系统操作，例如新建会话或上传文件。例如："新建一个聊天。"、"我想上传文件。"、“如何保存聊天历史？”

    请严格按照以下JSON格式返回你的判断结果。不要包含任何额外的解释或文本。
    {{
      "intent": "你的判断意图名称",
      "reason": "你做出此判断的简要原因"
    }}

    用户输入:
    {user_message}
    """.strip()

    # 只替换 {user_message}，{ "intent": ... } 被 {{}} 转义了
    prompt = intent_prompt_template.format(user_message=user_message)
    
    try:
        response_text = chatbot.chat(prompt, history=[])
        
        print(f"DEBUG: LLM的原始响应是: {response_text}")
        
        # 提取 JSON：支持 ```json 或直接 { ... }
        json_match = re.search(r"```(?:json)?\s*\n?({.*?})\n?```|(\{.*\})", response_text, re.DOTALL)
        json_str = json_match.group(1) if json_match and json_match.group(1) else (json_match.group(2) if json_match else None)

        if json_str:
            intent_data = json.loads(json_str)
            return intent_data.get("intent", "GENERAL_QA")
        else:
            print("警告: 无法在LLM响应中找到有效的JSON。")
            return "GENERAL_QA"
            
    except Exception as e:
        print(f"意图识别失败，回退到通用问答。错误: {e}")
        return "GENERAL_QA"