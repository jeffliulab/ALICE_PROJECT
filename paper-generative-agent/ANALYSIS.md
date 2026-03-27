# Generative Agents 论文与代码深度分析

> 本文档是对 Park et al. (2023) "Generative Agents: Interactive Simulacra of Human Behavior" 论文及其开源代码库的深度分析，作为 ALICE PROJECT 重构的核心参考。

**论文引用**: Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, Michael S. Bernstein. "Generative Agents: Interactive Simulacra of Human Behavior." UIST '23, October 29-November 1, 2023, San Francisco, CA, USA.

**代码库**: https://github.com/joonspk-research/generative_agents

---

## 1. 论文总览

### 1.1 核心贡献

本论文提出了一种 **生成式代理（Generative Agent）** 架构，使 LLM 驱动的虚拟角色能够展示可信的类人行为。核心创新在于三个相互关联的模块：

1. **记忆流（Memory Stream）**：用自然语言记录代理的全部经历
2. **检索（Retrieval）**：基于时近性、重要性、相关性三因子检索相关记忆
3. **反思（Reflection）**：将底层记忆综合为高层次洞见

### 1.2 Smallville 世界

论文构建了一个名为 **Smallville** 的虚拟小镇沙盒环境，包含 **25 个代理**，它们：
- 每天起床、做早餐、去上班
- 在合适的时间和地点进行社交互动
- 对彼此形成看法和关系
- 协调复杂的社会活动（如情人节派对）

### 1.3 关键发现

- **信息扩散**：一个代理的信息（如派对邀请）可以通过社交网络自发传播
- **关系演化**：代理之间形成新的友谊和浪漫关系
- **涌现行为**：5 个代理在没有预编程的情况下成功协调出席了派对
- **消融实验**：移除记忆、反思或计划中的任何一个组件都会显著降低行为可信度

---

## 2. 认知架构总览

### 2.1 三层架构

```
┌─────────────────────────────────────────┐
│         高阶认知 (Higher Cognition)       │
│   反思 Reflection  |  计划 Planning      │
│   反应 Reaction    |  对话 Conversation   │
├─────────────────────────────────────────┤
│         检索 (Retrieval)                 │
│   recency + importance + relevance      │
├─────────────────────────────────────────┤
│         记忆流 (Memory Stream)           │
│   event nodes | thought nodes | chat    │
│   嵌入向量 | 重要性评分 | 时间戳         │
└─────────────────────────────────────────┘
```

### 2.2 主循环（每个时间步，每个代理）

```
perceive(maze) → retrieve(perceived) → plan(maze, personas, new_day, retrieved) → reflect() → execute(maze, personas, plan)
```

**原始代码位置**: `persona/persona.py` 的 `move()` 方法（第 185-231 行）

```python
# persona.py: move() 方法
def move(self, maze, personas, curr_tile, curr_time):
    self.scratch.curr_tile = curr_tile

    # 判断是否新的一天
    new_day = False
    if not self.scratch.curr_time:
        new_day = "First day"
    elif (self.scratch.curr_time.strftime('%A %B %d')
          != curr_time.strftime('%A %B %d')):
        new_day = "New day"
    self.scratch.curr_time = curr_time

    # 核心认知序列
    perceived = self.perceive(maze)
    retrieved = self.retrieve(perceived)
    plan = self.plan(maze, personas, new_day, retrieved)
    self.reflect()
    return self.execute(maze, personas, plan)
```

**关键观察**：
- `new_day` 有三种值：`False`（不是新一天）、`"First day"`（第一天）、`"New day"`（新一天）
- `perceive()` 返回 `ConceptNode` 列表
- `retrieve()` 接收感知到的节点，返回相关记忆的字典
- `plan()` 返回目标地址字符串（`persona.scratch.act_address`）
- `reflect()` 无返回值，直接修改记忆
- `execute()` 返回 `(next_tile, pronunciatio, description)` 三元组

---

## 3. 记忆流 (Memory Stream / Associative Memory)

### 3.1 ConceptNode 数据结构

**原始代码位置**: `persona/memory_structures/associative_memory.py`

```python
class ConceptNode:
    def __init__(self, node_id, node_count, type_count, node_type, depth,
                 created, expiration, s, p, o,
                 description, embedding_key, poignancy, keywords, filling):
        self.node_id = node_id          # "node_1", "node_2", ...
        self.node_count = node_count    # 全局序号
        self.type_count = type_count    # 类型内序号
        self.type = node_type           # "event" | "thought" | "chat"
        self.depth = depth              # 0=event, 1+=thought/reflection

        self.created = created          # datetime 创建时间
        self.expiration = expiration    # datetime 过期时间（可为None）
        self.last_accessed = self.created  # datetime 最后访问时间（检索时更新）

        self.subject = s                # 主语 (e.g., "Isabella Rodriguez")
        self.predicate = p              # 谓语 (e.g., "is")
        self.object = o                 # 宾语 (e.g., "cooking breakfast")

        self.description = description  # 完整自然语言描述
        self.embedding_key = embedding_key  # 嵌入向量的键
        self.poignancy = poignancy      # 重要性评分 1-10
        self.keywords = keywords        # 关键词集合（用于快速索引）
        self.filling = filling          # evidence node_id 列表（thought 的证据链）
```

### 3.2 AssociativeMemory 类

```python
class AssociativeMemory:
    def __init__(self, f_saved):
        self.id_to_node = dict()        # node_id -> ConceptNode

        self.seq_event = []             # 按时间排序的 event 列表
        self.seq_thought = []           # 按时间排序的 thought 列表
        self.seq_chat = []              # 按时间排序的 chat 列表

        self.kw_to_event = dict()       # keyword -> [ConceptNode] 事件索引
        self.kw_to_thought = dict()     # keyword -> [ConceptNode] 思想索引
        self.kw_to_chat = dict()        # keyword -> [ConceptNode] 对话索引

        self.kw_strength_event = dict() # keyword -> int 关键词强度
        self.kw_strength_thought = dict()

        self.embeddings = dict()        # embedding_key -> vector
```

