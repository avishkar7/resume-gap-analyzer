# bedrock-resume-rag-assistant

A small Streamlit project that demonstrates Amazon Bedrock model inference with `boto3`, a resume/job-description gap analyzer, and an optional Amazon Bedrock Knowledge Bases RAG tab.

The app is intentionally minimal. It opens locally even when AWS credentials, a model ID, or a Knowledge Base are not configured. When Bedrock cannot be reached, the UI shows a readable configuration or request error instead of inventing a response.

## Screenshots

### Direct Bedrock Chat

![Direct Bedrock Chat](demo-chat.png)

### Resume Gap Analyzer

![Resume Gap Analyzer form](demo-resume-analyser.png)

### Resume Gap Analyzer Results

![Resume Gap Analyzer results](demo-resume-analyser-2.png)

## Architecture

- `app.py` contains the Streamlit UI.
- `src/config.py` loads settings from environment variables and `.env`.
- `src/bedrock_chat.py` calls the Bedrock Runtime Converse API.
- `src/bedrock_rag.py` calls Bedrock Agent Runtime `retrieve_and_generate` only when a Knowledge Base ID is configured.
- `src/prompts.py` contains prompt text for the resume analyzer.
- `data/` contains generic sample text files.

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local `.env` file:

```bash
cp .env.example .env
```

Edit `.env` as needed:

```bash
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.nova-pro-v1:0
BEDROCK_KNOWLEDGE_BASE_ID=
BEDROCK_GUARDRAIL_ID=
BEDROCK_GUARDRAIL_VERSION=
```

Do not put AWS access keys in `.env`. Use normal AWS credential configuration, such as AWS CLI profiles, SSO, IAM roles, or environment variables managed outside the repository.

## Run

```bash
streamlit run app.py
```

Then open the local Streamlit URL shown in the terminal.

## AWS Services Used

- Amazon Bedrock Runtime for direct model inference through the Converse API.
- Amazon Bedrock Knowledge Bases through Bedrock Agent Runtime for optional RAG.

To use direct chat, your AWS identity needs permission to call Bedrock Runtime and access the configured model. To use the Knowledge Base tab, set `BEDROCK_KNOWLEDGE_BASE_ID` and make sure the Knowledge Base already exists in the selected AWS region.


## Limitations

- No Terraform, CDK, or deployment automation is included.
- The app does not create or sync a Knowledge Base.
- Guardrail settings are loaded and displayed, but this minimal demo does not attach guardrails to requests.
- Error messages are returned to the UI instead of raising exceptions.
