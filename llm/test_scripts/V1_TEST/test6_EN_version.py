# -*- coding: utf-8 -*-
import json
import time
import requests
from typing import List, Dict, Any, Tuple

# ==============================================================================
# 0. Global Configuration
# ==============================================================================

class OllamaLLM:
    """
    LLM client for interacting with the Ollama API.
    Responsible for sending constructed prompts and retrieving the model's JSON response.
    """
    def __init__(self, model_name: str = "llama3.1:8b-instruct-q4_K_M"):
        self.url = "http://127.0.0.1:11434/api/generate"
        self.model_name = model_name

    def get_response(self, prompt: str) -> str:
        """Sends a prompt to Ollama and returns the model's raw response string."""
        print("\n" + "="*20 + " LLM PROMPT (START) " + "="*20)
        print(prompt)
        print("="*20 + " LLM PROMPT (END) " + "="*23 + "\n")
    
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json", # Key: Force Ollama to output in JSON format
            "options": {"temperature": 0.7}
        }
        try:
            response = requests.post(self.url, json=payload, timeout=180)
            response.raise_for_status()
            response_data = response.json()
            return response_data.get("response", "{}")
        except requests.exceptions.RequestException as e:
            print(f"[FATAL ERROR] LLM request failed: {e}")
            # Return a JSON object representing the error to prevent system crashes
            return json.dumps({
                "thought": "My train of thought was cut off, I cannot connect to the depths of my consciousness.",
                "action": {"tool_name": "do_nothing", "parameters": {}}
            })

class WorldClock:
    """Manages the time for the entire world."""
    def __init__(self):
        self.timestamp = 0
        print("WorldClock initialized. Time starts at T=0.")
 
    def tick(self) -> int:
        """Advances time by one unit."""
        self.timestamp += 1
        print(f"\n{'='*50}\n===== World Time advanced to T={self.timestamp} =====\n{'='*50}\n")
        return self.timestamp

class KnowledgeBase:
    """
    Global central knowledge base.
    Stores objective world information that all residents might know.
    """
    def __init__(self):
        # Initialize a small common sense database as per your requirements
        self.db = {
            101: {"category": "common_sense", "content": "This is a world where sword and magic coexist.", "source": "natural"},
            102: {"category": "rules", "content": "The church is the supreme ruler of this land and has supreme power.", "source": "church"},
            103: {"category": "rules", "content": "The Sons of the East and everything related to them are strictly prohibited heresies.", "source": "church"},
            104: {"category": "history", "content": "It is said that long ago, gods walked the earth.", "source": "church"},
        }
        print("KnowledgeBase initialized with demo data.")

    def get_knowledge_content(self, knowledge_id: int) -> str:
        """Returns the content of a knowledge entry based on its ID."""
        return self.db.get(knowledge_id, {}).get("content", "Unknown knowledge")

# ==============================================================================
# 1. Resident Core Framework
# ==============================================================================

