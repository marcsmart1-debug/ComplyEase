from sqlalchemy import Column, String, DateTime, ForeignKey, Index, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import os

Base = declarative_base()

class UserDB(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    stripe_customer_id = Column(String, nullable=True, index=True)
    
    subscriptions = relationship("SubscriptionDB", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_stripe_customer_id', 'stripe_customer_id'),
    )

class SubscriptionDB(Base):
    __tablename__ = "subscriptions"
    
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    stripe_subscription_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    user = relationship("UserDB", back_populates="subscriptions")

def get_database_url():
    return os.getenv("DATABASE_URL", "sqlite:///./test.db")

def get_engine():
    return create_engine(get_database_url(), pool_pre_ping=True)
