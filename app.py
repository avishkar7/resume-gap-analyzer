from hashlib import sha256
from pathlib import Path

import streamlit as st

from src.bedrock_chat import BedrockChatClient
from src.bedrock_rag import BedrockRagClient
from src.config import get_settings
from src.prompts import GAP_ANALYZER_PROMPT_TEMPLATE, RESUME_ANALYZER_SYSTEM_PROMPT


BASE_DIR = Path(__file__).resolve().parent
TEXT_UPLOAD_TYPES = ["txt", "md", "csv", "json"]


def load_sample(relative_path: str) -> str:
    sample_path = BASE_DIR / relative_path
    try:
        return sample_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def read_uploaded_text(uploaded_file) -> tuple[str, str]:
    file_bytes = uploaded_file.getvalue()
    signature = f"{uploaded_file.name}:{sha256(file_bytes).hexdigest()}"

    try:
        return file_bytes.decode("utf-8"), signature
    except UnicodeDecodeError:
        return file_bytes.decode("utf-8", errors="replace"), signature


def render_configuration_status() -> None:
    settings = get_settings()

    st.sidebar.header("Configuration Status")
    st.sidebar.write(f"AWS region: `{settings.aws_region or 'Not set'}`")
    st.sidebar.write(f"Model ID: `{settings.bedrock_model_id or 'Not set'}`")

    if settings.has_model_config:
        st.sidebar.success("Bedrock model configured")
    else:
        st.sidebar.warning("Bedrock model not configured")

    if settings.has_knowledge_base_config:
        st.sidebar.success("Knowledge Base configured")
    else:
        st.sidebar.warning("Knowledge Base not configured")

    if settings.has_knowledge_base_ingestion_config:
        st.sidebar.success("Knowledge Base ingestion configured")
    elif settings.has_knowledge_base_config:
        st.sidebar.warning("Knowledge Base data source not configured")

    if settings.has_guardrail_config:
        st.sidebar.success("Guardrail configured")
    else:
        st.sidebar.info("Guardrail not configured")


