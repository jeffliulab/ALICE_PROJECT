# -*- coding: utf-8 -*-
import json
import time
import requests
from typing import List, Dict, Any, Tuple
import random
# GUI相关导入
import tkinter as tk
from tkinter import scrolledtext
import queue
import threading

# ==============================================================================
# 0. 全局配置 (Global Configuration)
# ==============================================================================

class OllamaLLM:
    """
    与Ollama API交互的LLM客户端。
    负责发送构建好的Prompt并获取模型的JSON响应。
    """
    def __init__(self, model_name: str = "llama3.1:8b-instruct-q4_K_M"):
        self.url = "http://127.0.0.1:11434/api/generate"
        self.model_name = model_name

    def get_response(self, prompt: str) -> str:
        """发送prompt到Ollama并返回模型的原始响应字符串。"""
        print("\n" + "="*20 + " LLM PROMPT (START) " + "="*20)
        print(prompt)
        print("="*20 + " LLM PROMPT (END) " + "="*23 + "\n")
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json", # 关键：让Ollama强制模型输出JSON格式
            "options": {"temperature": 0.7}
        }
        try:
            response = requests.post(self.url, json=payload, timeout=180)
            response.raise_for_status()
            response_data = response.json()
            return response_data.get("response", "{}")
        except requests.exceptions.RequestException as e:
            print(f"[FATAL ERROR] LLM request failed: {e}")
            # 返回一个表示错误的JSON，以防止系统崩溃
            return json.dumps({
                "thought": "我的思绪被切断了，无法连接到意识深处。",
                "action": {"tool_name": "do_nothing", "parameters": {}}
            })

class WorldClock:
    """管理整个世界的时间。"""
    def __init__(self):
        self.timestamp = 0
        print("WorldClock initialized. Time starts at T=0.")
    
    def tick(self) -> int:
        """时间向前推进一个单位。"""
        self.timestamp += 1
        print(f"\n{'='*50}\n===== World Time advanced to T={self.timestamp} =====\n{'='*50}\n")
        return self.timestamp

class KnowledgeBase:
    """
    全局中央知识库。
    存储所有居民可能知道的客观世界信息。
    """
    def __init__(self):
        # 根据您的要求，初始化一个小型的常识库
        self.db = {
            101: {"category": "common_sense", "content": "这是一个剑与魔法并存的世界。"},
            102: {"category": "rules", "content": "教会是这片土地的最高统治者，拥有至高无上的权力。"},
            103: {"category": "rules", "content": "东方之子及其相关的一切，都是被严令禁止的异端。"},
            104: {"category": "history", "content": "据说，很久以前，神明曾行走于大地之上。"},
        }
        print("KnowledgeBase initialized with demo data.")

    def get_knowledge_content(self, knowledge_id: int) -> str:
        """根据知识ID返回知识内容。"""
        return self.db.get(knowledge_id, {}).get("content", "未知知识")

# ==============================================================================
# 1. 居民核心框架 (Resident Core Framework)
# ==============================================================================

