"""Voice node executors.

Voice nodes accumulate telecom *actions* (AT-style: Say / Play / GetSpeech /
Dial / Hangup) that the voice webhook returns to Africa's Talking.
"""

from app.modules.workflows.nodes.base import (
    RunContext,
    NodeResult,
    ServiceBag,
    completed,
    render_template,
    resolve_value,
    waiting,
)


def execute_make_call(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    to = render_template(config.get("to", ""), ctx.variables)
    services.comms.make_call(to=to)
    ctx.actions.append({"action": "Dial", "phoneNumber": to})
    return completed(detail={"dialed": to})


def execute_collect_speech(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    """Pause the run and ask the caller to speak.

    The engine stops here and returns a GetSpeech action; the next voice
    webhook (with the recording URL) resumes the run at the ``speech`` output.
    """
    prompt = render_template(config.get("prompt", "") or "Please speak now.", ctx.variables)
    if prompt:
        ctx.actions.append({"action": "Say", "text": prompt})
    ctx.actions.append({
        "action": "GetSpeech",
        "timeout": int(config.get("timeout", 10) or 10),
    })
    return waiting(prompt, detail={"prompt": prompt})


def execute_play_audio(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    audio_url = resolve_value(config, ctx.variables, "audio_url")
    if not audio_url:
        return NodeResult(status="failed", detail={"error": "play_audio: no audio_url configured or produced"})
    ctx.actions.append({"action": "Play", "url": audio_url})
    return completed(detail={"played": audio_url})


def execute_play_text(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    """Play Voice: speak literal text or a variable (usually a translation)."""
    text = resolve_value(config, ctx.variables, "text", var_key="from_variable")
    if not text:
        return NodeResult(status="failed", detail={"error": "play_text: no text provided"})
    text = render_template(str(text), ctx.variables)
    ctx.actions.append({"action": "Say", "text": text})
    return completed(output={"spoken": text}, detail={"spoken": text})


def execute_hang_up(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    ctx.actions.append({"action": "Hangup"})
    return completed()
