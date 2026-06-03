import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)

from src.config import Settings, get_settings


class BedrockChatClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def chat(self, user_message: str, system_prompt: str) -> str:
        if not self.settings.has_model_config:
            return "Bedrock model is not configured. Set AWS_REGION and BEDROCK_MODEL_ID in your .env file."

        try:
            client = boto3.client(
                "bedrock-runtime",
                region_name=self.settings.aws_region,
            )
            response = client.converse(
                modelId=self.settings.bedrock_model_id,
                system=[{"text": system_prompt}],
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_message}],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 800,
                    "temperature": 0.2,
                },
            )
        except (NoCredentialsError, PartialCredentialsError):
            return "AWS credentials were not found. Configure AWS credentials before calling Amazon Bedrock."
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "ClientError")
            message = error.get("Message", str(exc))
            return f"Bedrock request failed ({code}): {message}"
        except BotoCoreError as exc:
            return f"Bedrock request failed: {exc}"

        content = (
            response.get("output", {})
            .get("message", {})
            .get("content", [])
        )
        text_parts = [item["text"] for item in content if item.get("text")]

        if not text_parts:
            return "Bedrock returned an empty response."

        return "\n\n".join(text_parts)
