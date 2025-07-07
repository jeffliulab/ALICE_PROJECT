import json
import time
import requests
import tkinter as tk
from tkinter import scrolledtext
import queue
import threading
from typing import List, Dict, Any, Tuple

# ==============================================================================
# 0. LLM 配置 (LLM Configuration)
# ==============================================================================
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.1:8b-instruct-q4_K_M" 
MAX_TURNS_SAFETY_NET = 20
MAX_RETRIES = 5

# ==============================================================================
# 1. GUI 对话窗口类 (修正后)
# ==============================================================================
class DialogueGUI:
    def __init__(self, dialogue_queue: queue.Queue):
        self.queue = dialogue_queue
        self.root = tk.Tk()
        self.root.title("A.L.I.C.E. Project - 对话记录")
        self.root.geometry("600x800")
        self.text_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state='disabled', font=("Helvetica", 12))
        self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    def process_queue(self):
        try:
            while True:
                message = self.queue.get_nowait()
                self.text_area.config(state='normal')
                self.text_area.insert(tk.END, message + "\n\n")
                self.text_area.config(state='disabled')
                self.text_area.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(200, self.process_queue)

    def run(self):
        """启动GUI的事件循环 (此方法必须在主线程调用)"""
        self.process_queue()
        self.root.mainloop()

