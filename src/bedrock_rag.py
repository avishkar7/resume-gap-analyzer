import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)

from src.config import Settings, get_settings


class BedrockRagClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def ask(self, question: str) -> dict:
        if not self.settings.has_knowledge_base_config:
            return {
                "answer": "Knowledge Base is not configured yet.",
                "citations": [],
            }

        if not self.settings.has_model_config:
            return {
                "answer": "Bedrock model is not configured. Set AWS_REGION and BEDROCK_MODEL_ID in your .env file.",
                "citations": [],
            }

        try:
            client = boto3.client(
                "bedrock-agent-runtime",
                region_name=self.settings.aws_region,
            )
            response = client.retrieve_and_generate(
                input={"text": question},
                retrieveAndGenerateConfiguration={
                    "type": "KNOWLEDGE_BASE",
                    "knowledgeBaseConfiguration": {
                        "knowledgeBaseId": self.settings.bedrock_knowledge_base_id,
                        "modelArn": self.settings.bedrock_model_arn,
                    },
                },
            )
        except (NoCredentialsError, PartialCredentialsError):
            return {
                "answer": "AWS credentials were not found. Configure AWS credentials before calling Bedrock Knowledge Bases.",
                "citations": [],
            }
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "ClientError")
            message = error.get("Message", str(exc))
            return {
                "answer": f"Knowledge Base request failed ({code}): {message}",
                "citations": [],
            }
        except BotoCoreError as exc:
            return {
                "answer": f"Knowledge Base request failed: {exc}",
                "citations": [],
            }

        return {
            "answer": response.get("output", {}).get("text", "Knowledge Base returned an empty response."),
            "citations": response.get("citations", []),
        }
