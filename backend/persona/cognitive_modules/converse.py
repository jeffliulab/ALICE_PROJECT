"""
Converse Module (agent_chat_v2)

Iterative turn-by-turn conversation generation between two personas.
Each turn retrieves memories, generates an utterance, and checks for [END].
"""

from __future__ import annotations

import math
import logging
from typing import TYPE_CHECKING

from backend.persona.cognitive_modules.retrieve import new_retrieve
from backend.llm.llm_client import safe_generate_response, ChatGPT_single_request

if TYPE_CHECKING:
    from backend.persona.persona import Persona

log = logging.getLogger(__name__)


def generate_summarize_agent_relationship(init_persona: Persona,
                                           target_persona: Persona,
                                           retrieved: dict) -> str:
    all_keys = []
    for _, val in retrieved.items():
        for i in val:
            all_keys.append(i.embedding_key)
    all_str = "\n".join(all_keys)

    prompt = (
        f"Given the following memories of {init_persona.scratch.name} about "
        f"{target_persona.scratch.name}:\n{all_str}\n\n"
        f"Summarize their relationship in 1-2 sentences."
    )
    return ChatGPT_single_request(prompt)


def generate_one_utterance(maze, init_persona: Persona,
                            target_persona: Persona,
                            retrieved: dict,
                            curr_chat: list) -> tuple[str, bool]:
    curr_context = (
        f"{init_persona.scratch.name} was {init_persona.scratch.act_description} "
        f"when {init_persona.scratch.name} saw {target_persona.scratch.name} "
        f"in the middle of {target_persona.scratch.act_description}.\n"
        f"{init_persona.scratch.name} is initiating a conversation with "
        f"{target_persona.scratch.name}."
    )

    all_keys = []
    for _, val in retrieved.items():
        for i in val:
            all_keys.append(i.embedding_key)
    context_str = "\n".join(all_keys[:8])

    prev_convo = ""
    for speaker, text in curr_chat[-6:]:
        prev_convo += f"{speaker}: {text}\n"

    identity = init_persona.scratch.get_str_iss()

    prompt = (
        f"{identity}\n\n"
        f"Context: {curr_context}\n\n"
        f"Relevant memories:\n{context_str}\n\n"
        f"Conversation so far:\n{prev_convo}\n\n"
        f"What would {init_persona.scratch.name} say next? "
        f"Keep it brief (1-2 sentences). "
        f"If {init_persona.scratch.name} would end the conversation, "
        f"include [END] at the end of the response."
    )

    def validate(resp, _):
        return len(resp.strip()) > 0

    def cleanup(resp, _):
        end = "[END]" in resp
        utt = resp.replace("[END]", "").strip()
        if not utt:
            utt = "..."
        return {"utterance": utt, "end": end}

    gpt_param = {"temperature": 0.8, "max_tokens": 128}
    result = safe_generate_response(
        prompt, gpt_param, 3, {"utterance": "...", "end": True},
        validate, cleanup)

    return result["utterance"], result["end"]


def agent_chat_v2(maze, init_persona: Persona,
                   target_persona: Persona) -> list[list[str]]:
    """Run a full iterative conversation (up to 8 turns)."""
    curr_chat = []

    for turn in range(8):
        # --- init_persona speaks ---
        focal_points = [target_persona.scratch.name]
        retrieved = new_retrieve(init_persona, focal_points, 50)
        relationship = generate_summarize_agent_relationship(
            init_persona, target_persona, retrieved)

        last_chat = ""
        for row in curr_chat[-4:]:
            last_chat += ": ".join(row) + "\n"

        if last_chat:
            focal_points = [
                relationship,
                f"{target_persona.scratch.name} is "
                f"{target_persona.scratch.act_description}",
                last_chat]
        else:
            focal_points = [
                relationship,
                f"{target_persona.scratch.name} is "
                f"{target_persona.scratch.act_description}"]
        retrieved = new_retrieve(init_persona, focal_points, 15)

        utt, end = generate_one_utterance(
            maze, init_persona, target_persona, retrieved, curr_chat)
        curr_chat.append([init_persona.scratch.name, utt])
        log.info("  %s: %s", init_persona.scratch.name, utt[:80])
        if end:
            break

        # --- target_persona speaks ---
        focal_points = [init_persona.scratch.name]
        retrieved = new_retrieve(target_persona, focal_points, 50)
        relationship = generate_summarize_agent_relationship(
            target_persona, init_persona, retrieved)

        last_chat = ""
        for row in curr_chat[-4:]:
            last_chat += ": ".join(row) + "\n"

        if last_chat:
            focal_points = [
                relationship,
                f"{init_persona.scratch.name} is "
                f"{init_persona.scratch.act_description}",
                last_chat]
        else:
            focal_points = [
                relationship,
                f"{init_persona.scratch.name} is "
                f"{init_persona.scratch.act_description}"]
        retrieved = new_retrieve(target_persona, focal_points, 15)

        utt, end = generate_one_utterance(
            maze, target_persona, init_persona, retrieved, curr_chat)
        curr_chat.append([target_persona.scratch.name, utt])
        log.info("  %s: %s", target_persona.scratch.name, utt[:80])
        if end:
            break

    return curr_chat


def generate_convo(maze, init_persona: Persona,
                    target_persona: Persona) -> tuple[list, int]:
    """Generate a full conversation and estimate duration in minutes."""
    convo = agent_chat_v2(maze, init_persona, target_persona)
    all_utt = ""
    for row in convo:
        all_utt += f"{row[0]}: {row[1]}\n"
    convo_length = math.ceil(int(len(all_utt) / 8) / 30)
    return convo, max(convo_length, 1)


def generate_convo_summary(persona: Persona, convo: list) -> str:
    convo_str = ""
    for row in convo:
        convo_str += f"{row[0]}: {row[1]}\n"

    prompt = (
        f"Summarize the following conversation in 1-2 sentences:\n"
        f"{convo_str}"
    )
    return ChatGPT_single_request(prompt)
