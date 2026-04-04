"""One-time linking codes for secure account connection.

Flow:
1. User signs up on tavernrecap.com (knows their email + Discord ID from OAuth)
2. Website calls POST /api/link/generate to create a short-lived code
3. User types /account link CODE in Discord
4. Bot calls POST /api/link/verify to validate the code
5. If valid, creates the UserLink and returns the subscription info
"""

import logging
import secrets
import time

log = logging.getLogger(__name__)

# In-memory store for linking codes (code → {email, discord_user_id, created_at})
# These expire after 10 minutes
_pending_codes: dict[str, dict] = {}

CODE_EXPIRY_SECONDS = 600  # 10 minutes


def _cleanup_expired():
    """Remove expired codes."""
    now = time.time()
    expired = [code for code, data in _pending_codes.items() if now - data["created_at"] > CODE_EXPIRY_SECONDS]
    for code in expired:
        del _pending_codes[code]


def generate_code(email: str, discord_user_id: int | None = None) -> str:
    """Generate a one-time linking code for an email.

    Args:
        email: The user's email from their tavernrecap.com account
        discord_user_id: Optional Discord ID from OAuth (for extra validation)

    Returns:
        A short code like "TR-7X4K"
    """
    _cleanup_expired()

    # Generate a short, readable code
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No I/O/0/1 to avoid confusion
    random_part = "".join(secrets.choice(chars) for _ in range(4))
    code = f"TR-{random_part}"

    # Ensure uniqueness (extremely unlikely collision but just in case)
    while code in _pending_codes:
        random_part = "".join(secrets.choice(chars) for _ in range(4))
        code = f"TR-{random_part}"

    _pending_codes[code] = {
        "email": email,
        "discord_user_id": discord_user_id,
        "created_at": time.time(),
    }

    log.info(f"Generated linking code {code} for {email}")
    return code


def verify_code(code: str, discord_user_id: int) -> dict | None:
    """Verify and consume a linking code.

    Args:
        code: The code the user typed in Discord
        discord_user_id: The Discord user ID of whoever typed the command

    Returns:
        {"email": ..., "discord_user_id": ...} if valid, None if invalid/expired
    """
    _cleanup_expired()

    code = code.upper().strip()

    if code not in _pending_codes:
        return None

    data = _pending_codes[code]

    # If the code was generated with a specific Discord ID, verify it matches
    if data["discord_user_id"] is not None and data["discord_user_id"] != discord_user_id:
        log.warning(f"Code {code} was generated for Discord user {data['discord_user_id']} but used by {discord_user_id}")
        return None

    # Consume the code (one-time use)
    del _pending_codes[code]

    log.info(f"Linking code {code} verified for {data['email']} by Discord user {discord_user_id}")
    return {
        "email": data["email"],
        "discord_user_id": discord_user_id,
    }


def get_pending_count() -> int:
    """Get number of pending (non-expired) codes. For monitoring."""
    _cleanup_expired()
    return len(_pending_codes)
