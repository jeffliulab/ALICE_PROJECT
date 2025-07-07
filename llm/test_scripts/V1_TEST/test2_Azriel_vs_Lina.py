import requests
import json
import time
from datetime import datetime

# --- 配置 ---
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.1:8b-instruct-q4_K_M" 
MAX_TURNS_SAFETY_NET = 20
MAX_RETRIES = 2

# --- Prompt 模板 (V7.3) ---

# 1. 战略家Prompt: 只负责思考和判断
STRATEGIST_PROMPT = """
### 指令: 作为角色进行思考和状态评估
你正在深度扮演一个角色。请分析你的全部信息，并决定你接下来的内心想法和任务状态。

**规则:**
1.  **第一人称思考**: 你就是这个角色，必须使用“我”进行思考。
2.  **决策前分析**: 你的`thought`必须基于你对目标的当前信念。
3.  **状态判断**: 只有当你内心有了非常确切的结论时，才能改变`status`。
4.  **JSON格式**: 你的所有输出都必须是一个严格的、单一的JSON对象。

### 你的系统设定 (System)
{system}

### 你的自我/目标 (Ego)
{ego}

### 你对他人的信念档案 (Beliefs)
{beliefs}

### 上下文 (Context)
{context}

### 你的思考与判断 (返回一个JSON对象)
{{
  "thought": "（你基于信念的详细分析，以及你下一步行动的意图）",
  "status": "（从[\"ongoing\", \"TARGET_CONFIRMED\", \"TARGET_CLEARED\"]中选择）"
}}
"""

# 2. 演员Prompt: 只负责将想法转化为原始对话
ACTOR_PROMPT = """
### 指令: 作为角色说话
你正在扮演 {character_name}。你刚刚在脑中闪过了以下想法。请根据这个想法，生成一句具体、自然的原始对话。

**规则:**
1.  **自然对话**: 尽可能地模拟真实人物的口语。
2.  **JSON格式**: 你的所有输出都必须是一个严格的、单一的JSON对象。

### 你当下的内心想法
{thought}

### 你的原始对话 (返回一个JSON对象)
{{
  "raw_dialogue": "（你接下来要说的具体的话）"
}}
"""

# 3. 润色师Prompt: 只负责修正格式和内容
FORMATTER_PROMPT = """
### 指令: 润色并格式化对话
你是一个严谨的文本编辑器。请将以下原始对话润色成一句通顺、精炼、符合角色的最终对话。

**规则:**
1.  **修正优化**: 去除不必要的口头禅、修正语病。
2.  **只输出对话**: 不要添加任何解释或额外文字。
3.  **JSON格式**: 你的所有输出都必须是一个严格的、单一的JSON对象。

### 待处理的原始对话
{raw_dialogue}

### 修正后的最终对话 (返回一个JSON对象)
{{
  "polished_dialogue": "（修正后的最终对话）"
}}
"""