### 3.3 三种节点类型

| 类型 | depth | 说明 | 示例 |
|------|-------|------|------|
| **event** | 0 | 感知到的事件 | "Isabella Rodriguez is cooking breakfast" |
| **thought** | 1+ | 反思产生的洞见 | "Isabella values community and relationships" |
| **chat** | 0 | 对话记录 | "Isabella chatted with Maria about the party" |

### 3.4 关键词索引机制

原始代码使用 **关键词到节点的映射** 进行快速检索：
- `kw_to_event[keyword]` → 与该关键词相关的所有事件节点
- `kw_strength_event[keyword]` → 该关键词出现的总次数

这是一个两层检索策略：先用关键词快速筛选，再用嵌入向量精确排序。

### 3.5 嵌入向量存储

- 每个记忆节点有一个 `embedding_key`（通常是描述文本本身）
- 嵌入向量存储在 `self.embeddings` 字典中
- 原始实现使用 OpenAI 的 `text-embedding-ada-002` 模型
- 嵌入会被缓存：如果 `embedding_key` 已存在于字典中，则复用

### 3.6 持久化格式

记忆流保存为三个 JSON 文件：
- `nodes.json`: 所有节点的序列化数据
- `embeddings.json`: 所有嵌入向量
- `kw_strength.json`: 关键词强度数据

---

## 4. 检索公式 (Retrieval) — 最关键部分

### 4.1 论文描述的公式

```
score = α_recency × recency + α_importance × importance + α_relevance × relevance
```

论文描述所有 α 权重均为 1（可调），但实际代码使用了不同的权重。

### 4.2 原始代码的精确实现

**原始代码位置**: `persona/cognitive_modules/retrieve.py` 的 `new_retrieve()` 函数（第 199-271 行）

```python
def new_retrieve(persona, focal_points, n_count=30):
    retrieved = dict()
    for focal_pt in focal_points:
        # 获取所有非 idle 的 event + thought 节点，按 last_accessed 排序
        nodes = [[i.last_accessed, i]
                  for i in persona.a_mem.seq_event + persona.a_mem.seq_thought
                  if "idle" not in i.embedding_key]
        nodes = sorted(nodes, key=lambda x: x[0])
        nodes = [i for created, i in nodes]

        # 计算三个分量，各自归一化到 [0, 1]
        recency_out = extract_recency(persona, nodes)
        recency_out = normalize_dict_floats(recency_out, 0, 1)
        importance_out = extract_importance(persona, nodes)
        importance_out = normalize_dict_floats(importance_out, 0, 1)
        relevance_out = extract_relevance(persona, nodes, focal_pt)
        relevance_out = normalize_dict_floats(relevance_out, 0, 1)

        # 加权组合
        gw = [0.5, 3, 2]  # [recency_global_weight, relevance_gw, importance_gw]
        master_out = dict()
        for key in recency_out.keys():
            master_out[key] = (persona.scratch.recency_w * recency_out[key] * gw[0]
                             + persona.scratch.relevance_w * relevance_out[key] * gw[1]
                             + persona.scratch.importance_w * importance_out[key] * gw[2])

        # 取 top n_count
        master_out = top_highest_x_values(master_out, n_count)
        master_nodes = [persona.a_mem.id_to_node[key] for key in master_out.keys()]

        # 更新 last_accessed
        for n in master_nodes:
            n.last_accessed = persona.scratch.curr_time

        retrieved[focal_pt] = master_nodes
    return retrieved
```

### 4.3 Recency（时近性）的精确算法

```python
def extract_recency(persona, nodes):
    # nodes 已按 last_accessed 升序排列（最旧的在前）
    # 使用索引位置的指数衰减，而非基于时间差
    recency_vals = [persona.scratch.recency_decay ** i
                    for i in range(1, len(nodes) + 1)]
    recency_out = dict()
    for count, node in enumerate(nodes):
        recency_out[node.node_id] = recency_vals[count]
    return recency_out
```

**关键发现**：
- `recency_decay` 默认值为 **0.99**（scratch.py 第 60 行）
- 排序基于 `last_accessed`（最后访问时间），不是 `created`（创建时间）
- **衰减是基于排序索引的**：第 1 旧的节点得分 `0.99^1`，第 2 旧的得分 `0.99^2`...
- 这意味着最新访问的节点在列表末尾，得分最低（`0.99^n`），而最旧的节点在列表前端，得分最高（`0.99^1`）
- **但！** 归一化后（normalize_dict_floats 到 [0,1]），最旧的变成 1，最新的变成 0...
- **等等**，再仔细看：nodes 按 `last_accessed` 升序排列，index 0 = 最旧。`recency_vals[0] = 0.99^1 = 0.99`（最高），`recency_vals[-1] = 0.99^n`（最低）。所以最旧的节点反而得到更高的 raw recency score。
- **但是！** 归一化后最旧的 = 1.0, 最新的 ≈ 0.0。这看起来是反直觉的。
- **实际上**：这段代码中，`nodes` 是按 `last_accessed` 升序排的。索引 0 是最旧的。`0.99^1` 给最旧的，`0.99^n` 给最新的。归一化后，最旧的 score 最高。

**重要纠正**：仔细重读代码后，注意到 `recency_vals` 列表的第一个元素是 `0.99^1`（最大值），分配给 `nodes[0]`（最旧的节点）。这确实意味着最旧的节点获得最高的 recency 分数。但归一化后，所有值被映射到 [0,1]，且 `gw[0] = 0.5` 权重较小。总体上，relevance (`gw[1]=3`) 和 importance (`gw[2]=2`) 权重远大于 recency (`gw[0]=0.5`)，因此检索结果主要由相关性和重要性驱动。