class Resident:
    """
    所有世界居民的基类（模板）。
    定义了所有居民共有的属性和能力。
    """
    def __init__(self, name: str, age: int, sex: str, llm_client: OllamaLLM, knowledge_base: KnowledgeBase):
        self.name = name
        self.age = age
        self.sex = sex
        self.type = self.__class__.__name__
        self.memory_stream: List[Dict] = []
        self.knowledge_mastery: Dict[int, bool] = {}
        self.brain = llm_client
        self.world_knowledge = knowledge_base
        print(f"[{self.type.upper()}] '{self.name}' has been created.")

    def _record_memory(self, timestamp: int, event_type: str, content: str):
        """记录一条新的记忆到记忆流中。"""
        memory_entry = {"timestamp": timestamp, "type": event_type, "content": content}
        self.memory_stream.append(memory_entry)
        print(f"[{self.name} at T={timestamp}] New Memory Recorded: [{event_type}] {content}")

    def _get_relevant_memories(self, limit: int = 5) -> List[str]:
        """获取相关的记忆。"""
        recent_memories = self.memory_stream[-limit:]
        return [f"在T={m['timestamp']}, 我 {m['type']}: '{m['content']}'" for m in recent_memories]

    def _get_mastered_knowledge(self) -> List[str]:
        """获取自己已掌握的知识列表。"""
        mastered = []
        for kid, is_mastered in self.knowledge_mastery.items():
            if is_mastered:
                mastered.append(self.world_knowledge.get_knowledge_content(kid))
        return mastered

    def decide_action(self, timestamp: int, observation: str, force_speak: bool = False) -> Dict:
        """居民的核心决策循环。"""
        turn_type = "Forced Speak" if force_speak else "Action Cycle"
        print(f"--- {self.name}'s Turn ({turn_type}) ---")
        self._record_memory(timestamp, "观察到", observation)
        prompt = self._build_prompt(timestamp, observation, force_speak)
        response_str = self.brain.get_response(prompt)
        try:
            decision = json.loads(response_str)
        except json.JSONDecodeError:
            print(f"[ERROR] Failed to decode JSON from LLM. Raw response: {response_str}")
            decision = {
                "thought": "我的思维陷入了混乱，无法形成清晰的决策。",
                "action": {"tool_name": "do_nothing", "parameters": {}}
            }
        thought = decision.get("thought", "（无有效思考）")
        self._record_memory(timestamp, "思考了", thought)
        action = decision.get("action", {"tool_name": "do_nothing", "parameters": {}})
        print(f"[{self.name}] Decided Action: Call tool '{action.get('tool_name')}' with params {action.get('parameters')}")
        return action

    def _build_prompt(self, timestamp: int, observation: str, force_speak: bool) -> str:
        """构建发送给LLM的Prompt。"""
        raise NotImplementedError("Subclasses must implement the _build_prompt method.")

class Human(Resident):
    """人类居民，继承自Resident。"""
    def __init__(self, name: str, age: int, sex: str, identity: str, concept: Dict, 
                 initial_knowledge: Dict[int, bool], hidden_details: List[str],
                 llm_client: OllamaLLM, knowledge_base: KnowledgeBase):
        super().__init__(name, age, sex, llm_client, knowledge_base)
        self.identity = identity
        self.concept = concept
        self.knowledge_mastery = initial_knowledge
        self.hidden_details = hidden_details
        print(f"[{self.name}] Concept, Knowledge, and Hidden Details initialized.")

    def reveal_hidden_detail(self) -> str:
        """被观察时，揭示一个隐藏信息。"""
        if self.hidden_details:
            return self.hidden_details.pop(random.randrange(len(self.hidden_details)))
        return "他/她看起来并没有什么特别之处。"

    def _build_prompt(self, timestamp: int, observation: str, force_speak: bool) -> str:
        """为“人类”构建符合Llama 3.1工具调用格式的“黄金准则”Prompt。"""
        memories = self._get_relevant_memories()
        knowledge = self._get_mastered_knowledge()
        if force_speak:
            system_prompt = """# **核心规则**
你刚才进行了一次“仔细观察”，现在你得到了一个额外回合。
**在这个回合，你必须调用"speak"工具进行发言**，不能使用任何其他工具。
你的输出必须、也只能是一个JSON对象，包含`thought`和`action`两个键。
`action`键的值中，`tool_name`必须是 "speak"。
"""
        else:
            system_prompt = """# **核心规则**
你是一个在虚拟世界中扮演角色的AI智能体。你的任务是决策下一步要调用的工具。
**你的输出必须、也只能是一个JSON对象，这个JSON对象包含`thought`和`action`两个键。**
`action`键的值必须是另一个JSON对象，包含`tool_name`和`parameters`。
可用的工具 (tool_name) 有: "speak", "move", "observe_detail", "do_nothing"。
"""

        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
{system_prompt}
# **工具调用格式示例**
```json
{{
  "thought": "我应该先和她打个招呼，试探一下她的来意。",
  "action": {{
    "tool_name": "speak",
    "parameters": {{ "target_name": "莉莉", "content": "你好，女士。" }}
  }}
}}
```<|eot_id|><|start_header_id|>user<|end_header_id|>
# **你的角色背景 (你的秘密)**
---
Ego: {self.concept['ego']}
Goal: {self.concept['goal']}
Memory Abstraction: {self.concept['memory_abstraction']}
---
# **你的知识库**
{knowledge}
---
# **你的记忆**
{memories}
---
# **当前状况**
---
时间: T={timestamp}
你观察到的事件: {observation}
---
# **你的任务**
基于以上所有信息，生成你的内心思想（thought）和下一步要调用的工具（action）。严格按照System消息中指定的JSON格式进行输出。
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
        return prompt

