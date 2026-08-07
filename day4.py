import duckdb
import os

conn = duckdb.connect('credit_scorecard.db')
os.makedirs('output', exist_ok=True)

# Query 8: Z-score risk rating per state
# Business question: Which states are statistically anomalous?
# Study note: Z-score = (value - mean) / standard deviation
# Z > 2 means top 2.5% — statistically unusual
# We use STDDEV as a window function so every state compares
# to the same national baseline

result8 = conn.execute("""
    WITH complaint_counts AS (
        SELECT 
            "State",
            COUNT(*) as complaints
        FROM complaints
        WHERE "State" IS NOT NULL
          AND "Date received" >= '2023-01-01'
          AND "State" IN (
            'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
            'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
            'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
            'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
            'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
          )
        GROUP BY "State"
    ),
    with_stats AS (
        SELECT 
            "State",
            complaints,
            AVG(complaints) OVER () as national_mean,
            STDDEV(complaints) OVER () as national_stddev
        FROM complaint_counts
    ),
    with_zscore AS (
        SELECT 
            "State",
            complaints,
            ROUND(national_mean, 0) as national_mean,
            ROUND(
                (complaints - national_mean) / NULLIF(national_stddev, 0),
            2) as z_score
        FROM with_stats
    )
    SELECT 
        "State",
        complaints,
        national_mean,
        z_score,
        CASE 
            WHEN z_score > 2  THEN 'Critical'
            WHEN z_score > 1  THEN 'Elevated'
            WHEN z_score > 0  THEN 'Moderate'
            WHEN z_score > -1 THEN 'Low'
            ELSE 'Very Low'
        END as risk_level
    FROM with_zscore
    ORDER BY z_score DESC
""").fetchdf()

print("Query 8: Z-score risk rating by state")
print(result8.to_string(index=False))
print("\nRisk level distribution:")
print(result8['risk_level'].value_counts())
result8.to_csv('output/q8_zscore_risk.csv', index=False)
# Key findings from Query 8:
# Critical states: TX (3.95σ), FL (3.85σ), CA (2.35σ)
# TX and FL are near 4 standard deviations above mean — extreme outliers
# 36 of 51 states are BELOW average — distribution heavily right-skewed
# Cross reference with Query 3: GA and MS are critical PER CAPITA
# but not by raw volume — different risk story
# Memo will use both metrics for complete picture




# Query 9: Rolling 90-day complaint trend by state
# Business question: Is each state's situation improving or getting worse right now?

result9 = conn.execute("""
    WITH daily_state AS (
        SELECT 
            "State",
            CAST("Date received" AS DATE) as complaint_date,
            COUNT(*) as daily_count
        FROM complaints
        WHERE "State" IS NOT NULL
          AND "Date received" >= '2024-01-01'
          AND "State" IN (
            'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
            'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
            'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
            'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
            'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
          )
        GROUP BY "State", CAST("Date received" AS DATE)
    )
    SELECT 
        "State",
        complaint_date,
        daily_count,
        SUM(daily_count) OVER (
            PARTITION BY "State"
            ORDER BY complaint_date
            ROWS BETWEEN 89 PRECEDING AND CURRENT ROW
        ) as rolling_90d_total
    FROM daily_state
    ORDER BY "State", complaint_date DESC
""").fetchdf()

# Show most recent 90-day totals for top states
latest = result9.groupby('State').first().reset_index()
latest = latest.sort_values('rolling_90d_total', ascending=False).head(15)
print("\nQuery 9: Most recent 90-day complaint totals (top 15 states)")
print(latest[['State','rolling_90d_total']].to_string(index=False))
result9.to_csv('output/q9_rolling_90d.csv', index=False)
# Key findings from Query 9:
# TX, FL, CA maintain Critical status in most recent 90 days
# MS appears at #10 in recent 90-day window — not in top 15 historically
# Suggests MS is a recently deteriorating state — flag for memo
# AL consistently elevated across queries 1, 3, 8, 9




# Query 10: States with accelerating complaint velocity
# Business question: Who is consistently getting worse, not just having one bad month?
# 3 consecutive months of growth = real trend, not seasonal noise

result10 = conn.execute("""
    WITH monthly AS (
        SELECT 
            "State",
            DATE_TRUNC('month', CAST("Date received" AS DATE)) as month,
            COUNT(*) as complaints
        FROM complaints
        WHERE "State" IS NOT NULL
          AND "Date received" >= '2024-01-01'
          AND "State" IN (
            'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
            'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
            'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
            'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
            'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
          )
        GROUP BY "State", DATE_TRUNC('month', CAST("Date received" AS DATE))
    ),
    with_lags AS (
        SELECT 
            "State", month, complaints,
            LAG(complaints, 1) OVER (PARTITION BY "State" ORDER BY month) as m1,
            LAG(complaints, 2) OVER (PARTITION BY "State" ORDER BY month) as m2,
            LAG(complaints, 3) OVER (PARTITION BY "State" ORDER BY month) as m3
        FROM monthly
    )
    SELECT 
        "State", month, complaints,
        ROUND((complaints - m3) * 100.0 / NULLIF(m3, 0), 1) as growth_vs_3mo_ago_pct,
        CASE 
            WHEN complaints > m1 AND m1 > m2 AND m2 > m3 
            THEN 'Accelerating'
            WHEN complaints < m1 AND m1 < m2 
            THEN 'Decelerating'
            ELSE 'Mixed'
        END as trend
    FROM with_lags
    WHERE m3 IS NOT NULL
      AND month = (
          SELECT MAX(month) FROM with_lags WHERE m3 IS NOT NULL
      )
    ORDER BY growth_vs_3mo_ago_pct DESC
""").fetchdf()

print("\nQuery 10: Complaint acceleration by state (most recent month)")
print(result10.head(20).to_string(index=False))

accelerating = result10[result10['trend'] == 'Accelerating']
print(f"\nStates showing consistent acceleration: {len(accelerating)}")
print(accelerating[['State','growth_vs_3mo_ago_pct']].to_string(index=False))
result10.to_csv('output/q10_acceleration.csv', index=False)

conn.close()
# Key findings from Query 10:
# 12 states show consistent 3-month acceleration
# TX and FL: BOTH Critical Z-score AND accelerating — highest priority states
# MS: fastest acceleration at 46.1% but low raw volume — emerging risk
# AL: consistent across Q1, Q3, Q8, Q9, Q10 — persistent stressed state
# This cross-reference is the core of the business memo
# States to flag: TX, FL (critical + accelerating), MS, AL (emerging)

