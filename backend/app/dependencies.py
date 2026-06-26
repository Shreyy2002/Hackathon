"""
FastAPI shared dependencies.
Requirements: 2.1, 13.1
"""
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve the current user from the 'X-Current-User' session cookie.

    Raises HTTP 401 when:
    - Cookie is missing
    - Cookie value is not a valid UUID
    - No matching User row exists in the database
    """
    raw = request.cookies.get("X-Current-User")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Current-User cookie",
        )

    try:
        user_id = UUID(raw)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in X-Current-User cookie",
        )

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
