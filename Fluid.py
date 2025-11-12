import pandas as pd
import pdb  # 引入pdb模块进行调试
import numpy as np  # 新增：用于处理除数为零的情况


# 文件路径定义
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
output_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database/test/Fluid.xlsx"
bundle_mapping_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\库存/component.xlsx"


# 规则函数：处理库存和销售数据的代码（保持不变）
def rule_code(x: str) -> str:
    x = str(x)
    if x.startswith(("08", "09", "14")) and len(x) > 7 and x[7] in ['0', '1', 'V', '4']:
        return x[:7]
    return x[:8]


# 加载销售数据（保持不变）
sales_all = [pd.read_excel(p) for p in sales_path]
sales = pd.concat(sales_all, ignore_index=True)
sales['year_month'] = pd.to_datetime(
    sales['Year'].astype(str) + "-" + sales['Month'].astype(str).str.zfill(2), format='%Y-%m'
).dt.to_period('M')
sales['Item - Code'] = sales['Item - Code'].astype(str)
sales['rule_item_code'] = sales['Item - Code'].apply(rule_code)
sales_agg = sales.groupby(['year_month', 'rule_item_code'])['Sales Qua'].sum().reset_index()

# 加载废弃产品数据（保持不变）
obsolete = pd.read_excel(obsolete_path)
obsolete['ax_part_number'] = obsolete['ax_part_number'].astype(str)
obsolete['rule_ax_part_number'] = obsolete['ax_part_number'].apply(rule_code)

# 加载新产品数据（保持不变）
new = pd.read_excel(new_path)
new['AX_PART_NUMBER'] = new['AX_PART_NUMBER'].astype(str)
new['rule_ax_part_number'] = new['AX_PART_NUMBER'].apply(rule_code)
new['created_date_time'] = pd.to_datetime(new['created_date_time'], errors='coerce')
new_entry_data_map = new.groupby('rule_ax_part_number')['created_date_time'].min().to_dict()

# 获取新产品的规则代码（保持不变）
cutoff_date = pd.Timestamp('2024-01-01')
new_entry_codes = set(
    new.groupby('rule_ax_part_number')['created_date_time'].min()
    .loc[lambda x: x >= cutoff_date]
    .index
)

# 加载bundle映射（保持不变）
bundle_mapping = pd.read_excel(bundle_mapping_path)
bundle_mapping = bundle_mapping[~bundle_mapping['Item number'].str.startswith('P')]

# 处理bundle销售数据（保持不变）
for _, row in bundle_mapping.iterrows():
    bundle_code = row['Item number']
    child_code = row['sub_Item number']
    child_sales = sales[sales['Item - Code'] == str(child_code)]
    for _, child_row in child_sales.iterrows():
        child_month = child_row['year_month']
        child_quantity = child_row['Sales Qua'] * 2
        match = (sales_agg['rule_item_code'] == bundle_code) & (sales_agg['year_month'] == child_month)
        if match.any():
            sales_agg.loc[match, 'Sales Qua'] += child_quantity
        else:
            new_row = pd.DataFrame({
                'year_month': [child_month],
                'rule_item_code': [bundle_code],
                'Sales Qua': [child_quantity]
            })
            sales_agg = pd.concat([sales_agg, new_row], ignore_index=True)

# 初始化结果存储
results = {}
sheet_names = pd.ExcelFile(inventory_path).sheet_names