### 4.4 Importance（重要性）的精确算法

```python
def extract_importance(persona, nodes):
    importance_out = dict()
    for count, node in enumerate(nodes):
        importance_out[node.node_id] = node.poignancy  # 直接使用原始评分
    return importance_out
```

- 直接使用节点的 `poignancy` 值（1-10 整数）
- 通过 `normalize_dict_floats` 归一化到 [0, 1]

**重要性评分的生成**（perceive.py）：
- 如果描述包含 "is idle"，直接返回 1
- 否则调用 LLM prompt `run_gpt_prompt_event_poignancy()` 评分

### 4.5 Relevance（相关性）的精确算法

```python
def extract_relevance(persona, nodes, focal_pt):
    focal_embedding = get_embedding(focal_pt)  # 获取查询的嵌入向量
    relevance_out = dict()
    for count, node in enumerate(nodes):
        node_embedding = persona.a_mem.embeddings[node.embedding_key]
        relevance_out[node.node_id] = cos_sim(node_embedding, focal_embedding)
    return relevance_out
```

- 使用余弦相似度计算查询与记忆的语义相关性
- 原始实现使用 OpenAI 的 `text-embedding-ada-002` 生成嵌入
- 归一化到 [0, 1]

### 4.6 归一化函数

```python
def normalize_dict_floats(d, target_min, target_max):
    min_val = min(val for val in d.values())
    max_val = max(val for val in d.values())
    range_val = max_val - min_val
    if range_val == 0:
        for key in d: d[key] = (target_max - target_min) / 2
    else:
        for key in d:
            d[key] = ((d[key] - min_val) * (target_max - target_min)
                      / range_val + target_min)
    return d
```

- 所有三个分量独立归一化到 [0, 1]
- 如果所有值相同（range=0），则全部设为中间值 0.5

### 4.7 最终权重

```python
gw = [0.5, 3, 2]  # 全局权重：[recency, relevance, importance]
# scratch.py 中的 per-persona 权重默认均为 1：
# self.recency_w = 1
# self.relevance_w = 1
# self.importance_w = 1
```

**最终公式**:
```
score = 1.0 * recency_normalized * 0.5
       + 1.0 * relevance_normalized * 3.0
       + 1.0 * importance_normalized * 2.0
```

即 **relevance 权重最大（3.0）> importance（2.0）> recency（0.5）**。

### 4.8 两种检索函数

原始代码有两个检索函数：
1. **`retrieve()`**（旧版，第 16 行）：基于关键词的检索（`retrieve_relevant_events/thoughts`），用于 perceive 后的初步检索
2. **`new_retrieve()`**（新版，第 199 行）：基于三因子评分的检索，用于反思和对话中的深度检索

`persona.py` 的 `retrieve()` 方法调用的是**旧版** `retrieve()`，而反思和对话模块调用的是 `new_retrieve()`。

---

## 5. 反思机制 (Reflection)

### 5.1 触发条件

**原始代码位置**: `persona/cognitive_modules/reflect.py`

```python
def reflection_trigger(persona):
    if (persona.scratch.importance_trigger_curr <= 0 and
        [] != persona.a_mem.seq_event + persona.a_mem.seq_thought):
        return True
    return False
```

- `importance_trigger_max` = **150**（scratch.py 第 61 行）
- 每次感知新事件时，`importance_trigger_curr -= event_poignancy`
- 当 `importance_trigger_curr <= 0` 时触发反思
- 触发后重置：`importance_trigger_curr = importance_trigger_max`

### 5.2 反思流程

**三步流程**：

**Step 1: 生成焦点问题**
```python
def generate_focal_points(persona, n=3):
    # 取最近的 importance_ele_n 个节点
    nodes = [sorted event+thought nodes by last_accessed]
    statements = ""
    for node in nodes[-1 * persona.scratch.importance_ele_n:]:
        statements += node.embedding_key + "\n"
    return run_gpt_prompt_focal_pt(persona, statements, n)  # 返回 3 个问题
```

**Step 2: 检索相关证据**
```python
retrieved = new_retrieve(persona, focal_points)  # 对每个焦点问题检索记忆
```

**Step 3: 生成洞见并存储**
```python
def run_reflect(persona):
    focal_points = generate_focal_points(persona, 3)
    retrieved = new_retrieve(persona, focal_points)

    for focal_pt, nodes in retrieved.items():
        thoughts = generate_insights_and_evidence(persona, nodes, 5)
        for thought, evidence in thoughts.items():
            # 为每个洞见生成 (s, p, o) 三元组
            s, p, o = generate_action_event_triple(thought, persona)
            # 评估重要性
            thought_poignancy = generate_poig_score(persona, "thought", thought)
            # 生成嵌入
            thought_embedding_pair = (thought, get_embedding(thought))
            # 存入记忆流，带有证据链接
            persona.a_mem.add_thought(created, expiration, s, p, o,
                                      thought, keywords, thought_poignancy,
                                      thought_embedding_pair, evidence)
```

### 5.3 对话结束后的特殊反思

在 `reflect()` 函数中，还有一段特殊逻辑：当对话即将结束时（`chatting_end_time` 即将到达），会生成：
1. **planning_thought**: 基于对话内容的计划性思考
2. **memo_thought**: 对话的个人备忘录

两者都以 thought 节点存入记忆流，并引用对话节点作为证据。

### 5.4 递归反思

thought 节点可以被后续的 `new_retrieve()` 检索到，这意味着反思可以建立在之前的反思之上，形成 **递归抽象层级**。

---

## 6. 计划系统 (Planning)

