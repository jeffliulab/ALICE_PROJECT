"""
Plan Module

Handles long-term planning (daily schedule), short-term action selection
with three-level decomposition, reaction decisions, and replanning.
Faithful reimplementation of the original Generative Agents plan.py.
"""

from __future__ import annotations

import datetime
import math
import random
import logging
from typing import TYPE_CHECKING

from backend.llm.llm_client import (safe_generate_response,
                                     ChatGPT_single_request)
from backend.llm.embedding import get_embedding
from backend.persona.cognitive_modules.retrieve import new_retrieve
from backend.persona.cognitive_modules.converse import (
    generate_convo, generate_convo_summary, agent_chat_v2)

if TYPE_CHECKING:
    from backend.persona.persona import Persona

log = logging.getLogger(__name__)


# ============================================================================
# CHAPTER 2: Generate functions
# ============================================================================

def generate_wake_up_hour(persona: Persona) -> int:
    prompt = (
        f"{persona.scratch.get_str_iss()}\n"
        f"{persona.scratch.get_str_lifestyle()}\n\n"
        f"What time does {persona.scratch.first_name} typically wake up?\n"
        f"Answer with just an hour (e.g., 7 for 7am): "
    )

    def validate(r, _):
        try:
            int(r.strip().split("am")[0].split()[0])
            return True
        except:
            try:
                int(r.strip().split()[0])
                return True
            except:
                return False

    def cleanup(r, _):
        try:
            return int(r.strip().split("am")[0].split()[0])
        except:
            return int(r.strip().split()[0])

    gpt_param = {"temperature": 0.8, "max_tokens": 8}
    return safe_generate_response(prompt, gpt_param, 5, 8, validate, cleanup)


def generate_first_daily_plan(persona: Persona, wake_up_hour: int) -> list:
    prompt = (
        f"{persona.scratch.get_str_iss()}\n"
        f"{persona.scratch.get_str_lifestyle()}\n"
        f"Today is {persona.scratch.get_str_curr_date_str()}.\n"
        f"{persona.scratch.first_name} wakes up at {wake_up_hour}:00 am.\n\n"
        f"List {persona.scratch.first_name}'s plan today in broad strokes "
        f"(4-6 items with times). Format:\n"
        f"1) wake up and complete the morning routine at {wake_up_hour}:00 am\n"
        f"2) ...\n"
    )

    def validate(r, _):
        return ")" in r or "." in r

    def cleanup(r, _):
        cr = []
        for line in r.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Strip numbering
            for sep in [")", ".", "-"]:
                if sep in line[:5]:
                    line = line.split(sep, 1)[-1].strip()
                    break
            if line and len(line) > 3:
                cr.append(line)
        return cr if cr else ["wake up", "work", "eat lunch", "work", "sleep"]

    gpt_param = {"temperature": 1.0, "max_tokens": 500}
    return safe_generate_response(prompt, gpt_param, 5,
                                   ["wake up", "work", "lunch", "rest", "sleep"],
                                   validate, cleanup)


