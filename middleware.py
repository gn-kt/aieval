from auth import decode_token
from database import get_db
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from logger import get_logger
from models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    if payload is None:
        logger.warning("Auth rejected: invalid or expired token")
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    username = payload.get("sub")
    if username is None:
        logger.warning("Auth rejected: token missing 'sub' claim")
        raise HTTPException(status_code=401, detail="Invalid token payload")
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        logger.warning("Auth rejected: user=%s not found in database", username)
        raise HTTPException(status_code=401, detail="User not found")
    return user
