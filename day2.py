import duckdb
import pandas as pd

conn = duckdb.connect('credit_scorecard.db')

# ── EXPLORATION ──────────────────────────────────────────────────────────────

print("Date range:")
print(conn.execute("""
    SELECT 
        MIN("Date received") as earliest,
        MAX("Date received") as latest,
        COUNT(*) as total_complaints
    FROM complaints
""").fetchdf())

print("\nProducts (top 10 by volume):")
print(conn.execute("""
    SELECT "Product", COUNT(*) as count
    FROM complaints
    GROUP BY "Product"
    ORDER BY count DESC
    LIMIT 10
""").fetchdf())

print("\nNumber of unique states:", 
    conn.execute('SELECT COUNT(DISTINCT "State") FROM complaints').fetchone()[0])

print("Complaints with null state:", 
    conn.execute('SELECT COUNT(*) FROM complaints WHERE "State" IS NULL').fetchone()[0])

print("\nCompany responses:")
print(conn.execute("""
    SELECT "Company response to consumer", COUNT(*) as count
    FROM complaints
    GROUP BY "Company response to consumer"
    ORDER BY count DESC
""").fetchdf())

# ── POPULATION TABLE ─────────────────────────────────────────────────────────

population_data = {
    'state': ['CA','TX','FL','NY','PA','IL','OH','GA','NC','MI',
              'NJ','VA','WA','AZ','TN','MA','IN','MD','CO','MN',
              'SC','AL','LA','KY','OR','OK','CT','UT','IA','NV',
              'AR','MS','KS','NM','NE','WV','ID','HI','NH','ME',
              'MT','RI','DE','SD','ND','AK','VT','WY','DC'],
    'population': [38965193,30503301,22610726,19571216,12961683,
                   12549689,11799448,11029227,10698973,10037261,
                   9290841,8715698,7812880,7431344,7126489,7029917,
                   6861936,6180253,5877610,5737915,5373555,5108468,
                   4590241,4526154,4233358,4053624,3617176,3417734,
                   3207004,3194176,3067732,2940057,2934582,2114371,
                   1967923,1775156,1939033,1435138,1402054,1395722,
                   1122867,1093734,1018396,909824,779261,733583,
                   647464,584057,689545]
}
pop_df = pd.DataFrame(population_data)
conn.execute("DROP TABLE IF EXISTS population")
conn.execute("CREATE TABLE population AS SELECT * FROM pop_df")
print("\nPopulation table loaded —", len(pop_df), "states")

# ── QUERY 1 — Total complaints by state with percentage share ─────────────────
# Business question: Which states generate the most complaints?
# Why percentage: raw counts favor big states

result1 = conn.execute("""
    SELECT 
        "State",
        COUNT(*) as total_complaints,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct_of_total
    FROM complaints
    WHERE "State" IS NOT NULL
      AND "State" IN (
        'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
        'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
        'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
        'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
        'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
      )
      AND "Date received" >= '2023-01-01'
    GROUP BY "State"
    ORDER BY total_complaints DESC
    LIMIT 15
""").fetchdf()

print("\nQuery 1: Top 15 states by complaint volume")
print(result1.to_string(index=False))
result1.to_csv('q1_state_volume.csv', index=False)

# Key findings:
# TX: 14.59% complaints vs ~9% population share — 60% more than expected
# FL: 14.27% complaints vs ~6.5% population share — more than double expected
# GA: 7.63% complaints vs ~3% population share — highly disproportionate
# CA: 9.46% complaints vs ~11.6% population share — roughly proportional

# ── QUERY 2 — Month over month complaint growth by state ──────────────────────
# Business question: Which states are getting worse?
# Why MoM: trend matters more than absolute volume
# Data quality decision: filtered to 50 states + DC, minimum 100 prev month complaints
# Reason: territories and military codes create meaningless percentage spikes

result2 = conn.execute("""
    WITH monthly_complaints AS (
        SELECT 
            "State",
            DATE_TRUNC('month', CAST("Date received" AS DATE)) as month,
            COUNT(*) as complaint_count
        FROM complaints
        WHERE "State" IS NOT NULL
          AND "Date received" >= '2022-01-01'
          AND "State" IN (
            'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
            'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
            'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
            'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
            'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
          )
        GROUP BY "State", DATE_TRUNC('month', CAST("Date received" AS DATE))
    ),
    with_lag AS (
        SELECT 
            "State",
            month,
            complaint_count,
            LAG(complaint_count, 1) OVER (
                PARTITION BY "State"
                ORDER BY month
            ) as prev_month_count
        FROM monthly_complaints
    )
    SELECT 
        "State",
        month,
        complaint_count,
        prev_month_count,
        ROUND(
            (complaint_count - prev_month_count) * 100.0 / prev_month_count,
        2) as mom_growth_pct
    FROM with_lag
    WHERE prev_month_count >= 100
      AND prev_month_count IS NOT NULL
    ORDER BY mom_growth_pct DESC
    LIMIT 20
""").fetchdf()

print("\nQuery 2: Top 20 state-months by MoM growth (50 states only)")
print(result2.to_string(index=False))
result2.to_csv('q2_mom_growth.csv', index=False)

# Key findings:
# January 2025 dominates — 14 of top 20 growth months are Jan 2025
# This is a NATIONAL spike, not state-specific — suggests systemic cause
# West Virginia appears twice (Jan + Apr 2025) — ongoing stress, not one-time
# Next step: research what happened nationally in January 2025

# ── QUERY 3 — Complaints per 100k residents ───────────────────────────────────
# Business question: Which states have disproportionately high complaint rates?
# Why normalize: raw counts always favor large states like CA and TX

result3 = conn.execute("""
    SELECT 
        c."State",
        COUNT(*) as complaints,
        p.population,
        ROUND(COUNT(*) * 100000.0 / p.population, 1) as complaints_per_100k
    FROM complaints c
    JOIN population p ON c."State" = p.state
    WHERE c."Date received" >= '2023-01-01'
    GROUP BY c."State", p.population
    ORDER BY complaints_per_100k DESC
    LIMIT 15
""").fetchdf()

print("\nQuery 3: Complaints per 100k residents")
print(result3.to_string(index=False))
result3.to_csv('q3_per_100k.csv', index=False)

# After running: compare top 5 here vs Query 1
# The ranking should look different
# States that rise after normalization = higher per-capita stress
# States that fall after normalization = high volume but proportional to population

conn.close()
print("\nDay 2 complete. 3 queries done. Results saved to CSV files.")

# Key finding from Query 3:
# Normalization completely changes the story
# GA: #4 raw volume → #1 per capita (9,455 per 100k)
# MS: not in top 15 raw → #3 per capita (8,576 per 100k)
# CA: #3 raw volume → not in top 15 per capita
# Southern states dominate per-capita stress: GA, FL, MS, LA, AL, SC
# This is your business insight — the South is disproportionately stressed