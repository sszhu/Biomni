# Copilot Instructions for Biomni

These instructions help AI coding agents quickly become productive in this repository. Focus on the concrete patterns and workflows used here.

## Big Picture
- Biomni is a biomedical AI agent. The main entry point is `biomni.agent.A1`, which orchestrates planning, retrieval, and tool execution using LangGraph (`StateGraph`) and LangChain message types.
- LLM selection and configuration is centralized in `biomni.llm.get_llm()` with `SourceType` (OpenAI, AzureOpenAI, Anthropic, Ollama, Gemini, Bedrock, Groq, Custom). Defaults can be auto-detected from model names or `LLM_SOURCE`.
- Data and tools: domain tools live in `biomni/tool/*`, are registered by `biomni/tool/tool_registry.py`, optionally retrieved via `biomni/model/retriever.py`. Know‑how documents are loaded via `biomni/know_how/loader.py` and can be filtered for commercial mode.
- Configuration is centralized in `biomni/config.py` (`default_config`). Agent constructor params override reasoning only; database/retrieval uses `default_config`.

## Developer Workflows
- Environment: See `biomni_env/README.md`. Typical flow:
  1) `conda env create -f biomni_env/environment.yml` or run `biomni_env/setup.sh` for full E1. Activate with `conda activate biomni_e1`.
  2) Install package: `pip install biomni --upgrade` or `pip install git+https://github.com/snap-stanford/Biomni.git@main`.
- Tests: See `tests/README.md`.
  - Install: `pip install -r requirements-test.txt`
  - Run all: `pytest tests/`
  - Markers: `-m unit`, `-m integration`, `-m "not slow"`
  - Integration (Bedrock): set `RUN_BEDROCK_INTEGRATION=1`, ensure `AWS_REGION`/`AWS_PROFILE` as needed.
  - Coverage: `pytest tests/ --cov=biomni --cov-report=html --cov-report=term-missing`
- Docs: See `docs/building_documentation.md`. Build with `cd docs && pip install sphinx sphinx-rtd-theme && make html`.

## Configuration Patterns
- Preferred: modify `default_config` or use env vars. Example:
  - `from biomni.config import default_config; default_config.llm = "gpt-4"; default_config.timeout_seconds = 1200`
  - `.env` supports keys like `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AWS_REGION`, `BIOMNI_*`.
- Constructor overrides: `A1(llm="claude-3-5-sonnet-20241022", source="Anthropic")` only affect agent reasoning. Retrieval/indexing uses `default_config`.
- Custom/Local models: set `default_config.source = "Custom"`, `default_config.base_url`, `default_config.api_key`, or pass `base_url`/`api_key` to `A1(...)`.

## Data Lake Behavior
- On first `A1(...)`, ~11GB of data is auto-downloaded into `./data/biomni_data/{data_lake,benchmark}` using `check_and_download_s3_files` and `env_desc.py`/`env_desc_cm.py`.
- To skip download for faster dev: `A1(..., expected_data_lake_files=[])` (some tools may then be unavailable).
- Commercial mode: `default_config.commercial_mode=True` switches to `env_desc_cm.py` datasets only.

## Integrations
- AWS Bedrock (LLMs): `biomni.llm.get_llm()` uses `langchain-aws.ChatBedrock`. Credentials follow AWS SDK chain (`AWS_PROFILE`, IAM roles, env vars). Helpful errors guide setup.
- AWS Bedrock (raw client): `biomni/bedrock_client.py` centralizes `boto3` client creation (`BedrockClientManager`), including streaming and rich error messages.
- MCP: `A1.add_mcp(config_path)` discovers and registers MCP server tools as callable functions. Examples in `tutorials/examples/add_mcp_server/` and `docs/mcp_integration.md`.

## Tool Authoring & Execution
- Register custom tools at runtime via `A1.add_tool(api_fn)`. A schema is generated (`function_to_api_schema`) then registered into `ToolRegistry` (requires fields: `name`, `description`, `required_parameters`).
- Code execution helpers: `run_python_repl`, `inject_custom_functions_to_repl`, `run_r_code`, `run_bash_script`, `run_with_timeout`. Respect `default_config.timeout_seconds` for long runs.
- Retrieval: When `use_tool_retriever=True`, `ToolRetriever.prompt_based_retrieval(...)` selects tools/data/libraries/know‑how via an LLM prompt.

## Conventions & Tips
- Place new domain tools under `biomni/tool/<domain>.py` and keep descriptions in `biomni/tool/tool_description/` aligned.
- For Azure models, prefix with `azure-` in constructor (e.g., `llm="azure-gpt-4o"`). For Groq/Gemini/Ollama, install respective langchain packages.
- Gradio UI: `agent.launch_gradio_demo()` (install `gradio`). Options include `share`, `server_name`, `require_verification`.
- Security: Biomni executes LLM‑generated code with full privileges. Use sandboxed environments for production.

## Examples
- Unified config:
  ```python
  from biomni.config import default_config; from biomni.agent import A1
  default_config.llm = "claude-3-5-sonnet-20241022"; default_config.source = "Anthropic"
  agent = A1(); agent.go("Plan a CRISPR screen...")
  ```
- Split costs (cheaper DB, stronger agent):
  ```python
  default_config.llm = "claude-3-5-haiku-20241022"; agent = A1(llm="claude-3-5-sonnet-20241022")
  ```
