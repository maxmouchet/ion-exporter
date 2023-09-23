from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ion_username: str = Field(..., title="Instant On username")
    ion_password: str = Field(..., title="Instant On password")
    ion_otp: str | None = Field(None, title="Instant On one-time password")
    log_format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        title="Log format",
    )
    log_level: str = Field("info", title="Log level")
    host: str = Field("", title="Address on which to listen")
    port: int = Field(8000, title="Port on which to listen")
