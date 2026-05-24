"""
认证 + 多租户中间件
公测版：Bearer Token 简单认证
每个用户（tenant）有独立的 tenant_id，数据完全隔离
"""

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
import jwt
import os
import hashlib
import time

# ============================================================
# 配置
# ============================================================
SECRET_KEY = os.getenv("JWT_SECRET", "replenishment-engine-mvp-secret-change-me")
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "720"))  # 30天
ALGORITHM = "HS256"

security = HTTPBearer(auto_error=False)


# ============================================================
# Token模型
# ============================================================

class TokenData:
    def __init__(self, tenant_id: str, exp: datetime):
        self.tenant_id = tenant_id
        self.exp = exp


# ============================================================
# 简单用户存储（公测版：内存 dict）
# 生产环境请替换为数据库
# ============================================================

class UserStore:
    """内存用户存储"""
    _users = {}

    @classmethod
    def get(cls, tenant_id: str):
        return cls._users.get(tenant_id)

    @classmethod
    def create(cls, tenant_id: str, password: str, extra: dict = None):
        """创建用户（注册）"""
        if cls._users.get(tenant_id):
            raise ValueError("用户已存在")

        salt = os.urandom(16).hex()
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()

        cls._users[tenant_id] = {
            "tenant_id": tenant_id,
            "pwd_salt": salt,
            "pwd_hash": pwd_hash,
            "created_at": datetime.now().isoformat(),
            "extra": extra or {},
        }
        return True

    @classmethod
    def verify(cls, tenant_id: str, password: str) -> bool:
        """验证密码"""
        user = cls._users.get(tenant_id)
        if not user:
            return False
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                        user["pwd_salt"].encode(), 100000).hex()
        return pwd_hash == user["pwd_hash"]


# ============================================================
# Token工具
# ============================================================

def create_token(tenant_id: str) -> str:
    """生成 JWT token"""
    exp = datetime.now() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"tenant_id": tenant_id, "exp": exp.timestamp()}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    """解析 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"])
        return TokenData(tenant_id=payload["tenant_id"], exp=exp)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token无效")


# ============================================================
# 认证依赖
# ============================================================

async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """FastAPI 依赖：从 Authorization header 获取当前 tenant_id"""
    if not credentials:
        raise HTTPException(status_code=401, detail="请提供认证Token")

    token_data = decode_token(credentials.credentials)
    return token_data.tenant_id


# ============================================================
# 注册 / 登录 API
# ============================================================

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class RegisterRequest(BaseModel):
    tenant_id: str
    password: str


class LoginRequest(BaseModel):
    tenant_id: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str


class RegisterResponse(BaseModel):
    tenant_id: str
    created_at: str


@router.post("/auth/register", response_model=RegisterResponse, status_code=201)
def register(data: RegisterRequest):
    """注册新用户（公测版）"""
    try:
        UserStore.create(data.tenant_id, data.password)
        return RegisterResponse(
            tenant_id=data.tenant_id,
            created_at=datetime.now().isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/auth/login", response_model=AuthResponse)
def login(data: LoginRequest):
    """登录获取Token"""
    if not UserStore.verify(data.tenant_id, data.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(data.tenant_id)
    return AuthResponse(access_token=token, tenant_id=data.tenant_id)