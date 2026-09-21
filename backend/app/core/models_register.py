"""Imports every model module so Base.metadata knows all tables (used by init_db)."""
from app.modules.workflows import models as workflows_models  # noqa: F401
from app.modules.communications import models as communications_models  # noqa: F401
from app.modules.conversations import models as conversations_models  # noqa: F401
from app.modules.contacts import models as contacts_models  # noqa: F401
