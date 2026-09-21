"""Contact service and schemas (spec section 30)."""
from pydantic import BaseModel

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contacts.models import Contact


class ContactOut(BaseModel):
    id: int
    phone_number: str
    name: str
    language: str | None
    created_at: object

    model_config = {"from_attributes": True}


class ContactCreate(BaseModel):
    phone_number: str
    name: str = ""
    language: str | None = None


class ContactService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, data: ContactCreate) -> Contact:
        result = await self.session.execute(
            select(Contact).where(Contact.phone_number == data.phone_number)
        )
        contact = result.scalar_one_or_none()
        if contact:
            if data.name:
                contact.name = data.name
            if data.language:
                contact.language = data.language
            return contact
        contact = Contact(
            phone_number=data.phone_number, name=data.name, language=data.language
        )
        self.session.add(contact)
        await self.session.flush()
        return contact

    async def list_contacts(self, limit: int = 200) -> list[Contact]:
        result = await self.session.execute(
            select(Contact).order_by(Contact.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_language_for(self, phone_number: str) -> str | None:
        result = await self.session.execute(
            select(Contact).where(Contact.phone_number == phone_number)
        )
        contact = result.scalar_one_or_none()
        return contact.language if contact else None
