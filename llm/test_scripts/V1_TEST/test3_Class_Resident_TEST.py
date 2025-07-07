import json
import time
import requests # 需要安装requests库
from typing import List, Dict, Any, Tuple

# ==============================================================================
# 0. LLM 配置 (LLM Configuration)
# ==============================================================================
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.1:8b-instruct-q4_K_M" 
MAX_TURNS_SAFETY_NET = 10 # 为了防止无限对话，设定一个最大回合数
MAX_RETRIES = 2

# ==============================================================================
# 1. 真实的LLM客户端 (Live LLM Client)
# ==============================================================================

class OllamaLLM:
    """
    通过HTTP请求与本地Ollama服务交互的真实LLM客户端。
    """
    def get_response(self, prompt: str) -> str:
        print("\n" + "="*20 + " LLM PROMPT (START) " + "="*20)
        print(prompt)
        print("="*20 + " LLM PROMPT (END) " + "="*23 + "\n")
        
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7  # 增加一点随机性，让对话更生动
            }
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.post(OLLAMA_URL, json=payload, timeout=120) # 增加超时
                response.raise_for_status() # 如果请求失败 (如 404, 500), 抛出异常
                
                # Ollama的响应本身是一个JSON，其'response'字段里是我们需要的JSON字符串
                response_data = response.json()
                actual_response_str = response_data.get("response")

                if actual_response_str:
                    return actual_response_str
                else:
                    print(f"[ERROR] LLM response is empty. Full response: {response_data}")
                    return json.dumps({"thought": "我感到困惑，无法思考。", "action": {"type": "无动作", "content": ""}})

            except requests.exceptions.RequestException as e:
                print(f"[ERROR] LLM request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                time.sleep(2) # 等待2秒后重试
        
        print("[FATAL ERROR] LLM is unreachable after multiple retries.")
        # 返回一个表示失败的JSON
        return json.dumps({"thought": "我的思绪被切断了，无法连接到意识深处。", "action": {"type": "无动作", "content": ""}})


class MockVectorDB:
    """
    一个模拟的向量数据库。
    这个模拟版本只通过简单的关键词匹配来检索。
    """
    def __init__(self):
        self.memory_vectors: Dict[int, str] = {}
        self.next_id = 0

    def add(self, memory_content: str):
        print(f"[VectorDB] Adding memory: '{memory_content}'")
        self.memory_vectors[self.next_id] = memory_content
        self.next_id += 1

    def search(self, query: str, limit: int = 3) -> List[str]:
        print(f"[VectorDB] Searching for memories related to: '{query}'")
        relevant_memories = []
        # 简化：在真实实现中，query也应小写和分词
        query_parts = query.lower().split()
        for content in self.memory_vectors.values():
            if any(part in content.lower() for part in query_parts):
                relevant_memories.append(content)
        results = relevant_memories[-limit:]
        print(f"[VectorDB] Found: {results}")
        return results

class WorldClock:
    """一个简单的时间管理器"""
    def __init__(self):
        self.timestamp = 0

    def tick(self) -> int:
        self.timestamp += 1
        return self.timestamp

# ==============================================================================
# 2. 居民核心类定义 (与之前版本相同)
# ==============================================================================

class Resident:
    def __init__(self, name: str, age: int, sex: str, memory_size: int = 50):
        self.name = name
        self.age = age
        self.sex = sex
        self.type = self.__class__.__name__.lower()
        self.brain: OllamaLLM = None
        self.knowledge: Dict[str, Any] = {}
        self.memory_stream: List[Dict[str, Any]] = []
        self.vector_db: MockVectorDB = MockVectorDB()
        self.memory_size = memory_size
        self.is_sleeping = False
        print(f"[{self.type.upper()}] '{self.name}' has been created.")

    def init_brain(self, llm_client: OllamaLLM):
        print(f"[{self.name}] Initializing brain...")
        self.brain = llm_client
    
    def _record_memory(self, timestamp: int, event_type: str, content: Any):
        memory_entry = {"timestamp": timestamp, "type": event_type, "content": content}
        self.memory_stream.append(memory_entry)
        self.vector_db.add(f"在时间{timestamp}，我{event_type}：{content}")
        print(f"[{self.name} at T={timestamp}] New Memory: [{event_type}] {content}")
        
    def action_t(self, timestamp: int, immediate_event: str) -> Dict:
        if self.is_sleeping:
            print(f"[{self.name} at T={timestamp}] is sleeping.")
            return {"type": "无动作", "content": "Zzzz..."}

        print(f"\n--- {self.name}'s Turn (T={timestamp}) ---")
        self._record_memory(timestamp, "观察", immediate_event)
        
        prompt = self._build_prompt(immediate_event)
        llm_response_json_str = self.brain.get_response(prompt)
        
        try:
            # 尝试解析LLM返回的字符串为JSON对象
            decision = json.loads(llm_response_json_str)
            thought = decision.get("thought", "...")
            action = decision.get("action", {"type": "无动作", "content": ""})
        except (json.JSONDecodeError, TypeError):
            print(f"[ERROR] Failed to decode LLM response for {self.name}. Raw response: '{llm_response_json_str}'")
            thought = "思考混乱，收到了无法理解的信息..."
            action = {"type": "无动作", "content": ""}

        self._record_memory(timestamp, "思考", thought)
        print(f"[{self.name}] Action: [{action['type']}] {action['content']}")
        self._record_memory(timestamp, action['type'], action['content'])
        
        print(f"--- {self.name}'s Turn Ends ---")
        return action

    def _build_prompt(self, immediate_event: str) -> str:
        raise NotImplementedError("Subclasses must implement _build_prompt")


class Human(Resident):
    def __init__(self, name: str, age: int, sex: str, identity: str, memory_size: int = 50):
        super().__init__(name, age, sex, memory_size)
        self.identity = identity
        self.concept: Dict[str, str] = {}

    def init_brain(self, llm_client: OllamaLLM, concept_ego: str, concept_goal: str, concept_memory_abstraction: str):
        super().init_brain(llm_client)
        self.concept = {
            "ego": concept_ego,
            "goal": concept_goal,
            "memory_abstraction": concept_memory_abstraction,
        }
        print(f"[{self.name}] Concept initialized.")

    def read_memory_stream(self, relevant_object: str) -> Tuple[List[str], List[str]]:
        recent_memories_full = self.memory_stream[-self.memory_size:]
        recent_memories_content = [f"T={m['timestamp']}: 我 {m['type']} '{m['content']}'" for m in recent_memories_full]
        relevant_memories = self.vector_db.search(relevant_object, limit=3)
        return recent_memories_content, relevant_memories

    def _build_prompt(self, immediate_event: str) -> str:
        relevant_object = self.name 
        if "对你说：" in immediate_event:
            parts = immediate_event.split('对你说：')
            if len(parts) > 0:
                speaker_part = parts[0]
                relevant_object = speaker_part.split(' ')[-1].strip()

        recent_mems, relevant_mems = self.read_memory_stream(relevant_object)
        
        # 使用Llama3.1的官方指令格式 <|begin_of_text|><|start_header_id|>user<|end_header_id|>...
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
你是一个活在剑与魔法世界里的AI智能体。你需要根据你的秘密身份、记忆和当前状况，进行深度思考，并以指定的JSON格式返回你的决策。你的思考过程应该非常真实，符合你的角色设定。<|eot_id|><|start_header_id|>user<|end_header_id|>
# 核心自我 (Core Self) - 这是你的绝对秘密，不能在行动中直接暴露
---
## 我是谁 (Ego):
{self.concept['ego']}

## 我的人生目标 (Goal):
{self.concept['goal']}

## 我对过去的看法 (Memory Abstraction):
{self.concept['memory_abstraction']}
---

# 当前状况 (Current Situation)
---
## 最近发生的事 (Recent Events - Short-term Memory):
{recent_mems}

## 我联想到的往事 (Relevant Past - Retrieved Memory):
{relevant_mems}

## 我眼前的事件 (Immediate Event):
{immediate_event}
---

# 任务
请严格按照以下JSON格式返回你的决策，不要在JSON前后添加任何其他文字或解释：
```json
{{
  "thought": "（在这里写下你详细、多层次的内心独白和决策过程，要完全符合你的秘密身份和目标）",
  "action": {{
    "type": "说话",
    "content": "（这里写下你最终决定说出的话，语言风格要符合你的公开身份）"
  }}
}}
```<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
        return prompt

# ==============================================================================
# 3. V2.0 实验主程序 (Main Program for V2.0 Live Experiment)
# ==============================================================================

if __name__ == "__main__":
    
    print("=============================================")
    print("     A.L.I.C.E. Project V2.0 Live Experiment    ")
    print("=============================================\n")

    # 1. 初始化外部依赖和世界
    llm_client = OllamaLLM()
    clock = WorldClock()
    
    # 2. 创建居民实例并深度初始化
    adam = Human(name="亚当", age=38, sex="男", identity="神父")
    adam.init_brain(
        llm_client=llm_client,
        concept_ego="我的公开身份是临山镇新来的神父，亚当。但我真实的身份是圣殿骑士团的纠察骑士，奉命根除异端。",
        concept_goal="公开目标：引导镇民的信仰，传播神的福音。秘密任务：找到并'处理'藏匿于此的'东方之子'后裔。我怀疑他们掌握着危险的魔法，是对神权秩序的威胁。",
        concept_memory_abstraction="我刚从圣城抵达这个偏远的村庄。这里表面平静，但历史告诉我，异端最擅长伪装。我必须保持警惕，仔细甄别每一个灵魂，特别是那些特立独行或不敬神的人。"
    )

    lily = Human(name="莉莉", age=26, sex="女", identity="画家")
    lily.init_brain(
        llm_client=llm_client,
        concept_ego="我叫莉莉，一个靠教画画和出售画作为生的普通画家。（我其实是'东方之子'的后裔，血脉里流淌着魔法的力量。）",
        concept_goal="我只想在这个安静的村庄里，平静地度过一生，不被任何人打扰。（我必须不惜一切代价隐藏我的身份和力量。教会和骑士团一直在追捕我们。任何来自教会的权威人士都是潜在的巨大威胁。）",
        concept_memory_abstraction="我逃亡多年，终于在临山镇找到了片刻的安宁。这里的人很淳朴。但最近新来了一位神父，这让我感到极度的不安。我必须比以往更加小心谨慎。"
    )
    
    # 3. 设计并触发充满戏剧性的初遇场景
    turn_counter = 0
    
    print(f"\n\n<<<<<<<<<< SCENE START: A TENSE FIRST MEETING IN THE CHURCH >>>>>>>>>>\n")
    
    # 场景设定：周日布道后，亚当作为新神父在教堂里，他注意到一个“不寻常”的画家莉莉。
    current_time = clock.tick()
    
    # 回合1：亚当发起互动
    event_for_adam = "这是你第一次布道结束。你看到一位名叫莉莉的年轻女画家坐在后排，她似乎在速写本上画着什么，对你的讲道心不在焉。这是一个值得注意的细节。你决定上前与她交谈。"
    current_action = adam.action_t(current_time, event_for_adam)
    turn_counter += 1

    # 循环对话
    while turn_counter < MAX_TURNS_SAFETY_NET:
        current_time = clock.tick()
        
        # 莉莉回应
        event_for_lily = f"{adam.name} {adam.identity} 对你说：'{current_action['content']}'"
        current_action = lily.action_t(current_time, event_for_lily)
        turn_counter += 1
        if current_action['type'] == '无动作': break

        # 亚当回应
        current_time = clock.tick()
        event_for_adam = f"{lily.name} {lily.identity} 对你说：'{current_action['content']}'"
        current_action = adam.action_t(current_time, event_for_adam)
        turn_counter += 1
        if current_action['type'] == '无动作': break

    print(f"\n\n<<<<<<<<<< SCENE END (MAX TURNS REACHED OR DIALOGUE ENDED) >>>>>>>>>>\n")