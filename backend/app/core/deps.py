"""FastAPI dependency injection helpers.

Common dependencies: current_user, require_role(level), etc.
Implementasi penuh di Sprint 1 (TSK-003 RBAC engine).
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

DBSession = Annotated[AsyncSession, Depends(get_db)]

# Sprint 1+:
# CurrentUser = Annotated[User, Depends(get_current_user)]
# RequireDirektur = Annotated[User, Depends(require_role(Level.L1))]
