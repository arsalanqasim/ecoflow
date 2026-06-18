# EcoFlow Architecture Document

This document outlines the multi-agent system structure, components, and data flow pipelines.

## Components Overview

1. **REST API Gateway (FastAPI):** Exposes JSON endpoints to the dashboard interface.
2. **AI Agents (ADK 2.0 / A2A):** Run inside containers. Orchestrated dynamically using A2A.
3. **FastMCP Servers:** Specialized microservices to process tabular merges, run predictive models, or render networks.
4. **Relational Database (Cloud SQL / Postgres):** Relational store containing tables for raw shipments, emission factors, computed emissions, CBAM logs, and agent memory state.
5. **Message Bus (Cloud Pub/Sub):** Broker facilitating decoupling of Agent2Agent calls.

## Data Ingestion & Audit Pipeline

```
  [User UI] -> (Post /api/data/upload) -> [FastAPI Gateway]
                                                  |
                                                  v
                                         [Data Ingest Agent]
                                                  |
                                                  v
                                     (Inserts raw data to DB)
                                                  |
                                                  v
                                     (Publishes DataIngested event)
                                                  |
                                                  v
                                       [Carbon Analysis Agent]
                                                  |
                                                  v
                                    (Triggers FastMCP Data Processing)
                                                  |
                                                  v
                                    (Computes Scope 3 and saves to DB)
                                                  |
                                                  v
                                      (Publishes EmissionsComputed)
                                                  |
                                                  v
                                            [CBAM Agent]
                                                  |
                                                  v
                                     (Audits tariffs and outputs logs)
```
