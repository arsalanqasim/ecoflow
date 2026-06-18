# Design Decisions

This document details key architectural choices made during the inception of EcoFlow.

## 1. Multi-Agent vs. Monolith
- **Decision:** Multi-Agent Architecture.
- **Rationale:** Separating concerns (Ingest, Carbon, Audit, Viz) makes testing modular. It showcases the Google Agentic stack (ADK, A2A) which is a major score criteria for this capstone competition.

## 2. A2A Communication Protocol
- **Decision:** Asynchronous Pub/Sub broker messaging.
- **Rationale:** Avoids tight coupling. Agents can register and dynamically discover capabilities on the bus. In case of transient agent downtime, messages remain in topics (durability).

## 3. FastMCP for Compute Offloading
- **Decision:** Offloading heavy calculations and visualization rendering to dedicated FastMCP servers.
- **Rationale:** Large pandas merges or network renders block the asynchronous agent loops. MCP servers provide horizontal scalability.
