"""Translation node (spec sections 11/26)."""
from typing import Any

from app.modules.ai.languages import LANGUAGES, normalize_language
from app.modules.workflows.nodes.base import BaseNode, NodeExecutionError, NodeResult, render_template

_LANGUAGE_CODES = sorted(LANGUAGES, key=lambda code: LANGUAGES[code])


class TranslateNode(BaseNode):
    type = "translate"
    label = "Translate"
    category = "ai"
    description = "Translates text into any language (source language is auto-detected)"
    icon = "languages"
    config_schema = [
        {"name": "target_language", "label": "Target Language", "type": "select",
         "required": True, "options": ["contact", *_LANGUAGE_CODES],
         "hint": "'contact' = the sender's saved language"},
        {"name": "source_language", "label": "Source Language", "type": "select",
         "required": False, "options": ["auto", *_LANGUAGE_CODES], "default": "auto"},
        {"name": "text", "label": "Text", "type": "textarea", "required": False,
         "hint": "Defaults to the transcript or incoming message; supports {{variables}}"},
    ]

    async def execute(self, config: dict[str, Any], ctx) -> NodeResult:
        ai = ctx.services.get("ai")
        text = (
            render_template(config.get("text", ""), ctx.variables)
            or ctx.variables.get("transcript")
            or ctx.variables.get("text", "")
        )
        if not text:
            raise NodeExecutionError("Translate has no input text")
        source = config.get("source_language") or "auto"
        raw_target = render_template(config.get("target_language") or "", ctx.variables) \
            or ctx.variables.get("target_language", "en")

        if raw_target == "contact":
            target = await self._contact_language(ctx)
            if not target:
                # Unknown preference: pass the text through untouched.
                ctx.variables["translation"] = text
                await ctx.record("translation.skipped", self, reason="contact language unknown")
                return NodeResult(outputs={"translation": text})
        else:
            target = normalize_language(raw_target) or raw_target

        try:
            result = await ai.translation.translate(text, source=source, target=target)
        except Exception as exc:
            raise NodeExecutionError(f"Translation failed: {exc}") from exc
        ctx.variables["translation"] = result.text
        ctx.variables["source_language"] = result.source
        ctx.variables["target_language"] = result.target
        await ctx.record(
            "translation.completed",
            self,
            source=result.source,
            target=result.target,
            text=result.text,
            provider=result.provider,
        )
        return NodeResult(outputs={"translation": result.text})

    @staticmethod
    async def _contact_language(ctx) -> str | None:
        db = ctx.services.get("db")
        phone = ctx.variables.get("sender") or ctx.variables.get("caller") or ctx.variables.get("phone_number")
        if db is None or not phone:
            return None
        from sqlalchemy import select

        from app.modules.contacts.models import Contact

        result = await db.execute(select(Contact.language).where(Contact.phone_number == phone))
        return result.scalar_one_or_none()
