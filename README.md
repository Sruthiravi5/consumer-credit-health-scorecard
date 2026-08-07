# consumer-credit-health-scorecard
SQL analytics on 16.9M CFPB consumer complaints to identify consumer credit stress signals across US states


## Key Decisions
- **DuckDB over SQLite** — 20-50x faster analytical query performance on 16.9M rows
- **2023 baseline for Z-scores** — post-pandemic complaint patterns differ structurally from pre-2020
- **Normalized by population before ranking** — raw counts always favor large states
- **2σ threshold for Critical flag** — captures ~2.5% of states, standard statistical outlier definition
- **Filtered to 50 US states** — territories and military codes (AP, AE, GU) create meaningless percentage spikes with near-zero volumes
- **Excluded credit reporting from product analysis** — accounts for 78% of volume but is not Capital One's core business
- **Combined two CFPB credit reporting categories** — same product renamed in 2015, summed for accurate analysis

## What I Learned
- LAG() requires PARTITION BY when comparing across groups — without it, Texas January gets compared to California December
- Z-scores computed as window functions allow every state to compare against the same national baseline simultaneously
- Statistical process control (Western Electric Rules) is the academic basis for 2σ anomaly thresholds — not arbitrary
- The January 2025 complaint spike is regulatory not economic — research revealed the CFPB/Navy Federal enforcement action as the trigger

## Limitations
- Delinquency data is national not state-level — state-level stress inferred from complaint patterns only
- Credit reporting dominates complaint volume (78%) — analysis filtered but this affects baseline
- 2026 data is partial — July 2026 complaint counts will increase as more complaints are processed

## Dashboard
*Tableau dashboard available for live demo — contains US Credit Stress Map, National Trend vs Delinquency Rate, and Product Breakdown with monetary relief rate analysis*