def generate_hourly_schedule(persona: Persona,
                              wake_up_hour: int) -> list[list]:
    """Generate hourly activity schedule in a SINGLE LLM call."""
    daily_plan = "; ".join(persona.scratch.daily_req)

    prompt = (
        f"{persona.scratch.get_str_iss()}\n"
        f"{persona.scratch.first_name} wakes up at {wake_up_hour}:00 AM.\n"
        f"Daily goals: {daily_plan}\n\n"
        f"Write {persona.scratch.first_name}'s hourly schedule for the "
        f"entire day from {wake_up_hour}:00 AM to 11:00 PM.\n"
        f"Before {wake_up_hour}:00 AM, {persona.scratch.first_name} is sleeping.\n\n"
        f"Format EACH line as: HH:MM activity_description\n"
        f"Example:\n"
        f"06:00 sleeping\n"
        f"07:00 waking up and morning routine\n"
        f"08:00 eating breakfast\n"
        f"09:00 working at the office\n"
        f"12:00 having lunch\n"
        f"22:00 getting ready for bed\n"
        f"23:00 sleeping\n\n"
        f"Output ALL 24 hours, one per line. No extra text."
    )

    def validate(r, _):
        lines = [l for l in r.strip().split("\n") if l.strip() and ":" in l[:5]]
        return len(lines) >= 10

    def cleanup(r, _):
        activities = []
        for line in r.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Try to extract "HH:MM activity"
            import re
            m = re.match(r'(\d{1,2}:\d{2})\s*[-–]?\s*(.*)', line)
            if m:
                activities.append(m.group(2).strip()[:80])
            elif len(line) > 3 and not line[0].isdigit():
                activities.append(line[:80])
        return activities

    gpt_param = {"temperature": 0.8, "max_tokens": 1024}
    raw_activities = safe_generate_response(prompt, gpt_param, 3, None,
                                             validate, cleanup)

    # Fallback
    if not raw_activities or len(raw_activities) < 5:
        raw_activities = (["sleeping"] * wake_up_hour
                          + ["morning routine", "working", "working",
                             "having lunch", "working", "working",
                             "relaxing", "having dinner", "leisure",
                             "getting ready for bed"]
                          + ["sleeping"] * max(0, 24 - wake_up_hour - 10))

    # Pad to 24 hours
    while len(raw_activities) < 24:
        raw_activities.append("sleeping")
    raw_activities = raw_activities[:24]

    # Prepend sleeping hours before wake up
    for i in range(wake_up_hour):
        raw_activities[i] = "sleeping"

    # Compress consecutive identical activities into [activity, duration_minutes]
    compressed = []
    prev = None
    for activity in raw_activities:
        if activity != prev:
            compressed.append([activity, 60])
            prev = activity
        else:
            compressed[-1][1] += 60

    log.info("%s: hourly schedule (%d slots): %s",
             persona.scratch.name, len(compressed),
             str(compressed[:4]))
    return compressed


def generate_task_decomp(persona: Persona, task: str,
                          duration: int) -> list[list]:
    """Decompose a task into 5-15 minute subtasks."""
    prompt = (
        f"{persona.scratch.get_str_iss()}\n"
        f"Today is {persona.scratch.get_str_curr_date_str()}.\n\n"
        f"{persona.scratch.first_name} needs to: {task}\n"
        f"Total time: {duration} minutes.\n\n"
        f"Break this into subtasks (5-15 min each). Format each as:\n"
        f"subtask description (duration in minutes)\n"
        f"The durations must add up to {duration}.\n"
        f"Example:\n"
        f"getting ready (15)\n"
        f"main activity (30)\n"
        f"wrapping up (15)\n"
    )

    def validate(r, _):
        return "(" in r and ")" in r

    def cleanup(r, _):
        result = []
        total = 0
        for line in r.strip().split("\n"):
            line = line.strip()
            if not line or "(" not in line:
                continue
            try:
                desc = line.split("(")[0].strip().lstrip("0123456789.-) ")
                dur = int(line.split("(")[-1].split(")")[0].strip()
                           .replace("minutes", "").replace("min", "").strip())
                if desc and 0 < dur <= duration:
                    result.append([desc, dur])
                    total += dur
            except:
                continue
        if not result:
            return [[task, duration]]
        # Adjust if total doesn't match
        if total != duration and result:
            result[-1][1] += (duration - total)
            if result[-1][1] <= 0:
                result[-1][1] = 5
        return result

    gpt_param = {"temperature": 0.7, "max_tokens": 512}
    return safe_generate_response(
        prompt, gpt_param, 3, [[task, duration]], validate, cleanup)


def generate_action_sector(act_desp: str, persona: Persona, maze) -> str:
    curr_world = maze.access_tile(persona.scratch.curr_tile)["world"]
    accessible = persona.s_mem.get_str_accessible_sectors(curr_world)

    prompt = (
        f"{persona.scratch.get_str_iss()}\n"
        f"Currently at: {persona.scratch.act_address or 'unknown'}\n"
        f"Next task: {act_desp}\n"
        f"Available areas: {accessible}\n\n"
        f"Which area should {persona.scratch.first_name} go to?\n"
        f"Answer with ONLY the area name from the list."
    )

    def validate(r, _):
        return len(r.strip()) > 0

    def cleanup(r, _):
        return r.strip().split("\n")[0].strip()

    gpt_param = {"temperature": 0.3, "max_tokens": 32}
    result = safe_generate_response(
        prompt, gpt_param, 3, accessible.split(",")[0].strip(),
        validate, cleanup)

    # Best match
    sectors = [s.strip() for s in accessible.split(",")]
    for s in sectors:
        if s.lower() == result.lower():
            return s
    for s in sectors:
        if s.lower() in result.lower() or result.lower() in s.lower():
            return s
    return sectors[0] if sectors else result


