# 设定一个通用的居民模板，然后创建新的居民的时候只需要调用这个模板创造instance就可以了

Class Resident:
    def init:
        type: human, creature, monster
        age: 0 - 200
        sex: male, female, unique
        memory_size: 1 - 200
        init_brain()

    def init_brain:
        brain即LLM大脑
        每当一个居民初始化的时候
        就要对其大脑进行初始化设定
    
    def ability:
        所有居民都会的能力：
        （1）移动、寻路
        （2）交互
        （3）观察
        
    def Cycle:
        这个cycle是每个居民的生物时钟，必须和世界时钟保持一致
        在世界时钟运行的时候，从T到T+1的时候，会进行一个半并发进程
        即根据算力情况，逐步让所有生物的时钟从T进到T+1
        当所有生物的T进到T+1后，就算是过了一个时间步


    def Action_T:
    在每一个特定的Timestamp（即T到T+1），居民会进行如下操作：
        如果居民在清醒状态：
        def Think:
            思考，将自己的环境、状况、目标等发送给大脑
            大脑返回思考结果

        def Action:
            根据思考结果进行动作
            可以是：
                移动
                说话
            等等

        def End_Action:
            结束动作
            将刚才的观察、交流、动作等存储到memory_stream中

        如果居民在睡觉状态：
        def dream：
            将当日的memory_stream中的内容发送给大脑，进行抽象理解
            将抽象理解的结果存储到concept的memory_abstraction中


    def Knowledge：
        知识系统由一个数据库组成
        每个居民在创建的时候都会复制数据库的内容，生成一个独特的副本
        数据库内容：
        【编号】 知识编号，主key
        【类别】0：common_sense
                1: history
                2: geography
                3: culture
                4: morality
                5: rules
        【内容】 该知识的内容
        【该知识的原出处】 0:无需出处，自然设定
                            1：church， 教会
                            2：dark，黑暗领域传出来的知识
                            3：oriental，东方之子内部流传的知识，比如维纳斯和骑士团东征的真相等
        【是否掌握】在原初数据库中全是0，然后创建具体的resident的时候根据需要进行设定
                    0：没有掌握
                    1：掌握
                    2：怀疑 （这个比较特殊，暂时先留一个口子）





Class Human extend from Resident: （继承自Resident）
    def init:
        type: human
        age: 1 - 100
        sex: male, female
        memory_size: 1 - 200
        identity: "神父"、圣殿骑士、圣骑士、骑士、剑士、农夫、木匠、铁匠、普通人等
        init_brain() # 初始化该居民的系统prompt
        init_knowledge() # 初始化该居民的知识储备

    def init_brain()
        重写Resident的init_brain()
        对于人类而言，需要用比较好的LLM
        同时在这里把System-prompt也要写好
        system-prompt存储在concept中

        初始化Concept（system-prompt）：
            concept-ego例：
            """
            我是谁：我叫亚瑟，是一名木匠
            我在哪：我生活在一个叫临山镇的地方
            """
            concept-goal例：
            """
            我想打造出一个非常好看的门框
            """
            concept-memory-abstration例：
            """
            （这里先初始化一个虚构的过去）
            我这几天在砍树采集木头
            """

    def Memory Stream:
        记忆流
        用一个字典存储记忆
        key is timestamp: value is the content 
        所有的对话等都会直接按照timestamp加入到记忆流中

    def read_memory_stream(相关对象):
        读取记忆流，根据memory_size的大小
            X = memory_stream中最新的memory_size条记忆
        根据相关对象，提取记忆流中符合相关性的内容，进行相关性检索：（也就是俗称的睹物思人）
            Y = memory_stream中和相关对象相关的若干条记忆
            这里可能需要用向量数据库
            这一部分的作用是因相关性而唤醒记忆
        return X, Y

    def concept_ego:
        存储我是谁、我在哪之类的信息
        这个部分取代了system-prompt
        在每日做梦的时候，会重新审视自己的ego
        单独设计是为了预留自我革新的设计

    def concept_goal:
        存储抽象的理想概念、梦想、人生追求等

    def concept_memory_abstraction:
        存储对过去记忆的抽象，一般在做梦的时候对当日的memory_stream的内容进行整理加入
        总结的时候需要有一个比较好的提炼流程：
        （1）总结 Summarization
            先用一个prompt让LLM将一天的记忆流进行高度概括
            比如，prompt："请将以下日常记录总结为5个关键事件"
        （2）Reflection 反思
            比如，prompt："基于今天发生的这些关键事件，你对世界、对自己、或对你的目标有什么新的看法或者感悟吗？请用1-3句话概括。"

    def init_knowledge：
        根据具体的居民设定进行对应的初始化设定
        具体内容就是读取数据库后对选定区域设定其知识掌握，掌握为1，没掌握为0

    def get_knowledge:
        在做梦的时候，如果发现特别的内容可以被认为是知识
        便可以对知识进行修改

    


Class 木匠 extends from Human
    def ability:
        木匠独特的技能

其他职业也类似，从Human中继承
具体的暂时还不添加，等基本居民能力测试通过后再添加