### 6.1 三级分解层次

**原始代码位置**: `persona/cognitive_modules/plan.py`

```
Level 1: Daily Plan（日计划）
    ↓ generate_first_daily_plan()
    "wake up at 6am, have breakfast, work on painting, lunch, ..."

Level 2: Hourly Schedule（小时日程）
    ↓ generate_hourly_schedule()
    [["sleeping", 360], ["morning routine", 60], ["work", 240], ...]

Level 3: Task Decomposition（5-15分钟分解）
    ↓ generate_task_decomp()
    [["get out of bed", 5], ["brush teeth", 10], ["make breakfast", 15], ...]
```

### 6.2 长期计划 (_long_term_planning)

在每个新一天的开始触发：

```python
def _long_term_planning(persona, new_day):
    wake_up_hour = generate_wake_up_hour(persona)

    if new_day == "First day":
        persona.scratch.daily_req = generate_first_daily_plan(persona, wake_up_hour)
    elif new_day == "New day":
        revise_identity(persona)  # 基于昨天的经历修订身份认知
        # daily_req 保持不变（TODO 标记 in code）

    # 生成小时级日程
    persona.scratch.f_daily_schedule = generate_hourly_schedule(persona, wake_up_hour)
    persona.scratch.f_daily_schedule_hourly_org = persona.scratch.f_daily_schedule[:]

    # 将计划存入记忆流
    persona.a_mem.add_thought(...)  # "This is X's plan for today: ..."
```

### 6.3 小时日程生成

```python
def generate_hourly_schedule(persona, wake_up_hour):
    # 逐小时生成活动（24 小时循环）
    # 起床前的小时全部填 "sleeping"
    # 之后每小时调用 LLM 生成活动
    # 结果压缩：相邻相同活动合并
    # 转换为分钟粒度
    # 输出: [["sleeping", 360], ["morning routine", 60], ...]
```

### 6.4 任务分解（关键的第三级）

```python
def _determine_action(persona, maze):
    curr_index = persona.scratch.get_f_daily_schedule_index()
    curr_index_60 = persona.scratch.get_f_daily_schedule_index(advance=60)

    # 对当前和下一个小时的活动进行分解
    # 条件：时长 >= 60 分钟 且 不是 "sleeping"
    if determine_decomp(act_desp, act_dura):
        persona.scratch.f_daily_schedule[curr_index:curr_index+1] = (
            generate_task_decomp(persona, act_desp, act_dura))

    # 确保日程总和 = 1440 分钟（24小时）
    x_emergency = sum(dur for _, dur in persona.scratch.f_daily_schedule)
    if 1440 - x_emergency > 0:
        persona.scratch.f_daily_schedule += [["sleeping", 1440 - x_emergency]]
```

**这是 ALICE 缺失的关键机制**：原始代码在运行时动态将大块活动分解为 5-15 分钟的细粒度任务。

### 6.5 地点选择（四级地址系统）

```python
# 完整地址格式: "{world}:{sector}:{arena}:{game_object}"
act_world = maze.access_tile(persona.scratch.curr_tile)["world"]
act_sector = generate_action_sector(act_desp, persona, maze)
act_arena = generate_action_arena(act_desp, persona, maze, act_world, act_sector)
act_game_object = generate_action_game_object(act_desp, f"{world}:{sector}:{arena}", persona, maze)
new_address = f"{act_world}:{act_sector}:{act_arena}:{act_game_object}"
```

每一级都调用 LLM 从可用选项中选择，使用角色的空间记忆来确定可访问的地点。

### 6.6 动作完成检测

```python
# scratch.py
def act_check_finished(self):
    # 当当前动作的时间用完时返回 True
    if not self.act_start_time: return True
    if self.curr_time >= (self.act_start_time
                          + timedelta(minutes=self.act_duration)):
        return True
    return False
```

**plan() 主函数的逻辑**：
1. 如果是新一天 → 生成长期计划
2. 如果当前动作已完成 (`act_check_finished()`) → 选择下一个动作 (`_determine_action`)
3. 如果检索到需要回应的事件 → 决定反应方式

---

## 7. 反应与重新计划 (Reaction & Replanning)

### 7.1 事件选择

```python
def _choose_retrieved(persona, retrieved):
    # 1. 过滤掉自身事件
    for event_desc, rel_ctx in copy_retrieved.items():
        if rel_ctx["curr_event"].subject == persona.name:
            del retrieved[event_desc]

    # 2. 优先选择其他 persona 的事件（不含 ":"）
    priority = []
    for event_desc, rel_ctx in retrieved.items():
        if ":" not in curr_event.subject and curr_event.subject != persona.name:
            priority += [rel_ctx]
    if priority: return random.choice(priority)

    # 3. 跳过 idle 事件
    # 4. 随机选择一个非 idle 事件
```

**关键**：原始代码**明确过滤掉自身事件**（`curr_event.subject == persona.name`），ALICE 缺少这个过滤。

### 7.2 反应决策 (_should_react)

两种反应类型：

**对话反应 (lets_talk)**：
```python
def lets_talk(init_persona, target_persona, retrieved):
    # 前置条件检查：
    # - 双方都有 act_address 和 act_description
    # - 双方都不在睡觉
    # - 不是 23 点
    # - 目标不在 <waiting> 状态
    # - 双方都没在和别人聊天
    # - 不在冷却期内（chatting_with_buffer）
    if generate_decide_to_talk(init_persona, target_persona, retrieved):
        return True
    return False
```

**等待反应 (lets_react)**：
```python
def lets_react(init_persona, target_persona, retrieved):
    # 额外条件：
    # - init_persona 有 planned_path（正在移动中）
    # - 双方在同一 act_address
    react_mode = generate_decide_to_react(init_persona, target_persona, retrieved)
    if react_mode == "1":  # wait
        return f"wait: {wait_until_time}"
    elif react_mode == "2":  # do other things
        return False
```

