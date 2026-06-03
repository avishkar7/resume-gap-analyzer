import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


class Settings(BaseModel):
    aws_region: str = Field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))
    bedrock_model_id: str = Field(
        default_factory=lambda: os.getenv("BEDROCK_MODEL_ID", "")
    )
    bedrock_knowledge_base_id: str = Field(
        default_factory=lambda: os.getenv("BEDROCK_KNOWLEDGE_BASE_ID", "")
    )
    bedrock_knowledge_base_data_source_id: str = Field(
        default_factory=lambda: os.getenv("BEDROCK_KNOWLEDGE_BASE_DATA_SOURCE_ID", "")
    )
    bedrock_guardrail_id: str = Field(
        default_factory=lambda: os.getenv("BEDROCK_GUARDRAIL_ID", "")
    )
    bedrock_guardrail_version: str = Field(
        default_factory=lambda: os.getenv("BEDROCK_GUARDRAIL_VERSION", "")
    )

    @property
    def has_model_config(self) -> bool:
        return bool(self.aws_region and self.bedrock_model_id)

    @property
    def has_knowledge_base_config(self) -> bool:
        return bool(self.bedrock_knowledge_base_id)

    @property
    def has_knowledge_base_ingestion_config(self) -> bool:
        return bool(
            self.bedrock_knowledge_base_id
            and self.bedrock_knowledge_base_data_source_id
        )

    @property
    def has_guardrail_config(self) -> bool:
        return bool(self.bedrock_guardrail_id and self.bedrock_guardrail_version)

    @property
    def bedrock_model_arn(self) -> str:
        if self.bedrock_model_id.startswith("arn:"):
            return self.bedrock_model_id
        return f"arn:aws:bedrock:{self.aws_region}:910929919929:inference-profile/{self.bedrock_model_id}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
