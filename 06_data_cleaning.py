import pandas as pd

products = pd.read_csv('tableau_data/product_analysis.csv')

# Combine both credit reporting categories
products['Product'] = products['Product'].replace({
    'Credit reporting, credit repair services, or other personal consumer reports': 'Credit Reporting',
    'Credit reporting or other personal consumer reports': 'Credit Reporting'
})

# Re-aggregate after combining
products = products.groupby(['Product', 'State'], as_index=False).agg({
    'complaints': 'sum',
    'relief_rate': 'mean'
})

products.to_csv('tableau_data/product_analysis.csv', index=False)
print(f"Fixed: {len(products)} rows")
print(products.groupby('Product')['complaints'].sum().sort_values(ascending=False).head(10))