def main() -> None:
    st.set_page_config(
        page_title="Bedrock Resume RAG Assistant",
        layout="wide",
    )

    settings = get_settings()
    chat_client = BedrockChatClient(settings)
    rag_client = BedrockRagClient(settings)

    st.title("Bedrock Resume RAG Assistant")
    st.caption("Direct Bedrock chat, resume gap analysis, and optional Knowledge Base RAG.")

    render_configuration_status()

    direct_tab, analyzer_tab, rag_tab = st.tabs(
        ["Direct Bedrock Chat", "Resume Gap Analyzer", "Knowledge Base RAG"]
    )

    with direct_tab:
        st.subheader("Direct Bedrock Chat")
        user_question = st.text_area(
            "Question",
            height=160,
            placeholder="Ask a question to send directly to Amazon Bedrock.",
        )

        if st.button("Ask Bedrock", type="primary"):
            if not user_question.strip():
                st.warning("Enter a question first.")
            else:
                with st.spinner("Calling Amazon Bedrock..."):
                    response = chat_client.chat(
                        user_message=user_question.strip(),
                        system_prompt="You are a concise, helpful assistant.",
                    )
                st.markdown(response)

    with analyzer_tab:
        st.subheader("Resume Gap Analyzer")
        st.session_state.setdefault("resume_text", load_sample("data/sample_resume.txt"))
        st.session_state.setdefault(
            "job_description_text",
            load_sample("data/sample_job_description.txt"),
        )

        resume_upload_col, job_description_upload_col = st.columns(2)
        upload_changed = False

        with resume_upload_col:
            resume_upload = st.file_uploader(
                "Upload resume",
                type=TEXT_UPLOAD_TYPES,
                key="resume_upload",
            )

        with job_description_upload_col:
            job_description_upload = st.file_uploader(
                "Upload job description",
                type=TEXT_UPLOAD_TYPES,
                key="job_description_upload",
            )

        if resume_upload:
            uploaded_resume_text, uploaded_resume_signature = read_uploaded_text(
                resume_upload
            )
            if uploaded_resume_signature != st.session_state.get(
                "resume_upload_signature"
            ):
                st.session_state["resume_text"] = uploaded_resume_text
                st.session_state["resume_upload_signature"] = uploaded_resume_signature
                upload_changed = True

        if job_description_upload:
            (
                uploaded_job_description_text,
                uploaded_job_description_signature,
            ) = read_uploaded_text(job_description_upload)
            if uploaded_job_description_signature != st.session_state.get(
                "job_description_upload_signature"
            ):
                st.session_state["job_description_text"] = (
                    uploaded_job_description_text
                )
                st.session_state["job_description_upload_signature"] = (
                    uploaded_job_description_signature
                )
                upload_changed = True

        if upload_changed:
            with st.spinner(
                "Uploading analyzer documents and starting Knowledge Base ingestion..."
            ):
                st.session_state["analyzer_sync_result"] = (
                    rag_client.sync_analyzer_documents(
                        resume_text=st.session_state["resume_text"],
                        job_description_text=st.session_state[
                            "job_description_text"
                        ],
                    )
                )

        analyzer_sync_result = st.session_state.get("analyzer_sync_result")
        if analyzer_sync_result:
            if analyzer_sync_result["ok"]:
                ingestion_job = analyzer_sync_result.get("ingestion_job", {})
                ingestion_job_id = ingestion_job.get("ingestionJobId", "unknown")
                st.success(
                    f"Analyzer documents uploaded. Ingestion job running in AWS: `{ingestion_job_id}`"
                )
            else:
                st.error(analyzer_sync_result["message"])

        resume_text = st.text_area(
            "Resume text",
            key="resume_text",
            height=260,
        )
        job_description_text = st.text_area(
            "Job description text",
            key="job_description_text",
            height=260,
        )

        if st.button("Analyze", type="primary"):
            if not resume_text.strip() or not job_description_text.strip():
                st.warning("Enter both resume text and job description text.")
            else:
                user_prompt = GAP_ANALYZER_PROMPT_TEMPLATE.format(
                    resume_text=resume_text.strip(),
                    job_description_text=job_description_text.strip(),
                )
                with st.spinner("Analyzing resume against job description..."):
                    response = chat_client.chat(
                        user_message=user_prompt,
                        system_prompt=RESUME_ANALYZER_SYSTEM_PROMPT,
                    )
                st.markdown(response)

    with rag_tab:
        st.subheader("Knowledge Base RAG")
        st.markdown("#### Knowledge Base ingestion")
        ingestion_disabled = not settings.has_knowledge_base_ingestion_config

        if st.button(
            "Start ingestion job",
            type="secondary",
            disabled=ingestion_disabled,
        ):
            with st.spinner("Starting Knowledge Base ingestion job..."):
                ingestion_result = rag_client.start_ingestion_job()

            if ingestion_result["ok"]:
                ingestion_job = ingestion_result.get("ingestion_job", {})
                ingestion_job_id = ingestion_job.get("ingestionJobId", "unknown")
                st.success(f"Ingestion job started: `{ingestion_job_id}`")
                # st.json(ingestion_job)
            else:
                st.error(ingestion_result["message"])

        if ingestion_disabled:
            st.info(
                "Set BEDROCK_KNOWLEDGE_BASE_ID and BEDROCK_KNOWLEDGE_BASE_DATA_SOURCE_ID to enable ingestion."
            )

        st.divider()

        rag_question = st.text_area(
            "Knowledge Base question",
            height=160,
            placeholder="Ask a question against your configured Bedrock Knowledge Base.",
        )

        if st.button("Ask Knowledge Base", type="primary"):
            if not rag_question.strip():
                st.warning("Enter a Knowledge Base question first.")
            else:
                with st.spinner("Calling Bedrock Knowledge Base..."):
                    result = rag_client.ask(rag_question.strip())
                st.markdown(result["answer"])
                st.json(result.get("citations", []))


if __name__ == "__main__":
    main()
