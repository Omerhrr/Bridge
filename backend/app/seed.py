"""First-start seeding: demo user + the Voice Translator workflow (spec section 39).

The demo workflow is the flagship scenario:
    Incoming Call -> Speech to Text -> Translate -> Text to Speech -> Play Voice
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.core.security import hash_password
from app.modules.workflows.models import User, Workflow, WorkflowStatus, WorkflowVersion
from app.modules.workflows.schemas import WorkflowDefinition

logger = get_logger("bridge.seed")

VOICE_TRANSLATOR = WorkflowDefinition(
    nodes=[
        {"id": "1", "type": "incoming_call", "position": {"x": 0, "y": 200}, "config": {}},
        {"id": "2", "type": "collect_speech", "position": {"x": 220, "y": 200}, "config": {"max_duration": 15}},
        {"id": "3", "type": "speech_to_text", "position": {"x": 440, "y": 200}, "config": {"language": "auto"}},
        {"id": "4", "type": "translate", "position": {"x": 660, "y": 200}, "config": {"source_language": "auto", "target_language": "ha"}},
        {"id": "5", "type": "text_to_speech", "position": {"x": 880, "y": 200}, "config": {"language": "ha"}},
        {"id": "6", "type": "play_voice", "position": {"x": 1100, "y": 200}, "config": {}},
    ],
    edges=[
        {"source": "1", "target": "2"},
        {"source": "2", "target": "3"},
        {"source": "3", "target": "4"},
        {"source": "4", "target": "5"},
        {"source": "5", "target": "6"},
    ],
)

SMS_TRANSLATOR = WorkflowDefinition(
    nodes=[
        {"id": "1", "type": "incoming_sms", "position": {"x": 0, "y": 200}, "config": {}},
        {"id": "2", "type": "translate", "position": {"x": 240, "y": 200}, "config": {"source_language": "auto", "target_language": "ha"}},
        {"id": "3", "type": "send_sms", "position": {"x": 480, "y": 200}, "config": {}},
    ],
    edges=[
        {"source": "1", "target": "2"},
        {"source": "2", "target": "3"},
    ],
)

USSD_INFO_SERVICE = WorkflowDefinition(
    # Hackathon track: USSD API. Stateless screens: Africa's Talking re-calls
    # the webhook with star-accumulated input ("1", "1*2", ...) per request.
    nodes=[
        {"id": "1", "type": "ussd_request", "position": {"x": 0, "y": 200}, "config": {}},
        {"id": "2", "type": "ussd_menu", "position": {"x": 240, "y": 200},
         "config": {"title": "Bridge Services", "options": "1. Check balance\n2. Translation help"}},
        {"id": "3", "type": "switch", "position": {"x": 480, "y": 200},
         "config": {"variable": "ussd_selection", "cases": "1,2"}},
        {"id": "4", "type": "ussd_end", "position": {"x": 720, "y": 40},
         "config": {"message": "Your Bridge balance is KES 240.50. Asante!"}},
        {"id": "5", "type": "ussd_menu", "position": {"x": 720, "y": 200},
         "config": {"title": "Translation Help", "options": "1. English to Hausa\n2. Hausa to English"}},
        {"id": "6", "type": "ussd_end", "position": {"x": 960, "y": 200},
         "config": {"message": "A Bridge translator will call you back shortly."}},
        {"id": "7", "type": "ussd_end", "position": {"x": 720, "y": 360},
         "config": {"message": "Invalid choice. Please dial again."}},
    ],
    edges=[
        {"source": "1", "target": "2"},
        {"source": "2", "target": "3"},
        {"source": "3", "target": "4", "source_handle": "1"},
        {"source": "3", "target": "5", "source_handle": "2"},
        {"source": "5", "target": "6"},
        {"source": "3", "target": "7", "source_handle": "default"},
    ],
)

SMS_AIRTIME_REWARD = WorkflowDefinition(
    # Hackathon track: Airtime API. Inactive by default so it does not
    # compete with the SMS Translator for the SMS webhook; activate to demo.
    nodes=[
        {"id": "1", "type": "incoming_sms", "position": {"x": 0, "y": 200}, "config": {}},
        {"id": "2", "type": "condition", "position": {"x": 240, "y": 200},
         "config": {"variable": "text", "operator": "contains", "value": "REWARD"}},
        {"id": "3", "type": "send_airtime", "position": {"x": 480, "y": 80},
         "config": {"amount": "10", "currency_code": "KES"}},
        {"id": "4", "type": "send_sms", "position": {"x": 720, "y": 80},
         "config": {"text": "Asante! You have received KES 10 airtime from Bridge."}},
        {"id": "5", "type": "send_sms", "position": {"x": 720, "y": 320},
         "config": {"text": "Send the word REWARD to receive KES 10 airtime."}},
    ],
    edges=[
        {"source": "1", "target": "2"},
        {"source": "2", "target": "3", "source_handle": "true"},
        {"source": "3", "target": "4"},
        {"source": "2", "target": "5", "source_handle": "false"},
    ],
)


async def seed_demo_data() -> None:
    if not settings.seed_demo_data:
        return
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(Workflow))).scalar_one()
        if count > 0:
            return

        # Demo user for the authenticated dashboard (spec section 32).
        user_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
        if user_count == 0:
            session.add(
                User(
                    email="demo@bridge.app",
                    full_name="Bridge Demo",
                    hashed_password=hash_password("bridge-demo-2026"),
                )
            )

        for name, description, definition, status in (
            ("Voice Translator", "Translate live speech between English and Hausa during a call.", VOICE_TRANSLATOR, WorkflowStatus.active),
            ("SMS Translator", "Translate incoming SMS and reply in the target language.", SMS_TRANSLATOR, WorkflowStatus.active),
            ("USSD Info Service", "Multi-level USSD menu: balance, translation help and invalid-input handling.", USSD_INFO_SERVICE, WorkflowStatus.active),
            ("SMS Airtime Reward", "Reward customers with airtime when they text REWARD (Airtime API demo).", SMS_AIRTIME_REWARD, WorkflowStatus.inactive),
        ):
            workflow = Workflow(name=name, description=description, status=status)
            session.add(workflow)
            await session.flush()
            version = WorkflowVersion(
                workflow_id=workflow.id, version_number=1,
                definition=definition.model_dump(), comment="seeded demo",
            )
            session.add(version)
            await session.flush()
            workflow.current_version_id = version.id

        await session.commit()
        log_event(logger, "seed.completed", workflows=4)
