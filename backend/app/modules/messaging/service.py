"""Messaging service: translated outbound SMS and the Bridge relay.

The relay is what makes Bridge useful day to day: two people who don't share
a language text each other *through* the Bridge shortcode, and each side
reads the conversation in their own language.

    Amina (Hausa)  --"TO +254712345678 Ina kwana?"-->  Bridge
    Bridge  --"+2348031234567 via Bridge: Habari za asubuhi?"-->  Juma (Swahili)
    Juma replies in Swahili --> Bridge --> Amina reads it in Hausa

SMS commands (case-insensitive):
    TO <number> <message>   start / switch a chat (also "@<number> <message>")
    <any text>              continue the current chat
    LANG <language>         set your language (code or name, e.g. "LANG Swahili")
    STOP                    end the current chat
    HELP                    how it works
    ASK <question>          ask the business (knowledge base); also the
                            default for any message sent outside a chat
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.modules.ai.languages import language_name, normalize_language
from app.modules.contacts.models import Contact
from app.modules.knowledge.assistant import KnowledgeAssistant
from app.modules.messaging.models import BridgeProfile, MessageLog

logger = get_logger("bridge.messaging")

# Calling codes used to expand local numbers ("0803…") from the sender's own
# country. Longest prefixes first so "+2547…" doesn't match "+2".
_CALLING_CODES = sorted(
    ["234", "254", "255", "256", "257", "250", "251", "252", "233", "225", "221",
     "223", "226", "227", "228", "229", "231", "232", "235", "237", "243", "244",
     "260", "263", "265", "266", "267", "27", "20", "212", "213", "216", "1", "44",
     "33", "49", "91", "86"],
    key=len, reverse=True,
)

HELP_TEXT = (
    "Bridge lets you text anyone in any language.\n"
    "TO +2547XXXXXXXX Hello - message someone; they read it in their language.\n"
    "Then just reply to keep chatting.\n"
    "LANG Swahili - set your language.\n"
    "STOP - end the chat."
)

_COMMAND_TO = re.compile(r"^\s*(?:to\s+|@)(\+?[\d\s\-()]{7,20})\s*[:,]?\s*(.*)$", re.I | re.S)
_COMMAND_LANG = re.compile(r"^\s*lang(?:uage)?\s+(.+?)\s*$", re.I)
_COMMAND_STOP = re.compile(r"^\s*(stop|end|bye)\s*$", re.I)
_COMMAND_HELP = re.compile(r"^\s*(help|menu|\?)\s*$", re.I)
_COMMAND_ASK = re.compile(r"^\s*ask\b[\s:,-]*(.*)$", re.I | re.S)


class InvalidPhoneNumber(ValueError):
    pass


def normalize_phone(raw: str, reference: str | None = None) -> str:
    """Return an E.164 number (+XXXXXXXXXXX).

    Local numbers ("0803 123 4567") are expanded with the calling code of
    `reference` (usually the sender's own number) when it is known.
    """
    digits = re.sub(r"[^\d+]", "", raw or "")
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if digits.startswith("+"):
        number = digits
    elif digits.startswith("0") and reference:
        ref = re.sub(r"[^\d]", "", reference)
        code = next((c for c in _CALLING_CODES if ref.startswith(c)), None)
        if not code:
            raise InvalidPhoneNumber(f"Add the country code to {raw.strip()}")
        number = f"+{code}{digits[1:]}"
    elif len(digits) >= 10:
        number = "+" + digits
    else:
        raise InvalidPhoneNumber(f"Add the country code to {raw.strip()}")
    if not re.fullmatch(r"\+\d{8,15}", number):
        raise InvalidPhoneNumber(f"'{raw.strip()}' is not a valid phone number")
    return number


def clean_phone(raw: str | None) -> str:
    """Best-effort E.164 for numbers arriving from webhooks (a "+" that was
    form-decoded into a space, stray whitespace); falls back to the input."""
    value = (raw or "").strip()
    if not value:
        return value
    try:
        return normalize_phone(value if value.startswith(("+", "0")) else "+" + value)
    except InvalidPhoneNumber:
        return value


@dataclass
class DeliveryResult:
    to: str
    status: str
    text: str
    original_text: str
    target_language: str | None = None
    source_language: str | None = None
    message_id: str | None = None
    error: str | None = None
    log_id: int | None = None

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class RelayOutcome:
    action: str
    deliveries: list[DeliveryResult] = field(default_factory=list)


class MessagingService:
    def __init__(self, session: AsyncSession, ai, comms, run_id: str | None = None):
        self.session = session
        self.ai = ai
        self.comms = comms
        self.run_id = run_id

    # ------------------------------------------------------------------ contacts
    async def get_contact(self, phone: str) -> Contact | None:
        result = await self.session.execute(select(Contact).where(Contact.phone_number == phone))
        return result.scalar_one_or_none()

    async def ensure_contact(self, phone: str) -> Contact:
        contact = await self.get_contact(phone)
        if contact is None:
            contact = Contact(phone_number=phone, name="", language=None)
            self.session.add(contact)
            await self.session.flush()
        return contact

    async def get_profile(self, phone: str) -> BridgeProfile:
        result = await self.session.execute(select(BridgeProfile).where(BridgeProfile.phone_number == phone))
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = BridgeProfile(phone_number=phone)
            self.session.add(profile)
            await self.session.flush()
        return profile

    async def set_language(self, phone: str, language: str, *, locked: bool) -> Contact:
        contact = await self.ensure_contact(phone)
        profile = await self.get_profile(phone)
        contact.language = language
        profile.language_locked = profile.language_locked or locked
        await self.session.flush()
        return contact

    async def learn_language(self, phone: str, detected: str | None) -> None:
        """Remember a detected language unless the person chose one explicitly."""
        code = normalize_language(detected)
        if not code:
            return
        contact = await self.ensure_contact(phone)
        profile = await self.get_profile(phone)
        if not profile.language_locked and contact.language != code:
            contact.language = code
            await self.session.flush()

    async def language_of(self, phone: str) -> str | None:
        contact = await self.get_contact(phone)
        return contact.language if contact else None

    async def display_name(self, phone: str) -> str:
        contact = await self.get_contact(phone)
        return contact.name if contact and contact.name else phone

    # --------------------------------------------------------------- translation
    async def translate(self, text: str, target: str | None, source: str = "auto") -> tuple[str, str | None]:
        """Translate `text` into `target`. Returns (text, detected_source)."""
        if not target:
            return text, None
        result = await self.ai.translation.translate(text, source=source, target=target)
        if result.source == target:
            return text, result.source
        return result.text, result.source

    async def localize(self, text: str, phone: str) -> str:
        """System messages are authored in English; send them in the
        recipient's language when we know it."""
        language = await self.language_of(phone)
        if not language or language == "en":
            return text
        try:
            translated, _ = await self.translate(text, language, source="en")
            return translated
        except Exception:  # never block a help message on the AI provider
            return text

    # ------------------------------------------------------------------ delivery
    async def deliver(
        self,
        to: str,
        text: str,
        *,
        target_language: str | None = None,
        source_language: str | None = None,
        sender: str | None = None,
        kind: str = "workflow",
        pretranslated: bool = False,
        original: str | None = None,
        author: str | None = None,
    ) -> DeliveryResult:
        """Translate (optionally), send and log a single SMS.

        `original` is the pre-translation wording when the caller already
        translated; `author` overrides the logged sender (relay messages are
        shown as coming from the person, not the shortcode)."""
        original = original if original is not None else text
        detected = source_language
        outgoing = text
        error = None
        status = "failed"
        message_id = None
        try:
            if target_language and not pretranslated:
                outgoing, detected = await self.translate(text, target_language)
            result = await self.comms.sms.send_sms(
                to=to, text=outgoing, sender_id=sender or settings.default_sms_sender
            )
            status = result.status or "sent"
            message_id = result.message_id
        except Exception as exc:
            error = str(exc)
        entry = MessageLog(
            direction="outbound", kind=kind,
            from_number=author or sender or settings.default_sms_sender,
            to_number=to, original_text=original if outgoing != original else None,
            text=outgoing, source_language=detected, target_language=target_language,
            status=status, provider_message_id=message_id, error=error, run_id=self.run_id,
        )
        self.session.add(entry)
        await self.session.flush()
        log_event(logger, "message.delivered" if not error else "message.failed",
                  to=to, kind=kind, target=target_language, status=status, error=error)
        return DeliveryResult(
            to=to, status=status, text=outgoing, original_text=original,
            target_language=target_language, source_language=detected,
            message_id=message_id, error=error, log_id=entry.id,
        )

    async def log_inbound(self, from_number: str, to_number: str | None, text: str,
                          provider_message_id: str | None = None) -> MessageLog:
        entry = MessageLog(
            direction="inbound", kind="inbound", from_number=clean_phone(from_number), to_number=to_number,
            text=text, status="received", provider_message_id=provider_message_id,
            run_id=self.run_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def broadcast(
        self, recipients: list[str], text: str, *, language_mode: str = "contact",
        sender: str | None = None,
    ) -> list[DeliveryResult]:
        """Send one message to many people, each in their own language.

        language_mode: "contact" (each recipient's saved language), "none"
        (original text), or a language code applied to everyone.
        """
        results: list[DeliveryResult] = []
        cache: dict[str, tuple[str, str | None]] = {}
        for raw in recipients:
            try:
                to = normalize_phone(raw)
            except InvalidPhoneNumber as exc:
                results.append(DeliveryResult(to=raw, status="failed", text=text,
                                              original_text=text, error=str(exc)))
                continue
            await self.ensure_contact(to)
            if language_mode == "none":
                target = None
            elif language_mode in ("contact", "auto"):
                target = await self.language_of(to)
            else:
                target = normalize_language(language_mode)
            # Translate once per language, not once per recipient.
            try:
                if target and target not in cache:
                    cache[target] = await self.translate(text, target)
            except Exception as exc:
                results.append(DeliveryResult(to=to, status="failed", text=text, original_text=text,
                                              target_language=target, error=f"Translation failed: {exc}"))
                continue
            outgoing, detected = cache[target] if target else (text, None)
            results.append(await self.deliver(
                to, outgoing, target_language=target, source_language=detected,
                sender=sender, kind="broadcast", pretranslated=True, original=text,
            ))
        return results

    # --------------------------------------------------------------------- relay
    async def handle_relay(self, sender: str, shortcode: str | None, text: str) -> RelayOutcome:
        """Process one inbound SMS sent to the Bridge shortcode."""
        sender = clean_phone(sender)
        text = (text or "").strip()
        reply_from = shortcode or settings.default_sms_sender
        await self.ensure_contact(sender)
        profile = await self.get_profile(sender)

        async def reply(message: str) -> DeliveryResult:
            localized = await self.localize(message, sender)
            return await self.deliver(sender, localized, sender=reply_from, kind="system", pretranslated=True)

        assistant = KnowledgeAssistant(self.session, self.ai)
        assistant_on = await assistant.is_available()

        if not text or _COMMAND_HELP.match(text):
            return RelayOutcome("help", [await reply(await self._help_text(assistant, assistant_on))])

        if match := _COMMAND_ASK.match(text):
            question = match.group(1).strip()
            if not assistant_on:
                return RelayOutcome("ask_unavailable", [await reply(
                    "Questions aren't available right now. " + HELP_TEXT)])
            if not question:
                return RelayOutcome("ask_empty", [await reply("Type your question after ASK, e.g. ASK What are your opening hours?")])
            return await self._answer_question(assistant, sender, question, reply_from)

        if match := _COMMAND_LANG.match(text):
            code = normalize_language(match.group(1))
            if not code:
                return RelayOutcome("lang_invalid", [await reply(
                    f"Sorry, I don't know the language '{match.group(1)}'. "
                    "Try a name or code, e.g. LANG Swahili, LANG ha, LANG French."
                )])
            await self.set_language(sender, code, locked=True)
            return RelayOutcome("lang_set", [await reply(
                f"Done. Bridge will send you messages in {language_name(code)}."
            )])

        if _COMMAND_STOP.match(text):
            partner = profile.partner_number
            profile.partner_number = None
            await self.session.flush()
            note = f"Chat with {await self.display_name(partner)} ended." if partner else "You have no open chat."
            return RelayOutcome("stop", [await reply(note + " Text TO <number> <message> to start a new one.")])

        if match := _COMMAND_TO.match(text):
            try:
                partner = normalize_phone(match.group(1), reference=sender)
            except InvalidPhoneNumber as exc:
                return RelayOutcome("to_invalid", [await reply(f"{exc}. Example: TO +254712345678 Hello")])
            body = match.group(2).strip()
            if partner == sender:
                return RelayOutcome("to_self", [await reply("You can't open a chat with your own number.")])
            profile.partner_number = partner
            partner_profile = await self.get_profile(partner)
            partner_profile.partner_number = sender
            await self.session.flush()
            if not body:
                return RelayOutcome("to_opened", [await reply(
                    f"Chat with {await self.display_name(partner)} is open. Your next message goes to them."
                )])
            delivery = await self._relay(sender, partner, body, reply_from, first=True)
            confirm = await reply(
                f"Sent to {await self.display_name(partner)}"
                + (f" in {language_name(delivery.target_language)}" if delivery.target_language else "")
                + ". Replies will come here, translated for you."
                if delivery.status != "failed" else
                f"Could not deliver to {partner}: {delivery.error or 'provider error'}"
            )
            return RelayOutcome("relayed", [delivery, confirm])

        if profile.partner_number:
            delivery = await self._relay(sender, profile.partner_number, text, reply_from)
            if delivery.status == "failed":
                return RelayOutcome("relay_failed", [delivery, await reply(
                    f"Could not deliver your message: {delivery.error or 'provider error'}"
                )])
            return RelayOutcome("relayed", [delivery])

        # No open chat: the business assistant answers, if one is configured.
        if assistant_on:
            return await self._answer_question(assistant, sender, text, reply_from)

        # Otherwise learn their language from the message, then onboard.
        try:
            detected = await self.ai.translation.detect(text)
            await self.learn_language(sender, detected)
        except Exception:
            pass
        return RelayOutcome("onboarding", [await reply(HELP_TEXT)])

    async def _help_text(self, assistant: KnowledgeAssistant, assistant_on: bool) -> str:
        if not assistant_on:
            return HELP_TEXT
        name = (await assistant.profile()).name or "us"
        return f"Ask {name} anything: just text your question (or ASK <question> during a chat).\n" + HELP_TEXT

    async def _answer_question(self, assistant: KnowledgeAssistant, sender: str, question: str,
                               reply_from: str | None) -> RelayOutcome:
        from app.modules.knowledge.service import log_query

        result = await assistant.answer(question)
        await self.learn_language(sender, result.language)
        await log_query(self.session, question, result, phone=sender, channel="sms")
        delivery = await self.deliver(sender, result.text, sender=reply_from, kind="answer",
                                      pretranslated=True, source_language=result.language)
        return RelayOutcome("answered" if result.answered else f"answer_{result.reason}", [delivery])

    async def _relay(self, sender: str, partner: str, text: str, reply_from: str | None,
                     first: bool = False) -> DeliveryResult:
        target = await self.language_of(partner)
        detected: str | None = None
        outgoing = text
        try:
            # Translating into the partner's language also detects the
            # sender's language, which we remember for replies to them.
            if target:
                outgoing, detected = await self.translate(text, target)
            else:
                detected = await self.ai.translation.detect(text)
        except Exception as exc:
            log_event(logger, "relay.translation_failed", error=str(exc))
        await self.learn_language(sender, detected)

        label = await self.display_name(sender)
        body = f"{label} via Bridge:\n{outgoing}"
        if first and not target:
            body += "\n\nReply in your own language - Bridge translates."
        return await self.deliver(
            partner, body, target_language=target, source_language=detected,
            sender=reply_from, kind="relay", pretranslated=True,
            original=text if outgoing != text else body, author=sender,
        )
