"""Node registry: maps node types to implementations and exposes metadata
for validation and the frontend palette (spec sections 11/14)."""
from app.modules.workflows.nodes.airtime import SendAirtimeNode
from app.modules.workflows.nodes.base import BaseNode
from app.modules.workflows.nodes.call import (
    CollectSpeechNode,
    HangUpNode,
    MakeCallNode,
    PlayAudioNode,
    PlayTextNode,
    PlayVoiceNode,
)
from app.modules.workflows.nodes.condition import (
    ConditionNode,
    DelayNode,
    SetVariableNode,
    SwitchNode,
)
from app.modules.workflows.nodes.end import EndNode
from app.modules.workflows.nodes.relay import BridgeRelayNode
from app.modules.workflows.nodes.sms import SendSmsNode
from app.modules.workflows.nodes.speech_to_text import SpeechToTextNode
from app.modules.workflows.nodes.text_to_speech import TextToSpeechNode
from app.modules.workflows.nodes.translate import TranslateNode
from app.modules.workflows.nodes.trigger import (
    IncomingCallNode,
    IncomingSmsNode,
    UssdRequestNode,
)
from app.modules.workflows.nodes.ussd import UssdEndNode, UssdMenuNode

NODE_REGISTRY: dict[str, type[BaseNode]] = {
    node.type: node
    for node in (
        IncomingCallNode,
        IncomingSmsNode,
        UssdRequestNode,
        MakeCallNode,
        CollectSpeechNode,
        PlayAudioNode,
        PlayTextNode,
        PlayVoiceNode,
        HangUpNode,
        SendSmsNode,
        BridgeRelayNode,
        SpeechToTextNode,
        TranslateNode,
        TextToSpeechNode,
        ConditionNode,
        SwitchNode,
        DelayNode,
        SetVariableNode,
        UssdMenuNode,
        UssdEndNode,
        SendAirtimeNode,
        EndNode,
    )
}

TRIGGER_TYPES = {n.type for n in NODE_REGISTRY.values() if n.category == "trigger"}


def get_node_class(node_type: str) -> type[BaseNode] | None:
    return NODE_REGISTRY.get(node_type)


def list_node_metadata() -> list[dict]:
    """Metadata for every node, used by the palette and inspector."""
    order = {"trigger": 0, "voice": 1, "ai": 2, "messaging": 3,
             "telecom": 4, "logic": 5, "flow": 6}
    nodes = [cls().metadata() for cls in NODE_REGISTRY.values()]
    return sorted(nodes, key=lambda n: (order.get(n["category"], 9), n["label"]))
