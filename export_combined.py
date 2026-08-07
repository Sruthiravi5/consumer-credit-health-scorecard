import duckdb
import pandas as pd

conn = duckdb.connect('credit_scorecard.db')

result = conn.execute("""
    WITH monthly AS (
        SELECT 
            DATE_TRUNC('month', CAST("Date received" AS DATE)) as period,
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
        GROUP BY DATE_TRUNC('month', CAST("Date received" AS DATE))
    )
    SELECT 
        m.period,
        m.complaints,
        d.delinquency_rate
    FROM monthly m
    LEFT JOIN delinquency d 
        ON DATE_TRUNC('quarter', m.period) = DATE_TRUNC('quarter', CAST(d.date AS DATE))
    ORDER BY m.period
""").fetchdf()

result['period'] = pd.to_datetime(result['period']).dt.strftime('%Y-%m-%d')
result.to_csv('tableau_data/combined_trend.csv', index=False)
print(f"Combined: {len(result)} rows")
print(result.head(5).to_string(index=False))
conn.close()