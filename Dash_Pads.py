import pandas as pd

inventory_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database/Inventory foto.xlsx"
sales_path = [
    r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database/QBT 2025 PL by Market YTD.xlsx",
    r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database/QBT 2024 PL by Market YTD.xlsx",
    r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database/QBT 2023 PL by Market YTD.xlsx",
    r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database/QBT 2022 PL by Market YTD.xlsx",
    r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database/QBT 2021 PL by Market YTD.xlsx",
    r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database/QBT 2020 PL by Market YTD.xlsx"
]
obsolete_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\库存/obsolete cleaned.xlsx"
new_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\库存/New.xlsx"
output_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database/Pads Oct.xlsx"
bundle_mapping_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\库存/component.xlsx"



sales_all = [pd.read_excel(path) for path in sales_path]
sales = pd.concat(sales_all, ignore_index=True)#future warning
sales['year_month'] = pd.to_datetime(
    sales['Year'].astype(str) + "-" + sales['Month'].astype(str).str.zfill(2),
    format='%Y-%m'
)
sales['Item - Code'] = sales['Item - Code'].astype(str)
sales['rule_item_code'] = sales['Item - Code']
sales_agg = sales.groupby(['year_month', 'rule_item_code'])['Sales Qua'].sum().reset_index()

bundle_mapping = pd.read_excel(bundle_mapping_path)
bundle_mapping = bundle_mapping[bundle_mapping['Item number'].str.startswith('P')]
for _, row in bundle_mapping.iterrows():
    bundle_code = row['Item number']
    child_code = row['sub_Item number']
    child_sales = sales[sales['Item - Code'] == child_code]
    for _, child_row in child_sales.iterrows():
        child_month = child_row['year_month']
        child_quantity = child_row['Sales Qua']
        match = (sales_agg['rule_item_code'] == bundle_code) & (sales_agg['year_month'] == child_month)
        if match.any():
            sales_agg.loc[match, 'Sales Qua'] += child_quantity
        else:
            new_row = pd.DataFrame(
                {'year_month': [child_month], 'rule_item_code': [bundle_code], 'Sales Qua': [child_quantity]}
            )
            sales_agg = pd.concat([sales_agg, new_row], ignore_index=True)#future warning
sales_agg['year_month'] = pd.to_datetime(sales_agg['year_month'], errors='coerce').dt.to_period('M')

obsolete = pd.read_excel(obsolete_path)
obsolete_codes = set(obsolete['ax_part_number'].astype(str))

new = pd.read_excel(new_path)
new['AX_PART_NUMBER'] = new['AX_PART_NUMBER'].astype(str)
new['create_date'] = pd.to_datetime(new['created_date_time'], errors='coerce')
new['min_entry_date'] = new.groupby('AX_PART_NUMBER')['create_date'].transform('min')
new_entry_data = new[new['min_entry_date'] >= pd.Timestamp('2024-01-01')]
new_entry_codes = set(new_entry_data['AX_PART_NUMBER'])
new_create_date_map = new[['AX_PART_NUMBER', 'create_date']].drop_duplicates().set_index('AX_PART_NUMBER')['create_date'].to_dict()

sheet_names = pd.ExcelFile(inventory_path).sheet_names
results = {}
keep_cols = [
    'Item number', 'On-hand', 'Inventory value', 'year_month',
    'sales_47months', 'sales_23months', 'category', 'create_date', 'coverage'
]

def format_df(df):
    for col in ['sales_47months', 'sales_23months', 'coverage']:
        if col not in df.columns:
            df[col] = None
    df['create_date'] = df['Item number'].map(new_create_date_map)
    return df[keep_cols]

for sheet_name in sheet_names:
    inv = pd.read_excel(inventory_path, sheet_name=sheet_name)
    inv['Item number'] = inv['Item number'].astype(str).str.strip()
    inv['year_month'] = pd.to_datetime(inv['year_month'], errors="coerce").dt.to_period('M')
    inv = inv[(inv['Cost center'] == '34N00001') & (inv['Item group'].isin([2000]))].copy()

    mask_ppap = inv['Warehouse'].astype(str).str.startswith(('CQ', 'NC'))
    ppap_df = inv[mask_ppap].copy()
    ppap_df['category'] = 'QualityLocation'
    inv = inv[~mask_ppap]

    inv_agg = inv.groupby('Item number').agg({
        'On-hand': 'sum',
        'Inventory value': 'sum',
        'year_month': 'max'
    }).reset_index()

    inv_agg['is_obsolete'] = inv_agg['Item number'].isin(obsolete_codes)
    inv_agg['is_new'] = inv_agg['Item number'].isin(new_entry_codes)

    cutoff = inv_agg['year_month'].max()
    sales_cut = sales_agg[sales_agg['year_month'] <= cutoff].copy()
    sales_cut['months_since_last_sale'] = (cutoff - sales_cut['year_month']).apply(lambda x: x.n)

    sales_47 = (
        sales_cut[sales_cut['months_since_last_sale'] <= 47]
        .groupby('rule_item_code')['Sales Qua']
        .sum()
        .rename('sales_47months')
    )
    sales_23 = (
        sales_cut[sales_cut['months_since_last_sale'] <= 23]
        .groupby('rule_item_code')['Sales Qua']
        .sum()
        .rename('sales_23months')
    )
    sales_6 = (
        sales_cut[sales_cut['months_since_last_sale'] <= 5]
        .groupby('rule_item_code')['Sales Qua']
        .sum()
        .rename('sales_6months')
    )

    inv_final = (
        inv_agg
        .merge(sales_47, left_on='Item number', right_index=True, how='left')
        .merge(sales_23, left_on='Item number', right_index=True, how='left')
        .merge(sales_6, left_on='Item number', right_index=True, how='left')
    )
    inv_final[['sales_47months', 'sales_23months', 'sales_6months']] = \
        inv_final[['sales_47months', 'sales_23months', 'sales_6months']].fillna(0)
    inv_final['coverage'] = inv_final['On-hand'] / (inv_final['sales_6months'] / 6)

    def classify(row):
        if row['is_obsolete']:
            return 'Obsolete'
        elif row['is_new']:
            return 'New Entry'
        elif row['On-hand'] > row['sales_47months']:
            return 'Excessive'
        elif row['On-hand'] > row['sales_23months']:
            return 'SlowMoving'
        else:
            return 'Normal'

    inv_final['category'] = inv_final.apply(classify, axis=1)
    inv_final = inv_final.drop(columns=['is_obsolete', 'is_new', 'sales_6months'], errors='ignore')

    combined = pd.concat([format_df(inv_final), format_df(ppap_df)], ignore_index=True)
    combined.rename(
        columns={
            'sales_47months': 'Sales Volume 4Y',
            'sales_23months': 'Sales Volume 2Y'
        },
        inplace=True
    )
    results[sheet_name] = combined

with pd.ExcelWriter(output_path) as writer:
    for sheet, df in results.items():
        df.to_excel(writer, sheet_name=sheet, index=False)

print(f"✅ 已完成清洗并保存至: {output_path}")

