# -*- coding: utf-8 -*-
import json
import time
import requests
from typing import List, Dict, Any, Tuple
import random # <--- 新增导入，用于随机获取隐藏信息

# ==============================================================================
# 0. 全局配置 (无变化)
# ==============================================================================
class OllamaLLM:
    # ... (这部分代码与上一版完全相同，为简洁省略)
    def __init__(self, model_name: str = "llama3.1:8b-instruct-q4_K_M"):
        self.url = "http://127.0.0.1:11434/api/generate"
        self.model_name = model_name
    def get_response(self, prompt: str) -> str:
        print("\n" + "="*20 + " LLM PROMPT (START) " + "="*20)
        print(prompt)
        print("="*20 + " LLM PROMPT (END) " + "="*23 + "\n")
        payload = {
            "model": self.model_name, "prompt": prompt, "stream": False,
            "format": "json", "options": {"temperature": 0.7}
        }
        try:
            response = requests.post(self.url, json=payload, timeout=180)
            response.raise_for_status()
            response_data = response.json()
            return response_data.get("response", "{}")
        except requests.exceptions.RequestException as e:
            print(f"[FATAL ERROR] LLM request failed: {e}")
            return json.dumps({
                "thought": "我的思绪被切断了。",
                "action": {"tool_name": "do_nothing", "parameters": {}}
            })

class WorldClock:
    # ... (无变化)
    def __init__(self):
        self.timestamp = 0
        print("WorldClock initialized.")
    def tick(self) -> int:
        self.timestamp += 1
        print(f"\n{'='*50}\n===== World Time advanced to T={self.timestamp} =====\n{'='*50}\n")
        return self.timestamp

class KnowledgeBase:
    # ... (无变化)
    def __init__(self):
        self.db = {
            101: {"category": "common_sense", "content": "这是一个剑与魔法并存的世界。"},
            102: {"category": "rules", "content": "教会是这片土地的最高统治者。"},
            103: {"category": "rules", "content": "东方之子及其相关的一切，都是被严令禁止的异端。"},
            104: {"category": "history", "content": "据说，很久以前，神明曾行走于大地之上。"},
        }
        print("KnowledgeBase initialized.")
    def get_knowledge_content(self, kid: int) -> str:
        return self.db.get(kid, {}).get("content", "未知知识")

# ==============================================================================
# 1. 居民核心框架 (有少量修改)
# ==============================================================================

class Resident:
    # ... (大部分无变化，只修改了decide_action的参数)
    def __init__(self, name: str, age: int, sex: str, llm_client: OllamaLLM, knowledge_base: KnowledgeBase):
        self.name, self.age, self.sex = name, age, sex
        self.type = self.__class__.__name__
        self.memory_stream: List[Dict] = []
        self.knowledge_mastery: Dict[int, bool] = {}
        self.brain = llm_client
        self.world_knowledge = knowledge_base
        print(f"[{self.type.upper()}] '{self.name}' has been created.")
    def _record_memory(self, timestamp: int, event_type: str, content: str):
        memory_entry = {"timestamp": timestamp, "type": event_type, "content": content}
        self.memory_stream.append(memory_entry)
        print(f"[{self.name} at T={timestamp}] New Memory Recorded: [{event_type}] {content}")
    def _get_relevant_memories(self, limit: int = 5) -> List[str]:
        recent_memories = self.memory_stream[-limit:]
        return [f"在T={m['timestamp']}, 我 {m['type']}: '{m['content']}'" for m in recent_memories]
    def _get_mastered_knowledge(self) -> List[str]:
        mastered = [self.world_knowledge.get_knowledge_content(kid) for kid, is_mastered in self.knowledge_mastery.items() if is_mastered]
        return mastered
    
    # <--- 关键改动: 增加了一个force_speak参数 ---
    def decide_action(self, timestamp: int, observation: str, force_speak: bool = False) -> Dict:
        """居民的核心决策循环。"""
        turn_type = "Forced Speak" if force_speak else "Action Cycle"
        print(f"--- {self.name}'s Turn ({turn_type}) ---")

        self._record_memory(timestamp, "观察到", observation)
        prompt = self._build_prompt(observation, force_speak)
        response_str = self.brain.get_response(prompt)
        
        try:
            decision = json.loads(response_str)
        except json.JSONDecodeError:
            print(f"[ERROR] Failed to decode JSON. Using fallback.")
            decision = {
                "thought": "我的思维陷入了混乱。",
                "action": {"tool_name": "do_nothing", "parameters": {}}
            }
        
        thought = decision.get("thought", "（无有效思考）")
        self._record_memory(timestamp, "思考了", thought)
        action = decision.get("action", {"tool_name": "do_nothing", "parameters": {}})
        print(f"[{self.name}] Decided Action: Call tool '{action.get('tool_name')}' with params {action.get('parameters')}")
        
        return action

    def _build_prompt(self, observation: str, force_speak: bool) -> str:
        raise NotImplementedError("Subclasses must implement _build_prompt.")

