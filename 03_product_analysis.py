import duckdb
import os

conn = duckdb.connect('credit_scorecard.db')

# Create output folder if it doesn't exist
os.makedirs('output', exist_ok=True)

# Query 4: Which products drive most complaints and which get resolved?
# Business question: Where is the most pain and is it being addressed?

result4 = conn.execute("""
    SELECT 
        "Product",
        COUNT(*) as total_complaints,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as pct_of_total,
        COUNT(CASE 
            WHEN "Company response to consumer" = 'Closed with monetary relief' 
            THEN 1 
        END) as resolved_with_relief,
        ROUND(
            COUNT(CASE WHEN "Company response to consumer" = 
                'Closed with monetary relief' THEN 1 END) * 100.0 / COUNT(*),
        1) as relief_rate_pct,
        ROUND(
            COUNT(CASE WHEN "Timely response?" = TRUE THEN 1 END) * 100.0 / COUNT(*),
        1) as timely_response_pct
    FROM complaints
    WHERE "Date received" >= '2022-01-01'
    GROUP BY "Product"
    ORDER BY total_complaints DESC
""").fetchdf()

print("Query 4: Product breakdown with resolution analysis")
print(result4.to_string(index=False))
result4.to_csv('output/q4_products.csv', index=False)

# Key findings from Query 4:
# Credit reporting = 78.75% of all complaints but 0% relief rate
# Credit card (Capital One's core product) = 13.3% relief rate
# Prepaid card = highest relief rate at 20.6%
# Student loans = lowest timely response at 82.4% — significant lag
# Business insight: most complaints get no monetary resolution
# National monetary relief rate = only 1.3% across all products






# Query 5: Top 5 complaint products for each state
# Business question: Is every state complaining about the same things?

result5 = conn.execute("""
    WITH product_state_counts AS (
        SELECT 
            "State",
            "Product",
            COUNT(*) as complaints
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
        GROUP BY "State", "Product"
    ),
    ranked AS (
        SELECT 
            "State",
            "Product",
            complaints,
            ROW_NUMBER() OVER (
                PARTITION BY "State"
                ORDER BY complaints DESC
            ) as rank_in_state
        FROM product_state_counts
    )
    SELECT "State", "Product", complaints, rank_in_state
    FROM ranked
    WHERE rank_in_state <= 5
    ORDER BY "State", rank_in_state
""").fetchdf()

# Show sample states
sample = ['CA','TX','FL','GA','MS']
print("\nQuery 5: Top 5 products by state (sample states)")
print(result5[result5['State'].isin(sample)].to_string(index=False))
result5.to_csv('output/q5_top_products_by_state.csv', index=False)
# Key findings from Query 5:
# Credit reporting is #1 in ALL states — systemic national issue
# Mississippi #4 = money transfer (not credit card like other states)
# Suggests higher alternative financial service usage in MS
# TX credit card rank = #4, higher than checking account
# Capital One relevance: credit card complaints are buried under
# credit reporting volume — filter to credit card only for deeper analysis






# Query 6: Quarterly complaints vs delinquency rate
# Business question: Does complaint volume track with credit stress?
# First time joining CFPB + FRED data

result6 = conn.execute("""
    WITH quarterly_complaints AS (
        SELECT 
            DATE_TRUNC('quarter', CAST("Date received" AS DATE)) as quarter,
            COUNT(*) as complaints,
            AVG(COUNT(*)) OVER (
                ORDER BY DATE_TRUNC('quarter', CAST("Date received" AS DATE))
                ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
            ) as rolling_4q_avg
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
        ROUND(q.rolling_4q_avg, 0) as rolling_avg,
        d.delinquency_rate
    FROM quarterly_complaints q
    LEFT JOIN delinquency d 
        ON DATE_TRUNC('quarter', CAST(d.date AS DATE)) = q.quarter
    WHERE d.delinquency_rate IS NOT NULL
    ORDER BY q.quarter
""").fetchdf()

print("\nQuery 6: Quarterly complaints vs delinquency rate")
print(result6.tail(12).to_string(index=False))
result6.to_csv('output/q6_complaints_vs_delinquency.csv', index=False)
# Key finding from Query 6:
# Complaints and delinquency tracked together through 2024 Q3
# Then diverged — complaints kept rising but delinquency fell
# Possible explanations:
# 1. Complaint spike driven by credit reporting volume, not credit card stress
# 2. Delinquency lags complaints by 2-3 quarters — watch Q3/Q4 2026
# Business implication: filter to credit card complaints only
# for a cleaner leading indicator signal






# Query 7: National complaint growth rate trend
# Business question: Is the complaint trend accelerating nationally?

result7 = conn.execute("""
    WITH monthly_national AS (
        SELECT 
            DATE_TRUNC('month', CAST("Date received" AS DATE)) as month,
            COUNT(*) as complaints
        FROM complaints
        WHERE "Date received" >= '2022-01-01'
          AND "State" IN (
            'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
            'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD',
            'MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
            'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC',
            'SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC'
          )
        GROUP BY DATE_TRUNC('month', CAST("Date received" AS DATE))
    )
    SELECT 
        month,
        complaints,
        LAG(complaints, 1) OVER (ORDER BY month) as prev_month,
        LAG(complaints, 12) OVER (ORDER BY month) as same_month_last_year,
        ROUND(
            (complaints - LAG(complaints,1) OVER (ORDER BY month)) * 100.0 / 
            NULLIF(LAG(complaints,1) OVER (ORDER BY month), 0), 
        1) as mom_pct,
        ROUND(
            (complaints - LAG(complaints,12) OVER (ORDER BY month)) * 100.0 / 
            NULLIF(LAG(complaints,12) OVER (ORDER BY month), 0), 
        1) as yoy_pct
    FROM monthly_national
    ORDER BY month DESC
    LIMIT 24
""").fetchdf()

print("\nQuery 7: National complaint trend (last 24 months)")
print(result7.to_string(index=False))
result7.to_csv('output/q7_national_trend.csv', index=False)
# Key findings from Query 7:
# January 2025: +56.9% MoM, +231% YoY — single largest spike in dataset
# YoY growth peaked at 231% (Jan 2025) and has decelerated to 45% (Jul 2026)
# Still 45% above last year — not recovering, just growing more slowly
# March 2026: secondary spike of +23.8% MoM — worth investigating
# Research needed: what happened in January 2025 nationally?





# RESEARCH FINDING — January 2025 spike explanation:
# Triggered by CFPB enforcement action against Navy Federal Credit Union
# New administration dropped the settlement order after taking office
# Servicemembers who filed complaints expecting relief got nothing
# Relief rate for servicemembers dropped from 35.4% to 2.2% by Dec 2025
# This is a POLITICAL/REGULATORY event, not a credit stress signal
# Important for README: explains why Jan 2025 spike ≠ organic credit deterioration
# The complaint surge reflects regulatory frustration, not consumer financial distress
# This nuance matters for interpreting the delinquency divergence in Query 6


conn.close()