### 7.3 对话反应 (_chat_react)

当决定聊天时：
1. 调用 `generate_convo()` 生成完整对话
2. 调用 `generate_convo_summary()` 生成摘要
3. 对双方都调用 `_create_react()` 来：
   - 设置 `act_address = "<persona> {target_name}"`
   - 设置 `chatting_with_buffer[target_name] = 800`（冷却值极高）
   - 重新分解当前时间段的日程

### 7.4 重新计划 (_create_react)

```python
def _create_react(persona, inserted_act, inserted_act_dur, ...):
    # 找到当前日程中受影响的时间段
    # 调用 generate_new_decomp_schedule() 重新生成该时间段的日程
    # 将新动作插入日程
    p.scratch.f_daily_schedule[start_index:end_index] = ret
    p.scratch.add_new_action(...)
```

**这意味着对话/等待事件会导致日程的部分重新生成，而不仅仅是简单地暂停。**

---

## 8. 对话系统 (Conversation)

### 8.1 对话版本

原始代码有两个版本：
- **v1 (`agent_chat_v1`)**: 批量生成整个对话
- **v2 (`agent_chat_v2`)**: 逐回合迭代生成（实际使用的版本）

### 8.2 agent_chat_v2 详细流程

```python
def agent_chat_v2(maze, init_persona, target_persona):
    curr_chat = []
    for i in range(8):  # 最多 8 轮
        # --- init_persona 说话 ---
        # 1. 检索关于对方的记忆
        focal_points = [f"{target_persona.scratch.name}"]
        retrieved = new_retrieve(init_persona, focal_points, 50)

        # 2. 生成关系摘要
        relationship = generate_summarize_agent_relationship(
            init_persona, target_persona, retrieved)

        # 3. 用关系 + 对方状态 + 最近对话作为焦点点检索
        focal_points = [relationship,
                        f"{target_persona.name} is {target_persona.scratch.act_description}",
                        last_chat]  # 最近 4 轮对话
        retrieved = new_retrieve(init_persona, focal_points, 15)

        # 4. 生成一句话
        utt, end = generate_one_utterance(maze, init_persona, target_persona,
                                           retrieved, curr_chat)
        curr_chat += [[init_persona.scratch.name, utt]]
        if end: break

        # --- target_persona 说话 ---
        # 对称的流程（角色互换）
        ...

    return curr_chat
```

### 8.3 对话长度计算

```python
convo_length = math.ceil(int(len(all_utt) / 8) / 30)
```
基于对话文本总长度估算持续时间（分钟）。

### 8.4 对话存储

对话结束后：
- 对双方都设置 `chatting_with_buffer[other_name] = 800`
- 对话内容存储在 `persona.scratch.chat` 中
- 在 `reflect()` 中，对话结束时会生成 planning_thought 和 memo_thought

---

## 9. 感知系统 (Perceive)

### 9.1 感知流程

**原始代码位置**: `persona/cognitive_modules/perceive.py`

```python
def perceive(persona, maze):
    # 1. 感知空间 - 更新空间记忆树
    nearby_tiles = maze.get_nearby_tiles(persona.scratch.curr_tile,
                                          persona.scratch.vision_r)
    for tile in nearby_tiles:
        tile_details = maze.access_tile(tile)
        # 更新 persona.s_mem.tree（世界→区域→地点→物体）

    # 2. 感知事件
    # 只感知同一 arena 内的事件
    curr_arena_path = maze.get_tile_path(persona.scratch.curr_tile, "arena")
    for tile in nearby_tiles:
        if maze.get_tile_path(tile, "arena") == curr_arena_path:
            # 按距离排序，取 att_bandwidth 个最近的
            ...

    # 3. 过滤已感知的事件（retention 机制）
    latest_events = persona.a_mem.get_summarized_latest_events(persona.scratch.retention)
    if p_event not in latest_events:
        # 生成嵌入和重要性评分
        event_embedding = get_embedding(desc)
        event_poignancy = generate_poig_score(persona, "event", desc)
        # 存入记忆流
        persona.a_mem.add_event(...)
        # 更新反思触发器
        persona.scratch.importance_trigger_curr -= event_poignancy
```

### 9.2 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `vision_r` | 4 | 视野半径（tiles） |
| `att_bandwidth` | 3 | 注意力带宽（最多同时感知的事件数） |
| `retention` | 5 | 记忆保持（最近 N 个事件不重复感知） |

### 9.3 自身事件过滤

**重要**：perceive 阶段不过滤自身事件。自身事件在 `_choose_retrieved()` 阶段才被过滤。但感知阶段自身事件也会被存入记忆流（作为自我意识的一部分），只是不会触发反应。

---

## 10. 执行系统 (Execute)

### 10.1 执行流程

```python
def execute(persona, maze, personas, plan):
    if not persona.scratch.act_path_set:
        # 解析 plan 字符串确定目标 tile
        if "<persona>" in plan:       # 走向另一个 persona
            target_tiles = [midpoint_of_path_to_target]
        elif "<waiting>" in plan:      # 在原地等待
            target_tiles = [[x, y]]
        elif "<random>" in plan:       # 随机选择目标 tile
            target_tiles = random.sample(maze.address_tiles[plan], 1)
        else:                          # 正常导航到地址
            target_tiles = maze.address_tiles[plan]

        # A* 寻路
        path = path_finder(maze.collision_maze, curr_tile, closest_target, collision_block_id)
        persona.scratch.planned_path = path[1:]  # 去掉当前 tile
        persona.scratch.act_path_set = True

    # 每步走一格
    ret = persona.scratch.curr_tile
    if persona.scratch.planned_path:
        ret = persona.scratch.planned_path[0]
        persona.scratch.planned_path = persona.scratch.planned_path[1:]

    return ret, persona.scratch.act_pronunciatio, description
```

