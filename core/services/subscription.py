import logging
from dataclasses import dataclass

import httpx

from bot.config import settings

log = logging.getLogger(__name__)

# Tier limits keyed by Stripe product_id
TIER_LIMITS = {
    # Free / no subscription
    "free": {
        "name": "Apprentice",
        "campaigns": 1,
        "sessions_per_month": 999,
        "session_length_hours": 4,
        "portraits_per_session": 0,
        "dm_tips": False,
        "multi_party": False,
    },
    # Tavern Regular - $5/mo
    "prod_UFzp7ylPjjYICA": {
        "name": "Tavern Regular",
        "campaigns": 2,
        "sessions_per_month": 4,
        "session_length_hours": 4,
        "portraits_per_session": 1,
        "dm_tips": False,
        "multi_party": False,
    },
    # Adventurer - $9/mo
    "prod_UGBhmLly8JXtcH": {
        "name": "Adventurer",
        "campaigns": 5,
        "sessions_per_month": 8,
        "session_length_hours": 4,
        "portraits_per_session": 2,
        "dm_tips": True,
        "multi_party": False,
    },
    # Guild Master - $19/mo
    "prod_UFtjWnJa0EOTqX": {
        "name": "Guild Master",
        "campaigns": 0,  # 0 = unlimited
        "sessions_per_month": 0,  # 0 = unlimited
        "session_length_hours": 0,  # 0 = unlimited
        "portraits_per_session": 0,  # 0 = unlimited (for Guild Master)
        "dm_tips": True,
        "multi_party": True,
    },
}

# Guild Master special case — 0 means unlimited for this tier
UNLIMITED_PRODUCT = "prod_UFtjWnJa0EOTqX"


@dataclass
class SubscriptionInfo:
    """Subscription status from Tavern Recap."""
    subscribed: bool
    product_id: str | None
    tier_name: str
    limits: dict


async def check_subscription(email: str) -> SubscriptionInfo:
    """Check subscription status by calling the Lovable check-subscription edge function."""
    url = f"{settings.tavern_recap_supabase_url}/functions/v1/bot-check-user"

    try:
        headers = {"Content-Type": "application/json"}
        if settings.bot_api_key:
            headers["x-bot-api-key"] = settings.bot_api_key

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                json={"email": email},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        log.error(f"Subscription check failed for {email}: {e.response.status_code}")
        # Default to free tier on error
        return SubscriptionInfo(
            subscribed=False,
            product_id=None,
            tier_name="Apprentice",
            limits=TIER_LIMITS["free"],
        )
    except Exception:
        log.exception(f"Subscription check failed for {email}")
        return SubscriptionInfo(
            subscribed=False,
            product_id=None,
            tier_name="Apprentice",
            limits=TIER_LIMITS["free"],
        )

    subscribed = data.get("subscribed", False)
    product_id = data.get("product_id")

    if subscribed and product_id and product_id in TIER_LIMITS:
        limits = TIER_LIMITS[product_id]
    else:
        limits = TIER_LIMITS["free"]
        product_id = None

    tier_name = limits["name"]
    log.info(f"Subscription check for {email}: {tier_name} (subscribed={subscribed})")

    return SubscriptionInfo(
        subscribed=subscribed,
        product_id=product_id,
        tier_name=tier_name,
        limits=limits,
    )


def is_unlimited(product_id: str | None) -> bool:
    """Check if a product ID is the unlimited (Guild Master) tier."""
    return product_id == UNLIMITED_PRODUCT


def get_limit(limits: dict, key: str) -> int | None:
    """Get a limit value. Returns None if unlimited (Guild Master with 0 value)."""
    value = limits.get(key, 0)
    if limits.get("name") == "Guild Master" and value == 0:
        return None  # unlimited
    return value