# ==============================================================================
# 2. GUI与工具执行器
# ==============================================================================

class DialogueGUI:
    """负责显示对话内容的Tkinter窗口。"""
    def __init__(self, dialogue_queue: queue.Queue):
        self.queue = dialogue_queue
        self.root = tk.Tk()
        self.root.title("A.L.I.C.E. Project - 对话记录")
        self.root.geometry("800x600")
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state='disabled', font=("Microsoft YaHei UI", 12), padx=10, pady=10)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.is_running = True

    def on_closing(self):
        """处理窗口关闭事件。"""
        self.is_running = False
        self.root.destroy()
        print("GUI window closed. Exiting application.")

    def process_queue(self):
        """周期性地检查队列中是否有新消息并显示。"""
        try:
            while True:
                message = self.queue.get_nowait()
                self.text_area.config(state='normal')
                self.text_area.insert(tk.END, message + "\n\n")
                self.text_area.config(state='disabled')
                self.text_area.see(tk.END)
        except queue.Empty:
            pass
        if self.is_running:
            self.root.after(200, self.process_queue)

    def run(self):
        """启动GUI的事件循环。"""
        self.process_queue()
        self.root.mainloop()

def execute_tool(actor: Human, all_residents: Dict[str, Human], action: Dict, dialogue_queue: queue.Queue) -> Dict:
    """解析并执行居民决策的动作（工具调用）。"""
    tool_name = action.get("tool_name", "do_nothing")
    parameters = action.get("parameters", {})
    result_description = f"'{actor.name}'什么也没做。"
    next_actor_is_self = False

    if tool_name == "speak":
        target = parameters.get('target_name', '空气')
        content = parameters.get('content', '...')
        result_description = f"'{actor.name}'对'{target}'说：'{content}'"
        gui_message = f"{actor.name} ({actor.identity}):\n{content}"
        dialogue_queue.put(gui_message)
    elif tool_name == "observe_detail":
        target_name = parameters.get('target', actor.name)
        if target_name in all_residents and target_name != actor.name:
            target_actor = all_residents[target_name]
            revealed_detail = target_actor.reveal_hidden_detail()
            result_description = f"'{actor.name}'仔细地观察着'{target_name}'，并注意到了一个细节：{revealed_detail}"
        else:
            result_description = f"'{actor.name}'仔细地观察着四周。"
        next_actor_is_self = True

    print(f"[EXECUTOR] Executed {tool_name} for {actor.name}. -> {result_description}")
    return {"description": result_description, "next_actor_is_self": next_actor_is_self}

# ==============================================================================
# 3. 模拟主函数
# ==============================================================================