### 10.2 plan 字符串的格式

| 格式 | 含义 | 示例 |
|------|------|------|
| `world:sector:arena:object` | 正常地址 | `"the ville:Hobbs Cafe:cafe:counter"` |
| `<persona> Name` | 走向另一个角色 | `"<persona> Maria Lopez"` |
| `<waiting> x y` | 在 (x,y) 处等待 | `"<waiting> 50 34"` |
| `...:object:<random>` | 随机选一个 tile | `"the ville:park:garden:<random>"` |

---

## 11. Prompt 模板详解

### 11.1 Prompt 架构

**原始代码位置**: `persona/prompt_template/`

```
prompt_template/
├── run_gpt_prompt.py       # 所有 prompt 构造和解析函数
├── gpt_structure.py        # LLM API 调用封装
├── print_prompt.py         # 调试输出
├── v1/                     # 旧版 prompt 模板
├── v2/                     # 中间版本
├── v3_ChatGPT/             # ChatGPT 版本 prompt 模板（最新）
└── safety/                 # 安全检查 prompt
```

### 11.2 Prompt 模式

每个 prompt 函数遵循统一模式：
```python
def run_gpt_prompt_xxx(persona, ...):
    def create_prompt_input(persona, ...):
        # 构造 prompt 模板的输入变量列表
        return [var1, var2, ...]

    def __func_clean_up(gpt_response, prompt=""):
        # 解析 LLM 输出
        return parsed_result

    def __func_validate(gpt_response, prompt=""):
        # 验证输出是否合法
        try: __func_clean_up(gpt_response)
        except: return False
        return True

    def get_fail_safe():
        # 返回默认值（LLM 失败时使用）
        return default_value

    # 使用模板文件 + 输入变量生成完整 prompt
    prompt = generate_prompt(prompt_input, prompt_template_file)
    # 安全调用 LLM（带重试和验证）
    output = safe_generate_response(prompt, gpt_param, retries, fail_safe,
                                     validate_fn, cleanup_fn)
    return output
```

### 11.3 关键 Prompt 列表

| Prompt 函数 | 用途 | 模板路径 |
|------------|------|----------|
| `run_gpt_prompt_wake_up_hour` | 生成起床时间 | `v2/wake_up_hour_v1.txt` |
| `run_gpt_prompt_daily_plan` | 生成日计划 | `v2/daily_planning_v6.txt` |
| `run_gpt_prompt_generate_hourly_schedule` | 生成小时日程 | `v2/hourly_schedule_v2.txt` |
| `run_gpt_prompt_task_decomp` | 任务分解 | `v2/task_decomp_v3.txt` |
| `run_gpt_prompt_action_sector` | 选择区域 | `v2/action_location_sector_v1.txt` |
| `run_gpt_prompt_action_arena` | 选择地点 | `v2/action_location_object_vMar11.txt` |
| `run_gpt_prompt_action_game_object` | 选择物体 | `v2/action_location_object_vMar11.txt` |
| `run_gpt_prompt_pronunciatio` | 生成 emoji | `v2/generate_pronunciatio_v1.txt` |
| `run_gpt_prompt_event_triple` | 生成事件三元组 | `v2/generate_event_triple_v1.txt` |
| `run_gpt_prompt_event_poignancy` | 评估事件重要性 | `v2/poignancy_event_v1.txt` |
| `run_gpt_prompt_focal_pt` | 生成反思焦点 | `v2/generate_focal_pt_v1.txt` |
| `run_gpt_prompt_insight_and_guidance` | 生成洞见 | `v2/insight_and_evidence_v1.txt` |
| `run_gpt_prompt_decide_to_talk` | 决定是否对话 | `v2/decide_to_talk_v2.txt` |
| `run_gpt_prompt_decide_to_react` | 决定反应类型 | `v2/decide_to_react_v1.txt` |
| `run_gpt_prompt_new_decomp_schedule` | 重新分解日程 | `v2/new_decomp_schedule_v1.txt` |
| `run_gpt_prompt_summarize_conversation` | 对话摘要 | `v2/summarize_chat_v1.txt` |
| `run_gpt_generate_iterative_chat_utt` | 迭代生成对话 | `v3_ChatGPT/iterative_convo_v1.txt` |

### 11.4 safe_generate_response 机制

```python
def safe_generate_response(prompt, gpt_param, retries, fail_safe,
                            validate_fn, cleanup_fn):
    for attempt in range(retries):
        response = GPT_request(prompt, gpt_param)
        if validate_fn(response):
            return cleanup_fn(response)
    return fail_safe  # 所有重试都失败时返回安全默认值
```

---

## 12. 关键常量与参数对照表

| 参数 | 原始代码值 | 位置 | 说明 |
|------|-----------|------|------|
| `vision_r` | 4 | scratch.py:19 | 视野半径 |
| `att_bandwidth` | 3 | scratch.py:21 | 注意力带宽 |
| `retention` | 5 | scratch.py:23 | 事件保持数 |
| `recency_w` | 1 | scratch.py:57 | 时近性权重（per-persona） |
| `relevance_w` | 1 | scratch.py:58 | 相关性权重（per-persona） |
| `importance_w` | 1 | scratch.py:59 | 重要性权重（per-persona） |
| `recency_decay` | 0.99 | scratch.py:60 | 时近性衰减因子 |
| `importance_trigger_max` | 150 | scratch.py:61 | 反思触发阈值 |
| `thought_count` | 5 | scratch.py:64 | 反思生成的思想数量 |
| `concept_forget` | 100 | scratch.py:49 | 概念遗忘阈值 |
| `daily_reflection_time` | 180 | scratch.py:50 | 每日反思时间（分钟） |
| `daily_reflection_size` | 5 | scratch.py:51 | 每日反思规模 |
| `gw` (global weights) | [0.5, 3, 2] | retrieve.py:244 | 全局检索权重 [recency, relevance, importance] |
| `n_count` (retrieve) | 30 | retrieve.py:199 | 默认检索数量 |
| `chatting_with_buffer` | 800 | plan.py:888 | 对话冷却步数 |
| `sec_per_step` | 10 | reverie meta.json | 每步游戏秒数 |
| `max_convo_turns` | 8 | converse.py:130 | 最大对话轮数 |

