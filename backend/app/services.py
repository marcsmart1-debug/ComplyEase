import feedparser
from openai import OpenAI
import os
from dotenv import load_dotenv
from typing import List, Optional
from app.models import Article
import stripe

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

async def fetch_fca_news() -> List[Article]:
    feed_url = "https://www.fca.org.uk/news/rss.xml"
    feed = feedparser.parse(feed_url)
    
    articles = []
    for entry in feed.entries[:20]:
        article = Article(
            title=entry.get("title", ""),
            link=entry.get("link", ""),
            published=entry.get("published", ""),
            summary=entry.get("summary", ""),
            full_content=entry.get("description", entry.get("summary", ""))
        )
        articles.append(article)
    
    return articles

async def summarize_article(content: str) -> str:
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes financial news articles concisely. Keep summaries to 2-3 sentences."},
                {"role": "user", "content": f"Summarize this article:\n\n{content}"}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating summary: {str(e)}"

def create_stripe_checkout_session(customer_email: str, customer_id: Optional[str] = None):
    price_id = os.getenv("STRIPE_PRICE_ID")
    
    session_params = {
        "payment_method_types": ["card"],
        "line_items": [
            {
                "price": price_id,
                "quantity": 1,
            }
        ],
        "mode": "subscription",
        "success_url": os.getenv("FRONTEND_URL", "http://localhost:5173") + "/success?session_id={CHECKOUT_SESSION_ID}",
        "cancel_url": os.getenv("FRONTEND_URL", "http://localhost:5173") + "/cancel",
        "customer_email": customer_email,
    }
    
    if customer_id:
        session_params["customer"] = customer_id
        del session_params["customer_email"]
    
    session = stripe.checkout.Session.create(**session_params)
    return session

def create_stripe_portal_session(customer_id: str):
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=os.getenv("FRONTEND_URL", "http://localhost:5173") + "/dashboard",
    )
    return session
