from typing import Optional
from app.models import User, Subscription
from app.db_models import UserDB, SubscriptionDB
from app.db_session import get_db_session
from datetime import datetime
import uuid

def create_user(email: str, hashed_password: str) -> User:
    user_id = str(uuid.uuid4())
    with get_db_session() as session:
        db_user = UserDB(
            id=user_id,
            email=email,
            hashed_password=hashed_password,
            created_at=datetime.utcnow()
        )
        session.add(db_user)
    
    return User(
        id=user_id,
        email=email,
        hashed_password=hashed_password,
        created_at=datetime.utcnow()
    )

def get_user_by_email(email: str) -> Optional[User]:
    with get_db_session() as session:
        db_user = session.query(UserDB).filter(UserDB.email == email).first()
        if db_user:
            return User(
                id=db_user.id,
                email=db_user.email,
                hashed_password=db_user.hashed_password,
                created_at=db_user.created_at,
                stripe_customer_id=db_user.stripe_customer_id
            )
    return None

def get_user_by_id(user_id: str) -> Optional[User]:
    with get_db_session() as session:
        db_user = session.query(UserDB).filter(UserDB.id == user_id).first()
        if db_user:
            return User(
                id=db_user.id,
                email=db_user.email,
                hashed_password=db_user.hashed_password,
                created_at=db_user.created_at,
                stripe_customer_id=db_user.stripe_customer_id
            )
    return None

def update_user_stripe_customer(user_id: str, stripe_customer_id: str):
    with get_db_session() as session:
        db_user = session.query(UserDB).filter(UserDB.id == user_id).first()
        if db_user:
            db_user.stripe_customer_id = stripe_customer_id

def create_subscription(user_id: str, stripe_subscription_id: str, status: str, current_period_end: datetime) -> Subscription:
    with get_db_session() as session:
        db_subscription = SubscriptionDB(
            user_id=user_id,
            stripe_subscription_id=stripe_subscription_id,
            status=status,
            current_period_end=current_period_end,
            created_at=datetime.utcnow()
        )
        session.merge(db_subscription)
    
    return Subscription(
        user_id=user_id,
        stripe_subscription_id=stripe_subscription_id,
        status=status,
        current_period_end=current_period_end,
        created_at=datetime.utcnow()
    )

def get_subscription_by_user_id(user_id: str) -> Optional[Subscription]:
    with get_db_session() as session:
        db_subscription = session.query(SubscriptionDB).filter(SubscriptionDB.user_id == user_id).first()
        if db_subscription:
            return Subscription(
                user_id=db_subscription.user_id,
                stripe_subscription_id=db_subscription.stripe_subscription_id,
                status=db_subscription.status,
                current_period_end=db_subscription.current_period_end,
                created_at=db_subscription.created_at
            )
    return None

def update_subscription(user_id: str, status: str, current_period_end: datetime):
    with get_db_session() as session:
        db_subscription = session.query(SubscriptionDB).filter(SubscriptionDB.user_id == user_id).first()
        if db_subscription:
            db_subscription.status = status
            db_subscription.current_period_end = current_period_end

def get_user_by_stripe_customer_id(stripe_customer_id: str) -> Optional[User]:
    with get_db_session() as session:
        db_user = session.query(UserDB).filter(UserDB.stripe_customer_id == stripe_customer_id).first()
        if db_user:
            return User(
                id=db_user.id,
                email=db_user.email,
                hashed_password=db_user.hashed_password,
                created_at=db_user.created_at,
                stripe_customer_id=db_user.stripe_customer_id
            )
    return None