def generate_action_arena(act_desp: str, persona: Persona, maze,
                           act_world: str, act_sector: str) -> str:
    accessible = persona.s_mem.get_str_accessible_sector_arenas(
        f"{act_world}:{act_sector}")
    if not accessible:
        return ""

    prompt = (
        f"{persona.scratch.first_name} is going to {act_sector} to: {act_desp}\n"
        f"Available locations: {accessible}\n\n"
        f"Which specific location? Answer with ONLY the location name."
    )

    def validate(r, _):
        return len(r.strip()) > 0

    def cleanup(r, _):
        return r.strip().split("\n")[0].strip()

    gpt_param = {"temperature": 0.3, "max_tokens": 32}
    result = safe_generate_response(
        prompt, gpt_param, 3, accessible.split(",")[0].strip(),
        validate, cleanup)

    arenas = [a.strip() for a in accessible.split(",")]
    for a in arenas:
        if a.lower() == result.lower():
            return a
    for a in arenas:
        if a.lower() in result.lower() or result.lower() in a.lower():
            return a
    return arenas[0] if arenas else result


def generate_action_game_object(act_desp: str, act_address: str,
                                 persona: Persona, maze) -> str:
    accessible = persona.s_mem.get_str_accessible_arena_game_objects(
        act_address)
    if not accessible:
        return "<random>"

    prompt = (
        f"{persona.scratch.first_name} is at {act_address} to: {act_desp}\n"
        f"Available objects: {accessible}\n\n"
        f"Which object? Answer with ONLY the object name."
    )

    def validate(r, _):
        return len(r.strip()) > 0

    def cleanup(r, _):
        return r.strip().split("\n")[0].strip()

    gpt_param = {"temperature": 0.3, "max_tokens": 32}
    result = safe_generate_response(
        prompt, gpt_param, 3, accessible.split(",")[0].strip(),
        validate, cleanup)

    objects = [o.strip() for o in accessible.split(",")]
    for o in objects:
        if o.lower() == result.lower():
            return o
    for o in objects:
        if o.lower() in result.lower() or result.lower() in o.lower():
            return o
    return objects[0] if objects else result


def generate_action_pronunciatio(act_desp: str, persona: Persona) -> str:
    prompt = (
        f"Convert the following action into 1-2 emojis:\n"
        f"Action: {act_desp}\n"
        f"Emojis: "
    )

    def validate(r, _):
        return len(r.strip()) > 0

    def cleanup(r, _):
        return r.strip()[:4]

    gpt_param = {"temperature": 0.8, "max_tokens": 8}
    try:
        return safe_generate_response(
            prompt, gpt_param, 3, "🙂", validate, cleanup)
    except:
        return "🙂"


def generate_action_event_triple(act_desp: str, persona: Persona) -> tuple:
    prompt = (
        f"Convert to (subject, predicate, object) triple:\n"
        f"Action: {act_desp}\nPerson: {persona.scratch.name}\n"
        f"Output: subject | predicate | object"
    )

    def validate(r, _):
        return "|" in r

    def cleanup(r, _):
        parts = r.strip().split("|")
        if len(parts) >= 3:
            return (parts[0].strip(), parts[1].strip(), parts[2].strip())
        return (persona.scratch.name, "is", act_desp)

    gpt_param = {"temperature": 0.3, "max_tokens": 64}
    return safe_generate_response(
        prompt, gpt_param, 3,
        (persona.scratch.name, "is", act_desp),
        validate, cleanup)


def generate_act_obj_desc(act_game_object: str, act_desp: str,
                           persona: Persona) -> str:
    prompt = (
        f"{persona.scratch.name} is {act_desp} using {act_game_object}.\n"
        f"What is the {act_game_object} doing? Describe in a few words."
    )
    return ChatGPT_single_request(prompt)[:80]


