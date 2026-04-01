from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    # S3
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "dnd-session-bot"


settings = Settings()
