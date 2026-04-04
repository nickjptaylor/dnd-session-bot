from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def fix_database_url(self):
        """Railway provides postgresql:// but asyncpg needs postgresql+asyncpg://"""
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self

    # Discord
    discord_bot_token: str
    discord_client_id: str = ""
    discord_client_secret: str = ""

    # AI / LLM
    anthropic_api_key: str = ""

    # Transcription
    deepgram_api_key: str = ""
    assemblyai_api_key: str = ""

    # Image Generation
    flux_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://dnd:dnd@localhost:5432/dnd_session_bot"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Debug — set to your Discord server ID for instant command registration
    debug_guild_ids: str = ""

    # Tavern Recap (Lovable/Supabase)
    tavern_recap_supabase_url: str = "https://kowjiumihltsgebyzgox.supabase.co"
    bot_api_key: str = ""

    # S3
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "dnd-session-bot"


settings = Settings()