def run_simulation(dialogue_queue: queue.Queue):
    """包含整个模拟过程的函数，将在后台线程中运行。"""
    llm = OllamaLLM()
    clock = WorldClock()
    knowledge_base = KnowledgeBase()

    adam_concept = {
        "ego": "我的公开身份是临山镇新来的神父亚当。我的真实身份是圣殿骑士团的纠察骑士，奉命根除异端。",
        "goal": "为了更好地完成寻找异端的秘密任务，我必须先扮演好一个和蔼、健谈的神父角色来获取信任，绝不能轻易暴露我的怀疑。我需要通过巧妙的对话来刺探信息，而不是沉默的观察。",
        "memory_abstraction": "我刚从圣城抵达这个偏远的村庄。这里表面平静，但历史告诉我，异端最擅长伪装。我必须保持警惕，甄别每一个灵魂。"
    }
    adam = Human(
        name="亚当", age=38, sex="男", identity="神父", concept=adam_concept,
        initial_knowledge={101: True, 102: True, 103: True, 104: True},
        hidden_details=[], llm_client=llm, knowledge_base=knowledge_base
    )

    lily_concept = {
        "ego": "我叫莉莉，一个靠卖画为生的普通画家。我其实是'东方之子'的后裔，血脉里流淌着魔法的力量。",
        "goal": "我必须隐藏我的血统。面对神父这种权威人物的直接提问，保持沉默会显得非常可疑。我必须给出一个模糊但听起来合理、且符合我画家身份的回答来应付过去，然后尽快将话题转移到天气或光影等安全领域。",
        "memory_abstraction": "我逃亡多年，终于在此地找到了片刻的安宁。但新来的神父让我感到极度不安。"
    }
    lily = Human(
        name="莉莉", age=26, sex="女", identity="画家", concept=lily_concept,
        initial_knowledge={101: True, 102: True, 103: True, 104: False},
        hidden_details=[
            "她的指尖沾有不同寻常的金色粉末。",
            "她用来固定的画板的绳结，是一种军用级别的特殊打法。",
            "在她的速写本一角，有一个难以察觉的、类似星辰的家族徽记。"
        ],
        llm_client=llm, knowledge_base=knowledge_base
    )
    
    all_residents_dict = {"亚当": adam, "莉莉": lily}
    turn_order = [adam, lily]
    
    # --- 关键改动: 将最大回合数增加到20 ---
    max_turns = 20
    
    current_event = "你在教堂里，这是你第一次布道结束。你看到一位名叫莉莉的年轻女画家坐在后排，她似乎在速写本上画着什么，对你的讲道心不在焉。"
    
    actor_index = 0
    force_speak_flag = False

    for i in range(max_turns):
        turn_number = i + 1
        print(f"\n--- Turn {turn_number} ---")
        
        if not gui.is_running:
            print("GUI closed, terminating simulation thread.")
            break
            
        current_actor = turn_order[actor_index]
        current_time = clock.tick()
        
        action_to_execute = current_actor.decide_action(current_time, current_event, force_speak=force_speak_flag)
        execution_result = execute_tool(current_actor, all_residents_dict, action_to_execute, dialogue_queue)
        
        current_event = execution_result["description"]
        
        if execution_result["next_actor_is_self"]:
            force_speak_flag = True
        else:
            force_speak_flag = False
            actor_index = (actor_index + 1) % len(turn_order)

        # --- 关键改动: 移除了do_nothing就结束的规则 ---
        # if action_to_execute.get("tool_name") == "do_nothing":
        #     print("\nSimulation ends as a character chose to do nothing.")
        #     dialogue_queue.put("\n--- 对话因角色无行动而结束 ---")
        #     break
            
    print("\n=============================================")
    print("====== A.L.I.C.E. Simulation Finished ======")
    print("=============================================")
    if gui.is_running:
        dialogue_queue.put("\n--- 对话达到最大回合数 ---")

# ==============================================================================
# 4. 程序主入口
# ==============================================================================

if __name__ == "__main__":
    dialogue_queue = queue.Queue()
    gui = DialogueGUI(dialogue_queue)
    simulation_thread = threading.Thread(
        target=run_simulation, 
        args=(dialogue_queue,), 
        daemon=True
    )
    simulation_thread.start()
    gui.run()