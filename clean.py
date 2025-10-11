import pandas as pd
import pdb  # 引入pdb模块进行调试


# 文件路径定义
inventory_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\库存/Inventory foto.xlsx"
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
output_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database\test/Disc.xlsx"
bundle_mapping_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\库存/component.xlsx"


# 规则函数：处理库存和销售数据的代码
def rule_code(x: str) -> str:
    x = str(x)
    if x.startswith(("08", "09", "14")) and len(x) > 7 and x[7] in ['0', '1', 'V', '4']:
        return x[:7]
    return x[:8]


# 加载销售数据
sales_all = [pd.read_excel(p) for p in sales_path]
sales = pd.concat(sales_all, ignore_index=True)
sales['year_month'] = pd.to_datetime(
    sales['Year'].astype(str) + "-" + sales['Month'].astype(str).str.zfill(2), format='%Y-%m'
).dt.to_period('M')
sales['Item - Code'] = sales['Item - Code'].astype(str)
sales['rule_item_code'] = sales['Item - Code'].apply(rule_code)
sales_agg = sales.groupby(['year_month', 'rule_item_code'])['Sales Qua'].sum().reset_index()

# 加载废弃产品数据
obsolete = pd.read_excel(obsolete_path)
obsolete['ax_part_number'] = obsolete['ax_part_number'].astype(str)
obsolete['rule_ax_part_number'] = obsolete['ax_part_number'].apply(rule_code)

# 加载新产品数据
new = pd.read_excel(new_path)
new['AX_PART_NUMBER'] = new['AX_PART_NUMBER'].astype(str)
new['rule_ax_part_number'] = new['AX_PART_NUMBER'].apply(rule_code)
new['created_date_time'] = pd.to_datetime(new['created_date_time'], errors='coerce')
new_entry_data_map = new.groupby('rule_ax_part_number')['created_date_time'].min().to_dict()

# 获取新产品的规则代码（创建日期大于 2024-01-01）
cutoff_date = pd.Timestamp('2024-01-01')
new_entry_codes = set(
    new.groupby('rule_ax_part_number')['created_date_time'].min()
    .loc[lambda x: x >= cutoff_date]
    .index
)

# 加载bundle映射，并筛选非以 'P' 开头的 bundle
bundle_mapping = pd.read_excel(bundle_mapping_path)
bundle_mapping = bundle_mapping[~bundle_mapping['Item number'].str.startswith('P')]

# 非 'P' 开头的项作为有效的 bundle
# 一开始就合并 bundle 销售数据并将销量乘以2
for _, row in bundle_mapping.iterrows():
    bundle_code = row['Item number']  # Bundle 的代码
    child_code = row['sub_Item number']  # 子项的代码

    # 找到子项的销售数据
    child_sales = sales[sales['Item - Code'] == str(child_code)]

    # 遍历每一条子项的销售记录
    for _, child_row in child_sales.iterrows():
        child_month = child_row['year_month']
        child_quantity = child_row['Sales Qua'] * 2  # 销量乘以2

        # 在销售数据汇总表（sales_agg）中查找对应的 Bundle 销售数据
        match = (sales_agg['rule_item_code'] == bundle_code) & (sales_agg['year_month'] == child_month)

        # 如果找到了对应月份的 bundle 销售记录，就累加数量
        if match.any():
            sales_agg.loc[match, 'Sales Qua'] += child_quantity
        else:
            # 如果没有找到，则创建新记录
            new_row = pd.DataFrame({
                'year_month': [child_month],
                'rule_item_code': [bundle_code],
                'Sales Qua': [child_quantity]
            })
            sales_agg = pd.concat([sales_agg, new_row], ignore_index=True)

# 初始化结果存储
results = {}
sheet_names = pd.ExcelFile(inventory_path).sheet_names  # 获取所有工作表名称

# 处理每一个工作表
for sheet_name in sheet_names:
    print(f"\n✨ 处理月份: {sheet_name}")

    # 加载当前工作表数据
    inv = pd.read_excel(inventory_path, sheet_name=sheet_name)

    #调试
   # pdb.set_trace()
    # 获取当前月与销售月份之间的差异，并强制转换为整数
    # sales_recent['months_diff'] = (current_month - sales_recent['year_month']).apply(
    #     lambda x: int(x.n)  # 强制将 Timedelta 对象的差值转换为整数
    # )

    # 提取 year 和 month 到外部字段
    # sales_recent['year'] = sales_recent['year_month'].dt.year
    # sales_recent['month'] = sales_recent['year_month'].dt.month
###########



    # 确保 'year_month' 列是 Period 类型
    if 'year_month' in inv.columns:
        inv['year_month'] = pd.to_datetime(inv['year_month'], errors="coerce").dt.to_period('M')