---

## 13. 评估方法与发现

### 13.1 受控评估

- **方法**: 100 名参与者的 within-subjects 研究
- **条件对比**:
  1. 完整架构
  2. 去除记忆/检索
  3. 去除反思
  4. 去除计划
  5. 人类撰写的基线
- **结果**: 完整架构显著优于所有消融版本

### 13.2 端到端评估（情人节派对实验）

- 25 个代理运行 2 个游戏日
- 唯一的用户指令：Isabella 想举办情人节派对
- **观测到的涌现行为**:
  - Isabella 决定举办派对 → 邀请 Maria
  - Maria 邀请 Klaus（她对他有好感）
  - Klaus 决定参加并准备
  - 5 个代理自发协调时间出席
  - 信息通过社交网络扩散

### 13.3 消融实验结论

| 移除的组件 | 影响 |
|-----------|------|
| 记忆流 | 行为不连贯，忘记之前的交互 |
| 反思 | 无法形成高层次理解，行为浅薄 |
| 计划 | 行为无组织，无法维持日常生活 |

---

## 14. ALICE PROJECT vs 原论文 关键差异分析

### 14.1 检索公式

| 方面 | 原论文 | ALICE | 影响 |
|------|--------|-------|------|
| 全局权重 | [0.5, 3, 2] | [0.5, 3, 2] | **一致** |
| Per-persona 权重 | recency_w=1, relevance_w=1, importance_w=1 | 无此机制 | 缺少个性化 |
| Recency 计算 | 按 last_accessed 排序的索引衰减 | 按列表顺序的索引衰减 | 基本一致 |
| 归一化 | min-max 到 [0,1] | 无归一化 | **重大差异** — ALICE 的 importance 用原始值 / max_p |
| 节点过滤 | 排除 "idle" | 无过滤 | idle 事件污染检索 |

### 14.2 计划深度

| 方面 | 原论文 | ALICE | 影响 |
|------|--------|-------|------|
| Daily plan | 有 | 有 | 一致 |
| Hourly schedule | 有 | 有 | 一致 |
| Task decomposition (5-15min) | **有** | **无** | **重大缺失** — 角色无法执行细粒度动作 |
| 动作完成检测 | `act_check_finished()` 基于 `act_start_time + act_duration` | 每步重新选择动作 | **重大差异** — ALICE 的 duration 字段完全无效 |
| 日程重新计划 | 有 (`_create_react()` + `generate_new_decomp_schedule()`) | **无** | 缺少动态适应能力 |

### 14.3 反应系统

| 方面 | 原论文 | ALICE | 影响 |
|------|--------|-------|------|
| 自身事件过滤 | `_choose_retrieved()` 排除自身 | **无** | **记忆被自身事件淹没** |
| 反应类型 | chat / wait / do other things | 仅 chat | 缺少等待和其他反应 |
| 对话冷却 | buffer = 800 步 | buffer = 100 步 | ALICE 冷却不足 |
| 重复对话防护 | 同一步内通过 `chatting_with` 状态防护 | **无** | 可能同步触发重复对话 |

### 14.4 时间系统

| 方面 | 原论文 | ALICE | 影响 |
|------|--------|-------|------|
| sec_per_step | 10 秒 | 600 秒（10分钟） | ALICE 粒度粗 60 倍 |
| 日程索引 | `get_f_daily_schedule_index()` 基于 `curr_time.hour * 60 + minute` | 相同 | 一致 |
| 起始时间 | 正常日期如 "June 25, 2022" | `datetime(1, 1, 1, 0, 0, 0)` | ALICE 从午夜开始 |

### 14.5 感知系统

| 方面 | 原论文 | ALICE | 影响 |
|------|--------|-------|------|
| 空间过滤 | 只感知同一 arena 内的事件 | 按距离感知 | ALICE 可能感知到不同房间的事件 |
| 空间记忆更新 | 动态更新 s_mem.tree | 仅初始化时加载 | 无法发现新区域 |
| 自身事件处理 | 自身事件进入记忆流但不触发反应 | 自身事件进入记忆流且触发反应 | 自循环问题 |

### 14.6 LLM 解析

| 方面 | 原论文 | ALICE | 影响 |
|------|--------|-------|------|
| Prompt 语言 | 英文 | 中文/英文混合 | 中文输出 + 英文解析 = **完全失效** |
| 验证机制 | `safe_generate_response` 带验证和重试 | 简单 try/except | 解析失败率高 |
| Fail-safe | 每个函数有专门的默认值 | 部分有，部分缺失 | 鲁棒性不足 |

### 14.7 前端

| 方面 | 原论文 | ALICE | 影响 |
|------|--------|-------|------|
| 框架 | Django + Phaser.js (2D sprite) | FastAPI + Canvas + WebSocket | 不同但功能等价 |
| 通信 | 文件系统 JSON 交换 | WebSocket 实时推送 | ALICE 更现代 |

### 14.8 ALICE 特有功能（原论文没有的）

