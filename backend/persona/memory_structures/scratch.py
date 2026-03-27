"""
Scratch (Short-Term / Working Memory)

Faithful reimplementation of the original Generative Agents scratch.py.
Holds persona's transient state: identity, planning, current action, chat state.
"""

from __future__ import annotations

import json
import datetime
from pathlib import Path


class Scratch:
    def __init__(self, f_saved: str):
        # Perception hyperparameters
        self.vision_r = 4
        self.att_bandwidth = 3
        self.retention = 5

        # World info
        self.curr_time: datetime.datetime | None = None
        self.curr_tile: tuple[int, int] | None = None
        self.daily_plan_req: str | None = None

        # Identity
        self.name: str | None = None
        self.first_name: str | None = None
        self.last_name: str | None = None
        self.age: int | None = None
        self.innate: str | None = None
        self.learned: str | None = None
        self.currently: str | None = None
        self.lifestyle: str | None = None
        self.living_area: str | None = None

        # Reflection variables
        self.concept_forget = 100
        self.daily_reflection_time = 180
        self.daily_reflection_size = 5
        self.overlap_reflect_th = 2
        self.kw_strg_event_reflect_th = 4
        self.kw_strg_thought_reflect_th = 4

        # Retrieval weights
        self.recency_w = 1
        self.relevance_w = 1
        self.importance_w = 1
        self.recency_decay = 0.99
        self.importance_trigger_max = 150
        self.importance_trigger_curr = 150
        self.importance_ele_n = 0
        self.thought_count = 5

        # Daily plan
        self.daily_req: list[str] = []
        self.f_daily_schedule: list[list] = []
        self.f_daily_schedule_hourly_org: list[list] = []

        # Current action
        self.act_address: str | None = None
        self.act_start_time: datetime.datetime | None = None
        self.act_duration: int | None = None
        self.act_description: str | None = None
        self.act_pronunciatio: str | None = None
        self.act_event = (self.name, None, None)

        self.act_obj_description: str | None = None
        self.act_obj_pronunciatio: str | None = None
        self.act_obj_event = (self.name, None, None)

        # Chat state
        self.chatting_with: str | None = None
        self.chat: list | None = None
        self.chatting_with_buffer: dict[str, int] = {}
        self.chatting_end_time: datetime.datetime | None = None

        # Path
        self.act_path_set = False
        self.planned_path: list[tuple[int, int]] = []

        # Load from file
        if Path(f_saved).exists():
            sl = json.load(open(f_saved))
            self.vision_r = sl["vision_r"]
            self.att_bandwidth = sl["att_bandwidth"]
            self.retention = sl["retention"]

            if sl["curr_time"]:
                self.curr_time = datetime.datetime.strptime(
                    sl["curr_time"], "%B %d, %Y, %H:%M:%S")
            self.curr_tile = sl["curr_tile"]
            self.daily_plan_req = sl["daily_plan_req"]

            self.name = sl["name"]
            self.first_name = sl["first_name"]
            self.last_name = sl["last_name"]
            self.age = sl["age"]
            self.innate = sl["innate"]
            self.learned = sl["learned"]
            self.currently = sl["currently"]
            self.lifestyle = sl["lifestyle"]
            self.living_area = sl["living_area"]

            self.concept_forget = sl["concept_forget"]
            self.daily_reflection_time = sl["daily_reflection_time"]
            self.daily_reflection_size = sl["daily_reflection_size"]
            self.overlap_reflect_th = sl["overlap_reflect_th"]
            self.kw_strg_event_reflect_th = sl["kw_strg_event_reflect_th"]
            self.kw_strg_thought_reflect_th = sl["kw_strg_thought_reflect_th"]

            self.recency_w = sl["recency_w"]
            self.relevance_w = sl["relevance_w"]
            self.importance_w = sl["importance_w"]
            self.recency_decay = sl["recency_decay"]
            self.importance_trigger_max = sl["importance_trigger_max"]
            self.importance_trigger_curr = sl["importance_trigger_curr"]
            self.importance_ele_n = sl["importance_ele_n"]
            self.thought_count = sl["thought_count"]

            self.daily_req = sl["daily_req"]
            self.f_daily_schedule = sl["f_daily_schedule"]
            self.f_daily_schedule_hourly_org = sl["f_daily_schedule_hourly_org"]

            self.act_address = sl["act_address"]
            if sl["act_start_time"]:
                self.act_start_time = datetime.datetime.strptime(
                    sl["act_start_time"], "%B %d, %Y, %H:%M:%S")
            self.act_duration = sl["act_duration"]
            self.act_description = sl["act_description"]
            self.act_pronunciatio = sl["act_pronunciatio"]
            self.act_event = tuple(sl["act_event"])

            self.act_obj_description = sl.get("act_obj_description")
            self.act_obj_pronunciatio = sl.get("act_obj_pronunciatio")
            raw_obj = sl.get("act_obj_event", [None, None, None])
            self.act_obj_event = tuple(raw_obj) if raw_obj else (None, None, None)

            self.chatting_with = sl["chatting_with"]
            self.chat = sl["chat"]
            self.chatting_with_buffer = sl["chatting_with_buffer"]
            if sl["chatting_end_time"]:
                self.chatting_end_time = datetime.datetime.strptime(
                    sl["chatting_end_time"], "%B %d, %Y, %H:%M:%S")

            self.act_path_set = sl["act_path_set"]
            self.planned_path = sl["planned_path"]

    def save(self, f_saved: str):
        Path(f_saved).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "vision_r": self.vision_r,
            "att_bandwidth": self.att_bandwidth,
            "retention": self.retention,
            "curr_time": (self.curr_time.strftime("%B %d, %Y, %H:%M:%S")
                          if self.curr_time else None),
            "curr_tile": self.curr_tile,
            "daily_plan_req": self.daily_plan_req,
            "name": self.name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "age": self.age,
            "innate": self.innate,
            "learned": self.learned,
            "currently": self.currently,
            "lifestyle": self.lifestyle,
            "living_area": self.living_area,
            "concept_forget": self.concept_forget,
            "daily_reflection_time": self.daily_reflection_time,
            "daily_reflection_size": self.daily_reflection_size,
            "overlap_reflect_th": self.overlap_reflect_th,
            "kw_strg_event_reflect_th": self.kw_strg_event_reflect_th,
            "kw_strg_thought_reflect_th": self.kw_strg_thought_reflect_th,
            "recency_w": self.recency_w,
            "relevance_w": self.relevance_w,
            "importance_w": self.importance_w,
            "recency_decay": self.recency_decay,
            "importance_trigger_max": self.importance_trigger_max,
            "importance_trigger_curr": self.importance_trigger_curr,
            "importance_ele_n": self.importance_ele_n,
            "thought_count": self.thought_count,
            "daily_req": self.daily_req,
            "f_daily_schedule": self.f_daily_schedule,
            "f_daily_schedule_hourly_org": self.f_daily_schedule_hourly_org,
            "act_address": self.act_address,
            "act_start_time": (self.act_start_time.strftime("%B %d, %Y, %H:%M:%S")
                               if self.act_start_time else None),
            "act_duration": self.act_duration,
            "act_description": self.act_description,
            "act_pronunciatio": self.act_pronunciatio,
            "act_event": list(self.act_event),
            "act_obj_description": self.act_obj_description,
            "act_obj_pronunciatio": self.act_obj_pronunciatio,
            "act_obj_event": list(self.act_obj_event),
            "chatting_with": self.chatting_with,
            "chat": self.chat,
            "chatting_with_buffer": self.chatting_with_buffer,
            "chatting_end_time": (self.chatting_end_time.strftime(
                "%B %d, %Y, %H:%M:%S") if self.chatting_end_time else None),
            "act_path_set": self.act_path_set,
            "planned_path": self.planned_path,
        }
        with open(f_saved, "w") as f:
            json.dump(data, f, indent=2)

    # --- Identity helpers ---
    def get_str_iss(self) -> str:
        """Identity Stable Set: name, age, innate, learned."""
        parts = []
        parts.append(f"Name: {self.name}")
        parts.append(f"Age: {self.age}")
        parts.append(f"Innate traits: {self.innate}")
        parts.append(f"Learned: {self.learned}")
        parts.append(f"Currently: {self.currently}")
        parts.append(f"Lifestyle: {self.lifestyle}")
        return "\n".join(parts)

    def get_str_lifestyle(self) -> str:
        return self.lifestyle or ""

    def get_str_firstname(self) -> str:
        return self.first_name or ""

    def get_str_curr_date_str(self) -> str:
        if self.curr_time:
            return self.curr_time.strftime("%A %B %d")
        return ""

    # --- Schedule helpers ---
    def get_f_daily_schedule_index(self, advance: int = 0) -> int:
        if not self.curr_time or not self.f_daily_schedule:
            return 0
        elapsed = self.curr_time.hour * 60 + self.curr_time.minute + advance
        total = 0
        for i, (_, dur) in enumerate(self.f_daily_schedule):
            total += dur
            if elapsed < total:
                return i
        return len(self.f_daily_schedule) - 1

    def get_f_daily_schedule_hourly_org_index(self, advance: int = 0) -> int:
        if not self.curr_time or not self.f_daily_schedule_hourly_org:
            return 0
        elapsed = self.curr_time.hour * 60 + self.curr_time.minute + advance
        total = 0
        for i, (_, dur) in enumerate(self.f_daily_schedule_hourly_org):
            total += dur
            if elapsed < total:
                return i
        return len(self.f_daily_schedule_hourly_org) - 1

    def get_str_daily_schedule_summary(self) -> str:
        ret = ""
        for task, dur in self.f_daily_schedule:
            ret += f"[{dur}] {task}\n"
        return ret

    def get_str_daily_schedule_hourly_org_summary(self) -> str:
        ret = ""
        for task, dur in self.f_daily_schedule_hourly_org:
            ret += f"[{dur}] {task}\n"
        return ret

    # --- Action helpers ---
    def act_check_finished(self) -> bool:
        if not self.act_start_time or not self.act_duration:
            return True
        end = self.act_start_time + datetime.timedelta(
            minutes=self.act_duration)
        return self.curr_time >= end

    def get_curr_event_and_desc(self):
        return (self.act_event[0], self.act_event[1], self.act_event[2],
                self.act_description)

    def get_curr_obj_event_and_desc(self):
        return (self.act_obj_event[0], self.act_obj_event[1],
                self.act_obj_event[2], self.act_obj_description)

    def add_new_action(self, address, duration, description, pronunciatio,
                       event, chatting_with=None, chat=None,
                       chatting_with_buffer=None, chatting_end_time=None,
                       obj_description=None, obj_pronunciatio=None,
                       obj_event=None, start_time=None):
        self.act_address = address
        self.act_duration = duration
        self.act_description = description
        self.act_pronunciatio = pronunciatio
        self.act_event = event
        self.act_start_time = start_time or self.curr_time

        self.chatting_with = chatting_with
        self.chat = chat
        if chatting_with_buffer:
            self.chatting_with_buffer.update(chatting_with_buffer)
        self.chatting_end_time = chatting_end_time

        self.act_obj_description = obj_description
        self.act_obj_pronunciatio = obj_pronunciatio
        self.act_obj_event = obj_event or (None, None, None)

        self.act_path_set = False
        self.planned_path = []
