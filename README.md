# EcoFlow — Federated Supply Chain Decarbonization & CBAM Auditor

EcoFlow is a federated multi-agent supply chain carbon auditing platform developed for the Kaggle × Google Gen AI Agent Capstone. It tracks Scope 3 carbon emissions across a supplier network, audits import shipments against EU Carbon Border Adjustment Mechanism (CBAM) regulations, and utilizes Gemini and Vertex AI to recommend mitigation strategies.

## System Architecture

The EcoFlow platform consists of five specialized AI agents operating on the **Agent2Agent (A2A)** protocol and three high-performance **FastMCP** server backends:

1. **AI Assistant Agent (`agents/ai_assistant_agent.py`):** Acts as the user-facing chatbot, orchestrating downstream agent tasks and displaying summaries.
2. **Data Ingest Agent (`agents/data_ingest_agent.py`):** Ingests and sanitizes shipping data and emission factors datasets.
3. **Carbon Analysis Agent (`agents/carbon_agent.py`):** Calculates product/tier-level carbon emissions by joining data using FastMCP.
4. **CBAM Audit Agent (`agents/cbam_agent.py`):** Checks shipments against EU tariff guidelines and generates regulatory descriptions.
5. **Visualization Agent (`agents/viz_agent.py`):** Generates graphs, geographical heatmaps, and network views.

## Repository Structure

```
/ecoflow
├── /agents                   # AI Agents utilizing Google ADK 2.0
│   ├── data_ingest_agent.py
│   ├── carbon_agent.py
│   ├── cbam_agent.py
│   ├── viz_agent.py
│   └── ai_assistant_agent.py
├── /fastmcp                  # FastMCP high-performance computation servers
│   ├── data_processing_server.py
│   ├── model_serving_server.py
│   └── visualization_server.py
├── /api                      # REST API backend (FastAPI)
│   ├── app.py
│   ├── routes.py
│   └── schemas.py
├── /frontend                 # React Web Dashboard (dashboard views & chat)
├── /data                     # Dataset store (Raw and Processed)
│   ├── raw/
│   ├── processed/
│   └── sample_inputs/
├── /notebooks                # Jupyter Notebooks for exploratory data analysis
├── /docs                     # Architectural & API Documentation
│   ├── architecture.md
│   ├── design_decisions.md
│   ├── deployment_guide.md
│   └── user_guide.md
├── /tests                    # PyTest Unit & Integration tests
├── /deployment               # Cloud Run, Pub/Sub, Cloud SQL configurations
├── docker-compose.yml        # Spin up PostgreSQL and Redis locally
├── LICENSE                   # MIT License
├── requirements.txt          # Python dependencies
└── README.md                 # Project README
```

## Setup Instructions

### Prerequisites
- Python 3.11 or later
- Docker (for database and broker services)
- Google Cloud SDK (if deploying to GCP)

### Local Environment Setup

1. **Create and Activate Python Virtual Environment:**
   ```bash
   python -m venv .venv
   # Windows (Command Prompt)
   .venv\Scripts\activate.bat
   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   # macOS/Linux
   source .venv/bin/activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Start Local Services:**
   Spin up a local PostgreSQL database and Redis store using Docker Compose:
   ```bash
   docker compose up -d
   ```

4. **Verify Database Connectivity:**
   Ensure your database is online and reachable on port `5432`.

## Next Steps
- Implement data models in `api/schemas.py`.
- Seed sample carbon emission factors into the database.
- Build the core FastMCP DataProcessing join logic.