###添加条件
    else:
        # 交互式输入年月
        while True:
            manual_input = input("请输入年月（格式为YYYY-MM）：")
            try:
                # 验证输入格式并转换为Period类型
                inv['year_month'] = pd.Period(manual_input, freq='M')
                print(f"已创建'year_month'列，并设置为：{manual_input}")
                break
            except ValueError:
                print("输入格式错误，请重新输入（例如：2023-01）")


    inv['Item number'] = inv['Item number'].astype(str)
    inv["Cost center"] = inv["Cost center"].astype(str)
    inv["Item group"] = inv["Item group"].astype(str)

    # -------------------------- 关键修复：提前定义 current_month --------------------------
    # 从当前库存数据中提取“当前月份”（必须在处理 sales_recent 之前定义！）
    current_month = inv['year_month'].max()  # 现在变量有值了，后面用的时候不会报错
    print(f"  当前处理的库存月份: {current_month}")  # 可选：验证月份是否正确
    # -------------------------------------------------------------------------------------

    # 筛选相关的成本中心和项目组
    inv = inv[(inv['Cost center'] == "34N00001") & (inv['Item group'].isin(["2300", "2330"]))]

    # 规则代码映射
    inv['rule_Item number'] = inv['Item number'].apply(rule_code)

    # 筛选 PPAP 数据
    mask_ppap = inv['Warehouse'].str.startswith(('CQ', 'NC')).fillna(False)
    ppap_df = inv[mask_ppap].copy()
    inv_normal = inv[~mask_ppap].copy()

    # 汇总库存数据
    inv_normal = inv_normal.groupby('rule_Item number', as_index=False).agg({
        'On-hand': 'sum',
        'Inventory value': 'sum',
        'year_month': 'max'
    })

    # 获取当前月
    #current_month = inv['year_month'].max()

    # 销售数据处理
    sales_recent = sales_agg[sales_agg['year_month'] <= current_month].copy()
    sales_recent['months_diff'] = (current_month - sales_recent['year_month']).apply(lambda x: x.n if pd.notna(x) else 0
                                                                                     )
    #强制转换为整数
    #sales_recent['months_diff'] = sales_recent['months_diff'].astype(int)

    sales_2y_dict = sales_recent[sales_recent['months_diff'] <= 23].groupby('rule_item_code')[
        'Sales Qua'].sum().to_dict()
    sales_4y_dict = sales_recent[sales_recent['months_diff'] <= 47].groupby('rule_item_code')[
        'Sales Qua'].sum().to_dict()
    sales_6_dict = sales_recent[sales_recent['months_diff'] <= 5].groupby('rule_item_code')['Sales Qua'].sum().to_dict()


    # 分类函数
    def classify(row):
        code = row['rule_Item number']
        qty = row['On-hand']
        if code in obsolete['rule_ax_part_number'].values:
            return 'Obsolete'
        elif code in new_entry_codes:
            return 'New Entry'
        s47 = sales_4y_dict.get(code, 0)
        s23 = sales_2y_dict.get(code, 0)
        if qty > s47:
            return 'Excessive'
        elif qty > s23:
            return 'SlowMoving'
        else:
            return 'Normal'


    # 处理库存数据并添加分类
    inv_normal['category'] = inv_normal.apply(classify, axis=1)
    inv_normal['sales_2y'] = inv_normal['rule_Item number'].map(sales_2y_dict).fillna(0)
    inv_normal['sales_4y'] = inv_normal['rule_Item number'].map(sales_4y_dict).fillna(0)
    inv_normal['created_date'] = inv_normal['rule_Item number'].map(new_entry_data_map)
    inv_normal['coverage'] = inv_normal['On-hand'] / (inv_normal['rule_Item number'].map(sales_6_dict).fillna(0) / 6)

    # 处理 PPAP 数据
    ppap_df = ppap_df.groupby('rule_Item number', as_index=False).agg({
        'On-hand': 'sum',
        'Inventory value': 'sum',
        'year_month': 'max'
    })
    ppap_df['category'] = 'QualityLocation'
    ppap_df['sales_2y'] = ppap_df['rule_Item number'].map(sales_2y_dict).fillna(0)
    ppap_df['sales_4y'] = ppap_df['rule_Item number'].map(sales_4y_dict).fillna(0)
    ppap_df['created_date'] = ppap_df['rule_Item number'].map(new_entry_data_map)
    ppap_df['coverage'] = ppap_df['On-hand'] / (ppap_df['rule_Item number'].map(sales_6_dict).fillna(0) / 6)

    # 合并数据
    month_df = pd.concat([inv_normal, ppap_df], ignore_index=True)
    month_df.rename(columns={'rule_Item number': "Item number"}, inplace=True)
    month_df.rename(columns={'sales_2y': "Sales Volume 2Y", 'sales_4y': "Sales Volume 4Y"}, inplace=True)

    results[sheet_name] = month_df
    print(f" 原始库存数量: {inv['On-hand'].sum()}")
    print(f" 分类后库存数量总和: {month_df['On-hand'].sum()}")
    print(f" ✅ 差异: {inv['On-hand'].sum() - month_df['On-hand'].sum()}")

# 将结果保存到 Excel 文件
with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
    for month, df in results.items():
        df.to_excel(writer, sheet_name=month, index=False)

print(f"\n✅ 修正版分类完成并保存到: {output_path}")
