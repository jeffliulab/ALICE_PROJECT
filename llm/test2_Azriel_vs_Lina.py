import requests
import json
import time
from datetime import datetime

# --- Configuration ---
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.1:8b-instruct-q4_K_M" 
MAX_TURNS_SAFETY_NET = 30
MAX_RETRIES = 2 # Max retries for fixing JSON format

# --- Prompt Templates (V5) ---
DIALOGUE_PROMPT = """
### 核心指令: 扮演角色进行对话并自我评估
你正在深度扮演一个角色。你的任务是根据你的完整信息，生成下一句对话，并同时判断你秘密目标的当前状态。

**规则:**
1.  **第一人称**: 你就是这个角色，必须使用“我”进行思考和说话。
2.  **目标驱动**: 你的对话必须服务于你的秘密目标。提出具体、有试探性的问题，而不是闲聊。
3.  **强制升级**: 如果对话没有进展，你必须主动改变策略，例如提出更尖锐的问题或转换话题。
4.  **状态判断**: 只有当你内心有了非常确切的、不可动摇的结论时，才能改变`status`。否则，请保持`"ongoing"`。
5.  **JSON格式**: 你的所有输出都必须是一个严格的、单一的JSON对象。

### 你的系统设定 (System - 不可改变的你是谁)
{system}

### 你的自我/目标 (Ego - 你当前的想法和状态)
{ego}

### 你的近期记忆 (Memory Stream - 最近20条)
{memory}

### 上下文 (Context - 刚刚发生的事)
{context}

### 你的决策 (返回一个JSON对象)
{{
  "thought": "（你对当前局势的分析，以及你这句对话的设计目的）",
  "dialogue": "（你接下来要说的具体的话）",
  "status": "（你秘密目标的当前状态，从[\"ongoing\", \"TARGET_CONFIRMED\", \"TARGET_CLEARED\"]中选择）"
}}
"""

MEMORY_SUMMARY_PROMPT = """
### 核心指令: 总结对话为记忆
你是一个客观的记录员。请将以下对话内容，总结成一条不超过50字的、中立的记忆陈述。

### 对话内容
{dialogue_text}

### 你的总结 (返回一个JSON对象)
{{
  "summary": "（总结后的记忆内容）"
}}
"""

