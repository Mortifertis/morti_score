from secrets import compare_digest

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_admin_token(
    x_admin_token: str | None = Header(default=None),
) -> None:
    settings = get_settings()
    if not x_admin_token or not compare_digest(
        x_admin_token,
        settings.admin_token,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin token",
        )
