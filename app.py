from pathlib import Path

import streamlit as st

from src.bedrock_chat import BedrockChatClient
from src.bedrock_rag import BedrockRagClient
from src.config import get_settings
from src.prompts import GAP_ANALYZER_PROMPT_TEMPLATE, RESUME_ANALYZER_SYSTEM_PROMPT


BASE_DIR = Path(__file__).resolve().parent


def load_sample(relative_path: str) -> str:
    sample_path = BASE_DIR / relative_path
    try:
        return sample_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


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
        resume_text = st.text_area(
            "Resume text",
            value=load_sample("data/sample_resume.txt"),
            height=260,
        )
        job_description_text = st.text_area(
            "Job description text",
            value=load_sample("data/sample_job_description.txt"),
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
