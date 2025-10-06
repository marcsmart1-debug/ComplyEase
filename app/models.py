from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class User(BaseModel):
    id: str
    email: EmailStr
    hashed_password: str
    created_at: datetime
    stripe_customer_id: Optional[str] = None

class UserInDB(User):
    pass

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class Subscription(BaseModel):
    user_id: str
    stripe_subscription_id: str
    status: str
    current_period_end: datetime
    created_at: datetime

class Article(BaseModel):
    title: str
    link: str
    published: str
    summary: str
    full_content: Optional[str] = None
    ai_summary: Optional[str] = None
