import pandas as pd

file_path = r"C:\Users\yangma\OneDrive - Brembo\桌面\Dash Database\Book1.xlsx"
df = pd.read_excel(file_path)
print(df.head())


# 要保留的列名
columns_to_keep = [
    'Month', 'Year','Region', 'Country', 'Customer code', 'Customer - Name',
    'Item - Code', '8 digit', 'Item - Item Group Full Name', 'Sales Qua',
    'Total Sales Amt', 'Sales Amt per Unit', 'Rebate Amount', 'Net Sales',
    'Freight Out', 'Act Material Cost Total', 'Contracted Work Total',
    'Other VC Total', 'Act VC Total', 'Act FC Total', 'Commission',
    'SG&A Total Exclud. Commission', 'EBIT','Product Type','Customer code','Sub Region','USD-rate','RMB-rate'
]

# 读取 Excel
df = pd.read_excel(file_path)

# 保留需要的列
df_filtered = df[columns_to_keep]



# 覆盖原文件（注意：这将删除原文件中未保留的列）
#df.to_excel(file_path,index=False)

df_filtered.to_excel(file_path, index=False)
print("数据清洗完成")