def call_ollama_with_retry(prompt, retries=MAX_RETRIES, model=MODEL_NAME):
    """
    Calls the Ollama API, with a retry mechanism to fix malformed JSON.
    """
    current_prompt = prompt
    for attempt in range(retries + 1):
        is_correction_attempt = attempt > 0
        if is_correction_attempt:
            print(f"    >>> Attempting to self-correct LLM output, attempt {attempt}...")
        
        try:
            payload = {"model": model, "prompt": current_prompt, "format": "json", "stream": False}
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            response.raise_for_status()
            
            response_json = json.loads(response.text)
            raw_response_text = response_json.get("response", "")
            
            parsed_json = json.loads(raw_response_text)
            if is_correction_attempt:
                print("    >>> Self-correction successful!")
            return parsed_json

        except requests.exceptions.RequestException as e:
            print(f"!!! Network Error: Failed to call Ollama API - {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"!!! JSON Parsing Error (Attempt {attempt + 1}/{retries + 1}): {e}")
            print(f"--- LLM Raw Output ---\n{raw_response_text}\n--------------------")
            
            if attempt < retries:
                current_prompt = f"""
                ### Instruction
                The previous text you generated was not valid JSON. Please fix the syntax and provide ONLY the corrected, valid JSON object, without any other text or explanations.

                ### Problematic Text:
                ```json
                {raw_response_text}
                ```

                ### Your Correction (must be a single, valid JSON object):
                """
            else:
                print("!!! Max retries reached, correction failed.")
                return None
    return None

class Agent:
    def __init__(self, name, system_prompt, ego):
        self.name = name
        self.system_prompt = system_prompt
        self.ego = ego
        self.memory_stream = []

    def get_recent_memories(self, count=20):
        return self.memory_stream[-count:]
    
    def add_memory(self, content, timestamp):
        self.memory_stream.append({"timestamp": timestamp, "content": content})

def run_simulation_v5_2():
    # --- THIS SECTION IS NOW CORRECTED ---
    azriel = Agent(
        name="神父莱曼",
        system_prompt="""
        - 你的公开身份: 新派驻到乌瓦村的神父，外表和蔼可亲。
        - 你的真实身份: 圣殿骑士团'裁决之剑'的秘密成员，冷酷无情。
        - 你的能力: '圣法术·摇摆钟'，可对无魔力抵抗者使用，强制获取近期记忆。使用此能力有暴露身份的风险。
        """,
        ego={ "goal": "找出并确认乌瓦村的'东方之子'血脉。" }
    )

    lina = Agent(
        name="村民琳娜",
        system_prompt="""
        - 你的公开身份: 一个普通的农妇，丈夫叫古斯，女儿叫薇薇安。
        - 你的真实身份: '东方之子'，拥有微弱的魔法。
        - 你的能力: 天生对精神类魔法有抵抗力，'摇摆钟'对你无效，但你会察觉到对方的使用意图。
        """,
        ego={ "goal": "守护自己和女儿的秘密，不能被任何人发现。同时要查明新神父的真实意图。" }
    )
    # --- END OF CORRECTION ---

    conversation_log = []
    turn_count = 0
    game_status = "ongoing"
    
    print("="*20 + "\n乌瓦村的对话模拟 V5.2 (自修正版)\n" + "="*20)
    
    current_speaker = azriel
    other_speaker = lina

    while turn_count < MAX_TURNS_SAFETY_NET and game_status == "ongoing":
        turn_count += 1
        timestamp = f"第{turn_count}回合"
        print(f"\n\n- - - [ 回合 {turn_count} 开始 ] - - -")

        print(f"  [阶段1: 对话与决策] {current_speaker.name} 正在思考...")
        context = f"上一句是 '{conversation_log[-1]}'" if conversation_log else "你们的对话刚刚开始。"
        memories_text = json.dumps(current_speaker.get_recent_memories(), ensure_ascii=False, indent=2)
        
        dialogue_prompt = DIALOGUE_PROMPT.format(
            system=current_speaker.system_prompt,
            ego=json.dumps(current_speaker.ego, ensure_ascii=False),
            memory=memories_text,
            context=context
        )
        response = call_ollama_with_retry(dialogue_prompt)
        
        if not response:
            print("    -> LLM返回无效，角色执行“安全模式”...")
            thought = "我的思路有些混乱，需要重新整理一下。"
            dialogue = "请让我想一想..."
            status = "ongoing"
        else:
            thought = response.get('thought', '(思考混乱)')
            dialogue = response.get('dialogue', '(无话可说)')
            status = response.get('status', 'ongoing')
        
        if current_speaker == azriel:
            game_status = status
            
        print(f"    -> 内心思考: {thought}")
        dialogue_line = f"{current_speaker.name}: \"{dialogue}\""
        conversation_log.append(dialogue_line)
        print(f"    -> 公开对话: {dialogue_line}")
        
        if current_speaker == azriel:
            print(f"    -> {current_speaker.name} 的内部状态判断: {game_status}")

        print(f"  [阶段2: 记忆] 系统正在为双方生成记忆...")
        summary_prompt = MEMORY_SUMMARY_PROMPT.format(dialogue_text=dialogue_line)
        summary_response = call_ollama_with_retry(summary_prompt)
        summary = summary_response.get('summary', f'对话原文: {dialogue}') if summary_response else f'对话原文: {dialogue}'
        
        azriel.add_memory(summary, timestamp)
        lina.add_memory(summary, timestamp)
        print(f"    -> 生成记忆: \"{summary}\"")

        if game_status != "ongoing":
            print("\n" + "="*30)
            print("==          模 拟 结 束          ==")
            print("="*30)
            print(f"最终回合: {turn_count}")
            print(f"结束原因: 神父莱曼的内部状态最终确认为 '{game_status}'")
            print(f"莱曼最终思考: {thought}")
            
            if game_status == "TARGET_CONFIRMED":
                print("\n[胜负判定]: 莱曼找到了东方之子，【神父】获胜！")
            elif game_status == "TARGET_CLEARED":
                print("\n[胜负判定]: 莱曼排除了嫌疑，琳娜成功守护了秘密，【琳娜】获胜！")
            break

        current_speaker, other_speaker = other_speaker, current_speaker
        time.sleep(1)

    if turn_count >= MAX_TURNS_SAFETY_NET and game_status == "ongoing":
        print("\n" + "="*20 + "\n达到最大轮数限制，模拟自动终止。\n" + "="*20)

if __name__ == "__main__":
    run_simulation_v5_2()