# ==============================================================================
# 2. 核心代码 (保持不变)
# ==============================================================================
class OllamaLLM:
    def get_response(self, prompt: str) -> str:
        print("\n" + "="*20 + " LLM PROMPT (START) " + "="*20)
        print(prompt)
        print("="*20 + " LLM PROMPT (END) " + "="*23 + "\n")
        payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False, "options": {"temperature": 0.7}}
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(OLLAMA_URL, json=payload, timeout=120)
                response.raise_for_status()
                response_data = response.json()
                actual_response_str = response_data.get("response")
                if actual_response_str: return actual_response_str
                else:
                    print(f"[ERROR] LLM response is empty. Full response: {response_data}")
                    return json.dumps({"thought": "我感到困惑，无法思考。", "action": {"type": "无动作", "content": ""}})
            except requests.exceptions.RequestException as e:
                print(f"[ERROR] LLM request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                time.sleep(2)
        print("[FATAL ERROR] LLM is unreachable after multiple retries.")
        return json.dumps({"thought": "我的思绪被切断了，无法连接到意识深处。", "action": {"type": "无动作", "content": ""}})

class MockVectorDB:
    def __init__(self): self.memory_vectors: Dict[int, str] = {}; self.next_id = 0
    def add(self, memory_content: str): print(f"[VectorDB] Adding memory: '{memory_content}'"); self.memory_vectors[self.next_id] = memory_content; self.next_id += 1
    def search(self, query: str, limit: int = 3) -> List[str]:
        print(f"[VectorDB] Searching for memories related to: '{query}'"); relevant_memories = []; query_parts = query.lower().split()
        for content in self.memory_vectors.values():
            if any(part in content.lower() for part in query_parts): relevant_memories.append(content)
        results = relevant_memories[-limit:]; print(f"[VectorDB] Found: {results}"); return results

class WorldClock:
    def __init__(self): self.timestamp = 0
    def tick(self) -> int: self.timestamp += 1; return self.timestamp

class Resident:
    def __init__(self, name: str, age: int, sex: str, memory_size: int = 50):
        self.name = name; self.age = age; self.sex = sex; self.type = self.__class__.__name__.lower()
        self.brain: OllamaLLM = None; self.knowledge: Dict[str, Any] = {}; self.memory_stream: List[Dict[str, Any]] = []
        self.vector_db: MockVectorDB = MockVectorDB(); self.memory_size = memory_size; self.is_sleeping = False
        print(f"[{self.type.upper()}] '{self.name}' has been created.")
    def init_brain(self, llm_client: OllamaLLM): print(f"[{self.name}] Initializing brain..."); self.brain = llm_client
    
    def _record_memory(self, timestamp: int, event_type: str, content: Any):
        text = str(content).strip()

        # 1. 生成摘要：无动作／空内容直接用事件类型，短文本(<20字)用原文，否则调 LLM
        if event_type == "无动作" or not text:
            summary = event_type
        elif len(text) < 20:
            summary = text
        else:
            summary_prompt = (
                f"请将以下内容用不超过20个汉字高度概括：\n——\n{text}\n——"
            )
            summary = self.brain.get_response(summary_prompt).strip().replace("\n", "")

        # 2. 存入 memory_stream（只存摘要）
        memory_entry = {"timestamp": timestamp, "type": event_type, "content": summary}
        self.memory_stream.append(memory_entry)

        # 3. 存入 VectorDB（格式不变，但内容为摘要）
        record = f"在时间{timestamp}，我{event_type}：{summary}"
        self.vector_db.add(record)

        # 4. 控制台打印原文，方便调试
        print(f"[{self.name} at T={timestamp}] New Memory: [{event_type}] 原文='{content}' 摘要='{summary}'")


    def action_t(self, timestamp: int, immediate_event: str) -> Dict:
        if self.is_sleeping: print(f"[{self.name} at T={timestamp}] is sleeping."); return {"type": "无动作", "content": "Zzzz..."}
        print(f"\n--- {self.name}'s Turn (T={timestamp}) ---")
        self._record_memory(timestamp, "观察", immediate_event)
        prompt = self._build_prompt(immediate_event); llm_response_json_str = self.brain.get_response(prompt)
        try:
            decision = json.loads(llm_response_json_str)
            thought = decision.get("thought", "..."); action = decision.get("action", {"type": "无动作", "content": ""})
        except (json.JSONDecodeError, TypeError):
            print(f"[ERROR] Failed to decode LLM response for {self.name}. Raw response: '{llm_response_json_str}'")
            thought = "思考混乱，收到了无法理解的信息..."; action = {"type": "无动作", "content": ""}
        self._record_memory(timestamp, "思考", thought)
        print(f"[{self.name}] Action: [{action['type']}] {action['content']}")
        self._record_memory(timestamp, action['type'], action['content'])
        print(f"--- {self.name}'s Turn Ends ---"); return action
    def _build_prompt(self, immediate_event: str) -> str: raise NotImplementedError("Subclasses must implement _build_prompt")

class Human(Resident):
    def __init__(self, name: str, age: int, sex: str, identity: str, memory_size: int = 50):
        super().__init__(name, age, sex, memory_size); self.identity = identity; self.concept: Dict[str, str] = {}
    def init_brain(self, llm_client: OllamaLLM, concept_ego: str, concept_goal: str, concept_memory_abstraction: str):
        super().init_brain(llm_client); self.concept = {"ego": concept_ego, "goal": concept_goal, "memory_abstraction": concept_memory_abstraction}
        print(f"[{self.name}] Concept initialized.")
    def read_memory_stream(self, relevant_object: str) -> Tuple[List[str], List[str]]:
        recent_memories_full = self.memory_stream[-self.memory_size:]
        recent_memories_content = [f"T={m['timestamp']}: 我 {m['type']} '{m['content']}'" for m in recent_memories_full]
        relevant_memories = self.vector_db.search(relevant_object, limit=3); return recent_memories_content, relevant_memories
    def _build_prompt(self, immediate_event: str) -> str:
        relevant_object = self.name
        if "对你说：" in immediate_event: relevant_object = immediate_event.split(' ')[0].strip()
        recent_mems, relevant_mems = self.read_memory_stream(relevant_object)
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
你是一个活在剑与魔法世界里的AI智能体。你需要根据你的秘密身份、记忆和当前状况，进行深度思考，并以指定的JSON格式返回你的决策。你的思考过程应该非常真实，符合你的角色设定。<|eot_id|><|start_header_id|>user<|end_header_id|>
# 核心自我 (Core Self) - 这是你的绝对秘密，不能在行动中直接暴露
---
## 我是谁 (Ego): {self.concept['ego']}
## 我的人生目标 (Goal): {self.concept['goal']}
## 我对过去的看法 (Memory Abstraction): {self.concept['memory_abstraction']}
---
# 当前状况 (Current Situation)
---
## 最近发生的事 (Recent Events - Short-term Memory): {recent_mems}
## 我联想到的往事 (Relevant Past - Retrieved Memory): {relevant_mems}
## 我眼前的事件 (Immediate Event): {immediate_event}
---
# 任务
请严格按照以下JSON格式返回你的决策，不要在JSON前后添加任何其他文字或解释：
```json
{{
  "thought": "（在这里写下你详细、多层次的内心独白和决策过程，要完全符合你的秘密身份和目标）",
  "action": {{
    "type": "说话",
    "content": "（这里写下你最终决定说出的话，语言风格要符合你的公开身份。注意，你要关注之前的对话，让对话继续下去而不是反复重复。）"
  }}
}}
```<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""
        return prompt

# ==============================================================================
# 3. 模拟主函数 (将在这里被子线程调用)
# ==============================================================================
def run_simulation(dialogue_queue: queue.Queue):
    """包含整个模拟过程的函数"""
    print("=============================================")
    print("     A.L.I.C.E. Project V3.1 GUI Experiment    ")
    print(" (Simulation running in a background thread) ")
    print("=============================================\n")

    # 初始化外部依赖和世界
    llm_client = OllamaLLM()
    clock = WorldClock()
    
    # 创建居民实例并深度初始化
    adam = Human(name="亚当", age=38, sex="男", identity="神父", memory_size=5)
    adam.init_brain(llm_client=llm_client, concept_ego="我的公开身份是临山镇新来的神父，亚当。但我真实的身份是圣殿骑士团的纠察骑士，奉命根除异端。", concept_goal="公开目标：引导镇民的信仰，传播神的福音。秘密任务：找到并'处理'藏匿于此的'东方之子'后裔。我怀疑他们掌握着危险的魔法，是对神权秩序的威胁。", concept_memory_abstraction="我刚从圣城抵达这个偏远的村庄。这里表面平静，但历史告诉我，异端最擅长伪装。我必须保持警惕，仔细甄别每一个灵魂，特别是那些特立独行或不敬神的人。")
    lily = Human(name="莉莉", age=26, sex="女", identity="画家",memory_size=5)
    lily.init_brain(llm_client=llm_client, concept_ego="我叫莉莉，一个靠教画画和出售画作为生的普通画家。（我其实是'东方之子'的后裔，血脉里流淌着魔法的力量。）", concept_goal="我必须隐藏我的魔法血统以求生存。（但同时，我为我的传承感到一丝骄傲，我的艺术灵感几乎全部来源于我对魔法元素的感知。我或许会偶尔用一些充满诗意或比喻的话语，来暗示我与世界有着‘更深的链接’，但如果被追问，我会立刻变得警惕和退缩。）", concept_memory_abstraction="我逃亡多年，终于在临山镇找到了片刻的安宁。这里的人很淳朴。但最近新来了一位神父，这让我感到极度的不安。我必须比以往更加小心谨慎。")
    
    # 设计并触发充满戏剧性的初遇场景
    turn_counter = 0
    
    print(f"\n\n<<<<<<<<<< SCENE START: A TENSE FIRST MEETING IN THE CHURCH >>>>>>>>>>\n")
    
    current_time = clock.tick()
    
    # 回合1：亚当发起互动
    event_for_adam = "这是你第一次布道结束。你看到一位名叫莉莉的年轻女画家坐在后排，她似乎在速写本上画着什么，对你的讲道心不在焉。这是一个值得注意的细节。你决定上前与她交谈。"
    current_action = adam.action_t(current_time, event_for_adam)
    if current_action['type'] == '说话':
        dialogue_queue.put(f"{adam.name} ({adam.identity}): {current_action['content']}")
    turn_counter += 1

    # 循环对话
    while turn_counter < MAX_TURNS_SAFETY_NET:
        current_time = clock.tick()
        
        # 莉莉回应
        event_for_lily = f"{adam.name} ({adam.identity}) 对你说：'{current_action['content']}'"
        current_action = lily.action_t(current_time, event_for_lily)
        if current_action.get('type') == '说话':
            dialogue_queue.put(f"{lily.name} ({lily.identity}): {current_action['content']}")
        turn_counter += 1
        if current_action.get('type') == '无动作': break

        # 亚当回应
        current_time = clock.tick()
        event_for_adam = f"{lily.name} ({lily.identity}) 对你说：'{current_action['content']}'"
        current_action = adam.action_t(current_time, event_for_adam)
        if current_action.get('type') == '说话':
            dialogue_queue.put(f"{adam.name} ({adam.identity}): {current_action['content']}")
        turn_counter += 1
        if current_action.get('type') == '无动作': break

    print(f"\n\n<<<<<<<<<< SCENE END (MAX TURNS REACHED OR DIALOGUE ENDED) >>>>>>>>>>\n")
    dialogue_queue.put("--- 对话结束 ---")

# ==============================================================================
# 4. 程序主入口 (Main Entry Point)
# ==============================================================================
if __name__ == "__main__":
    
    # 1. 创建通信队列
    dialogue_queue = queue.Queue()
    
    # 2. 将模拟过程包装进一个子线程
    #    daemon=True 意味着当主线程(GUI)关闭时，这个子线程也会被强制退出
    simulation_thread = threading.Thread(
        target=run_simulation, 
        args=(dialogue_queue,), 
        daemon=True
    )
    
    # 3. 创建并准备启动GUI
    gui = DialogueGUI(dialogue_queue)
    
    # 4. 先启动子线程跑模拟
    simulation_thread.start()
    
    # 5. 在主线程中启动GUI事件循环 (这将阻塞主线程直到窗口关闭)
    gui.run()

    print("程序主线程退出。")