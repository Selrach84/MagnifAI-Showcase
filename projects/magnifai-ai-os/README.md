# MagnifAI AI OS — Automation Delivery Platform

> An internal platform that eliminates repetitive work in client automation delivery. 7 layers: infrastructure, LLM gateway, connectors, templates, agents, monitoring, and client pipeline.

**Stack:** Python 3.11+ · FastAPI · PostgreSQL 15 · Redis 7 · Docker · SQLAlchemy 2.0 (async)

## The problem

Every automation client engagement follows a similar pattern: understand the client's systems, pick an LLM provider, build connectors, set up monitoring, deploy. Without a platform, each engagement starts from scratch — wasting time on foundational work instead of client value.

## The solution

A layered AI delivery platform that turns "build from scratch" into "configure from template":

```
┌──────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                │
├──────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌─────────┐ │
│  │ Agents  │ │Connectors│ │ Templates │ │Monitor  │ │
│  └────┬────┘ └────┬─────┘ └─────┬─────┘ └────┬────┘ │
│       └───────────┴─────────────┴────────────┘       │
├──────────────────────────────────────────────────────┤
│            Unified LLM Gateway                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │  OpenAI  │ │  Claude  │ │  Gemini  │  ...         │
│  └──────────┘ └──────────┘ └──────────┘              │
├──────────────────────────────────────────────────────┤
│            Infrastructure Layer                        │
│  PostgreSQL · Redis · Docker · Async Workers          │
└──────────────────────────────────────────────────────┘
```

## Layers

| Layer | What it does |
|-------|-------------|
| **API Layer** | FastAPI endpoints for health, LLM chat, agent management, connector CRUD, templates, monitoring |
| **Agents** | Abstract base agent → concrete implementations: automation agents, LLM agents, orchestrators |
| **Connectors** | Pluggable integrations: GoHighLevel, n8n, webhooks — add one per client |
| **Templates** | Prompt template registry with validation — reuse prompt patterns across clients |
| **Monitoring** | Metrics collection, structured logging, alerting — every run has an execution log |
| **LLM Gateway** | Unified interface for OpenAI, Claude, Gemini — provider-swappable with cost tracking |
| **Infrastructure** | PostgreSQL (async via SQLAlchemy 2.0), Redis caching, Docker Compose, Alembic migrations |

## Key design decisions

- **Provider-agnostic LLM gateway**: Same interface for OpenAI/Claude/Gemini — swap providers per task
- **Usage tracking**: Every LLM call tracked with token counts and cost (pricing tables built in)
- **ABC-based architecture**: Abstract base classes for agents, connectors, providers — easy to extend
- **Async throughout**: FastAPI + async SQLAlchemy + async Redis
- **Docker-first**: Single `docker-compose up` gets PostgreSQL + Redis running

## Files

| Directory | What |
|-----------|------|
| `backend/` | FastAPI application (67 Python files) |
| `backend/api/` | REST endpoints (health, LLM, agents, connectors, templates, monitoring) |
| `backend/agents/` | Agent implementations (base, orchestrator, automation, LLM) |
| `backend/connectors/` | External service connectors (GoHighLevel, n8n, webhooks) |
| `backend/llm/` | Unified LLM client + providers (OpenAI, Claude, Gemini) |
| `backend/models/` | SQLAlchemy models (client, project, agent, connector, template, deployment) |
| `backend/monitoring/` | Metrics, logging, alerts |
| `backend/templates/` | Prompt template engine + validator + library |
| `tests/` | 14 test files |
| `alembic/` | Database migrations |
| `docker-compose.yml` | PostgreSQL + Redis |

## Quick start

```bash
docker compose up -d        # PostgreSQL + Redis
cp .env.example .env        # edit API keys
pip install -e .            # install package
uvicorn backend.main:app --reload
```

## What this demonstrates

- Platform engineering for AI delivery — not just building one automation, but the system that builds them
- Provider-agnostic architecture — clients aren't locked into one LLM vendor
- Production-grade async Python with FastAPI + SQLAlchemy 2.0
- Connector pattern for CRM/n8n/webhook integrations
- Cost-aware design with usage tracking across providers

## Status

Active development · Production scaffold built · Tested (14 test suites)
