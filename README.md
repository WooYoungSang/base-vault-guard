# Base Vault Guard — AI-Powered DeFi Safety Scores

> **Base Vault Guard** assigns AI-powered safety grades (A–F) to every lending market and yield vault on Base — so you can find the best yield *without* the hidden risks.

[![Built on Base](https://img.shields.io/badge/Built%20on-Base-0052FF?logo=coinbase)](https://base.org)
[![Live Demo](https://img.shields.io/badge/Live-vault--guard.warvis.org-brightgreen)](https://vault-guard.warvis.org)
[![Tests](https://img.shields.io/badge/Tests-110%20passing-brightgreen)](https://github.com/WooYoungSang/base-vault-guard)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)

**Live Demo:** https://vault-guard.warvis.org  
**API:** https://api-vault-guard.warvis.org/docs

---

## Problem

DeFi on Base offers hundreds of vaults across Morpho, Aave v3, Compound v3, and Aerodrome — but raw APY numbers hide liquidity risk, oracle vulnerabilities, and audit gaps. Users either chase yield blindly or miss out on safe opportunities because risk assessment is too complex.

---

## Solution

**Base Vault Guard** continuously scans 578+ live Base vaults via DeFiLlama and scores each one using an XGBoost model trained on real on-chain data — assigning a transparent A–F safety grade with a full risk breakdown.

---

## Features

| Feature | Description |
|---------|-------------|
| **F1 — Safety Grades (A–F)** | Every vault gets a letter grade backed by a 0–100 numeric score |
| **F2 — Multi-Protocol Coverage** | Morpho Blue, Aave v3, Compound v3, Aerodrome on Base (578 vaults) |
| **F3 — XGBoost ML Scoring** | 94.0% accuracy model trained on real DeFiLlama data + rule-based fallback |
| **F4 — Safe Yield Finder** | Filter by minimum safety grade, sorted by APY descending |
| **F5 — Grade History** | Track safety grade changes over time with automatic drop alerts |
| **F6 — REST API** | Open API for wallets, bots, and DeFi dashboards |

---

## ML Model Performance

| Metric | Value |
|--------|-------|
| Accuracy | **94.0%** |
| AUC-ROC | **0.9961** |
| Training set | 578 real vaults + synthetic fill for C/D/F grades |
| Data source | DeFiLlama API (free, no key), Base RPC |
| Baseline (synthetic-only) | 89.8% accuracy |

**Real data pipeline:**
- DeFiLlama: TVL, APY, 7-day TVL change for all 578 Base vaults
- Base RPC: live utilization rate per vault
- AUDIT_REGISTRY: 15 known-audited protocols with quality scores

---

## Safety Score Methodology

| Factor | Weight | Description |
|--------|--------|-------------|
| Utilization Rate | 20% | High utilization → liquidity crunch risk |
| TVL Trend (7d) | 15% | Sharp TVL drops signal confidence loss |
| Oracle Risk | 25% | TWAP vs Chainlink; manipulation surface |
| Audit Coverage | 25% | Number and quality of security audits |
| Max Drawdown | 15% | Worst historical loss event |

**Grade mapping:** A (85–100) · B (70–84) · C (55–69) · D (35–54) · F (0–34)

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
Scanner      Risk            XGBoost          SQLite
(DeFiLlama)  Collector       Scorer           History
             (Base RPC)      (94% acc)        + Alerts
```

---

## Quick Start

### Backend

```bash
cd backend
pip install -e ".[dev]"
uvicorn vault_guard.api:app --reload --port 8000
pytest tests/ -v   # 110 tests
```

### Frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

### Docker Compose

```bash
docker compose up
```

### Real Data Collection & Retrain

```bash
python -m vault_guard.ml.collect   # 578 Base vaults from DeFiLlama
python -m vault_guard.ml.retrain   # XGBoost retrain
```

---

## API Reference

Base URL: `https://api-vault-guard.warvis.org`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check + vault count |
| `GET` | `/vaults` | List all vaults (paginated) |
| `GET` | `/vaults?protocol=morpho` | Filter by protocol |
| `GET` | `/vaults?grade=A` | Filter by safety grade |
| `GET` | `/vaults/{address}` | Vault detail + risk breakdown |
| `GET` | `/vaults/{address}/history` | Grade history (last 30 records) |
| `GET` | `/vaults/safe-yield?min_grade=B` | Safe Yield Finder, APY-sorted |

### Example Response

```json
{
  "vault": {
    "address": "0xA238Dd80C259...",
    "protocol": "aave_v3",
    "asset": "USDC",
    "tvl_usd": 10000000,
    "apy": 4.5
  },
  "score": 82.4,
  "grade": "B",
  "scoring_method": "ml",
  "ml_confidence": 0.89,
  "disclaimer": "Safety scores are informational only, not financial advice."
}
```

Interactive docs: `https://api-vault-guard.warvis.org/docs`

---

## Tech Stack

**Backend:** Python 3.10, FastAPI, Pydantic v2, XGBoost, scikit-learn, web3.py, httpx, SQLite  
**Frontend:** Next.js 14, TypeScript, Tailwind CSS, TanStack Query, Recharts  
**Data:** DeFiLlama API (578 Base vaults, free), Base RPC  
**Infra:** Docker, Caddy reverse proxy, self-hosted

---

## Project Structure

```
grant-base-vault-guard/
├── backend/
│   ├── src/vault_guard/
│   │   ├── scanner.py          # Morpho/Aave/Compound/Aerodrome scanner
│   │   ├── risk_collector.py   # Risk profile builder
│   │   ├── scorer.py           # XGBoost + rule-based scorer
│   │   ├── yield_finder.py     # Safe yield filter
│   │   ├── history.py          # Grade history + drop alerts
│   │   ├── ml/
│   │   │   ├── data_collector.py  # DeFiLlama + Base RPC
│   │   │   ├── data_processor.py  # Feature engineering
│   │   │   ├── collect.py         # CLI: collect 578 vaults
│   │   │   └── retrain.py         # CLI: retrain model
│   │   ├── api.py
│   │   └── schemas.py
│   └── tests/                  # 110 pytest tests
└── frontend/
    └── src/
        ├── app/
        ├── components/
        └── lib/
```

---

## Use Cases

- **DeFi users**: Find the safest yield on Base without reading audit reports
- **Risk managers**: Screen vault allocations before deployment
- **Protocol teams**: Benchmark your vault's safety grade against peers
- **Bots & integrations**: Gate deposits by safety grade via REST API

---

## Built for Base Ecosystem Grants

Base Vault Guard makes DeFi risk assessment **transparent, automated, and free** for every Base user.

**Impact metrics:**
- 578 Base vaults scored in real-time (Morpho, Aave v3, Compound v3, Aerodrome)
- 94.0% ML accuracy (AUC 0.9961) — 4.2% improvement over synthetic-only baseline
- 110 automated tests with grade history + drop alert coverage
- Safe Yield Finder: one endpoint to find the best risk-adjusted yield on Base

---

## Disclaimer

Safety scores are informational only, not financial advice. DeFi investments carry significant risk. Always do your own research before depositing.

---

## License

MIT © 2025 Base Vault Guard Contributors
