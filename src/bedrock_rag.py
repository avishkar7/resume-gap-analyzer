from datetime import date, datetime
from uuid import uuid4

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)

from src.config import Settings, get_settings


ANALYZER_UPLOAD_PREFIX = "streamlit-analyzer"


def _json_safe(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _bucket_name_from_arn(bucket_arn: str) -> str:
    if bucket_arn.startswith("arn:") and ":::" in bucket_arn:
        return bucket_arn.split(":::", 1)[1]
    return bucket_arn


def _join_s3_key(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part.strip("/"))


class BedrockRagClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _get_s3_upload_target(self) -> dict:
        client = boto3.client(
            "bedrock-agent",
            region_name=self.settings.aws_region,
        )
        response = client.get_data_source(
            knowledgeBaseId=self.settings.bedrock_knowledge_base_id,
            dataSourceId=self.settings.bedrock_knowledge_base_data_source_id,
        )
        data_source = response.get("dataSource", {})
        data_source_config = data_source.get("dataSourceConfiguration", {})

        if data_source_config.get("type") != "S3":
            data_source_type = data_source_config.get("type", "unknown")
            raise ValueError(
                f"Analyzer uploads require an S3-backed Knowledge Base data source. Current data source type: {data_source_type}."
            )

        s3_config = data_source_config.get("s3Configuration", {})
        bucket_name = _bucket_name_from_arn(s3_config.get("bucketArn", ""))
        if not bucket_name:
            raise ValueError("Knowledge Base S3 data source does not include a bucket ARN.")

        inclusion_prefixes = s3_config.get("inclusionPrefixes") or [""]
        upload_prefix = _join_s3_key(inclusion_prefixes[0], ANALYZER_UPLOAD_PREFIX)

        return {
            "bucket": bucket_name,
            "prefix": upload_prefix,
        }

    def sync_analyzer_documents(
        self,
        resume_text: str,
        job_description_text: str,
    ) -> dict:
        if not self.settings.has_knowledge_base_ingestion_config:
            return {
                "ok": False,
                "message": "Knowledge Base ingestion is not configured. Set BEDROCK_KNOWLEDGE_BASE_ID and BEDROCK_KNOWLEDGE_BASE_DATA_SOURCE_ID in your .env file.",
                "uploaded_documents": [],
                "ingestion_job": {},
            }

        if not resume_text.strip() or not job_description_text.strip():
            return {
                "ok": False,
                "message": "Upload both resume text and job description text before syncing analyzer documents.",
                "uploaded_documents": [],
                "ingestion_job": {},
            }

        uploaded_documents = []

        try:
            upload_target = self._get_s3_upload_target()
            s3_client = boto3.client(
                "s3",
                region_name=self.settings.aws_region,
            )
            analyzer_documents = {
                "resume.txt": resume_text.strip(),
                "job-description.txt": job_description_text.strip(),
            }

            for filename, document_text in analyzer_documents.items():
                object_key = _join_s3_key(upload_target["prefix"], filename)
                s3_client.put_object(
                    Bucket=upload_target["bucket"],
                    Key=object_key,
                    Body=document_text.encode("utf-8"),
                    ContentType="text/plain; charset=utf-8",
                )
                uploaded_documents.append(
                    {
                        "bucket": upload_target["bucket"],
                        "key": object_key,
                    }
                )
        except ValueError as exc:
            return {
                "ok": False,
                "message": str(exc),
                "uploaded_documents": uploaded_documents,
                "ingestion_job": {},
            }
        except (NoCredentialsError, PartialCredentialsError):
            return {
                "ok": False,
                "message": "AWS credentials were not found. Configure AWS credentials before uploading analyzer documents.",
                "uploaded_documents": uploaded_documents,
                "ingestion_job": {},
            }
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "ClientError")
            message = error.get("Message", str(exc))
            return {
                "ok": False,
                "message": f"Analyzer document upload failed ({code}): {message}",
                "uploaded_documents": uploaded_documents,
                "ingestion_job": {},
            }
        except BotoCoreError as exc:
            return {
                "ok": False,
                "message": f"Analyzer document upload failed: {exc}",
                "uploaded_documents": uploaded_documents,
                "ingestion_job": {},
            }

        ingestion_result = self.start_ingestion_job()
        if not ingestion_result["ok"]:
            return {
                "ok": False,
                "message": f"Analyzer documents were uploaded, but ingestion did not start. {ingestion_result['message']}",
                "uploaded_documents": uploaded_documents,
                "ingestion_job": {},
            }

        return {
            "ok": True,
            "message": "Analyzer documents uploaded and Knowledge Base ingestion job started.",
            "uploaded_documents": uploaded_documents,
            "ingestion_job": ingestion_result.get("ingestion_job", {}),
        }

    def start_ingestion_job(self) -> dict:
        if not self.settings.has_knowledge_base_config:
            return {
                "ok": False,
                "message": "Knowledge Base is not configured yet.",
                "ingestion_job": {},
            }

        if not self.settings.bedrock_knowledge_base_data_source_id:
            return {
                "ok": False,
                "message": "Knowledge Base data source is not configured. Set BEDROCK_KNOWLEDGE_BASE_DATA_SOURCE_ID in your .env file.",
                "ingestion_job": {},
            }

        try:
            client = boto3.client(
                "bedrock-agent",
                region_name=self.settings.aws_region,
            )
            response = client.start_ingestion_job(
                knowledgeBaseId=self.settings.bedrock_knowledge_base_id,
                dataSourceId=self.settings.bedrock_knowledge_base_data_source_id,
                clientToken=str(uuid4()),
            )
        except (NoCredentialsError, PartialCredentialsError):
            return {
                "ok": False,
                "message": "AWS credentials were not found. Configure AWS credentials before starting Knowledge Base ingestion.",
                "ingestion_job": {},
            }
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = error.get("Code", "ClientError")
            message = error.get("Message", str(exc))
            return {
                "ok": False,
                "message": f"Knowledge Base ingestion failed ({code}): {message}",
                "ingestion_job": {},
            }
        except BotoCoreError as exc:
            return {
                "ok": False,
                "message": f"Knowledge Base ingestion failed: {exc}",
                "ingestion_job": {},
            }

        return {
            "ok": True,
            "message": "Knowledge Base ingestion job started.",
            "ingestion_job": _json_safe(response.get("ingestionJob", {})),
        }

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
