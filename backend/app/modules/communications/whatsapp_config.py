"""Persistence for the business's own WhatsApp (Meta Cloud API) credentials,
entered on the Settings page instead of set as backend environment
variables (spec: user-configurable WhatsApp channel)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret
from app.modules.communications.models import WhatsAppSettings


async def get_whatsapp_settings(session: AsyncSession) -> WhatsAppSettings:
    row = (await session.execute(select(WhatsAppSettings).limit(1))).scalar_one_or_none()
    if row is None:
        row = WhatsAppSettings()
        session.add(row)
        await session.flush()
    return row


async def get_whatsapp_credentials(session: AsyncSession) -> tuple[str, str, str]:
    """Return (phone_number_id, access_token, verify_token); access_token is
    decrypted here, the only place it's ever read back in the clear."""
    row = await get_whatsapp_settings(session)
    access_token = decrypt_secret(row.access_token) if row.access_token else ""
    return row.phone_number_id, access_token, row.verify_token


async def save_whatsapp_settings(
    session: AsyncSession, *, phone_number_id: str, access_token: str | None, verify_token: str,
) -> WhatsAppSettings:
    """`access_token=None` keeps whatever token is already stored (so the
    Settings form can be resaved without re-entering it, like the knowledge
    base's database sources)."""
    row = await get_whatsapp_settings(session)
    row.phone_number_id = phone_number_id.strip()
    row.verify_token = verify_token.strip()
    if access_token:
        row.access_token = encrypt_secret(access_token.strip())
    await session.flush()
    return row