def generate_act_obj_event_triple(act_game_object: str, act_obj_desc: str,
                                   persona: Persona) -> tuple:
    return (act_game_object, "is", act_obj_desc)


def generate_decide_to_talk(init_persona: Persona,
                             target_persona: Persona,
                             retrieved: dict) -> bool:
    context_strs = []
    for _, rel_ctx in retrieved.items():
        if "events" in rel_ctx:
            for n in rel_ctx["events"][:3]:
                context_strs.append(n.embedding_key)
        if "thoughts" in rel_ctx:
            for n in rel_ctx["thoughts"][:2]:
                context_strs.append(n.embedding_key)
    context = "\n".join(context_strs) if context_strs else "no prior interactions"

    prompt = (
        f"{init_persona.scratch.name} encounters {target_persona.scratch.name}.\n"
        f"Context/memories:\n{context}\n\n"
        f"{init_persona.scratch.name} is: {init_persona.scratch.act_description}\n"
        f"{target_persona.scratch.name} is: {target_persona.scratch.act_description}\n\n"
        f"Should {init_persona.scratch.name} start a conversation?\n"
        f"Answer yes or no."
    )

    def validate(r, _):
        return "yes" in r.lower() or "no" in r.lower()

    def cleanup(r, _):
        return "yes" in r.lower()

    gpt_param = {"temperature": 0.5, "max_tokens": 8}
    return safe_generate_response(prompt, gpt_param, 3, False, validate, cleanup)


def generate_decide_to_react(init_persona: Persona,
                              target_persona: Persona,
                              retrieved: dict) -> str:
    prompt = (
        f"{init_persona.scratch.name} sees {target_persona.scratch.name} "
        f"doing: {target_persona.scratch.act_description}.\n"
        f"They are both at: {target_persona.scratch.act_address}.\n\n"
        f"Should {init_persona.scratch.name}:\n"
        f"1. Wait for {target_persona.scratch.name} to finish\n"
        f"2. Do something else\n"
        f"3. Keep their current plan\n"
        f"Answer with just the number (1, 2, or 3)."
    )

    def validate(r, _):
        return r.strip()[0] in "123"

    def cleanup(r, _):
        return r.strip()[0]

    gpt_param = {"temperature": 0.5, "max_tokens": 8}
    return safe_generate_response(prompt, gpt_param, 3, "3", validate, cleanup)


# ============================================================================
# CHAPTER 3: Plan (main planning logic)
# ============================================================================

def revise_identity(persona: Persona):
    """On new day, revise persona's 'currently' based on recent events."""
    p_name = persona.scratch.name
    focal_points = [
        f"{p_name}'s plan for {persona.scratch.get_str_curr_date_str()}.",
        f"Important recent events for {p_name}'s life."]
    retrieved = new_retrieve(persona, focal_points)

    statements = "[Statements]\n"
    for _, val in retrieved.items():
        for i in val:
            statements += (f"{i.created.strftime('%A %B %d -- %H:%M %p')}: "
                           f"{i.embedding_key}\n")

    plan_prompt = (
        f"{statements}\n"
        f"Given the above, is there anything {p_name} should remember for "
        f"{persona.scratch.curr_time.strftime('%A %B %d')}?\n"
        f"Write from {p_name}'s perspective."
    )
    plan_note = ChatGPT_single_request(plan_prompt)

    thought_prompt = (
        f"{statements}\n"
        f"How might we summarize {p_name}'s feelings about their days?\n"
        f"Write from {p_name}'s perspective."
    )
    thought_note = ChatGPT_single_request(thought_prompt)

    yesterday = (persona.scratch.curr_time -
                 datetime.timedelta(days=1)).strftime('%A %B %d')
    currently_prompt = (
        f"{p_name}'s status from {yesterday}:\n"
        f"{persona.scratch.currently}\n\n"
        f"{p_name}'s thoughts:\n{(plan_note + thought_note).replace(chr(10), ' ')}\n\n"
        f"It is now {persona.scratch.curr_time.strftime('%A %B %d')}. "
        f"Write {p_name}'s new status in third-person.\n"
        f"Follow: Status: <new status>"
    )
    new_currently = ChatGPT_single_request(currently_prompt)
    persona.scratch.currently = new_currently

    daily_req_prompt = (
        f"{persona.scratch.get_str_iss()}\n"
        f"Today is {persona.scratch.curr_time.strftime('%A %B %d')}.\n"
        f"Plan today in broad strokes (4-6 items with times):\n"
        f"1. wake up at <time>, 2. ..."
    )
    new_daily_req = ChatGPT_single_request(daily_req_prompt).replace('\n', ' ')
    persona.scratch.daily_plan_req = new_daily_req


