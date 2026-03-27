"""
Associative Memory (Memory Stream)

Faithful reimplementation of the Generative Agents paper's memory stream.
Stores event, thought, and chat nodes with keyword indexing and embeddings.
"""

from __future__ import annotations

import json
import datetime
from pathlib import Path
from typing import Optional


class ConceptNode:
    def __init__(self, node_id, node_count, type_count, node_type, depth,
                 created, expiration, s, p, o,
                 description, embedding_key, poignancy, keywords, filling):
        self.node_id = node_id
        self.node_count = node_count
        self.type_count = type_count
        self.type = node_type  # "event" | "thought" | "chat"
        self.depth = depth

        self.created = created
        self.expiration = expiration
        self.last_accessed = self.created

        self.subject = s
        self.predicate = p
        self.object = o

        self.description = description
        self.embedding_key = embedding_key
        self.poignancy = poignancy
        self.keywords = keywords
        self.filling = filling  # evidence node_ids for thoughts

    def spo_summary(self):
        return (self.subject, self.predicate, self.object)


class AssociativeMemory:
    def __init__(self, f_saved: str):
        self.id_to_node: dict[str, ConceptNode] = {}

        self.seq_event: list[ConceptNode] = []
        self.seq_thought: list[ConceptNode] = []
        self.seq_chat: list[ConceptNode] = []

        self.kw_to_event: dict[str, list[ConceptNode]] = {}
        self.kw_to_thought: dict[str, list[ConceptNode]] = {}
        self.kw_to_chat: dict[str, list[ConceptNode]] = {}

        self.kw_strength_event: dict[str, int] = {}
        self.kw_strength_thought: dict[str, int] = {}

        self.embeddings: dict[str, list[float]] = {}

        # Load from saved files
        embeddings_path = f_saved + "/embeddings.json"
        if Path(embeddings_path).exists():
            self.embeddings = json.load(open(embeddings_path))

        nodes_path = f_saved + "/nodes.json"
        if Path(nodes_path).exists():
            nodes_load = json.load(open(nodes_path))
            for count in range(len(nodes_load.keys())):
                node_id = f"node_{count + 1}"
                if node_id not in nodes_load:
                    continue
                nd = nodes_load[node_id]

                created = datetime.datetime.strptime(nd["created"],
                                                     '%Y-%m-%d %H:%M:%S')
                expiration = None
                if nd["expiration"]:
                    expiration = datetime.datetime.strptime(
                        nd["expiration"], '%Y-%m-%d %H:%M:%S')

                embedding_pair = (nd["embedding_key"],
                                  self.embeddings.get(nd["embedding_key"], []))
                keywords = set(nd["keywords"])

                if nd["type"] == "event":
                    self.add_event(created, expiration, nd["subject"],
                                   nd["predicate"], nd["object"],
                                   nd["description"], keywords,
                                   nd["poignancy"], embedding_pair,
                                   nd["filling"])
                elif nd["type"] == "chat":
                    self.add_chat(created, expiration, nd["subject"],
                                  nd["predicate"], nd["object"],
                                  nd["description"], keywords,
                                  nd["poignancy"], embedding_pair,
                                  nd["filling"])
                elif nd["type"] == "thought":
                    self.add_thought(created, expiration, nd["subject"],
                                     nd["predicate"], nd["object"],
                                     nd["description"], keywords,
                                     nd["poignancy"], embedding_pair,
                                     nd["filling"])

        kw_path = f_saved + "/kw_strength.json"
        if Path(kw_path).exists():
            kw_load = json.load(open(kw_path))
            if kw_load.get("kw_strength_event"):
                self.kw_strength_event = kw_load["kw_strength_event"]
            if kw_load.get("kw_strength_thought"):
                self.kw_strength_thought = kw_load["kw_strength_thought"]

    def save(self, out_json: str):
        Path(out_json).mkdir(parents=True, exist_ok=True)

        r = {}
        for count in range(len(self.id_to_node.keys()), 0, -1):
            node_id = f"node_{count}"
            node = self.id_to_node[node_id]
            r[node_id] = {
                "node_count": node.node_count,
                "type_count": node.type_count,
                "type": node.type,
                "depth": node.depth,
                "created": node.created.strftime('%Y-%m-%d %H:%M:%S'),
                "expiration": (node.expiration.strftime('%Y-%m-%d %H:%M:%S')
                               if node.expiration else None),
                "subject": node.subject,
                "predicate": node.predicate,
                "object": node.object,
                "description": node.description,
                "embedding_key": node.embedding_key,
                "poignancy": node.poignancy,
                "keywords": list(node.keywords),
                "filling": node.filling,
            }

        with open(out_json + "/nodes.json", "w") as f:
            json.dump(r, f)
        with open(out_json + "/kw_strength.json", "w") as f:
            json.dump({"kw_strength_event": self.kw_strength_event,
                        "kw_strength_thought": self.kw_strength_thought}, f)
        with open(out_json + "/embeddings.json", "w") as f:
            json.dump(self.embeddings, f)

    def add_event(self, created, expiration, s, p, o, description,
                  keywords, poignancy, embedding_pair, filling):
        node_count = len(self.id_to_node) + 1
        type_count = len(self.seq_event) + 1
        node_id = f"node_{node_count}"

        if "(" in description:
            description = (" ".join(description.split()[:3]) + " "
                           + description.split("(")[-1][:-1])

        node = ConceptNode(node_id, node_count, type_count, "event", 0,
                           created, expiration, s, p, o, description,
                           embedding_pair[0], poignancy, keywords, filling)

        self.seq_event.insert(0, node)
        kw_lower = [i.lower() for i in keywords]
        for kw in kw_lower:
            self.kw_to_event.setdefault(kw, []).insert(0, node)
        self.id_to_node[node_id] = node

        if f"{p} {o}" != "is idle":
            for kw in kw_lower:
                self.kw_strength_event[kw] = \
                    self.kw_strength_event.get(kw, 0) + 1

        self.embeddings[embedding_pair[0]] = embedding_pair[1]
        return node

    def add_thought(self, created, expiration, s, p, o, description,
                    keywords, poignancy, embedding_pair, filling):
        node_count = len(self.id_to_node) + 1
        type_count = len(self.seq_thought) + 1
        node_id = f"node_{node_count}"
        depth = 1

        node = ConceptNode(node_id, node_count, type_count, "thought", depth,
                           created, expiration, s, p, o, description,
                           embedding_pair[0], poignancy, keywords, filling)

        self.seq_thought.insert(0, node)
        kw_lower = [i.lower() for i in keywords]
        for kw in kw_lower:
            self.kw_to_thought.setdefault(kw, []).insert(0, node)
        self.id_to_node[node_id] = node

        if f"{p} {o}" != "is idle":
            for kw in kw_lower:
                self.kw_strength_thought[kw] = \
                    self.kw_strength_thought.get(kw, 0) + 1

        self.embeddings[embedding_pair[0]] = embedding_pair[1]
        return node

    def add_chat(self, created, expiration, s, p, o, description,
                 keywords, poignancy, embedding_pair, filling):
        node_count = len(self.id_to_node) + 1
        type_count = len(self.seq_chat) + 1
        node_id = f"node_{node_count}"

        node = ConceptNode(node_id, node_count, type_count, "chat", 0,
                           created, expiration, s, p, o, description,
                           embedding_pair[0], poignancy, keywords, filling)

        self.seq_chat.insert(0, node)
        kw_lower = [i.lower() for i in keywords]
        for kw in kw_lower:
            self.kw_to_chat.setdefault(kw, []).insert(0, node)
        self.id_to_node[node_id] = node

        self.embeddings[embedding_pair[0]] = embedding_pair[1]
        return node

    def get_summarized_latest_events(self, retention):
        ret = set()
        for e in self.seq_event[:retention]:
            ret.add(e.spo_summary())
        return ret

    def get_last_chat(self, target_name: str) -> Optional[ConceptNode]:
        for node in self.seq_chat:
            if target_name in node.object or target_name in node.subject:
                return node
        return None

    def retrieve_relevant_events(self, s, p, o):
        kw_set = set()
        if s:
            kw_set.add(s.lower().split(":")[-1] if ":" in s else s.lower())
        if o:
            kw_set.add(o.lower().split(":")[-1] if ":" in o else o.lower())
        ret = []
        for kw in kw_set:
            if kw in self.kw_to_event:
                ret.extend(self.kw_to_event[kw])
        return ret

    def retrieve_relevant_thoughts(self, s, p, o):
        kw_set = set()
        if s:
            kw_set.add(s.lower().split(":")[-1] if ":" in s else s.lower())
        if o:
            kw_set.add(o.lower().split(":")[-1] if ":" in o else o.lower())
        ret = []
        for kw in kw_set:
            if kw in self.kw_to_thought:
                ret.extend(self.kw_to_thought[kw])
        return ret
