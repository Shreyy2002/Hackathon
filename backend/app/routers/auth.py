"""
Auth router — role-switching endpoint.
Requirements: 2.1, 13.1

Prefix /api is added in main.py, so routes here use bare paths.
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.user import RoleSwitchRequest, UserRead

router = APIRouter(tags=["auth"])


@router.post("/auth/switch-role", response_model=UserRead)
async def switch_role(
    body: RoleSwitchRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """
    Switch the active persona by setting the X-Current-User session cookie.

    Returns the UserRead for the selected user.
    Raises 404 if the user_id does not exist.
    """
    user = await db.get(User, body.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    response.set_cookie(
        key="X-Current-User",
        value=str(user.id),
        httponly=False,
        samesite="lax",
        max_age=86400,
    )

    return UserRead.model_validate(user)
