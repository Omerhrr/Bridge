"""AI node executors.

Nodes never talk to AI providers directly — they go through the AI service
abstraction (spec §26), so swapping providers never touches the workflow.
"""

from app.modules.workflows.nodes.base import (
    RunContext,
    NodeResult,
    ServiceBag,
    completed,
    render_template,
    resolve_value,
)


def execute_speech_to_text(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    recording_url = ctx.variables.get("recording_url")
    if not recording_url:
        return NodeResult(status="failed", detail={"error": "speech_to_text: no recording available"})
    text = services.ai.transcribe(recording_url, language=config.get("language", "auto"))
    return completed(
        output={"transcript": text, "last_node_output": text},
        detail={"transcript": text, "recording_url": recording_url},
    )


def execute_text_to_speech(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    text = resolve_value(config, ctx.variables, "text", var_key="from_variable")
    if not text:
        return NodeResult(status="failed", detail={"error": "text_to_speech: no text provided"})
    text = render_template(str(text), ctx.variables)
    language = config.get("language", "en")
    audio_url = services.ai.synthesize(text, language=language)
    return completed(output={"audio_url": audio_url}, detail={"audio_url": audio_url, "language": language})


def execute_translate(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    text = resolve_value(config, ctx.variables, "text", var_key="from_variable")
    if not text:
        text = ctx.variables.get("last_node_output")
    if not text:
        return NodeResult(status="failed", detail={"error": "translate: no text provided"})
    source = config.get("source_language", "auto") or "auto"
    target = config.get("target_language") or "ha"
    result = services.ai.translate(str(text), source=source, target=target)
    return completed(
        output={
            "translation": result.text,
            "source_language": result.detected_source or source,
            "target_language": target,
            "last_node_output": result.text,
        },
        detail={"source": result.detected_source or source, "target": target, "translated": result.text},
    )


def execute_detect_language(config: dict, ctx: RunContext, services: ServiceBag) -> NodeResult:
    text = resolve_value(config, ctx.variables, "text", var_key="from_variable") or ctx.variables.get("last_node_output")
    if not text:
        return NodeResult(status="failed", detail={"error": "detect_language: no text provided"})
    language = services.ai.detect_language(str(text))
    return completed(output={"detected_language": language}, detail={"language": language})
