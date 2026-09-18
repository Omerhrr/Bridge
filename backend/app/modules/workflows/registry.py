"""Node registry — the catalogue of every node type the engine can run.

Each entry describes: category, label, icon, description, the configuration
fields the Inspector renders (spec §22) and the executor that runs the node.
"""

from dataclasses import dataclass, field
from typing import Any

from app.modules.workflows.nodes import base as base_node
from app.modules.workflows.nodes import ai_nodes, end, logic, sms, trigger, voice


@dataclass
class ConfigField:
    name: str
    label: str
    type: str = "text"  # text | textarea | select | number | boolean
    required: bool = False
    default: Any = None
    options: list[str] = field(default_factory=list)
    placeholder: str = ""


@dataclass
class NodeSpec:
    type: str
    label: str
    icon: str
    category: str  # trigger | voice | ai | messaging | logic | flow
    description: str
    executor: Any  # callable(config, ctx, services) -> NodeResult
    outputs: list[str] = field(default_factory=lambda: ["out"])
    config_fields: list[ConfigField] = field(default_factory=list)


def _f(*args, **kwargs) -> ConfigField:
    return ConfigField(*args, **kwargs)


LANGUAGES = ["en", "ha", "sw", "yo", "ig", "am", "fr"]  # en/ha/sw have mock dictionaries

REGISTRY: dict[str, NodeSpec] = {}


def register(spec: NodeSpec) -> None:
    REGISTRY[spec.type] = spec


# --- Flow -------------------------------------------------------------------
register(NodeSpec("start", "Start", "▶", "flow", "Workflow entry point", base_node.execute_start))
register(NodeSpec("end", "End", "■", "flow", "Terminates the workflow", end.execute_end))

# --- Trigger nodes (spec §11) -------------------------------------------------
register(NodeSpec(
    "incoming_call", "Incoming Call", "📞", "trigger",
    "Receives a phone call via the telecom provider", trigger.execute_incoming_call,
    config_fields=[_f("phone_number", "Phone number filter", placeholder="Leave empty to accept all")],
))
register(NodeSpec(
    "incoming_sms", "Incoming SMS", "✉", "trigger",
    "Receives an SMS message via the telecom provider", trigger.execute_incoming_sms,
    config_fields=[_f("phone_number", "Phone number filter", placeholder="Leave empty to accept all")],
))
register(NodeSpec(
    "ussd_request", "USSD Request", "▤", "trigger",
    "Receives a USSD session request", trigger.execute_ussd_request,
))

# --- Voice nodes ---------------------------------------------------------------
register(NodeSpec(
    "make_call", "Make Call", "☎", "voice",
    "Places an outbound call through the provider", voice.execute_make_call,
    config_fields=[_f("to", "Dial number", required=True, placeholder="+234...")],
))
register(NodeSpec(
    "collect_speech", "Collect Speech", "🎙", "voice",
    "Asks the caller to speak and captures the recording", voice.execute_collect_speech,
    config_fields=[
        _f("prompt", "Prompt text", placeholder="Please say your message"),
        _f("timeout", "Timeout (seconds)", type="number", default=10),
    ],
    outputs=["speech"],
))
register(NodeSpec(
    "play_audio", "Play Audio", "🔊", "voice",
    "Plays an audio file or a generated audio URL to the caller", voice.execute_play_audio,
    config_fields=[_f("audio_url", "Audio URL", placeholder="https://... or {{audio_url}}")],
))
register(NodeSpec(
    "play_text", "Play Voice", "🗣", "voice",
    "Converts text to speech and plays it to the caller", voice.execute_play_text,
    config_fields=[
        _f("text", "Text", type="textarea", placeholder="Hello {{name}}... supports {{variables}}"),
        _f("from_variable", "From variable", placeholder="e.g. translation"),
    ],
))
register(NodeSpec(
    "hang_up", "Hang Up", "⏹", "voice", "Ends the call", voice.execute_hang_up,
))

