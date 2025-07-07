# llama3.1:8b-instruct-q4_K_M
# https://ollama.com/library/llama3.1:8b-instruct-q4_K_M
# context window: 128K
#   128K ≈ 98,000 english words OR 130,000 chinese characters
#   embedding length: default 4096
# model size: 4.9GB

# Ollama使用说明：
# 1、下载客户端，运行
# 2、在Powershell中：
#   ollama --version 查看安装是否成功
#   ollama run llama3.1:8b-instruct-q4_K_M 安装
#   安装完成后可以直接在命令行中聊天
# 3、在程序中，使用API（11434端口）即可进行交互

import requests
import json

# Ollama API的地址和模型名称
OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.1:8b-instruct-q4_K_M" # 确保这个模型已经在Ollama中下载好了

# 对话历史记录，这是实现多轮对话的关键
# 我们会把每一次的用户提问和AI回答都存进去
conversation_history = []

def initialize_npc():
    """
    初始化NPC的角色设定，作为对话的开端。
    """
    system_prompt = {
        "role": "system",
        "content": "You are a helpful and friendly NPC in a fantasy village named Oakenshield. You are a blacksmith, wise and kind, always willing to chat with travelers. Keep your responses relatively short and in character."
    }
    conversation_history.append(system_prompt)
    print("NPC: (A warm smile) Welcome to Oakenshield, traveler. I'm the village blacksmith. What can I help you with today?\n")

def chat_with_npc(user_input: str):
    """
    发送用户输入并获取NPC的回复。
    """
    # 将用户的最新输入添加到对话历史中
    user_message = {
        "role": "user",
        "content": user_input
    }
    conversation_history.append(user_message)

    # 构建发送给Ollama API的数据体
    payload = {
        "model": MODEL_NAME,
        "messages": conversation_history,
        "stream": False # 我们希望一次性收到完整回复
    }

    try:
        # 发送POST请求
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status() # 如果请求失败 (例如404, 500), 会抛出异常

        # 解析返回的JSON数据
        response_data = response.json()
        
        # 提取NPC的回复内容
        npc_reply_content = response_data['message']['content']

        # 将NPC的回复也添加到对话历史中，以便它记住自己说过什么
        npc_message = {
            "role": "assistant",
            "content": npc_reply_content
        }
        conversation_history.append(npc_message)

        return npc_reply_content

    except requests.exceptions.RequestException as e:
        return f"Error connecting to Ollama: {e}"
    except KeyError:
        return "Error: Unexpected response format from Ollama."

def main():
    """
    主函数，运行聊天循环。
    """
    initialize_npc()
    
    while True:
        # 获取用户输入
        user_input = input("You: ")
        print()

        # 检查退出命令
        if user_input.lower() in ["quit", "exit", "/bye"]:
            print("NPC: (Nods) Safe travels, friend.")
            break
            
        # 获取并打印NPC的回复
        npc_response = chat_with_npc(user_input)
        print(f"NPC: {npc_response}\n")


if __name__ == "__main__":
    main()