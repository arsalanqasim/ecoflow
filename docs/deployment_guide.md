# Deployment Guide

This document outlines instructions for deploying EcoFlow to Google Cloud Platform.

## GCP Resources Required

1. **Cloud Run:** For hosting the FastAPI gateway and individual agents.
2. **Cloud SQL (PostgreSQL):** For persistent storage of shipments and audits.
3. **Cloud Pub/Sub:** Event bus configuration for the A2A messaging protocol.
4. **Vertex AI Registry:** (Optional) If deploying custom forecasting models.

## Initial Deployment Steps

1. **Enable Google APIs:**
   ```bash
   gcloud services enable run.googleapis.com sqladmin.googleapis.com pubsub.googleapis.com
   ```

2. **Configure Database Instance:**
   Provision a PostgreSQL database instance and configure environment variables.

3. **Build & Submit Container Images:**
   Using Google Cloud Build:
   ```bash
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ecoflow-api .
   ```
