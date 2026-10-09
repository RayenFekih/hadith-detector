from pydantic import BaseModel, ConfigDict


class Config(BaseModel):
    """Application settings. Immutable after construction."""

    model_config = ConfigDict(frozen=True)


config = Config()
