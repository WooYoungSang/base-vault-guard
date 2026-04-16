# Base Vault Guard — AI-Powered DeFi Safety Scores

> **Base Vault Guard** assigns AI-powered safety scores (A–F) to every lending market and yield vault on Base — so you can find the best yield *without* the hidden risks.

[![Built on Base](https://img.shields.io/badge/Built%20on-Base-0052FF?logo=coinbase)](https://base.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)

---

## Overview

DeFi on Base offers hundreds of vaults across Morpho, Aave v3, Compound v3, and Aerodrome — but raw APY numbers hide liquidity risk, oracle vulnerabilities, and audit gaps. **Base Vault Guard** solves this with a transparent, explainable safety scoring engine.

### Key Features

| Feature | Description |
|---------|-------------|
| **F1 — Safety Grades (A–F)** | Every vault receives a letter grade backed by a 0–100 numeric score |
| **F2 — Multi-Protocol Coverage** | Morpho Blue, Aave v3, Compound v3, Aerodrome on Base |
| **F3 — Rule-Based + ML Scoring** | XGBoost classifier with transparent rule-based fallback |
| **F4 — Safe Yield Finder** | Filter by minimum safety grade, sorted by APY descending |
| **F5 — Grade History** | Track safety grade changes over time with drop alerts |
| **F6 — REST API** | Open API for integrations, bots, and dashboards |

### Safety Score Methodology

Each vault is scored on 5 risk dimensions:

| Factor | Weight | Description |
|--------|--------|-------------|
| Utilization Rate | 20% | High utilization → liquidity crunch risk |
| TVL Trend (7d) | 15% | Sharp TVL drops signal confidence loss |
| Oracle Risk | 25% | TWAP vs Chainlink; manipulation surface |
| Audit Coverage | 25% | Number and quality of security audits |
| Max Drawdown | 15% | Worst historical loss event |

**Score → Grade mapping**: A (85–100) · B (70–84) · C (55–69) · D (35–54) · F (0–34)

> ⚠️ Safety scores are informational only, not financial advice. Vaults with insufficient data are marked **Unrated**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js 14 Frontend                   │
│  / (overview) · /vaults · /vaults/[addr] · /safe-yield  │
└──────────────────────┬──────────────────────────────────┘
                       │ REST (NEXT_PUBLIC_API_URL)
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                        │
│  GET /vaults · /vaults/{addr} · /safe-yield · /health   │
└──┬──────────────┬───────────────┬────────────────┬──────┘
   │              │               │                │
┌──▼──┐     ┌────▼────┐    ┌─────▼────┐    ┌──────▼──────┐
│Scan │     │  Risk   │    │  Scorer  │    │  SQLite DB  │
│ner  │     │Collector│    │(XGB/Rule)│    │  (History)  │
└──┬──┘     └────┬────┘    └──────────┘    └─────────────┘
   │              │
   ▼              ▼
Base RPC    Hardcoded
(Morpho     Registry
 subgraph)  (Aave/Comp/
             Aerodrome)
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- (Optional) Docker & Docker Compose

### Backend

```bash
cd backend
pip install -e ".[dev]"

# Run API server
uvicorn vault_guard.api:app --reload --port 8000

# Run tests
pytest tests/ -v

# Lint
ruff check .
```

### Frontend

```bash
cd frontend
npm install

# Development
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# Production build
npm run build
npm run lint
```

### Docker Compose (full stack)

```bash
docker compose up
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

---

## API Reference

Base URL: `http://localhost:8000`

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check + vault count |
| `GET` | `/vaults` | List all vaults (paginated) |
| `GET` | `/vaults?protocol=morpho` | Filter by protocol |
| `GET` | `/vaults?grade=A` | Filter by safety grade |
| `GET` | `/vaults/{address}` | Single vault detail + risk breakdown |
| `GET` | `/vaults/{address}/history` | Grade history for a vault |
| `GET` | `/vaults/safe-yield?min_grade=B` | Safe Yield Finder (APY-sorted) |

### Example Response

```json
// GET /vaults/safe-yield?min_grade=B
{
  "items": [
    {
      "vault": {
        "address": "0xA238Dd80C259...",
        "protocol": "aave_v3",
        "asset": "USDC",
        "tvl_usd": 10000000,
        "apy": 4.5,
        "utilization_rate": 0.65
      },
      "risk": {
        "utilization": 0.65,
        "oracle_risk_score": 0.10,
        "audit_score": 0.95,
        "drawdown_max": 0.03,
        "sufficient_data": true
      },
      "score": 82.4,
      "grade": "B",
      "disclaimer": "Safety scores are informational only, not financial advice."
    }
  ],
  "min_grade": "B",
  "total": 3
}
```

### Interactive Docs

Visit `http://localhost:8000/docs` for the auto-generated Swagger UI.

---

## Tech Stack

**Backend**
- Python 3.10, FastAPI, Pydantic v2
- XGBoost (ML scoring), rule-based fallback
- web3.py (Base RPC), httpx (subgraph queries)
- SQLite (grade history), in-memory TTL cache

**Frontend**
- Next.js 14, TypeScript, Tailwind CSS
- TanStack Query (data fetching + caching)
- Recharts (risk breakdown bar chart, grade history line chart)

**Infrastructure**
- Docker Compose (local full-stack)
- Vercel-ready (frontend `output: "standalone"`)
- Base RPC: `https://mainnet.base.org`

---

## Project Structure

```
grant-base-vault-guard/
├── backend/
│   ├── src/vault_guard/
│   │   ├── scanner.py        # Morpho/Aave/Compound/Aerodrome scanner
│   │   ├── risk_collector.py # Risk profile builder
│   │   ├── scorer.py         # XGBoost + rule-based scorer
│   │   ├── yield_finder.py   # Safe yield filter
│   │   ├── history.py        # SQLite grade history
│   │   ├── cache.py          # TTL cache
│   │   ├── api.py            # FastAPI application
│   │   └── schemas.py        # Pydantic response models
│   └── tests/                # 60 pytest tests
├── frontend/
│   └── src/
│       ├── app/              # Next.js App Router pages
│       ├── components/       # VaultTable, SafetyBadge, RiskBreakdown, etc.
│       └── lib/              # API client, query config
└── docker-compose.yml
```

---

## Safety & Disclaimers

- Safety scores are **informational only** and do not constitute financial advice
- DeFi investments carry significant risk including total loss of funds
- Vault grades reflect point-in-time analysis; conditions change rapidly
- Vaults with insufficient on-chain data are marked **Unrated** and excluded from yield results
- Always do your own research before depositing funds

---

## Built for Base Builder Grants

This project was built as part of the **Base Builder Grants** program to improve DeFi safety tooling on Base. Our goal is to make it easier for users to understand the risks of DeFi vaults and find safe yield opportunities.

**Why Base?**
- Growing DeFi ecosystem (Morpho, Aave, Compound, Aerodrome)
- Low transaction costs make safety tooling economically viable
- Strong developer community and grant support

---

## License

MIT © 2024 Base Vault Guard Contributors

---

*Built with ❤️ on Base*