# 处理每一个工作表
for sheet_name in sheet_names:
    print(f"\n✨ 处理月份: {sheet_name}")
    inv = pd.read_excel(inventory_path, sheet_name=sheet_name)

    # 确保 'year_month' 列是 Period 类型（保持不变）
    if 'year_month' in inv.columns:
        inv['year_month'] = pd.to_datetime(inv['year_month'], errors="coerce").dt.to_period('M')
    else:
        while True:
            manual_input = input("请输入年月（格式为YYYY-MM）：")
            try:
                inv['year_month'] = pd.Period(manual_input, freq='M')
                print(f"已创建'year_month'列，并设置为：{manual_input}")
                break
            except ValueError:
                print("输入格式错误，请重新输入（例如：2023-01）")

    inv['Item number'] = inv['Item number'].astype(str)
    inv["Cost center"] = inv["Cost center"].astype(str)
    inv["Item group"] = inv["Item group"].astype(str)

    # 提取当前月份
    current_month = inv['year_month'].max()
    print(f"  当前处理的库存月份: {current_month}")

    # -------------------------- Fluid核心筛选（移除Item group） --------------------------
    inv = inv[
        (inv['Cost center'] == "34N00001") &
        (inv['Item number'].str.startswith('L', na=False))
        ]
    # ---------------------------------------------------------------------------------

    # 规则代码映射（保持不变）
    inv['rule_Item number'] = inv['Item number'].apply(rule_code)

    # 筛选 PPAP 数据（保持不变）
    mask_ppap = inv['Warehouse'].str.startswith(('CQ', 'NC')).fillna(False)
    ppap_df = inv[mask_ppap].copy()
    inv_normal = inv[~mask_ppap].copy()

    # 汇总库存数据（保持不变）
    inv_normal = inv_normal.groupby('rule_Item number', as_index=False).agg({
        'On-hand': 'sum',
        'Inventory value': 'sum',
        'year_month': 'max'
    })

    # 销售数据处理（保持不变）
    sales_recent = sales_agg[sales_agg['year_month'] <= current_month].copy()
    sales_recent['months_diff'] = (current_month - sales_recent['year_month']).apply(
        lambda x: x.n if pd.notna(x) else 0)
    sales_2y_dict = sales_recent[sales_recent['months_diff'] <= 23].groupby('rule_item_code')[
        'Sales Qua'].sum().to_dict()
    sales_4y_dict = sales_recent[sales_recent['months_diff'] <= 47].groupby('rule_item_code')[
        'Sales Qua'].sum().to_dict()
    sales_12_dict = sales_recent[sales_recent['months_diff'] <= 11].groupby('rule_item_code')[
        'Sales Qua'].sum().to_dict()

    # 计算销售指标（保持不变）
    inv_normal['sales_12m'] = inv_normal['rule_Item number'].map(sales_12_dict).fillna(0)
    inv_normal['sales_2y'] = inv_normal['rule_Item number'].map(sales_2y_dict).fillna(0)
    inv_normal['sales_4y'] = inv_normal['rule_Item number'].map(sales_4y_dict).fillna(0)


    # 分类函数（保持不变）
    def classify(row):
        code = row['rule_Item number']
        qty = row['On-hand']
        s2y = row['sales_2y']
        s4y = row['sales_4y']
        if code in obsolete['rule_ax_part_number'].values:
            return 'Obsolete'
        elif code in new_entry_codes:
            return 'New Entry'
        if qty > s4y:
            return 'Excessive'
        elif qty > s2y:
            return 'SlowMoving'
        else:
            return 'Normal'


    # 库存分类 + 新增DIO计算
    inv_normal['category'] = inv_normal.apply(classify, axis=1)
    inv_normal['create_time'] = inv_normal['rule_Item number'].map(new_entry_data_map)
    inv_normal['coverage'] = inv_normal['On-hand'] / (inv_normal['rule_Item number'].map(sales_12_dict).fillna(0) / 12)
    # # 新增：计算DIO（处理除数为零）
    # inv_normal['DIO'] = np.where(
    #     inv_normal['sales_12m'] != 0,  # 避免12个月销售额为0时出错
    #     (inv_normal['On-hand'] / inv_normal['sales_12m']) * 360,
    #     0  # 销售额为0时DIO设为0（可根据需求调整为NaN）
    # )

    # 处理 PPAP 数据
    ppap_df = ppap_df.groupby('rule_Item number', as_index=False).agg({
        'On-hand': 'sum',
        'Inventory value': 'sum',
        'year_month': 'max'
    })
    ppap_df['category'] = 'QualityLocation'
    ppap_df['sales_2y'] = ppap_df['rule_Item number'].map(sales_2y_dict).fillna(0)
    ppap_df['sales_4y'] = ppap_df['rule_Item number'].map(sales_4y_dict).fillna(0)
    # 新增：为ppap_df添加sales_12m列（用于计算DIO）
    ppap_df['sales_12m'] = ppap_df['rule_Item number'].map(sales_12_dict).fillna(0)
    ppap_df['create_time'] = ppap_df['rule_Item number'].map(new_entry_data_map)
    ppap_df['coverage'] = ppap_df['On-hand'] / (ppap_df['rule_Item number'].map(sales_12_dict).fillna(0) / 12)
    # # 新增：计算DIO（处理除数为零）
    # ppap_df['DIO'] = np.where(
    #     ppap_df['sales_12m'] != 0,
    #     (ppap_df['On-hand'] / ppap_df['sales_12m']) * 360,
    #     0
    # )

    # 合并数据（保持不变）
    month_df = pd.concat([inv_normal, ppap_df], ignore_index=True)
    month_df.rename(columns={'rule_Item number': "Item number"}, inplace=True)
    month_df.rename(columns={'sales_2y': "Sales Volume 2Y", 'sales_4y': "Sales Volume 4Y"}, inplace=True)
    results[sheet_name] = month_df

    # 输出校验信息
    print(f" 原始库存数量: {inv['On-hand'].sum()}")
    print(f" 分类后库存数量总和: {month_df['On-hand'].sum()}")
    print(f" ✅ 差异: {inv['On-hand'].sum() - month_df['On-hand'].sum()}")

# 保存结果
with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
    for month, df in results.items():
        df.to_excel(writer, sheet_name=month, index=False)
print(f"\n✅ Fluid分类完成并保存到: {output_path}")