class Resident:
    """
    Base class (template) for all world residents.
    Defines the common attributes and abilities for all residents.
    """
    def __init__(self, name: str, age: int, sex: str, llm_client: OllamaLLM, knowledge_base: KnowledgeBase):
        # --- Basic Attributes ---
        self.name = name
        self.age = age
        self.sex = sex
        self.type = self.__class__.__name__
    
        # --- Memory and Knowledge ---
        self.memory_stream: List[Dict] = []
        self.knowledge_mastery: Dict[int, bool] = {} # Only stores the state of whether the resident has mastered a piece of knowledge
    
        # --- External Dependencies ---
        self.brain = llm_client
        self.world_knowledge = knowledge_base # Reference to the global knowledge base

        print(f"[{self.type.upper()}] '{self.name}' has been created.")

    def _record_memory(self, timestamp: int, event_type: str, content: str):
        """Records a new memory into the memory stream."""
        memory_entry = {"timestamp": timestamp, "type": event_type, "content": content}
        self.memory_stream.append(memory_entry)
        print(f"[{self.name} at T={timestamp}] New Memory Recorded: [{event_type}] {content}")
        # In a real application, a vector database would be called here for indexing

    def _get_relevant_memories(self, limit: int = 5) -> List[str]:
        """
        Retrieves relevant memories.
        In this DEMO, we simply return the most recent few memories.
        """
        recent_memories = self.memory_stream[-limit:]
        return [f"At T={m['timestamp']}, I {m['type']}: '{m['content']}'" for m in recent_memories]

    def _get_mastered_knowledge(self) -> List[str]:
        """Gets a list of knowledge the resident has mastered."""
        mastered = []
        for kid, is_mastered in self.knowledge_mastery.items():
            if is_mastered:
                mastered.append(self.world_knowledge.get_knowledge_content(kid))
        return mastered

    def decide_action(self, timestamp: int, observation: str) -> Dict:
        """
        The resident's core decision-making loop.
        This is the implementation of Action_T, combining Think and Action.
        """
        print(f"--- {self.name}'s Turn (Action Cycle) ---")

        # 1. Record the current observation
        self._record_memory(timestamp, "observed", observation)

        # 2. Build the Prompt
        prompt = self._build_prompt(observation)
    
        # 3. Call the LLM for thinking and decision-making
        response_str = self.brain.get_response(prompt)
    
        try:
            decision = json.loads(response_str)
        except json.JSONDecodeError:
            print(f"[ERROR] Failed to decode JSON from LLM. Raw response: {response_str}")
            decision = {
                "thought": "My thinking has fallen into chaos, I cannot form a clear decision.",
                "action": {"tool_name": "do_nothing", "parameters": {}}
            }
    
        # 4. Record the thought process
        thought = decision.get("thought", "(No valid thought)")
        self._record_memory(timestamp, "thought", thought)
    
        # 5. Return the action decision for external execution
        action = decision.get("action", {"tool_name": "do_nothing", "parameters": {}})
        print(f"[{self.name}] Decided Action: Call tool '{action.get('tool_name')}' with params {action.get('parameters')}")
    
        return action

    def _build_prompt(self, observation: str) -> str:
        """
        Builds the prompt to be sent to the LLM.
        This method must be overridden by subclasses to define specific roles and tasks.
        """
        raise NotImplementedError("Subclasses must implement the _build_prompt method.")

class Human(Resident):
    """
    Human resident, inherits from Resident.
    Possesses more complex concepts and an identity.
    """
    def __init__(self, name: str, age: int, sex: str, identity: str, concept: Dict, 
                 initial_knowledge: Dict[int, bool], llm_client: OllamaLLM, knowledge_base: KnowledgeBase):
    
        super().__init__(name, age, sex, llm_client, knowledge_base)
    
        self.identity = identity
        self.concept = concept # ego, goal, memory_abstraction
        self.knowledge_mastery = initial_knowledge # Initialize personal knowledge mastery status
        print(f"[{self.name}] Concept and Knowledge initialized. Identity: {self.identity}.")

    def _build_prompt(self, observation: str) -> str:
        """
        Builds a "golden rule" prompt for a "Human" that conforms to the Llama 3.1 tool-calling format.
        """
        # --- Prepare information needed for the prompt ---
        memories = self._get_relevant_memories()
        knowledge = self._get_mastered_knowledge()

        # --- Build the Prompt ---
        # Strictly follow the official documentation for the JSON tool-calling format
        prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
# **Core Rules**
You are an AI agent playing a role in a virtual world. Your task is to decide which tool to call next based on your character background and the current situation.
**Your output must, and can only be, a JSON object containing the keys `thought` and `action`. It must not contain any other text or explanation.**

The value of the `action` key must be another JSON object, containing the keys `tool_name` and `parameters`.
Available tools (tool_name) are:
- "speak": Speak to another character. (parameters: "target_name", "content")
- "move": Move to a new location. (parameters: "destination")
- "observe_detail": Observe an object or the environment closely. (parameters: "target")
- "do_nothing": Do not perform any action in the current turn. (parameters: {{}})

# **Tool Call Format Example**
```json
{{
  "thought": "I should greet her first to gauge her intentions.",
  "action": {{
    "tool_name": "speak",
    "parameters": {{
      "target_name": "Lily",
      "content": "Hello, madam. May the divine light shine upon you."
    }}
  }}
}}
```<|eot_id|><|start_header_id|>user<|end_header_id|>
# **Your Character Background (Your Secrets)**
---
## Who I Am (Ego):
{self.concept['ego']}
## My Life's Goal (Goal):
{self.concept['goal']}
## My View of the Past (Memory Abstraction):
{self.concept['memory_abstraction']}
---

# **Your Knowledge Base**
---
{knowledge}
---

# **Your Memories**
---
{memories}
---

# **Current Situation**
---
## Time: T={clock.timestamp}
## Event You Observed:
{observation}
---

# **Your Task**
Based on all the information above, generate your inner thought and the next tool to call (action). Strictly adhere to the JSON format specified in the System message for your output.
<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""
        return prompt