class Human(Resident):
    def __init__(self, name: str, age: int, sex: str, identity: str, concept: Dict, 
                 initial_knowledge: Dict[int, bool], hidden_details: List[str], # <--- 新增: 角色的隐藏信息
                 llm_client: OllamaLLM, knowledge_base: KnowledgeBase):
        
        super().__init__(name, age, sex, llm_client, knowledge_base)
        self.identity = identity
        self.concept = concept
        self.knowledge_mastery = initial_knowledge
        self.hidden_details = hidden_details # <--- 新增
        print(f"[{self.name}] Concept, Knowledge, and Hidden Details initialized.")

    # <--- 新增一个方法，用于被观察时揭示信息 ---
    def reveal_hidden_detail(self) -> str:
        if self.hidden_details:
            return self.hidden_details.pop(random.randrange(len(self.hidden_details)))
        return "他/她看起来并没有什么特别之处。"

    def _build_prompt(self, observation: str, force_speak: bool) -> str:
        memories = self._get_relevant_memories()
        knowledge = self._get_mastered_knowledge()

        # <--- 关键改动: 根据是否强制发言，构建不同的System Prompt ---
        if force_speak:
            system_prompt = """
# **核心规则**
你刚才进行了一次“仔细观察”，现在你得到了一个额外回合。
**在这个回合，你必须调用"speak"工具进行发言**，不能使用任何其他工具。
你的输出必须、也只能是一个JSON对象，包含`thought`和`action`两个键。
`action`键的值中，`tool_name`必须是 "speak"。
"""
        else:
            system_prompt = """
# **核心规则**
你是一个在虚拟世界中扮演角色的AI智能体。你的任务是决策下一步要调用的工具。
**你的输出必须、也只能是一个JSON对象，包含`thought`和`action`两个键。**
`action`键的值必须是另一个JSON对象，包含`tool_name`和`parameters`。
可用的工具 (tool_name) 有: "speak", "move", "observe_detail", "do_nothing"。
"""

        # 构建完整的Prompt
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
时间: T={clock.timestamp}
你观察到的事件: {observation}
---
# **你的任务**
基于以上所有信息，生成你的内心思想（thought）和下一步要调用的工具（action）。严格按照System消息中指定的JSON格式进行输出。
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
        return prompt

# ==============================================================================
# 2. 工具执行器 (有关键修改)
# ==============================================================================