def _long_term_planning(persona: Persona, new_day: str):
    """Generate daily schedule at start of a new day."""
    wake_up_hour = generate_wake_up_hour(persona)

    if new_day == "First day":
        persona.scratch.daily_req = generate_first_daily_plan(
            persona, wake_up_hour)
    elif new_day == "New day":
        revise_identity(persona)

    persona.scratch.f_daily_schedule = generate_hourly_schedule(
        persona, wake_up_hour)
    persona.scratch.f_daily_schedule_hourly_org = (
        persona.scratch.f_daily_schedule[:])

    # Store plan in memory
    thought = (f"This is {persona.scratch.name}'s plan for "
               f"{persona.scratch.curr_time.strftime('%A %B %d')}:")
    for item in persona.scratch.daily_req:
        thought += f" {item},"
    thought = thought[:-1] + "."

    created = persona.scratch.curr_time
    expiration = created + datetime.timedelta(days=30)
    s, p, o = (persona.scratch.name, "plan",
               persona.scratch.curr_time.strftime('%A %B %d'))
    keywords = set(["plan"])
    embedding_pair = (thought, get_embedding(thought))
    persona.a_mem.add_thought(created, expiration, s, p, o,
                               thought, keywords, 5, embedding_pair, None)


def _determine_action(persona: Persona, maze):
    """Select current action, decomposing hourly blocks into subtasks."""

    def determine_decomp(act_desp, act_dura):
        if "sleep" not in act_desp and "bed" not in act_desp:
            return True
        if "sleeping" in act_desp or "asleep" in act_desp or "in bed" in act_desp:
            return False
        if ("sleep" in act_desp or "bed" in act_desp) and act_dura > 60:
            return False
        return True

    curr_index = persona.scratch.get_f_daily_schedule_index()
    curr_index_60 = persona.scratch.get_f_daily_schedule_index(advance=60)

    # Decompose current and next hour's blocks
    if curr_index == 0:
        act_desp, act_dura = persona.scratch.f_daily_schedule[curr_index]
        if act_dura >= 60 and determine_decomp(act_desp, act_dura):
            persona.scratch.f_daily_schedule[curr_index:curr_index + 1] = (
                generate_task_decomp(persona, act_desp, act_dura))
        if curr_index_60 + 1 < len(persona.scratch.f_daily_schedule):
            act_desp, act_dura = persona.scratch.f_daily_schedule[curr_index_60 + 1]
            if act_dura >= 60 and determine_decomp(act_desp, act_dura):
                persona.scratch.f_daily_schedule[curr_index_60 + 1:curr_index_60 + 2] = (
                    generate_task_decomp(persona, act_desp, act_dura))

    if curr_index_60 < len(persona.scratch.f_daily_schedule):
        if persona.scratch.curr_time.hour < 23:
            act_desp, act_dura = persona.scratch.f_daily_schedule[curr_index_60]
            if act_dura >= 60 and determine_decomp(act_desp, act_dura):
                persona.scratch.f_daily_schedule[curr_index_60:curr_index_60 + 1] = (
                    generate_task_decomp(persona, act_desp, act_dura))

    # Ensure schedule sums to 1440 minutes
    x_emergency = sum(dur for _, dur in persona.scratch.f_daily_schedule)
    if 1440 - x_emergency > 0:
        persona.scratch.f_daily_schedule.append(
            ["sleeping", 1440 - x_emergency])

    # Get current action
    curr_index = persona.scratch.get_f_daily_schedule_index()
    act_desp, act_dura = persona.scratch.f_daily_schedule[curr_index]

    # Determine location
    act_world = maze.access_tile(persona.scratch.curr_tile)["world"]
    act_sector = generate_action_sector(act_desp, persona, maze)
    act_arena = generate_action_arena(act_desp, persona, maze,
                                       act_world, act_sector)
    act_address = f"{act_world}:{act_sector}:{act_arena}"
    act_game_object = generate_action_game_object(
        act_desp, act_address, persona, maze)
    new_address = f"{act_world}:{act_sector}:{act_arena}:{act_game_object}"

    act_pron = generate_action_pronunciatio(act_desp, persona)
    act_event = generate_action_event_triple(act_desp, persona)

    act_obj_desc = generate_act_obj_desc(act_game_object, act_desp, persona)
    act_obj_pron = generate_action_pronunciatio(act_obj_desc, persona)
    act_obj_event = generate_act_obj_event_triple(
        act_game_object, act_obj_desc, persona)

    persona.scratch.add_new_action(
        new_address, int(act_dura), act_desp, act_pron, act_event,
        obj_description=act_obj_desc,
        obj_pronunciatio=act_obj_pron,
        obj_event=act_obj_event)


