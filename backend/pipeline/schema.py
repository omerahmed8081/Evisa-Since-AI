"""
Schema for extracted knowledge.

STRUCTURE is fixed: Gemini must always return exactly these fields (structured output),
so every chat, email or call produces the same shape no matter how messy it is.

WORDS are open: symptoms/actions/events are free text terms. Gemini reuses existing
vocabulary terms where they fit and creates new ones where they don't; vocabulary.py
then merges near-duplicates and stores the growing vocabulary in Neo4j.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

# ---------- Fixed structure (these small lists are part of the design, not vocabulary) ----------
KnowledgeType = Literal[
    "troubleshooting_rule", "known_false_alarm", "hardware_compatibility", "practical_tip", "access_info"
]
NodeType = Literal["transmission", "aggregation_router", "base_station", "microwave_link"]

# Starting vocabulary. Loaded into Neo4j once; after that the vocabulary lives in
# Neo4j and GROWS automatically when Gemini needs a term that doesn't exist yet
# (see vocabulary.py). These are suggestions, not hard limits.
SEED_VOCABULARY: dict[str, list[str]] = {
    "event": [
        "SFP_REPLACEMENT", "PATCH_CABLE_CHANGE", "MODULE_HOT_SWAP", "FIRMWARE_UPGRADE",
        "POWER_OUTAGE", "STORM", "HEAVY_SNOW_ICE", "COLD_WEATHER", "MAINTENANCE",
    ],
    "symptom": [
        "INTERFACE_UP", "INTERFACE_DOWN", "OPTICAL_LEVELS_NORMAL", "OPTICAL_LEVELS_LOW",
        "ALARMS_CLEARED", "TRAFFIC_COUNTERS_ZERO", "LINK_FLAPPING", "LINK_DOWN",
        "LACP_BUNDLE_DOWN", "HIGH_CPU", "BATTERY_ALARM", "FAN_ALARM", "GPS_SYNC_LOST",
        "ALIGNMENT_LOST", "SFP_NOT_RECOGNISED", "CRC_ERRORS", "CELL_DOWN", "MODULE_UNKNOWN",
        "LINK_FADING",
    ],
    "action": [
        "CHECK_TRAFFIC_COUNTERS", "BOUNCE_INTERFACE", "REBOOT_UNIT", "REPLACE_SFP",
        "CLEAN_CONNECTOR", "CLEAR_ICE_RADOME", "REPLACE_PSU", "READD_PORT_CHANNEL_MEMBER",
        "CHECK_TEMP_SENSOR", "CHECK_CHASSIS_TEMP", "CHECK_MOUNT_BOLTS", "REALIGN_ANTENNA",
        "REPLACE_FUSE", "USE_APPROVED_PART", "SET_CONSOLE_BAUD_9600", "REPLACE_PATCH_CABLE",
        "REPLACE_LINE_CARD", "COLD_RESTART_BASEBAND", "WARM_REBOOT", "ENABLE_ATPC",
        "WAIT_INVENTORY_REFRESH", "RESEAT_MODULE", "NO_DISPATCH_NEEDED",
    ],
}
Outcome = Literal["worked", "failed", "unknown"]
ScopeHint = Literal["this_device_only", "older_devices_of_same_type", "all_devices_of_same_type"]


# ---------- What Gemini must return ----------
class Knowledge(BaseModel):
    knowledge_type: KnowledgeType
    summary: str = Field(description="One or two plain English sentences an engineer can act on: the situation, the cause if known, and what to do. Always English, even if the chat is Finnish. Keep codes, part numbers and values exactly as written.")
    device_mentions: list[str] = Field(description="IDs of the devices where this knowledge was actually observed or applied in the conversation, exactly as written, e.g. 'TRN-042'. Do NOT include devices only mentioned for comparison, as background, or as still waiting for something. Empty if none.")
    node_type: Optional[NodeType] = Field(description="Type of device the knowledge is about, if it can be told.")
    scope_hint: ScopeHint = Field(description="Does the expert say it applies only to this device, to older units of this type, or to all units of this type?")
    firmware_below: Optional[str] = Field(description="Only if the text says the knowledge applies only BELOW a firmware version (e.g. a workaround only needed before '3.4'). Otherwise null.")
    firmware_at_least: Optional[str] = Field(description="Only if the text says the knowledge applies only FROM a firmware version upward (e.g. 'on 3.4 and later the problem is gone'). Otherwise null.")
    events: list[str] = Field(description="Event terms: what happened before the problem. Reuse vocabulary terms; create a new UPPER_SNAKE_CASE term only if none fits.")
    symptoms: list[str] = Field(description="Symptom terms: everything observed about the problem, including what the field engineer reports (e.g. 'RX power looks normal' = OPTICAL_LEVELS_NORMAL). Reuse vocabulary terms; create a new UPPER_SNAKE_CASE term only if none fits.")
    actions: list[str] = Field(description="Action terms: recommended steps in order. For failed advice: the action that was tried. Reuse vocabulary terms; create new ones only if none fits.")
    avoid: list[str] = Field(description="Action terms that should NOT be done (yet): what the expert advises against or talks the engineer out of (e.g. 'Should I replace the SFP again?' 'No, usually it's fine' = REPLACE_SFP), and actions the expert says to try only as a last resort.")
    outcome: Outcome = Field(description="worked = success is confirmed in the conversation, or the author says it has worked before; failed = it was tried and did not help; unknown = advice given but no result reported.")
    author: str = Field(description="Full name of the person whose knowledge this is: the person who gave the advice or rule (usually the expert, not the person asking). For failed advice: the person who suggested it.")
    source_message_seqs: list[int] = Field(description="seq numbers of the messages that contain the knowledge.")
    confirmed_at_seq: Optional[int] = Field(description="seq of the message where the result was confirmed (e.g. 'Traffic is back'), else the seq where the advice was given.")
    details: Optional[str] = Field(description="Important specifics the terms don't capture (part numbers, values, conditions). Else null.")


class ExtractionResult(BaseModel):
    useful: bool = Field(description="True if the conversation contains reusable operational knowledge.")
    reason: str = Field(description="One sentence explaining the decision.")
    knowledge: list[Knowledge] = Field(description="Empty list if useful is false.")


# ---------- How a new tip relates to older, similar tips (used by reconcile.py) ----------
Relation = Literal["same_knowledge", "narrows_scope", "supersedes", "conflicts", "unrelated"]


class RelationJudgement(BaseModel):
    existing_id: str = Field(description="id of the existing tip this judgement is about")
    relation: Relation
    firmware_below: Optional[str] = Field(description="For narrows_scope only: the existing tip now only applies below this firmware version, e.g. '3.4'. Else null.")
    reason: str = Field(description="One short sentence.")


class RelationResult(BaseModel):
    judgements: list[RelationJudgement] = Field(description="Exactly one judgement per existing tip.")