# <--- 关键改动: execute_tool现在需要知道所有居民，以便揭示信息 ---
def execute_tool(actor: Human, all_residents: Dict[str, Human], action: Dict) -> Dict:
    tool_name = action.get("tool_name", "do_nothing")
    parameters = action.get("parameters", {})
    
    result_description = f"'{actor.name}'什么也没做。"
    next_actor_is_self = False

    if tool_name == "speak":
        target = parameters.get('target_name', '空气')
        content = parameters.get('content', '...')
        result_description = f"'{actor.name}'对'{target}'说：'{content}'"
    
    elif tool_name == "observe_detail":
        target_name = parameters.get('target', actor.name)
        # 从被观察者身上揭示一个隐藏信息
        if target_name in all_residents and target_name != actor.name:
            target_actor = all_residents[target_name]
            revealed_detail = target_actor.reveal_hidden_detail()
            result_description = f"'{actor.name}'仔细地观察着'{target_name}'，并注意到了一个细节：{revealed_detail}"
        else:
            result_description = f"'{actor.name}'仔细地观察着四周。"
        
        # <--- 关键改动: 设定特殊信号，让当前角色获得额外回合 ---
        next_actor_is_self = True

    # 返回一个字典，包含事件描述和下一个行动者的信息
    return {"description": result_description, "next_actor_is_self": next_actor_is_self}

# ==============================================================================
# 3. 主模拟循环 (有关键修改)
# ==============================================================================

if __name__ == "__main__":
    llm = OllamaLLM()
    clock = WorldClock()
    knowledge_base = KnowledgeBase()

    # <--- 新增: 为角色添加'hidden_details' ---
    adam_concept = {"ego": "...", "goal": "...", "memory_abstraction": "..."} # 为简洁省略
    adam_knowledge = {101: True, 102: True, 103: True, 104: True}
    adam = Human(
        name="亚当", age=38, sex="男", identity="神父", concept=adam_concept,
        initial_knowledge=adam_knowledge, hidden_details=[], # 神父没有可被轻易观察的秘密
        llm_client=llm, knowledge_base=knowledge_base
    )

    lily_concept = {"ego": "...", "goal": "...", "memory_abstraction": "..."} # 为简洁省略
    lily_knowledge = {101: True, 102: True, 103: True, 104: False}
    lily = Human(
        name="莉莉", age=26, sex="女", identity="画家", concept=lily_concept,
        initial_knowledge=lily_knowledge,
        hidden_details=[ # <--- 莉莉有一些可被观察到的细节
            "她的指尖沾有不同寻常的金色粉末。",
            "她用来固定的画板的绳结，是一种军用级别的特殊打法。",
            "在她的速写本一角，有一个难以察觉的、类似星辰的家族徽记。"
        ],
        llm_client=llm, knowledge_base=knowledge_base
    )
    
    # <--- 关键改动: 使用字典来存储居民，方便按名字查找 ---
    all_residents_dict = {"亚当": adam, "莉莉": lily}
    turn_order = [adam, lily]
    max_turns = 10
    current_event = "你在教堂里，这是你第一次布道结束。你看到一位名叫莉莉的年轻女画家坐在后排，她似乎在速写本上画着什么，对你的讲道心不在焉。"
    
    actor_index = 0
    force_speak_flag = False

    for i in range(max_turns):
        turn_number = i + 1
        print(f"\n--- Turn {turn_number} ---")
        
        current_actor = turn_order[actor_index]
        current_time = clock.tick()
        
        # <--- 关键改动: 核心循环逻辑重写 ---
        action_to_execute = current_actor.decide_action(current_time, current_event, force_speak=force_speak_flag)
        execution_result = execute_tool(current_actor, all_residents_dict, action_to_execute)
        
        current_event = execution_result["description"] # 新的事件是工具执行的结果
        
        # 检查是否需要强制发言
        if execution_result["next_actor_is_self"]:
            force_speak_flag = True
            # 下一轮行动者不变
        else:
            force_speak_flag = False
            # 轮到下一个角色
            actor_index = (actor_index + 1) % len(turn_order)

        if action_to_execute.get("tool_name") == "do_nothing":
            print("\nSimulation ends as a character chose to do nothing.")
            break
            
    print("\n=============================================")
    print("====== A.L.I.C.E. Simulation Finished ======")
    print("=============================================")