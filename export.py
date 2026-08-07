import duckdb
import os

conn = duckdb.connect('credit_scorecard.db')
os.makedirs('tableau_data', exist_ok=True)

# Export all key tables for Tableau
# 1. State risk summary — combines Q1, Q3, Q8, Q10
summary = conn.execute("""
    WITH volume AS (
        SELECT 
            "State",
            COUNT(*) as total_complaints,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct_of_total
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
    with_zscore AS (
        SELECT
            "State",
            total_complaints,
            pct_of_total,
            ROUND((total_complaints - AVG(total_complaints) OVER()) / 
                  NULLIF(STDDEV(total_complaints) OVER(), 0), 2) as z_score,
            CASE 
                WHEN (total_complaints - AVG(total_complaints) OVER()) / 
                     NULLIF(STDDEV(total_complaints) OVER(), 0) > 2 THEN 'Critical'
                WHEN (total_complaints - AVG(total_complaints) OVER()) / 
                     NULLIF(STDDEV(total_complaints) OVER(), 0) > 1 THEN 'Elevated'
                WHEN (total_complaints - AVG(total_complaints) OVER()) / 
                     NULLIF(STDDEV(total_complaints) OVER(), 0) > 0 THEN 'Moderate'
                WHEN (total_complaints - AVG(total_complaints) OVER()) / 
                     NULLIF(STDDEV(total_complaints) OVER(), 0) > -1 THEN 'Low'
                ELSE 'Very Low'
            END as risk_level
        FROM volume
    )
    SELECT * FROM with_zscore
    ORDER BY z_score DESC
""").fetchdf()

summary.to_csv('tableau_data/state_risk_summary.csv', index=False)
print(f"State risk summary: {len(summary)} states")

# 2. Monthly trends
monthly = conn.execute("""
    SELECT 
        "State",
        DATE_TRUNC('month', CAST("Date received" AS DATE)) as month,
        COUNT(*) as complaints
    FROM complaints
    WHERE "State" IS NOT NULL
      AND "Date received" >= '2020-01-01'
      AND "State" IN (
        'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
        'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
        'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
        'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
        'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
      )
    GROUP BY "State", DATE_TRUNC('month', CAST("Date received" AS DATE))
    ORDER BY "State", month
""").fetchdf()

monthly.to_csv('tableau_data/monthly_trends.csv', index=False)
print(f"Monthly trends: {len(monthly)} rows")

# 3. Product analysis
products = conn.execute("""
    SELECT 
        "Product",
        "State",
        COUNT(*) as complaints,
        ROUND(COUNT(CASE WHEN "Company response to consumer" = 
            'Closed with monetary relief' THEN 1 END) * 100.0 / COUNT(*), 1) as relief_rate
    FROM complaints
    WHERE "Date received" >= '2022-01-01'
      AND "State" IN (
        'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
        'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
        'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
        'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
        'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
      )
    GROUP BY "Product", "State"
    ORDER BY complaints DESC
""").fetchdf()

products.to_csv('tableau_data/product_analysis.csv', index=False)
print(f"Product analysis: {len(products)} rows")

# 4. Quarterly vs delinquency
quarterly = conn.execute("""
    WITH q AS (
        SELECT 
            DATE_TRUNC('quarter', CAST("Date received" AS DATE)) as quarter,
            COUNT(*) as complaints
        FROM complaints
        WHERE "Date received" >= '2015-01-01'
          AND "State" IN (
            'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
            'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
            'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
            'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
            'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
          )
        GROUP BY DATE_TRUNC('quarter', CAST("Date received" AS DATE))
    )
    SELECT 
        q.quarter,
        q.complaints,
        d.delinquency_rate
    FROM q
    LEFT JOIN delinquency d 
        ON DATE_TRUNC('quarter', CAST(d.date AS DATE)) = q.quarter
    WHERE d.delinquency_rate IS NOT NULL
    ORDER BY q.quarter
""").fetchdf()

quarterly.to_csv('tableau_data/quarterly_delinquency.csv', index=False)
print(f"Quarterly delinquency: {len(quarterly)} rows")

conn.close()
print("\nAll files exported to tableau_data/ folder. Ready for Tableau.")