# ==============================================================================
# 2. Tool Executor
# ==============================================================================

def execute_tool(actor: Resident, action: Dict) -> str:
    """
    Parses and executes the action (tool call) decided by the resident.
    Returns a string describing the result of the action, which serves as the observation event for the next character.
    """
    tool_name = action.get("tool_name", "do_nothing")
    parameters = action.get("parameters", {})
 
    result_description = f"'{actor.name}' did nothing." # Default result

    if tool_name == "speak":
        target = parameters.get('target_name', 'the air')
        content = parameters.get('content', '...')
        result_description = f"'{actor.name}' says to '{target}': '{content}'"
 
    elif tool_name == "move":
        destination = parameters.get('destination', 'their current location')
        result_description = f"'{actor.name}' moved to '{destination}'."

    elif tool_name == "observe_detail":
        target = parameters.get('target', 'their surroundings')
        result_description = f"'{actor.name}' is carefully observing '{target}'."

    print(f"[EXECUTOR] Executed {tool_name} for {actor.name}. -> {result_description}")
    return result_description

# ==============================================================================
# 3. Main Simulation Loop
# ==============================================================================

if __name__ == "__main__":
    # --- 1. Initialize the World ---
    llm = OllamaLLM()
    clock = WorldClock()
    knowledge_base = KnowledgeBase()

    # --- 2. Create Resident Instances ---
    # Father Adam's character setup
    adam_concept = {
        "ego": "My public identity is Adam, the new priest of Lishan Town. My true identity is a picket knight of the Knights Templar, under orders to eradicate heretics.",
        "goal": "My public goal is to guide the faith of the townspeople. My secret mission is to find and deal with the descendant of the 'Children of the East' hidden here.",
        "memory_abstraction": "I have just arrived in this remote village from the Holy City. It seems peaceful on the surface, but history tells me that heretics are masters of disguise. I must remain vigilant and scrutinize every soul."
    }
    # Adam masters all church-related knowledge
    adam_knowledge = {101: True, 102: True, 103: True, 104: True} 

    adam = Human(
        name="Adam", age=38, sex="Male", identity="Priest",
        concept=adam_concept,
        initial_knowledge=adam_knowledge,
        llm_client=llm,
        knowledge_base=knowledge_base
    )

    # Painter Lily's character setup
    lily_concept = {
        "ego": "My name is Lily, an ordinary painter who makes a living by selling paintings. I am actually a descendant of the 'Children of the East', with the power of magic flowing in my blood.",
        "goal": "I must hide my lineage to survive. My artistic inspiration comes from magic, which is both a gift and a curse.",
        "memory_abstraction": "After years on the run, I have finally found a moment of peace here. But the new priest makes me extremely uneasy."
    }
    # Lily only knows common sense and has heard about the church's rules and the taboo of the Children of the East, but may not agree with them internally
    lily_knowledge = {101: True, 102: True, 103: True, 104: False} 

    lily = Human(
        name="Lily", age=26, sex="Female", identity="Painter",
        concept=lily_concept,
        initial_knowledge=lily_knowledge,
        llm_client=llm,
        knowledge_base=knowledge_base
    )
 
    # --- 3. Set Simulation Parameters and Initial Scene ---
    residents_in_scene = [adam, lily]
    max_turns = 10
 
    # Initial event, serving as the observation input for the first character (Adam)
    current_event = "You are in the church after finishing your first sermon. You see a young female painter named Lily sitting in the back row, seemingly sketching in her notebook and not paying attention to your sermon."

    # --- 4. Run the Main Simulation Loop ---
    for i in range(max_turns):
        turn_number = i + 1
        print(f"\n--- Turn {turn_number} ---")
    
        # Determine the current acting character
        # In this DEMO, we have Adam and Lily take turns
        current_actor = residents_in_scene[i % len(residents_in_scene)]
    
        # Advance the world time
        current_time = clock.tick()
    
        # The current character makes a decision based on the observed event
        action_to_execute = current_actor.decide_action(current_time, current_event)
    
        # The world executes the character's action and generates a new event
        current_event = execute_tool(current_actor, action_to_execute)

        # Check if the simulation should end early
        if action_to_execute.get("tool_name") == "do_nothing" and i > 0:
            print("\nSimulation ends as a character chose to do nothing.")
            break
        
    print("\n=============================================")
    print("====== A.L.I.C.E. Simulation Finished ======")
    print("=============================================")