def _choose_retrieved(persona: Persona, retrieved: dict):
    """Choose which perceived event to react to, excluding self-events."""
    copy_retrieved = retrieved.copy()
    for event_desc, rel_ctx in list(copy_retrieved.items()):
        if rel_ctx["curr_event"].subject == persona.name:
            del retrieved[event_desc]

    # Prioritize persona events (no ":" in subject)
    priority = []
    for event_desc, rel_ctx in retrieved.items():
        curr = rel_ctx["curr_event"]
        if ":" not in curr.subject and curr.subject != persona.name:
            priority.append(rel_ctx)
    if priority:
        return random.choice(priority)

    # Skip idle
    for event_desc, rel_ctx in retrieved.items():
        if "is idle" not in event_desc:
            priority.append(rel_ctx)
    if priority:
        return random.choice(priority)
    return None


def _should_react(persona: Persona, retrieved: dict, personas: dict):
    """Determine reaction: 'chat with X', 'wait: time', or False."""

    def lets_talk(init_p, target_p, retrieved):
        if (not target_p.scratch.act_address or
                not target_p.scratch.act_description or
                not init_p.scratch.act_address or
                not init_p.scratch.act_description):
            return False
        if ("sleeping" in (target_p.scratch.act_description or "") or
                "sleeping" in (init_p.scratch.act_description or "")):
            return False
        if init_p.scratch.curr_time.hour == 23:
            return False
        if "<waiting>" in (target_p.scratch.act_address or ""):
            return False
        if target_p.scratch.chatting_with or init_p.scratch.chatting_with:
            return False
        if target_p.name in init_p.scratch.chatting_with_buffer:
            if init_p.scratch.chatting_with_buffer[target_p.name] > 0:
                return False
        return generate_decide_to_talk(init_p, target_p, retrieved)

    def lets_react(init_p, target_p, retrieved):
        if (not target_p.scratch.act_address or
                not init_p.scratch.act_address):
            return False
        if ("sleeping" in (target_p.scratch.act_description or "") or
                "sleeping" in (init_p.scratch.act_description or "")):
            return False
        if init_p.scratch.curr_time.hour == 23:
            return False
        if "waiting" in (target_p.scratch.act_description or ""):
            return False
        if not init_p.scratch.planned_path:
            return False
        if init_p.scratch.act_address != target_p.scratch.act_address:
            return False
        react_mode = generate_decide_to_react(init_p, target_p, retrieved)
        if react_mode == "1":
            wait_until = (
                (target_p.scratch.act_start_time +
                 datetime.timedelta(
                     minutes=(target_p.scratch.act_duration or 1) - 1))
                .strftime("%B %d, %Y, %H:%M:%S"))
            return f"wait: {wait_until}"
        return False

    if persona.scratch.chatting_with:
        return False
    if "<waiting>" in (persona.scratch.act_address or ""):
        return False

    curr_event = retrieved["curr_event"]
    if ":" not in curr_event.subject:
        if curr_event.subject in personas:
            if lets_talk(persona, personas[curr_event.subject], retrieved):
                return f"chat with {curr_event.subject}"
            return lets_react(persona, personas[curr_event.subject], retrieved)
    return False