# --- AI nodes -------------------------------------------------------------------
register(NodeSpec(
    "speech_to_text", "Speech to Text", "🎧", "ai",
    "Transcribes recorded speech into text", ai_nodes.execute_speech_to_text,
    config_fields=[_f("language", "Language", type="select", options=["auto", *LANGUAGES], default="auto")],
))
register(NodeSpec(
    "text_to_speech", "Text to Speech", "📢", "ai",
    "Synthesises speech audio from text", ai_nodes.execute_text_to_speech,
    config_fields=[
        _f("from_variable", "From variable", placeholder="e.g. translation"),
        _f("text", "Text", type="textarea", placeholder="Used when no variable given"),
        _f("language", "Language", type="select", options=LANGUAGES, default="en"),
    ],
))
register(NodeSpec(
    "translate", "Translate", "🌐", "ai",
    "Translates text between languages", ai_nodes.execute_translate,
    config_fields=[
        _f("from_variable", "From variable", placeholder="e.g. transcript"),
        _f("source_language", "Source language", type="select", options=["auto", *LANGUAGES], default="auto"),
        _f("target_language", "Target language", type="select", options=LANGUAGES, required=True, default="ha"),
        _f("fallback", "Fallback enabled", type="boolean", default=True),
    ],
))
register(NodeSpec(
    "detect_language", "Detect Language", "🔎", "ai",
    "Detects the language of a piece of text", ai_nodes.execute_detect_language,
    config_fields=[_f("from_variable", "From variable", placeholder="e.g. transcript")],
))

# --- Messaging nodes ---------------------------------------------------------------
register(NodeSpec(
    "send_sms", "Send SMS", "📤", "messaging",
    "Sends an SMS through the telecom provider", sms.execute_send_sms,
    config_fields=[
        _f("to", "To", placeholder="+234... or {{caller}}"),
        _f("message", "Message", type="textarea", placeholder="Supports {{variables}}"),
        _f("from_variable", "From variable", placeholder="e.g. translation"),
    ],
))

# --- Logic nodes -------------------------------------------------------------------
register(NodeSpec(
    "condition", "Condition", "◆", "logic",
    "Branches the flow based on a variable check", logic.execute_condition,
    outputs=["true", "false"],
    config_fields=[
        _f("variable", "Variable name", required=True, placeholder="e.g. translation"),
        _f("operator", "Operator", type="select", options=["exists", "equals", "contains", "not_empty"], default="exists"),
        _f("value", "Value", placeholder="Compared value"),
    ],
))
register(NodeSpec(
    "switch", "Switch", "⚈", "logic",
    "Routes the flow by the value of a variable", logic.execute_switch,
    outputs=["default"],
    config_fields=[
        _f("variable", "Variable name", required=True),
        _f("cases", "Cases (comma separated)", placeholder="en, ha, sw"),
    ],
))
register(NodeSpec(
    "delay", "Delay", "⏱", "logic",
    "Waits before continuing (short delays only)", logic.execute_delay,
    config_fields=[_f("seconds", "Seconds", type="number", default=1)],
))
register(NodeSpec(
    "set_variable", "Set Variable", "✎", "logic",
    "Stores a value into the run variables", logic.execute_set_variable,
    config_fields=[
        _f("name", "Variable name", required=True),
        _f("value", "Value", placeholder="Supports {{variables}}"),
    ],
))

NODE_CATEGORIES = ["trigger", "voice", "ai", "messaging", "logic", "flow"]


def get_spec(node_type: str) -> NodeSpec:
    return REGISTRY[node_type]


def registry_dump() -> list[dict]:
    """Serialised registry for the frontend palette and inspector."""
    dump = []
    for spec in REGISTRY.values():
        dump.append({
            "type": spec.type,
            "label": spec.label,
            "icon": spec.icon,
            "category": spec.category,
            "description": spec.description,
            "outputs": spec.outputs,
            "config_fields": [
                {
                    "name": f.name, "label": f.label, "type": f.type, "required": f.required,
                    "default": f.default, "options": f.options, "placeholder": f.placeholder,
                }
                for f in spec.config_fields
            ],
        })
    return sorted(dump, key=lambda s: (NODE_CATEGORIES.index(s["category"]), s["label"]))
