from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Admin
from backend.api.deps import get_db, verify_password, create_access_token, get_current_admin

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)):
    result = await session.execute(
        select(Admin).where(Admin.username == body.username, Admin.is_active == True)
    )
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Login yoki parol noto‘g‘ri")
    token = create_access_token({"sub": admin.username})
    return TokenResponse(access_token=token)


@router.get("/me")
async def me(admin: Admin = Depends(get_current_admin)):
    return {"id": admin.id, "username": admin.username}
