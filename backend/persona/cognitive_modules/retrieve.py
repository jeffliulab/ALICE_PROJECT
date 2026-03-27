"""
Retrieve Module

Faithful reimplementation of the original Generative Agents retrieval system.
Includes both keyword-based retrieve() and three-factor new_retrieve().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.llm.embedding import get_embedding, cos_sim

if TYPE_CHECKING:
    from backend.persona.persona import Persona
    from backend.persona.memory_structures.associative_memory import ConceptNode


def normalize_dict_floats(d: dict, target_min: float, target_max: float) -> dict:
    """Min-max normalize dict values to [target_min, target_max]."""
    min_val = min(d.values())
    max_val = max(d.values())
    range_val = max_val - min_val

    if range_val == 0:
        for key in d:
            d[key] = (target_max - target_min) / 2
    else:
        for key in d:
            d[key] = ((d[key] - min_val) * (target_max - target_min)
                      / range_val + target_min)
    return d


def top_highest_x_values(d: dict, x: int) -> dict:
    return dict(sorted(d.items(), key=lambda item: item[1], reverse=True)[:x])


def extract_recency(persona: Persona, nodes: list[ConceptNode]) -> dict:
    """Recency scores: exponential decay based on sort position."""
    recency_vals = [persona.scratch.recency_decay ** i
                    for i in range(1, len(nodes) + 1)]
    return {node.node_id: recency_vals[count]
            for count, node in enumerate(nodes)}


def extract_importance(persona: Persona, nodes: list[ConceptNode]) -> dict:
    return {node.node_id: node.poignancy for node in nodes}


def extract_relevance(persona: Persona, nodes: list[ConceptNode],
                      focal_pt: str) -> dict:
    focal_embedding = get_embedding(focal_pt)
    result = {}
    for node in nodes:
        node_emb = persona.a_mem.embeddings.get(node.embedding_key)
        if node_emb:
            result[node.node_id] = cos_sim(node_emb, focal_embedding)
        else:
            result[node.node_id] = 0.0
    return result


def retrieve(persona: Persona, perceived: list) -> dict:
    """Keyword-based retrieval (used after perceive)."""
    retrieved = {}
    for event in perceived:
        retrieved[event.description] = {}
        retrieved[event.description]["curr_event"] = event

        relevant_events = persona.a_mem.retrieve_relevant_events(
            event.subject, event.predicate, event.object)
        retrieved[event.description]["events"] = list(relevant_events)

        relevant_thoughts = persona.a_mem.retrieve_relevant_thoughts(
            event.subject, event.predicate, event.object)
        retrieved[event.description]["thoughts"] = list(relevant_thoughts)

    return retrieved


def new_retrieve(persona: Persona, focal_points: list[str],
                 n_count: int = 30) -> dict:
    """Three-factor retrieval: recency + importance + relevance.

    All three components are independently normalized to [0, 1],
    then combined with global weights gw = [0.5, 3, 2] and
    per-persona weights (recency_w, relevance_w, importance_w).
    """
    retrieved = {}
    for focal_pt in focal_points:
        # Get all non-idle event+thought nodes sorted by last_accessed
        nodes = [[i.last_accessed, i]
                 for i in persona.a_mem.seq_event + persona.a_mem.seq_thought
                 if "idle" not in i.embedding_key]
        nodes = sorted(nodes, key=lambda x: x[0])
        nodes = [i for _, i in nodes]

        if not nodes:
            retrieved[focal_pt] = []
            continue

        # Compute and normalize each component to [0, 1]
        recency_out = extract_recency(persona, nodes)
        recency_out = normalize_dict_floats(recency_out, 0, 1)
        importance_out = extract_importance(persona, nodes)
        importance_out = normalize_dict_floats(importance_out, 0, 1)
        relevance_out = extract_relevance(persona, nodes, focal_pt)
        relevance_out = normalize_dict_floats(relevance_out, 0, 1)

        # Weighted combination
        gw = [0.5, 3, 2]  # [recency, relevance, importance]
        master_out = {}
        for key in recency_out:
            master_out[key] = (
                persona.scratch.recency_w * recency_out[key] * gw[0]
                + persona.scratch.relevance_w * relevance_out[key] * gw[1]
                + persona.scratch.importance_w * importance_out[key] * gw[2]
            )

        # Top n
        master_out = top_highest_x_values(master_out, n_count)
        master_nodes = [persona.a_mem.id_to_node[key]
                        for key in master_out if key in persona.a_mem.id_to_node]

        # Update last_accessed
        for n in master_nodes:
            n.last_accessed = persona.scratch.curr_time

        retrieved[focal_pt] = master_nodes

    return retrieved
