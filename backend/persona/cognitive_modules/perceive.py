"""
Perceive Module

Detects events within persona's vision range in the same arena,
filters by attention bandwidth and retention, scores importance,
and stores new events in the memory stream.
"""

from __future__ import annotations

import math
import logging
from operator import itemgetter
from typing import TYPE_CHECKING

from backend.llm.embedding import get_embedding
from backend.llm.llm_client import safe_generate_response

if TYPE_CHECKING:
    from backend.persona.persona import Persona

log = logging.getLogger(__name__)


def generate_poig_score(persona: Persona, event_type: str,
                        description: str) -> int:
    """Ask LLM to rate event importance 1-10."""
    if "is idle" in description:
        return 1

    prompt = (
        f"On the scale of 1 to 10, where 1 is purely mundane (e.g., brushing "
        f"teeth, making bed) and 10 is extremely poignant (e.g., a break up, "
        f"college acceptance), rate the likely poignancy of the following "
        f"piece of memory.\n"
        f"Memory: {description}\n"
        f"Rating: <fill in>"
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
    score = safe_generate_response(prompt, gpt_param, 3, 5, validate, cleanup)
    return min(max(score, 1), 10)


def perceive(persona: Persona, maze) -> list:
    """
    Perceive events around the persona.
    1. Get nearby tiles within vision radius
    2. Update spatial memory from nearby tiles
    3. Filter events to same arena only
    4. Sort by distance, keep top att_bandwidth
    5. Check retention to avoid re-perceiving
    6. Store new events in associative memory

    Returns list of ConceptNode for newly perceived events.
    """
    scratch = persona.scratch
    curr_tile = scratch.curr_tile
    if not curr_tile:
        return []

    # Get nearby tiles
    nearby_tiles = maze.get_nearby_tiles(curr_tile, scratch.vision_r)

    # Update spatial memory
    for tile_coord in nearby_tiles:
        tile_info = maze.access_tile(tile_coord)
        w = tile_info["world"]
        s = tile_info["sector"]
        a = tile_info["arena"]
        go = tile_info["game_object"]

        if w and w not in persona.s_mem.tree:
            persona.s_mem.tree[w] = {}
        if s and w and s not in persona.s_mem.tree.get(w, {}):
            persona.s_mem.tree[w][s] = {}
        if a and w and s and a not in persona.s_mem.tree.get(w, {}).get(s, {}):
            persona.s_mem.tree[w][s][a] = []
        if (go and w and s and a and
                go not in persona.s_mem.tree.get(w, {}).get(s, {}).get(a, [])):
            persona.s_mem.tree[w][s][a].append(go)

    # Perceive events — only from same arena
    curr_arena_path = maze.get_tile_path(curr_tile, "arena")
    percept_events_set = set()
    percept_events_list = []

    for tile_coord in nearby_tiles:
        tile_info = maze.access_tile(tile_coord)
        if tile_info["events"]:
            if maze.get_tile_path(tile_coord, "arena") == curr_arena_path:
                dist = math.dist(
                    [tile_coord[0], tile_coord[1]],
                    [curr_tile[0], curr_tile[1]])
                for event in tile_info["events"]:
                    if event not in percept_events_set:
                        percept_events_list.append([dist, event])
                        percept_events_set.add(event)

    # Sort by distance, keep top att_bandwidth
    percept_events_list.sort(key=itemgetter(0))
    perceived_events = [ev for _, ev in
                        percept_events_list[:scratch.att_bandwidth]]

    # Store new events
    ret_events = []
    for p_event in perceived_events:
        s, p, o, desc = p_event
        if not p:
            p = "is"
            o = "idle"
            desc = "idle"
        desc = f"{s.split(':')[-1]} is {desc}"
        p_event_tuple = (s, p, o)

        latest = persona.a_mem.get_summarized_latest_events(scratch.retention)
        if p_event_tuple in latest:
            continue

        # Keywords
        keywords = set()
        sub = p_event_tuple[0].split(":")[-1] if ":" in p_event_tuple[0] else p_event_tuple[0]
        obj = p_event_tuple[2].split(":")[-1] if ":" in p_event_tuple[2] else p_event_tuple[2]
        keywords.update([sub, obj])

        # Embedding
        desc_for_emb = desc
        if "(" in desc:
            desc_for_emb = desc.split("(")[1].split(")")[0].strip()
        if desc_for_emb in persona.a_mem.embeddings:
            event_embedding = persona.a_mem.embeddings[desc_for_emb]
        else:
            event_embedding = get_embedding(desc_for_emb)
        embedding_pair = (desc_for_emb, event_embedding)

        # Poignancy
        poignancy = generate_poig_score(persona, "event", desc_for_emb)

        # Handle self-chat perception
        chat_node_ids = []
        if (p_event_tuple[0] == persona.name and
                p_event_tuple[1] == "chat with"):
            curr_event = scratch.act_event
            chat_desc = scratch.act_description
            if chat_desc in persona.a_mem.embeddings:
                chat_emb = persona.a_mem.embeddings[chat_desc]
            else:
                chat_emb = get_embedding(chat_desc)
            chat_poignancy = generate_poig_score(persona, "chat", chat_desc)
            chat_node = persona.a_mem.add_chat(
                scratch.curr_time, None,
                curr_event[0], curr_event[1], curr_event[2],
                chat_desc, keywords, chat_poignancy,
                (chat_desc, chat_emb), scratch.chat)
            chat_node_ids = [chat_node.node_id]

        # Add event to memory
        node = persona.a_mem.add_event(
            scratch.curr_time, None,
            s, p, o, desc, keywords, poignancy,
            embedding_pair, chat_node_ids)
        scratch.importance_trigger_curr -= poignancy
        scratch.importance_ele_n += 1
        ret_events.append(node)

    return ret_events
