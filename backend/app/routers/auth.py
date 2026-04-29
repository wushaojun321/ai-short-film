from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from app.models.user import User
from app.models.invite_code import InviteCode
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.services.auth_service import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(data: RegisterRequest):
    # 检查用户名是否已占用
    existing = await User.find_one(User.username == data.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    # 验证激活码（原子：找到未使用的才继续）
    code_doc = await InviteCode.find_one(
        InviteCode.code == data.invite_code,
        InviteCode.used == False,
    )
    if not code_doc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="激活码无效或已使用")

    # 创建用户
    user = User(username=data.username, hashed_password=hash_password(data.password))
    await user.insert()

    # 标记激活码已使用
    now = datetime.now(timezone.utc)
    await code_doc.set({
        InviteCode.used: True,
        InviteCode.used_by: user.id,
        InviteCode.used_at: now,
    })

    token = create_access_token(user.username)
    return TokenResponse(access_token=token, username=user.username)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    user = await User.find_one(User.username == data.username)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    token = create_access_token(user.username)
    return TokenResponse(access_token=token, username=user.username)
