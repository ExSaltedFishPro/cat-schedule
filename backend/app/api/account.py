from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import api_success
from app.db.session import get_db
from app.models import User
from app.schemas.portal import PortalAccountUpsertRequest
from app.services.portal_service import get_portal_account_summary, save_portal_credentials


router = APIRouter(prefix="/account", tags=["account"])


@router.get("/portal")
def get_portal_account(current_user: User = Depends(get_current_user)) -> dict:
    return api_success(get_portal_account_summary(current_user))


@router.post("/portal")
def save_portal_account(
    payload: PortalAccountUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    save_portal_credentials(
        db,
        user=current_user,
        portal_username=payload.portal_username,
        portal_password=payload.portal_password,
    )
    db.refresh(current_user)
    return api_success(get_portal_account_summary(current_user), message="教务账号绑定成功")

