"""User Pydantic schemas."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from models.common import AuthProvider, SubscriptionTier


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None
    role: str = "user"
    auth_provider: AuthProvider = AuthProvider.email
    subscription_tier: SubscriptionTier = SubscriptionTier.free
    onboarding_complete: bool = False
    user_type: Optional[str] = None
    niche: List[str] = Field(default_factory=list)
    created_at: datetime


class SignupBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthBody(BaseModel):
    session_token: str = Field(min_length=10)


class RefreshBody(BaseModel):
    refresh_token: str


class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UpdateProfileBody(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    avatar_url: Optional[str] = None
    user_type: Optional[str] = None
    niche: Optional[List[str]] = None
    onboarding_complete: Optional[bool] = None


class AuthResponse(BaseModel):
    user: UserPublic
    access_token: str
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
