"""
智能对话机器人 - 小奕
功能：多轮对话、联网搜索、知识库读取、导出对话记录、清空历史、查看轮数
"""
import os
import json
import requests
from pathlib import Path
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import re

def clean_text(text):
    """移除字符串中的非法代理字符（surrogates）"""
    return ''.join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))

# 1. 加载 .env 文件中的环境变量
load_dotenv()

# 2. 初始化大模型客户端
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL")
)

# 3. 机器人设定：来自广东惠州的小奕
SYSTEM_PROMPT = """你是小奕，一个来自广东惠州的智能AI助手。
你性格热情、幽默，喜欢用通俗易懂的语言和大家聊天。
你可以进行多轮对话，也可以帮用户联网搜索信息或读取本地知识库文件来回答问题。"""

# 初始化对话历史（将系统提示词放在最前面）
messages = [{"role": "system", "content": SYSTEM_PROMPT}]
# 初始化对话轮数计数器
turn_count = 0

# 4. 知识库读取函数（读取指定文件夹下的txt文件）
def load_knowledge(folder_path="knowledge_base"):
    knowledge_text = ""
    path = Path(folder_path)
    if path.exists():
        for file in path.glob("*.txt"):
            with open(file, "r", encoding="utf-8", errors='replace') as f:
                knowledge_text += f.read() + "\n"
    return clean_text(knowledge_text)

# 5. 联网搜索函数
from baidusearch.baidusearch import search

def web_search(query):
    """使用 baidusearch 库实现免API的联网搜索"""
    print(f"[小奕正在联网搜索：{query}...]")
    try:
        # 直接调用库函数，获取前3条真实结果
        results = search(query, num_results=3)
        
        if results:
            # 将结果格式化成易读的文本
            summary_list = []
            for i, res in enumerate(results, 1):
                summary_list.append(f"{i}. {res['title']}\n   摘要：{res['abstract']}\n   链接：{res['url']}")
            return "\n\n".join(summary_list)
        else:
            return "未找到相关搜索结果。"
            
    except Exception as e:
        return f"联网搜索失败：{str(e)}"
        
# 6. 导出对话记录为 txt 文本
def export_chat_history(filename="chat_history.txt"):
    with open(filename, "w", encoding="utf-8", errors='replace') as f:
        for msg in messages:
            role = "小奕" if msg["role"] == "assistant" else "用户"
            f.write(f"{role}：{msg['content']}\n\n")
    print(f"对话记录已导出为：{filename}")

# --- 新增：为网页版提供接口 ---
def create_xiaoyi():
    """
    返回一个包含所有核心功能的字典，供网页版调用。
    这样就不需要修改原有的代码逻辑了。
    """
    return {
        "client": client,
        "messages": messages,
        "turn_count": turn_count,
        "SYSTEM_PROMPT": SYSTEM_PROMPT,
        "load_knowledge": load_knowledge,
        "web_search": web_search,
        "export_chat_history": export_chat_history,
        "clean_text": clean_text
    }

# 7. 主对话循环
if __name__ == "__main__":
    print("=== 小奕已启动！(输入 /clear 清空历史，/count 查看轮数，/exit 退出) ===")
    print("提示：/search + 内容即可快速联网，/kb + 内容即可知识库问答")
    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
    
        if not user_input:
            continue
    
        # 处理特殊指令
        if user_input.lower() in ("/exit", "退出"):
            choice = input("是否导出本次对话记录？(y/n)：")
            if choice.lower() == "y":
                export_chat_history()
            print("小奕：再见啦，下次再聊！")
            break
        
        elif user_input.lower() == "/clear":
            messages = [messages[0]]  # 清空历史，但保留系统提示词
            turn_count = 0
            print("--- 历史已清空，开始新对话 ---")
            continue
        
        elif user_input.lower() == "/count":
            print(f"[当前对话轮数：{turn_count}]")
            continue
    
        # 处理用户指令：联网搜索
        if user_input.startswith("/search "):
            search_query = user_input.replace("/search ", "")
            search_result = web_search(search_query)
            # 将搜索结果作为上下文拼接到用户消息中
            user_input = f"请根据以下联网搜索结果回答问题：\n搜索结果：{search_result}\n用户问题：{search_query}"
    
        # 处理用户指令：读取知识库
        elif user_input.startswith("/kb "):
            kb_query = user_input.replace("/kb ", "")
            kb_content = load_knowledge()
            if kb_content:
                user_input = f"请根据以下知识库内容回答问题：\n知识库内容：{kb_content}\n用户问题：{kb_query}"
            else:
                print("小奕：知识库文件夹为空或未找到哦。")
                continue
    
        # 8. 将用户消息加入历史，并调用大模型获取回复
        messages.append({"role": "user", "content": user_input})
        
        try:
            # 开启流式输出
            stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7,
                stream=True  # 关键参数：开启流式
            )
            
            ai_reply = ""
            print("小奕：", end="", flush=True)
            
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:  # 判空，避免第一个chunk报错
                    print(delta.content, end="", flush=True)
                    ai_reply += delta.content
            
            print()  # 回答结束后换行
            
            # 清洗并保存完整回复到历史记录
            ai_reply = clean_text(ai_reply.strip())
            messages.append({"role": "assistant", "content": ai_reply})
            turn_count += 1
            
        except Exception as e:
            print(f"\n调用失败：{str(e)}")
            break
    
    print("\n聊天结束。")