def call_ollama_with_retry(prompt, retries=MAX_RETRIES, model=MODEL_NAME):
    """
    具备重试和修正能力的通用Ollama调用函数
    """
    current_prompt = prompt
    raw_response_text = ""
    for attempt in range(retries + 1):
        is_correction_attempt = attempt > 0
        if is_correction_attempt:
            print(f"    >>> 正在进行第 {attempt} 次修正尝试...")
        
        try:
            payload = {"model": model, "prompt": current_prompt, "format": "json", "stream": False}
            response = requests.post(OLLAMA_URL, json=payload, timeout=120)
            response.raise_for_status()
            
            response_json = json.loads(response.text)
            raw_response_text = response_json.get("response", "")
            
            parsed_json = json.loads(raw_response_text)
            if is_correction_attempt:
                print("    >>> 修正成功！")
            return parsed_json

        except requests.exceptions.RequestException as e:
            print(f"!!! 网络错误: 调用Ollama API失败 - {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"!!! JSON解析错误 (尝试 {attempt + 1}/{retries + 1}): {e}")
            print(f"--- LLM原始返回内容 ---\n{raw_response_text}\n--------------------")
            
            if attempt < retries:
                current_prompt = f"""
                ### 指令
                你之前生成的文本不是有效的JSON。请严格修正以下文本的语法错误，并只返回修正后的、严格的JSON对象，不要包含任何解释或额外的文字。
                ### 有问题的文本:
                ```json
                {raw_response_text}
                ```
                ### 你的修正 (返回一个JSON对象):
                """
            else:
                print("!!! 已达到最大重试次数，修正失败。")
                return None
    return None

class Agent:
    def __init__(self, name, system_prompt, ego):
        self.name = name
        self.system_prompt = system_prompt
        self.ego = ego
        self.beliefs = {}

    def get_belief_about(self, target_name):
        if target_name not in self.beliefs:
            self.beliefs[target_name] = {
                "belief": "此人身份未知，需要通过对话进行初步观察。",
                "notes": []
            }
        return self.beliefs[target_name]

def run_simulation_v7_3():
    # --- 角色数据直接定义在脚本内部 ---
    azriel = Agent(
        name="神父莱曼",
        system_prompt="""
        - 你的公开身份: 新派驻到乌瓦村的神父，外表和蔼可亲。
        - 你的真实身份: 圣殿骑士团'裁决之剑'的秘密成员，冷酷无情。
        - 你的能力: '圣法术·摇摆钟'，可对无魔力抵抗者使用，强制获取近期记忆。
        """,
        ego={ "goal": "找出并确认乌瓦村的'东方之子'血脉。" }
    )

    lina = Agent(
        name="村民琳娜",
        system_prompt="""
        - 你的公开身份: 一个普通的农妇。
        - 你的真实身份: '东方之子'，拥有微弱的魔法。
        - 你的能力: 你的能力是'被动精神护盾'，天生对精神类魔法有抵抗力。你无法主动施法，但当受到精神攻击时，你会察觉到并能抵抗。
        """,
        ego={ "goal": "守护自己和女儿的秘密，不能被任何人发现。同时要查明新神父的真实意图。" }
    )
    
    conversation_log = []
    turn_count = 0
    game_status = "ongoing"
    context = "你们在一个安静的村庄广场初次相遇，对话刚刚开始。"

    print("="*20 + "\n乌瓦村的对话模拟 V7.3 (三段式LLM流水线)\n" + "="*20)
    
    current_speaker = azriel
    other_speaker = lina

    while turn_count < MAX_TURNS_SAFETY_NET and game_status == "ongoing":
        turn_count += 1
        print(f"\n\n- - - [ 回合 {turn_count} 开始 ] - - -")
        
        # --- 流水线步骤 1: 战略家LLM负责思考 ---
        print(f"  [阶段1: 战略思考] {current_speaker.name} 正在分析局势...")
        beliefs = current_speaker.get_belief_about(other_speaker.name)
        beliefs_text = json.dumps(beliefs, ensure_ascii=False, indent=2)
        
        strategist_prompt = STRATEGIST_PROMPT.format(
            system=current_speaker.system_prompt,
            ego=json.dumps(current_speaker.ego, ensure_ascii=False),
            beliefs=beliefs_text,
            context=context
        )
        strategy_response = call_ollama_with_retry(strategist_prompt)

        if not strategy_response:
            print("    -> 警告: 战略思考失败，跳过此回合。")
            current_speaker, other_speaker = other_speaker, current_speaker
            time.sleep(1)
            continue
            
        thought = strategy_response.get('thought', '我需要整理一下思绪...')
        status = strategy_response.get('status', 'ongoing')
        print(f"    -> 内心思考: {thought}")

        if current_speaker.name == azriel.name:
            game_status = status
            print(f"    -> 莱曼状态判断: {game_status}")

        # --- 流水线步骤 2: 演员LLM负责生成原始对话 ---
        print(f"  [阶段2: 对话生成] {current_speaker.name} 正在组织语言...")
        actor_prompt = ACTOR_PROMPT.format(character_name=current_speaker.name, thought=thought)
        actor_response = call_ollama_with_retry(actor_prompt)

        raw_dialogue = "(沉默...)" if not actor_response else actor_response.get('raw_dialogue', '(一时语塞...)')
        print(f"    -> 原始对话: \"{raw_dialogue}\"")

        # --- 流水线步骤 3: 润色师LLM负责修正和最终输出 ---
        print(f"  [阶段3: 内容润色] 系统正在优化输出...")
        formatter_prompt = FORMATTER_PROMPT.format(raw_dialogue=raw_dialogue)
        formatter_response = call_ollama_with_retry(formatter_prompt)

        polished_dialogue = raw_dialogue if not formatter_response else formatter_response.get('polished_dialogue', raw_dialogue)
        
        dialogue_line = f"{current_speaker.name}: \"{polished_dialogue}\""
        conversation_log.append(dialogue_line)
        context = f"上一句是: {dialogue_line}"
        print(f"    -> 最终对话: {dialogue_line}")

        # --- 结束条件检查 ---
        if game_status != "ongoing":
            print("\n" + "="*30)
            print("==          模 拟 结 束          ==")
            # ... (结束逻辑和之前一样) ...
            break

        current_speaker, other_speaker = other_speaker, current_speaker
        time.sleep(1)

    if turn_count >= MAX_TURNS_SAFETY_NET and game_status == "ongoing":
        print("\n" + "="*20 + "\n达到最大轮数限制，模拟自动终止。\n" + "="*20)


if __name__ == "__main__":
    run_simulation_v7_3()