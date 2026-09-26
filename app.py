# app.py - 小奕的网页版启动文件 
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import main  # 导入你原来的 main.py 文件

app = Flask(__name__)
CORS(app)

# 从 main.py 中获取所有核心功能
xiaoyi_core = main.create_xiaoyi()
client = xiaoyi_core["client"]
messages = xiaoyi_core["messages"]
turn_count = xiaoyi_core["turn_count"]
load_knowledge = xiaoyi_core["load_knowledge"]
web_search = xiaoyi_core["web_search"]
export_chat_history = xiaoyi_core["export_chat_history"]
clean_text = xiaoyi_core["clean_text"]

@app.route("/")
def index():
    """主页：渲染网页"""
    return render_template("index.html")

import json
from flask import Response, stream_with_context

@app.route("/get_response", methods=["POST"])
def get_response():
    """API接口：流式返回AI回复"""
    global turn_count, messages
    user_input = request.json.get("message", "").strip()

    if not user_input:
        return Response(
            f"data: {json.dumps({'content': '请输入内容哦！', 'done': True})}\n\n",
            mimetype="text/event-stream"
        )

    # 处理特殊指令
    if user_input.lower() in ("/exit", "退出"):
        return Response(
            f"data: {json.dumps({'content': '网页版不支持退出指令，请刷新页面即可开始新对话。', 'done': True})}\n\n",
            mimetype="text/event-stream"
        )
    elif user_input.lower() == "/clear":
        messages = [messages[0]]
        turn_count = 0
        return Response(
            f"data: {json.dumps({'content': '【系统】历史已清空，我们可以重新开始聊啦！', 'done': True})}\n\n",
            mimetype="text/event-stream"
        )
    elif user_input.lower() == "/count":
        return Response(
            f"data: {json.dumps({'content': f'[当前对话轮数：{turn_count}]', 'done': True})}\n\n",
            mimetype="text/event-stream"
        )

    # 处理搜索和知识库指令
    if user_input.startswith("/search "):
        search_query = user_input.replace("/search ", "")
        search_result = web_search(search_query)
        user_input = f"请根据以下联网搜索结果回答问题：\n搜索结果：{search_result}\n用户问题：{search_query}"
    elif user_input.startswith("/kb "):
        kb_query = user_input.replace("/kb ", "")
        kb_content = load_knowledge()
        if kb_content:
            user_input = f"请根据以下知识库内容回答问题：\n知识库内容：{kb_content}\n用户问题：{kb_query}"
        else:
            return Response(
                f"data: {json.dumps({'content': '小奕：知识库文件夹为空或未找到哦。', 'done': True})}\n\n",
                mimetype="text/event-stream"
            )

    # 加入用户消息
    messages.append({"role": "user", "content": user_input})

    def generate():
        global turn_count, messages
        try:
            stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.7,
                stream=True
            )
            ai_reply = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    ai_reply += delta.content
                    yield f"data: {json.dumps({'content': delta.content, 'done': False})}\n\n"

            # 回答完毕，保存并发送结束标记
            ai_reply = clean_text(ai_reply.strip())
            messages.append({"role": "assistant", "content": ai_reply})
            turn_count += 1
            yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'content': f'调用失败：{str(e)}', 'done': True})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

if __name__ == "__main__":
    print("=== 小奕网页版已启动！请在浏览器访问 http://127.0.0.1:5000 ===")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