def _chat_react(maze, persona: Persona, focused_event, reaction_mode,
                personas: dict):
    """Handle conversation reaction between two personas."""
    init_persona = persona
    target_persona = personas[reaction_mode[9:].strip()]

    convo, duration_min = generate_convo(maze, init_persona, target_persona)
    convo_summary = generate_convo_summary(init_persona, convo)
    inserted_act = convo_summary
    inserted_act_dur = duration_min

    curr_time = target_persona.scratch.curr_time
    if curr_time.second != 0:
        temp = curr_time + datetime.timedelta(seconds=60 - curr_time.second)
        chatting_end_time = temp + datetime.timedelta(minutes=inserted_act_dur)
    else:
        chatting_end_time = curr_time + datetime.timedelta(
            minutes=inserted_act_dur)

    for role, p in [("init", init_persona), ("target", target_persona)]:
        if role == "init":
            act_address = f"<persona> {target_persona.name}"
            act_event = (p.name, "chat with", target_persona.name)
            chatting_with = target_persona.name
            buffer = {target_persona.name: 800}
        else:
            act_address = f"<persona> {init_persona.name}"
            act_event = (p.name, "chat with", init_persona.name)
            chatting_with = init_persona.name
            buffer = {init_persona.name: 800}

        p.scratch.add_new_action(
            act_address, inserted_act_dur, inserted_act, "💬",
            act_event, chatting_with=chatting_with, chat=convo,
            chatting_with_buffer=buffer,
            chatting_end_time=chatting_end_time,
            start_time=target_persona.scratch.act_start_time)


def _wait_react(persona: Persona, reaction_mode: str):
    """Handle wait reaction."""
    p = persona
    inserted_act = (f"waiting to start "
                    f"{p.scratch.act_description.split('(')[-1][:-1]}"
                    if "(" in (p.scratch.act_description or "")
                    else f"waiting")
    end_time = datetime.datetime.strptime(
        reaction_mode[6:].strip(), "%B %d, %Y, %H:%M:%S")
    inserted_act_dur = ((end_time.minute + end_time.hour * 60)
                        - (p.scratch.curr_time.minute
                           + p.scratch.curr_time.hour * 60) + 1)

    act_address = (f"<waiting> {p.scratch.curr_tile[0]} "
                   f"{p.scratch.curr_tile[1]}")
    desc_part = (p.scratch.act_description.split("(")[-1][:-1]
                 if "(" in (p.scratch.act_description or "")
                 else "activity")
    act_event = (p.name, "waiting to start", desc_part)

    p.scratch.add_new_action(
        act_address, max(inserted_act_dur, 1), inserted_act, "⌛",
        act_event)


def plan(persona: Persona, maze, personas: dict, new_day, retrieved: dict):
    """Main planning entry point.

    1. Long-term planning on new day
    2. Determine action when current one finishes
    3. React to perceived events (chat/wait)
    """
    # PART 1: Long-term planning
    if new_day:
        _long_term_planning(persona, new_day)

    # PART 2: Short-term action selection
    if persona.scratch.act_check_finished():
        _determine_action(persona, maze)

    # PART 3: Reaction to perceived events
    focused_event = None
    if retrieved:
        focused_event = _choose_retrieved(persona, retrieved)

    if focused_event:
        reaction_mode = _should_react(persona, focused_event, personas)
        if reaction_mode:
            if str(reaction_mode).startswith("chat with"):
                _chat_react(maze, persona, focused_event,
                            reaction_mode, personas)
            elif str(reaction_mode).startswith("wait"):
                _wait_react(persona, reaction_mode)

    # Chat state cleanup
    if persona.scratch.act_event[1] != "chat with":
        persona.scratch.chatting_with = None
        persona.scratch.chat = None
        persona.scratch.chatting_end_time = None

    # Decrement chat buffer
    for pname in list(persona.scratch.chatting_with_buffer.keys()):
        if pname != persona.scratch.chatting_with:
            persona.scratch.chatting_with_buffer[pname] -= 1
            if persona.scratch.chatting_with_buffer[pname] <= 0:
                del persona.scratch.chatting_with_buffer[pname]

    return persona.scratch.act_address
