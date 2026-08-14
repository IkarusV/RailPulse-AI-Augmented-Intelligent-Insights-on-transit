# RailPulse AI

<img width="1964" height="989" alt="image" src="https://github.com/user-attachments/assets/458c15f3-ba45-4200-b9e7-8c5405f79709" />

RailPulse AI is the conversational layer of the RailPulse project to make it accecible to anyone to ask legimate question that can have a verified answerd only based on fact in the database.

***Live demo at: https://railpulse-ai.streamlit.app/***

After building the Belgian railway SQL database, Azure collection pipeline, and Power BI operations dashboard, this assistant makes the same transit data accessible to people without SQL or analytics knowledge. Users ask operational questions in plain language and receive a direct answer, the supporting data, and a short recommendation.

Instead of manually creating a new dashboard view for every question, RailPulse AI can generate and run the required read-only query on demand.

<img width="1538" height="1110" alt="image" src="https://github.com/user-attachments/assets/df5d0f63-c6f2-44eb-b6d9-425881d9c6e0" />




## How It Works

```text
User question
    |
    v
LLM generates a structured SQL proposal
    |
    v
Python validates the query
    |
    v
Read-only database execution
    |
    v
Result table and operational summary
```

The model never connects directly to the database. It proposes one query, which must pass the application safety checks before execution. A second grounded model call summarizes only the validated query result.

<img width="1360" height="991" alt="image" src="https://github.com/user-attachments/assets/35db80cc-efc6-4353-8068-a4d002caf985" />


## Example Questions

- Which platform had the worst average delay?
- What was the overall on-time rate?
- Which train class caused the most delayed minutes?
- Show the five most delayed departures.
- Compare average delay by hour.
- Which destinations accumulated the most delay?

Every response includes the result table and an expandable copy of the validated SQL, making the answer easy to inspect and verify.

<img width="1618" height="447" alt="image" src="https://github.com/user-attachments/assets/be80ae18-1538-48d5-9c97-7c13f9fce18f" />


## Query Safety

The assistant accepts one read-only `SELECT` query against the prepared departures view.

The validation layer blocks:

- database modifications such as `INSERT`, `UPDATE`, `DELETE`, `DROP`, and `ALTER`;
- stacked statements and SQL comments;
- unknown tables, joins, unions, and unrestricted `SELECT *` queries;
- results above the 100-row limit.

The SQLite connection is also opened in read-only and query-only mode, so database writes remain unavailable independently of the generated SQL.

## Model Configuration

The endpoint, API key, model, and API style are environment configuration rather than application or interface choices.

The assistant is not tied to a model name or provider. It supports both Responses API and OpenAI-compatible Chat Completions services while keeping the same structured-output and SQL safety contracts.

Create `.env` from `.env.example`:

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your_model
LLM_API_STYLE=responses
```

Use `LLM_API_STYLE=chat_completions` for a service that exposes `/v1/chat/completions`. These settings are not exposed to chat users.

## Local Setup

Create the Python environment and install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Build the local analytical database from the latest RailPulse data snapshot:

```powershell
python scripts/build_database.py
```

Run the tests:

```powershell
python -m unittest discover -s tests -v
```

Start the application:

```powershell
streamlit run app.py
```

Open `http://localhost:8501`.

On Windows, `start.bat` performs the local setup and starts Streamlit automatically. It is kept outside Git because it is only a local convenience launcher.

## Streamlit Cloud

Deploy with:

```text
Repository: IkarusV/RailPulse-AI-Augmented-Intelligent-Insights-on-transit
Branch: main
Main file path: app.py
Python version: 3.11
```

Add the model configuration under **Advanced settings -> Secrets** using TOML syntax:

```toml
LLM_API_KEY = "your_api_key"
LLM_BASE_URL = "https://your-provider.example/v1"
LLM_MODEL = "your_model"
LLM_API_STYLE = "responses"
```

Unlike `.env`, TOML string values must be quoted. The application reads local `.env` variables during development and `st.secrets` when deployed.

The SQLite snapshot is generated automatically when a new cloud instance starts, so the database file is not committed to GitHub.

## Executive Brief

The project can also generate a Markdown summary of the most significant observed delays:

```powershell
python scripts/weekly_brief.py
```

The report is written to:

```text
reports/executive_brief.md
```

## Project Structure

```text
app.py                     Streamlit chat interface
assistant.py               question-to-answer orchestration
llm_client.py              Responses API client
prompts.py                 SQL and consultant prompt contracts
sql_guard.py               deterministic SQL validation
database.py                read-only query execution
config.py                  environment configuration
scripts/build_database.py  database snapshot builder
scripts/weekly_brief.py     executive report generator
tests/                      safety and database tests
```

## RailPulse Series

- [Belgian Transit SQL Analysis](https://github.com/IkarusV/Belgian-transit-SQL-analysis)
- [RailPulse Cloud Azure ETL](https://github.com/IkarusV/railpulse-cloud-azure)
- [RailPulse Power BI Dashboard](https://github.com/IkarusV/railpulse-powerbi-dashboard)
