from typing import Dict, Optional
from app.models import User, Subscription
from datetime import datetime
import uuid

users_db: Dict[str, User] = {}
subscriptions_db: Dict[str, Subscription] = {}
email_to_user_id: Dict[str, str] = {}

def create_user(email: str, hashed_password: str) -> User:
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=email,
        hashed_password=hashed_password,
        created_at=datetime.utcnow()
    )
    users_db[user_id] = user
    email_to_user_id[email] = user_id
    return user

def get_user_by_email(email: str) -> Optional[User]:
    user_id = email_to_user_id.get(email)
    if user_id:
        return users_db.get(user_id)
    return None

def get_user_by_id(user_id: str) -> Optional[User]:
    return users_db.get(user_id)

def update_user_stripe_customer(user_id: str, stripe_customer_id: str):
    if user_id in users_db:
        user = users_db[user_id]
        user.stripe_customer_id = stripe_customer_id
        users_db[user_id] = user

def create_subscription(user_id: str, stripe_subscription_id: str, status: str, current_period_end: datetime) -> Subscription:
    subscription = Subscription(
        user_id=user_id,
        stripe_subscription_id=stripe_subscription_id,
        status=status,
        current_period_end=current_period_end,
        created_at=datetime.utcnow()
    )
    subscriptions_db[user_id] = subscription
    return subscription

def get_subscription_by_user_id(user_id: str) -> Optional[Subscription]:
    return subscriptions_db.get(user_id)

def update_subscription(user_id: str, status: str, current_period_end: datetime):
    if user_id in subscriptions_db:
        subscription = subscriptions_db[user_id]
        subscription.status = status
        subscription.current_period_end = current_period_end
        subscriptions_db[user_id] = subscription

def get_user_by_stripe_customer_id(stripe_customer_id: str) -> Optional[User]:
    for user in users_db.values():
        if user.stripe_customer_id == stripe_customer_id:
            return user
    return None
