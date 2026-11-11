from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AuthMessage(BaseModel):
    code: str
    message: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class ResetPasswordRequest(TokenRequest):
    password: str = Field(min_length=8, max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class EmailRequest(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    display_name: str | None
    role: str
    account_status: str
    email_verified_at: datetime | None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    current: bool = False


class CsrfResponse(BaseModel):
    token: str


class AdminUserStatusRequest(BaseModel):
    account_status: str

    @field_validator("account_status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"active", "suspended"}:
            raise ValueError("Invalid account status")
        return value


class AdminUserRoleRequest(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in {"user", "admin", "superadmin"}:
            raise ValueError("Invalid role")
        return value


class AdminUserResponse(UserResponse):
    created_at: datetime
    last_login_at: datetime | None
