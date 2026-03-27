"""
Reflect Module

When accumulated importance exceeds threshold, generates focal points,
retrieves evidence, and produces higher-level insights stored as thoughts.
Also handles post-conversation reflection.
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

from backend.llm.embedding import get_embedding
from backend.llm.llm_client import safe_generate_response, ChatGPT_single_request
from backend.persona.cognitive_modules.retrieve import new_retrieve

if TYPE_CHECKING:
    from backend.persona.persona import Persona

log = logging.getLogger(__name__)


def generate_focal_points(persona: Persona, n: int = 3) -> list[str]:
    nodes = [[i.last_accessed, i]
             for i in persona.a_mem.seq_event + persona.a_mem.seq_thought
             if "idle" not in i.embedding_key]
    nodes = sorted(nodes, key=lambda x: x[0])
    nodes = [i for _, i in nodes]

    statements = ""
    for node in nodes[-1 * persona.scratch.importance_ele_n:]:
        statements += node.embedding_key + "\n"

    if not statements.strip():
        return []

    prompt = (
        f"Given the following statements, what are {n} most salient "
        f"high-level questions we can answer about the subjects?\n\n"
        f"{statements}\n"
        f"Output {n} questions, one per line."
    )

    def validate(resp, _):
        return len(resp.strip().split("\n")) >= 1

    def cleanup(resp, _):
        lines = [l.strip() for l in resp.strip().split("\n") if l.strip()]
        return lines[:n]

    gpt_param = {"temperature": 0.7, "max_tokens": 256}
    return safe_generate_response(prompt, gpt_param, 3, [], validate, cleanup)


def generate_insights_and_evidence(persona: Persona, nodes: list,
                                    n: int = 5) -> dict:
    statements = ""
    for count, node in enumerate(nodes):
        statements += f"{count}. {node.embedding_key}\n"

    prompt = (
        f"Given the following statements:\n{statements}\n"
        f"What {n} high-level insights can you infer?\n"
        f"Format each as: insight (because of 0, 2, 5)\n"
        f"The numbers reference the statement indices above."
    )

    def validate(resp, _):
        return len(resp.strip()) > 0

    def cleanup(resp, _):
        ret = {}
        for line in resp.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if "(because of" in line:
                thought = line.split("(because of")[0].strip()
                try:
                    nums = line.split("(because of")[1].split(")")[0]
                    indices = [int(x.strip()) for x in nums.split(",")
                               if x.strip().isdigit()]
                except:
                    indices = []
                ret[thought] = indices
            else:
                # No evidence format, just take the line
                cleaned = line.lstrip("0123456789.-) ").strip()
                if cleaned:
                    ret[cleaned] = []
        return ret

    gpt_param = {"temperature": 0.7, "max_tokens": 512}
    return safe_generate_response(prompt, gpt_param, 3, {}, validate, cleanup)


def generate_action_event_triple(act_desp: str, persona: Persona) -> tuple:
    prompt = (
        f"Convert the following action description into a "
        f"(subject, predicate, object) triple:\n"
        f"Action: {act_desp}\n"
        f"Person: {persona.scratch.name}\n"
        f"Output format: subject | predicate | object"
    )

    def validate(resp, _):
        return "|" in resp

    def cleanup(resp, _):
        parts = resp.strip().split("|")
        if len(parts) >= 3:
            return (parts[0].strip(), parts[1].strip(), parts[2].strip())
        return (persona.scratch.name, "is", act_desp)

    gpt_param = {"temperature": 0.3, "max_tokens": 64}
    return safe_generate_response(
        prompt, gpt_param, 3,
        (persona.scratch.name, "is", act_desp),
        validate, cleanup)


def generate_poig_score(persona: Persona, event_type: str,
                        description: str) -> int:
    if "is idle" in description:
        return 1
    prompt = (
        f"On the scale of 1 to 10, where 1 is purely mundane and 10 is "
        f"extremely poignant, rate the likely poignancy of:\n"
        f"{description}\nRating: "
    )

    def validate(resp, _):
        try:
            int(resp.strip().split()[0])
            return True
        except:
            return False

    def cleanup(resp, _):
        return int(resp.strip().split()[0])

    gpt_param = {"temperature": 0.3, "max_tokens": 8}
    return min(max(safe_generate_response(
        prompt, gpt_param, 3, 5, validate, cleanup), 1), 10)


def generate_planning_thought_on_convo(persona: Persona,
                                        all_utt: str) -> str:
    prompt = (
        f"{persona.scratch.name} just had this conversation:\n"
        f"{all_utt}\n"
        f"What planning thought would {persona.scratch.name} have? "
        f"Respond in one sentence."
    )
    return ChatGPT_single_request(prompt)


def generate_memo_on_convo(persona: Persona, all_utt: str) -> str:
    prompt = (
        f"{persona.scratch.name} just had this conversation:\n"
        f"{all_utt}\n"
        f"Summarize what {persona.scratch.name} would remember. "
        f"Respond in one sentence starting with a verb."
    )
    return ChatGPT_single_request(prompt)


def run_reflect(persona: Persona):
    """Run the reflection cycle: focal points -> retrieve -> insights."""
    focal_points = generate_focal_points(persona, 3)
    if not focal_points:
        return

    retrieved = new_retrieve(persona, focal_points)

    for focal_pt, nodes in retrieved.items():
        if not nodes:
            continue
        thoughts = generate_insights_and_evidence(persona, nodes, 5)
        for thought, evi_raw in thoughts.items():
            evidence_ids = []
            for i in evi_raw:
                if i < len(nodes):
                    evidence_ids.append(nodes[i].node_id)

            created = persona.scratch.curr_time
            expiration = created + datetime.timedelta(days=30)
            s, p, o = generate_action_event_triple(thought, persona)
            keywords = set([s, p, o])
            thought_poignancy = generate_poig_score(persona, "thought", thought)
            thought_embedding = (thought, get_embedding(thought))

            persona.a_mem.add_thought(
                created, expiration, s, p, o,
                thought, keywords, thought_poignancy,
                thought_embedding, evidence_ids)


def reflection_trigger(persona: Persona) -> bool:
    return (persona.scratch.importance_trigger_curr <= 0 and
            (persona.a_mem.seq_event or persona.a_mem.seq_thought))


def reset_reflection_counter(persona: Persona):
    persona.scratch.importance_trigger_curr = \
        persona.scratch.importance_trigger_max
    persona.scratch.importance_ele_n = 0


def reflect(persona: Persona):
    """Main reflection entry point: check trigger, run, reset."""
    if reflection_trigger(persona):
        run_reflect(persona)
        reset_reflection_counter(persona)

    # Post-conversation reflection
    if persona.scratch.chatting_end_time:
        if (persona.scratch.curr_time + datetime.timedelta(seconds=10)
                == persona.scratch.chatting_end_time):
            all_utt = ""
            if persona.scratch.chat:
                for row in persona.scratch.chat:
                    all_utt += f"{row[0]}: {row[1]}\n"

            evidence = []
            last_chat = persona.a_mem.get_last_chat(
                persona.scratch.chatting_with)
            if last_chat:
                evidence = [last_chat.node_id]

            # Planning thought
            planning_thought = generate_planning_thought_on_convo(
                persona, all_utt)
            planning_thought = (
                f"For {persona.scratch.name}'s planning: {planning_thought}")

            created = persona.scratch.curr_time
            expiration = created + datetime.timedelta(days=30)
            s, p, o = generate_action_event_triple(planning_thought, persona)
            keywords = set([s, p, o])
            poignancy = generate_poig_score(
                persona, "thought", planning_thought)
            emb = (planning_thought, get_embedding(planning_thought))
            persona.a_mem.add_thought(
                created, expiration, s, p, o,
                planning_thought, keywords, poignancy, emb, evidence)

            # Memo thought
            memo = generate_memo_on_convo(persona, all_utt)
            memo = f"{persona.scratch.name} {memo}"

            s2, p2, o2 = generate_action_event_triple(memo, persona)
            keywords2 = set([s2, p2, o2])
            poignancy2 = generate_poig_score(persona, "thought", memo)
            emb2 = (memo, get_embedding(memo))
            persona.a_mem.add_thought(
                created, expiration, s2, p2, o2,
                memo, keywords2, poignancy2, emb2, evidence)