| 功能 | 状态 | 说明 |
|------|------|------|
| Concept (ego/goal/memory_abstraction) | 已定义，未注入 LLM | Phase 2 功能 |
| Dream 模块 | 代码存在但未激活 | Phase 3 功能 |
| Knowledge 系统 | 代码存在但未激活 | Phase 4 功能 |
| Special Abilities | 数据字段存在 | Phase 5 功能 |
| 玩家聊天 (player chat) | 已实现 | Phase 6 功能 |

---

## 15. 重构建议

基于以上分析，以下是 ALICE PROJECT 重构的优先级建议：

### P0 - 必须修复（当前完全不工作的部分）

1. **修复语言冲突**：所有解析逻辑必须同时支持中文和英文输出。建议在 prompt 中强制要求结构化输出格式（如 JSON），而非依赖自然语言解析。

2. **修复日程索引 vs 起始时间**：世界时间应从合理的日期开始（如 "January 1, 2024, 08:00:00"），而非 `datetime(1,1,1,0,0,0)`。

3. **过滤自身事件**：在 `_choose_retrieved` 等价逻辑中排除 `curr_event.subject == persona.name` 的事件。

### P1 - 功能完善（使行为符合论文预期）

4. **实现三级任务分解**：添加 `generate_task_decomp()` 的等价实现，在运行时将 >= 60 分钟的活动分解为 5-15 分钟的子任务。

5. **实现动作完成检测**：添加 `act_check_finished()` 机制，只有当前动作完成后才选择下一个动作，让 duration 字段生效。

6. **实现日程重新计划**：对话或等待事件后，重新生成受影响时间段的日程。

7. **修复检索归一化**：使用 min-max 归一化将三个分量映射到 [0,1]。

8. **添加同 arena 过滤**：感知时只处理同一 arena 内的事件。

### P2 - 优化改进

9. **减少 LLM 调用**：使用缓存和批处理减少每步的 API 调用次数。

10. **时间粒度调优**：考虑减小 `SEC_PER_STEP`（如从 600 秒减到 60 秒）以获得更细粒度的行为。

11. **对话冷却调整**：将 `chatting_with_buffer` 从 100 增加到 800 或更高。

12. **添加等待反应**：除了 chat 反应，增加 wait 反应类型。

### 后续阶段

在基础 GA 架构稳定后，再逐步加入 ALICE 特有功能（ego 注入、dream、knowledge、special abilities、player interaction）。

---

## 附录 A: 原始代码库文件树

```
reverie/backend_server/
├── reverie.py                          # 主仿真循环 (ReverieServer)
├── maze.py                             # Tile-based 地图系统
├── path_finder.py                      # A* 寻路算法
├── global_methods.py                   # 全局工具函数
├── utils.py                            # 配置文件（API keys, paths）
└── persona/
    ├── persona.py                      # Persona 核心类
    ├── cognitive_modules/
    │   ├── perceive.py                 # 感知模块
    │   ├── retrieve.py                 # 检索模块（两版本）
    │   ├── plan.py                     # 计划模块（最复杂，1054行）
    │   ├── reflect.py                  # 反思模块
    │   ├── execute.py                  # 执行模块
    │   └── converse.py                 # 对话模块
    ├── memory_structures/
    │   ├── associative_memory.py       # 记忆流 (ConceptNode + AssociativeMemory)
    │   ├── spatial_memory.py           # 空间记忆树 (MemoryTree)
    │   └── scratch.py                  # 工作记忆 (Scratch)
    └── prompt_template/
        ├── run_gpt_prompt.py           # 所有 prompt 构造函数
        ├── gpt_structure.py            # LLM API 封装
        ├── print_prompt.py             # 调试打印
        ├── v1/                         # 旧版 prompt 模板
        ├── v2/                         # 中间版本 prompt 模板
        └── v3_ChatGPT/                 # ChatGPT 版本 prompt 模板
```

## 附录 B: ALICE 代码与原始代码的对应关系

| ALICE 文件 | 原始文件 | 状态 |
|-----------|---------|------|
| `backend/main.py` + `backend/world_engine.py` | `reverie.py` | 功能等价但架构不同 |
| `backend/persona/persona.py` | `persona/persona.py` | 基本对应 |
| `backend/persona/cognitive_modules/perceive.py` | `persona/cognitive_modules/perceive.py` | 简化版，缺少 arena 过滤 |
| `backend/persona/cognitive_modules/retrieve.py` | `persona/cognitive_modules/retrieve.py` | 实现了 new_retrieve，缺少归一化 |
| `backend/persona/cognitive_modules/plan.py` | `persona/cognitive_modules/plan.py` | 缺少三级分解和重新计划 |
| `backend/persona/cognitive_modules/reflect.py` | `persona/cognitive_modules/reflect.py` | 基本对应，缺少对话后反思 |
| `backend/persona/cognitive_modules/execute.py` | `persona/cognitive_modules/execute.py` | 简化版 |
| `backend/persona/cognitive_modules/converse.py` | `persona/cognitive_modules/converse.py` | 类似 v2 版本 |
| `backend/persona/memory_structures/associative_memory.py` | `persona/memory_structures/associative_memory.py` | 简化版，缺少 kw 索引 |
| `backend/persona/memory_structures/spatial_memory.py` | `persona/memory_structures/spatial_memory.py` | 功能等价 |
| `backend/persona/memory_structures/scratch.py` | `persona/memory_structures/scratch.py` | 简化版 |
| `backend/persona/memory_structures/concept.py` | (无对应) | ALICE 特有 |
| `backend/llm/llm_client.py` | `persona/prompt_template/gpt_structure.py` | 不同 LLM 提供商 |
| `backend/llm/embedding.py` | `global_methods.py` 中的 `get_embedding()` | 不同嵌入模型 |
| `backend/world/maze.py` | `maze.py` | 简化版 |
| `backend/world/path_finder.py` | `path_finder.py` | 功能等价 |
