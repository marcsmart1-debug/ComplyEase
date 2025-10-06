from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import List
import stripe
import os
from dotenv import load_dotenv
import logging

from app.models import UserCreate, UserLogin, Token, Article
from app.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user_email,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.database import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user_stripe_customer,
    create_subscription,
    get_subscription_by_user_id,
    update_subscription,
    get_user_by_stripe_customer_id,
    email_to_user_id
)
from app.services import (
    fetch_fca_news,
    summarize_article,
    create_stripe_checkout_session,
    create_stripe_portal_session
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.post("/api/auth/register", response_model=Token)
async def register(user: UserCreate):
    existing_user = get_user_by_email(user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = get_password_hash(user.password)
    new_user = create_user(user.email, hashed_password)
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": new_user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/login", response_model=Token)
async def login(user: UserLogin):
    db_user = get_user_by_email(user.email)
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
async def get_current_user(email: str = Depends(get_current_user_email)):
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = get_subscription_by_user_id(user.id)
    
    return {
        "email": user.email,
        "id": user.id,
        "has_subscription": subscription is not None and subscription.status == "active",
        "subscription": {
            "status": subscription.status if subscription else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription else None
        } if subscription else None
    }

@app.post("/api/stripe/create-checkout-session")
async def create_checkout_session(email: str = Depends(get_current_user_email)):
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        session = create_stripe_checkout_session(
            customer_email=user.email,
            customer_id=user.stripe_customer_id
        )
        return {"sessionId": session.id, "url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stripe/create-portal-session")
async def create_portal_session(email: str = Depends(get_current_user_email)):
    user = get_user_by_email(email)
    if not user or not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found")
    
    try:
        session = create_stripe_portal_session(user.stripe_customer_id)
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except Exception as e:
        if "signature" in str(e).lower():
            logger.error(f"Invalid webhook signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    logger.info(f"Received webhook event: {event['type']}")
    
    try:
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            customer_id = session["customer"]
            subscription_id = session["subscription"]
            
            customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
            logger.info(f"Processing checkout.session.completed for email: {customer_email}")
            
            if customer_email:
                user = get_user_by_email(customer_email)
                if user:
                    logger.info(f"Found user {user.id} for email {customer_email}")
                    update_user_stripe_customer(user.id, customer_id)
                    logger.info(f"Updated user {user.id} with Stripe customer {customer_id}")
                    
                    try:
                        subscription = stripe.Subscription.retrieve(subscription_id)
                        logger.info(f"Retrieved subscription {subscription_id} with status {subscription.status}")
                        
                        create_subscription(
                            user_id=user.id,
                            stripe_subscription_id=subscription_id,
                            status=subscription.status,
                            current_period_end=datetime.fromtimestamp(subscription.current_period_end)
                        )
                        logger.info(f"Created subscription record for user {user.id}")
                    except stripe.error.StripeError as e:
                        logger.error(f"Stripe API error retrieving subscription {subscription_id}: {e}")
                        return {"status": "error", "message": "Failed to retrieve subscription details"}
                else:
                    logger.warning(f"No user found for email: {customer_email}")
            else:
                logger.warning(f"No customer email in checkout session: {session.get('id')}")
        
        elif event["type"] == "customer.subscription.updated":
            subscription = event["data"]["object"]
            customer_id = subscription["customer"]
            logger.info(f"Processing customer.subscription.updated for customer {customer_id}")
            
            user = get_user_by_stripe_customer_id(customer_id)
            if user:
                update_subscription(
                    user_id=user.id,
                    status=subscription["status"],
                    current_period_end=datetime.fromtimestamp(subscription["current_period_end"])
                )
                logger.info(f"Updated subscription for user {user.id}")
            else:
                logger.warning(f"No user found for Stripe customer: {customer_id}")
        
        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            customer_id = subscription["customer"]
            logger.info(f"Processing customer.subscription.deleted for customer {customer_id}")
            
            user = get_user_by_stripe_customer_id(customer_id)
            if user:
                update_subscription(
                    user_id=user.id,
                    status="canceled",
                    current_period_end=datetime.fromtimestamp(subscription["current_period_end"])
                )
                logger.info(f"Canceled subscription for user {user.id}")
            else:
                logger.warning(f"No user found for Stripe customer: {customer_id}")
        
    except Exception as e:
        logger.error(f"Error processing webhook event {event['type']}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    
    return {"status": "success"}

@app.get("/api/news", response_model=List[Article])
async def get_news(email: str = Depends(get_current_user_email)):
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = get_subscription_by_user_id(user.id)
    if not subscription or subscription.status != "active":
        raise HTTPException(
            status_code=403,
            detail="Active subscription required to access news"
        )
    
    articles = await fetch_fca_news()
    return articles

@app.get("/api/news/{article_index}/summary")
async def get_article_summary(article_index: int, email: str = Depends(get_current_user_email)):
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription = get_subscription_by_user_id(user.id)
    if not subscription or subscription.status != "active":
        raise HTTPException(
            status_code=403,
            detail="Active subscription required"
        )
    
    articles = await fetch_fca_news()
    
    if article_index < 0 or article_index >= len(articles):
        raise HTTPException(status_code=404, detail="Article not found")
    
    article = articles[article_index]
    
    if not article.ai_summary:
        article.ai_summary = await summarize_article(article.full_content or article.summary)
    
    return {"summary": article.ai_summary}

@app.get("/api/config")
async def get_config():
    return {
        "stripePublishableKey": os.getenv("STRIPE_PUBLISHABLE_KEY")
    }
