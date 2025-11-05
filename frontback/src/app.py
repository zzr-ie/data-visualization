from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import io
import base64
import traceback
import os
import glob
from datetime import datetime

app = Flask(__name__)
CORS(app)

# In-memory storage for uploaded dataframes
STORE = {
    "df_store": None,
    "inventory": None,
    "balance": None,
    "pads": None,
    "disc": None
}


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    # keep a lightweight version of the cleaning logic used in the Dash app
    df = df.copy()
    df.columns = df.columns.str.strip()
    if 'Year' in df.columns and 'Month' in df.columns:
        df['Date'] = pd.to_datetime(
            df['Year'].astype(str) + '-' + df['Month'].astype(str).apply(lambda x: x.zfill(2)),
            format='%Y-%m', errors='coerce'
        ).dt.strftime('%Y-%m')
        df = df.drop(columns=[c for c in ['Year', 'Month'] if c in df.columns])

    # ensure string columns are strings
    string_cols = ['Region', 'Sub Region', 'Country', 'Product Type',
                   'Item - Item Group Full Name', 'Customer - Name', 'Item - Code']
    for col in df.columns:
        if col in string_cols:
            df[col] = df[col].astype(str).fillna("")
        elif col != 'Date':
            # try to coerce numeric columns
            df[col] = pd.to_numeric(df[col], errors='coerce')
    # drop packaging group if present
    if 'Item - Item Group Full Name' in df.columns:
        df = df[df['Item - Item Group Full Name'] != '2900 - Packaging']
    # reorder Date first
    cols = ['Date'] + [c for c in df.columns if c != 'Date']
    cols = [c for c in cols if c in df.columns]
    return df[cols]


def normalize_inventory_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()
    lower = {c.lower(): c for c in df.columns}
    aliases = {
        'item number': 'Item number', 'item_number': 'Item number', 'itemno': 'Item number',
        'cost center': 'Cost center', 'cost_center': 'Cost center',
        'year_month': 'year_month', 'year-month': 'year_month',
        'on-hand': 'On-hand', 'on hand': 'On-hand',
    }
    col_map = {}
    for k, std in aliases.items():
        if k in lower:
            col_map[lower[k]] = std
    if col_map:
        df = df.rename(columns=col_map)
    if 'Item number' in df.columns:
        df['Item number'] = df['Item number'].astype(str).fillna('').str.upper().str.strip()
    if 'Cost center' in df.columns:
        df['Cost center'] = df['Cost center'].astype(str).fillna('').str.upper().str.strip()
    if 'year_month' in df.columns:
        df['year_month'] = pd.to_datetime(df['year_month'], errors='coerce').dt.strftime('%Y-%m')
    return df


def sum_curr_prev(field, starts, df1: pd.DataFrame, df2: pd.DataFrame):
    """Sum `field` in df1 and df2 for rows whose Item number starts with any of `starts`.
    `starts` may be a string, tuple, list or None. Returns tuple (curr_sum, prev_sum).
    """
    # normalize starts
    if starts is None:
        starts_t = None
    elif isinstance(starts, (list, set, tuple)):
        starts_t = tuple(str(s).upper() for s in starts)
    else:
        starts_t = (str(starts).upper(),)

    def _prepare_idx(df):
        if df is None or df.empty:
            return pd.Series([], dtype=str)
        if 'Item number' in df.columns:
            s = df['Item number'].astype(str).fillna('').str.upper().str.strip()
        elif 'Item - Code' in df.columns:
            s = df['Item - Code'].astype(str).fillna('').str.upper().str.strip()
        else:
            s = df.index.to_series().astype(str).fillna('').str.upper().str.strip()
        return s

    s1 = _prepare_idx(df1)
    if starts_t is None:
        curr = df1[field].sum() if (df1 is not None and field in df1.columns) else 0
    else:
        mask1 = s1.str.startswith(starts_t)
        curr = df1.loc[mask1, field].sum() if (df1 is not None and field in df1.columns) else 0

    if df2 is None or df2.empty:
        prev = 0
    else:
        s2 = _prepare_idx(df2)
        if starts_t is None:
            prev = df2[field].sum() if field in df2.columns else 0
        else:
            mask2 = s2.str.startswith(starts_t)
            prev = df2.loc[mask2, field].sum() if field in df2.columns else 0

    try:
        curr = float(curr)
    except Exception:
        curr = 0
    try:
        prev = float(prev)
    except Exception:
        prev = 0
    return curr, prev


def compute_cost_breakdown(df: pd.DataFrame):
    """Compute breakdown dataframe similar to the Dash app.
    Returns (breakdown_df, total_sales_amt). If input df is empty or missing columns, returns (None, 0).
    """
    if df is None or df.empty:
        return pd.DataFrame(), 0
    # ensure required columns exist; use 0 as fallback
    total_sales_amt = df.get('Total Sales Amt', pd.Series([0])).sum()
    net_sales_amt = df.get('Net Sales', pd.Series([0])).sum()

    if net_sales_amt == 0:
        # Avoid division by zero; return empty
        return pd.DataFrame(), int(total_sales_amt)

    # Safely get sums for each category column
    def s(col):
        return df.get(col, pd.Series([0])).sum()

    rows = [
        ("Rebate", s('Rebate Amount')),
        ("Freight Out", s('Freight Out')),
        ("Purchasing Material", s('Act Material Cost Total')),
        ("Warehouse Operation", s('Contracted Work Total')),
        ("Commission", s('Commission')),
        ("Other SG&A", s('SG&A Total Exclud. Commission')),
        ("EBIT", s('EBIT'))
    ]

    breakdown_df = pd.DataFrame(rows, columns=['Category', 'Absolute Value'])
    breakdown_df['Percentage'] = breakdown_df['Absolute Value'] / float(net_sales_amt)
    breakdown_df['Absolute Value'] = breakdown_df['Absolute Value'].clip(lower=0)
    # enforce category order
    breakdown_df['Category'] = pd.Categorical(
        breakdown_df['Category'],
        categories=["Rebate", "Freight Out", "Purchasing Material", "Warehouse Operation", "Commission", "Other SG&A", "EBIT"],
        ordered=True
    )
    return breakdown_df.sort_values('Category'), float(total_sales_amt)


def compute_avg_monthly_sales(sales_df: pd.DataFrame, months: int = 12):
    """Compute average monthly sales quantity per item code over the last `months` months.
    Returns a Series indexed by item code (uppercased) with the average monthly sales quantity.
    """
    if sales_df is None or sales_df.empty:
        return pd.Series(dtype=float)
    df = sales_df.copy()
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        last_date = df['Date'].max()
        if pd.isna(last_date):
            last_date = None
    else:
        last_date = None

    if last_date is not None:
        start_cut = (last_date - pd.DateOffset(months=months)).replace(day=1)
        df = df[df['Date'] >= start_cut]

    # choose item code column
    if 'Item - Code' in df.columns:
        key = 'Item - Code'
    elif 'Item Code' in df.columns:
        key = 'Item Code'
    else:
        # cannot compute
        return pd.Series(dtype=float)

    grp = df.groupby([key]).agg({'Sales Qua': 'sum'}).rename(columns={'Sales Qua': 'total_qty'})
    grp['avg_monthly'] = grp['total_qty'] / float(months)
    # normalize index keys
    grp.index = grp.index.astype(str).str.upper().str.strip()
    return grp['avg_monthly']


def load_data_from_disk(data_dir=None):
    """Scan backend/data/ directory and load available xlsx/csv files into STORE.
    Files containing keywords determine target: inventory, pads, disc, balance, otherwise treated as sales.
    """
    base = data_dir or os.path.join(os.path.dirname(__file__), 'data')
    if not os.path.isdir(base):
        return {'loaded': False, 'reason': f'data dir not found: {base}'}

    sales_dfs = []
    # find files
    patterns = ['*.xlsx', '*.xls', '*.csv']
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(base, p)))

    for fp in files:
        fname = os.path.basename(fp).lower()
        try:
            if fp.lower().endswith('.csv'):
                df = pd.read_csv(fp)
            else:
                xls = pd.read_excel(fp, sheet_name=None)
                df = pd.concat(xls.values(), ignore_index=True)
        except Exception as e:
            # skip unreadable files
            continue

        if 'inventory' in fname or 'inv' in fname:
            # normalize and concatenate
            inv = normalize_inventory_df(df)
            if STORE.get('inventory') is None or STORE['inventory'].empty:
                STORE['inventory'] = inv
            else:
                STORE['inventory'] = pd.concat([STORE['inventory'], inv], ignore_index=True)
        elif 'pads' in fname:
            STORE['pads'] = pd.concat([STORE['pads'], df], ignore_index=True) if STORE.get('pads') is not None and not STORE['pads'].empty else df
        elif 'disc' in fname:
            STORE['disc'] = pd.concat([STORE['disc'], df], ignore_index=True) if STORE.get('disc') is not None and not STORE['disc'].empty else df
        elif 'balance' in fname or 'bal' in fname:
            STORE['balance'] = pd.concat([STORE['balance'], df], ignore_index=True) if STORE.get('balance') is not None and not STORE['balance'].empty else df
        else:
            # treat as sales / transactions
            try:
                cleaned = clean_data(df)
                sales_dfs.append(cleaned)
            except Exception:
                # skip if cannot clean
                continue

    if sales_dfs:
        STORE['df_store'] = pd.concat(sales_dfs, ignore_index=True)

    # post-process inventory: ensure year_month and compute coverage if possible
    if STORE.get('inventory') is not None and not STORE['inventory'].empty:
        inv = STORE['inventory']
        if 'year_month' in inv.columns:
            inv['year_month'] = pd.to_datetime(inv['year_month'], errors='coerce').dt.strftime('%Y-%m')
        # parse created_date
        if 'created_date' in inv.columns:
            inv['created_date'] = pd.to_datetime(inv['created_date'], errors='coerce')

        # compute coverage from sales if not present
        if 'coverage' not in inv.columns or inv['coverage'].isnull().all():
            avg_sales = pd.Series(dtype=float)
            if STORE.get('df_store') is not None and not STORE['df_store'].empty:
                avg_sales = compute_avg_monthly_sales(STORE['df_store'], months=12)
            if not avg_sales.empty and 'Item number' in inv.columns and 'On-hand' in inv.columns:
                inv['Item number_key'] = inv['Item number'].astype(str).str.upper().str.strip()
                inv = inv.merge(avg_sales.rename('avg_monthly'), left_on='Item number_key', right_index=True, how='left')
                inv['coverage'] = None
                mask = inv['avg_monthly'].notna() & (inv['avg_monthly'] > 0)
                inv.loc[mask, 'coverage'] = inv.loc[mask, 'On-hand'].astype(float) / inv.loc[mask, 'avg_monthly'].astype(float)
                # fill inf/null with large number
                inv['coverage'] = inv['coverage'].replace([pd.NA, pd.NaT], None)
                inv.drop(columns=['Item number_key', 'avg_monthly'], inplace=True, errors='ignore')

        STORE['inventory'] = inv

    return {'loaded': True, 'files_found': len(files)}


@app.route('/api/reload-data', methods=['POST'])
def api_reload_data():
    payload = request.json or {}
    data_dir = payload.get('data_dir')
    res = load_data_from_disk(data_dir)
    return jsonify(res)


@app.route('/api/inventory-cards', methods=['GET'])
def inventory_cards():
    """Return a list of inventory card metrics for a given month.
    Cards include Total Inventory, Pads, Disc, Coverage, and DIO where computable.
    """
    month = request.args.get('month')
    if STORE['inventory'] is None:
        return jsonify({'error': 'no inventory uploaded'}), 400

    inv_resp = inventory().get_json()

    # compute coverage: need avg monthly sales per item
    avg_sales = pd.Series(dtype=float)
    if STORE.get('df_store') is not None and not STORE['df_store'].empty:
        avg_sales = compute_avg_monthly_sales(STORE['df_store'], months=12)

    # coverage: for overall inventory, compute weighted average coverage where possible
    coverage = None
    try:
        inv = STORE['inventory'].copy()
        if month and 'year_month' in inv.columns:
            inv_curr = inv[inv['year_month'] == month].copy()
        else:
            inv_curr = inv.copy()

        if 'Item number' in inv_curr.columns and 'On-hand' in inv_curr.columns and not avg_sales.empty:
            # join by item code: uppercase
            inv_curr['Item number_key'] = inv_curr['Item number'].astype(str).str.upper().str.strip()
            merged = inv_curr.merge(avg_sales.rename('avg_monthly'), left_on='Item number_key', right_index=True, how='left')
            # only where avg_monthly > 0
            merged = merged[merged['avg_monthly'] > 0]
            if not merged.empty:
                merged['coverage_months'] = merged['On-hand'].astype(float) / merged['avg_monthly'].astype(float)
                # median coverage
                coverage = float(merged['coverage_months'].median())
    except Exception:
        coverage = None

    # compute DIO: inventory value / (avg monthly COGS) * 30 (days)
    dio = None
    try:
        inv_val = float(inv_resp.get('total_value', 0.0))
        # estimate monthly COGS from sales data Act Material Cost Total
        if STORE.get('df_store') is not None and not STORE['df_store'].empty:
            sales = STORE['df_store'].copy()
            # consider last 12 months
            sales['Date'] = pd.to_datetime(sales['Date'], errors='coerce')
            last = sales['Date'].max()
            start_cut = (last - pd.DateOffset(months=12)).replace(day=1) if not pd.isna(last) else None
            if start_cut is not None:
                sales_12 = sales[sales['Date'] >= start_cut]
            else:
                sales_12 = sales
            monthly_cogs = sales_12.get('Act Material Cost Total', pd.Series([0])).sum() / 12.0
            if monthly_cogs > 0:
                dio = (inv_val / monthly_cogs) * 30.0
    except Exception:
        dio = None

    cards = [
        {'id': 'total_inventory', 'title': 'Total Inventory', 'value': inv_resp.get('total_qty', 0), 'value_amt': inv_resp.get('total_value', 0.0), 'mom_qty': inv_resp.get('qty_mom'), 'mom_value': inv_resp.get('val_mom')},
        {'id': 'pads', 'title': 'Pads', 'value': inv_resp.get('pads_qty', 0), 'value_amt': inv_resp.get('pads_value', 0.0)},
        {'id': 'disc', 'title': 'Disc', 'value': inv_resp.get('disc_qty', 0), 'value_amt': inv_resp.get('disc_value', 0.0)},
        {'id': 'coverage', 'title': 'Coverage (months)', 'value': coverage},
        {'id': 'dio', 'title': 'DIO (days)', 'value': dio}
    ]

    # --- compute coverage distribution & top items for frontend histogram/table ---
    coverage_distribution = []
    top_items = []
    try:
        inv = STORE['inventory'].copy()
        if month and 'year_month' in inv.columns:
            inv_curr = inv[inv['year_month'] == month].copy()
        else:
            inv_curr = inv.copy()

        # helper: find a column name by substring (case-insensitive)
        def find_col(df, substrs):
            cols = list(df.columns)
            lower = [c.lower() for c in cols]
            for s in substrs:
                s = s.lower()
                for i, c in enumerate(lower):
                    if s in c:
                        return cols[i]
            return None

        on_hand_col = find_col(inv_curr, ['on-hand', 'on hand', 'onhand']) or 'On-hand'
        value_col = find_col(inv_curr, ['inventory value', 'inventory_value', 'inventoryvalue', 'value']) or 'Inventory value'
        item_col = find_col(inv_curr, ['item number', 'item - code', 'item - code'.lower()]) or 'Item number'

        # compute coverage values if avg_sales exists
        if not avg_sales.empty and item_col in inv_curr.columns and on_hand_col in inv_curr.columns:
            inv_curr['__item_key'] = inv_curr[item_col].astype(str).str.upper().str.strip()
            merged = inv_curr.merge(avg_sales.rename('avg_monthly'), left_on='__item_key', right_index=True, how='left')
            merged['coverage_months'] = None
            mask = merged['avg_monthly'].notna() & (merged['avg_monthly'] > 0)
            merged.loc[mask, 'coverage_months'] = merged.loc[mask, on_hand_col].astype(float) / merged.loc[mask, 'avg_monthly'].astype(float)
            # drop null/inf
            covs = pd.to_numeric(merged['coverage_months'], errors='coerce')
            covs = covs.replace([np.inf, -np.inf], np.nan).dropna()
            coverage_distribution = covs.tolist()

            # top items by inventory value
            if value_col in merged.columns:
                merged[value_col] = pd.to_numeric(merged[value_col], errors='coerce').fillna(0.0)
                top_df = merged.sort_values(by=value_col, ascending=False).head(50)
                for _, r in top_df.iterrows():
                    top_items.append({
                        'item': str(r.get(item_col)) if item_col in merged.columns else None,
                        'on_hand': float(r.get(on_hand_col)) if on_hand_col in merged.columns and pd.notna(r.get(on_hand_col)) else None,
                        'value': float(r.get(value_col)) if pd.notna(r.get(value_col)) else None,
                        'coverage': float(r.get('coverage_months')) if pd.notna(r.get('coverage_months')) else None
                    })
    except Exception:
        # Non-fatal: leave distributions empty
        pass

    return jsonify({
        'month': month,
        'cards': cards,
        'cost_breakdown': inv_resp.get('cost_breakdown', []),
        'total_sales_amt': inv_resp.get('total_sales_amt', 0.0),
        'coverage_distribution': coverage_distribution,
        'top_items': top_items
    })


@app.route('/api/demo-ebit', methods=['POST'])
def demo_ebit():
    """Return cost breakdown suitable for bubble chart, accepts same filters as /api/chart-data via JSON payload."""
    payload = request.json or {}
    # reuse chart_data filtering logic to get a subset of sales
    if STORE['df_store'] is None:
        return jsonify({'error': 'no data'}), 400
    df = STORE['df_store'].copy()
    start = payload.get('start')
    end = payload.get('end')
    regions = payload.get('regions', [])
    countries = payload.get('countries', [])
    products = payload.get('products', [])

    if start:
        df = df[df['Date'] >= start]
    if end:
        df = df[df['Date'] <= end]
    if regions and 'ALL Region' not in regions:
        df = df[df['Region'].isin(regions)]
    if countries and 'ALL Country' not in countries:
        df = df[df['Country'].isin(countries)]
    if products and 'ALL Product Type' not in products:
        df = df[df['Product Type'].isin(products)]

    breakdown_df, total_sales_amt = compute_cost_breakdown(df)
    if breakdown_df.empty:
        return jsonify({'error': 'no breakdown available'}), 400
    res = breakdown_df[['Category', 'Percentage', 'Absolute Value']].to_dict(orient='records')
    return jsonify({'breakdown': res, 'total_sales_amt': total_sales_amt})


@app.route('/api/upload', methods=['POST'])
def upload_files():
    try:
        # accept multiple files under 'files'
        files = request.files.getlist('files')
        dfs = []
        for f in files:
            filename = f.filename.lower()
            content = f.read()
            # try reading excel
            try:
                xls = pd.read_excel(io.BytesIO(content), sheet_name=None)
                df = pd.concat(xls.values(), ignore_index=True)
            except Exception:
                # try csv
                try:
                    df = pd.read_csv(io.StringIO(content.decode('utf-8')))
                except Exception:
                    return jsonify({"error": f"Cannot parse file {f.filename}"}), 400

            if 'inventory' in filename:
                STORE['inventory'] = normalize_inventory_df(df)
            elif 'balance' in filename:
                STORE['balance'] = df
                if 'year_month' in STORE['balance'].columns:
                    STORE['balance']['year_month'] = pd.to_datetime(STORE['balance']['year_month'], errors='coerce').dt.strftime('%Y-%m')
            elif 'pads' in filename:
                STORE['pads'] = df
            elif 'disc' in filename:
                STORE['disc'] = df
            else:
                # assume sales / transactions
                cleaned = clean_data(df)
                dfs.append(cleaned)

        if dfs:
            STORE['df_store'] = pd.concat(dfs, ignore_index=True)
        # respond with available dataset summary
        resp = {
            'has_sales': STORE['df_store'] is not None,
            'has_inventory': STORE['inventory'] is not None,
            'rows_sales': 0 if STORE['df_store'] is None else len(STORE['df_store'])
        }
        return jsonify(resp)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/filters', methods=['GET'])
def get_filters():
    if STORE['df_store'] is None:
        return jsonify({'error': 'no sales data uploaded'}), 400
    df = STORE['df_store']
    date_options = sorted(df['Date'].dropna().unique().tolist())
    region_options = ['ALL Region'] + sorted(df['Region'].dropna().unique().tolist()) if 'Region' in df.columns else []
    country_options = ['ALL Country'] + sorted(df['Country'].dropna().unique().tolist()) if 'Country' in df.columns else []
    product_options = ['ALL Product Type'] + sorted(df['Product Type'].dropna().unique().tolist()) if 'Product Type' in df.columns else []
    item_group_options = ['ALL Item Group'] + sorted(df['Item - Item Group Full Name'].dropna().unique().tolist()) if 'Item - Item Group Full Name' in df.columns else []
    customer_options = ['ALL Customer'] + sorted(df['Customer - Name'].dropna().unique().tolist()) if 'Customer - Name' in df.columns else []
    item_code_options = ['ALL Item Code'] + sorted(df['Item - Code'].dropna().unique().tolist()) if 'Item - Code' in df.columns else []

    return jsonify({
        'dates': date_options,
        'regions': region_options,
        'countries': country_options,
        'products': product_options,
        'item_groups': item_group_options,
        'customers': customer_options,
        'item_codes': item_code_options
    })


@app.route('/api/chart-data', methods=['POST'])
def chart_data():
    '''Expect JSON with filter spec: {start, end, regions, countries, products, item_groups, customers, item_codes, currency}
       Return grouped timeseries for charts.'''
    payload = request.json or {}
    if STORE['df_store'] is None:
        return jsonify({'error': 'no data'}), 400
    df = STORE['df_store'].copy()
    start = payload.get('start')
    end = payload.get('end')
    regions = payload.get('regions', [])
    countries = payload.get('countries', [])
    products = payload.get('products', [])
    item_groups = payload.get('item_groups', [])
    customers = payload.get('customers', [])
    item_codes = payload.get('item_codes', [])
    aggregation = payload.get('aggregation', 'monthly')
    currency = payload.get('currency', 'RMB')

    # apply filters
    if start:
        df = df[df['Date'] >= start]
    if end:
        df = df[df['Date'] <= end]
    if regions and 'ALL Region' not in regions:
        df = df[df['Region'].isin(regions)]
    if countries and 'ALL Country' not in countries:
        df = df[df['Country'].isin(countries)]
    if products and 'ALL Product Type' not in products:
        df = df[df['Product Type'].isin(products)]
    if item_groups and 'ALL Item Group' not in item_groups:
        df = df[df['Item - Item Group Full Name'].isin(item_groups)]
    if customers and 'ALL Customer' not in customers:
        df = df[df['Customer - Name'].isin(customers)]
    if item_codes and 'ALL Item Code' not in item_codes:
        df = df[df['Item - Code'].isin(item_codes)]

    # currency adjustments: use same simple logic as Dash
    if 'RMB_rate' in df.columns and currency == 'EUR':
        df['Adj Sales Amt'] = df['Total Sales Amt'] / df['RMB_rate']
        df['Adj EBIT'] = df['EBIT'] / df['RMB_rate']
        df['Adj Net Sales'] = df['Net Sales'] / df['RMB_rate']
    elif 'RMB_rate' in df.columns and 'USD_rate' in df.columns and currency == 'USD':
        df['Adj Sales Amt'] = (df['Total Sales Amt'] / df['RMB_rate']) * df['USD_rate']
        df['Adj EBIT'] = (df['EBIT'] / df['RMB_rate']) * df['USD_rate']
        df['Adj Net Sales'] = (df['Net Sales'] / df['RMB_rate']) * df['USD_rate']
    else:
        # default RMB
        df['Adj Sales Amt'] = df['Total Sales Amt'] if 'Total Sales Amt' in df.columns else 0
        df['Adj EBIT'] = df['EBIT'] if 'EBIT' in df.columns else 0
        df['Adj Net Sales'] = df['Net Sales'] if 'Net Sales' in df.columns else 0

    # group by Date (monthly) or Year (yearly)
    if aggregation == 'yearly':
        df['Year'] = pd.to_datetime(df['Date']).dt.year
        g = df.groupby('Year').agg({
            'Adj Sales Amt': 'sum',
            'Sales Qua': 'sum',
            'Adj EBIT': 'sum',
            'Adj Net Sales': 'sum'
        }).reset_index().sort_values('Year')
        g['Unit Price'] = g['Adj Sales Amt'] / g['Sales Qua'].replace(0, pd.NA)
        g['EBIT %'] = (g['Adj EBIT'] / g['Adj Net Sales']).replace([pd.NA, pd.inf, -pd.inf], pd.NA)
        # convert to lists
        return jsonify({'x': g['Year'].astype(str).tolist(),
                        'adj_sales': g['Adj Sales Amt'].fillna(0).tolist(),
                        'sales_qua': g['Sales Qua'].fillna(0).tolist(),
                        'unit_price': g['Unit Price'].fillna(0).tolist(),
                        'ebit_pct': g['EBIT %'].fillna(0).tolist()})
    else:
        df['Date'] = pd.to_datetime(df['Date'])
        g = df.groupby('Date').agg({
            'Adj Sales Amt': 'sum',
            'Sales Qua': 'sum',
            'Adj EBIT': 'sum',
            'Adj Net Sales': 'sum'
        }).reset_index().sort_values('Date')
        g['Unit Price'] = g['Adj Sales Amt'] / g['Sales Qua'].replace(0, pd.NA)
        g['EBIT %'] = (g['Adj EBIT'] / g['Adj Net Sales']).replace([pd.NA, pd.inf, -pd.inf], pd.NA)
        return jsonify({'x': g['Date'].dt.strftime('%Y-%m-%d').tolist(),
                        'adj_sales': g['Adj Sales Amt'].fillna(0).tolist(),
                        'sales_qua': g['Sales Qua'].fillna(0).tolist(),
                        'unit_price': g['Unit Price'].fillna(0).tolist(),
                        'ebit_pct': g['EBIT %'].fillna(0).tolist()})


@app.route('/api/inventory', methods=['GET'])
def inventory():
    month = request.args.get('month')
    source = request.args.get('source', 'Total')
    if STORE['inventory'] is None:
        return jsonify({'error': 'no inventory uploaded'}), 400
    inv = STORE['inventory'].copy()

    # current and previous month selection
    if 'year_month' in inv.columns and month:
        inv_curr = inv[inv['year_month'] == month].copy()
        try:
            prev_month = (pd.to_datetime(month + '-01') - pd.DateOffset(months=1)).strftime('%Y-%m')
        except Exception:
            prev_month = None
        inv_prev = inv[inv['year_month'] == prev_month] if prev_month is not None else pd.DataFrame()
    else:
        inv_curr = inv.copy()
        inv_prev = pd.DataFrame()
        prev_month = None

    # totals
    if 'On-hand' in inv_curr.columns and 'Inventory value' in inv_curr.columns:
        total_qty = float(inv_curr['On-hand'].sum())
        total_val = float(inv_curr['Inventory value'].sum())
    else:
        total_qty = float(inv_curr.shape[0])
        total_val = 0.0

    if not inv_prev.empty and 'On-hand' in inv_prev.columns and 'Inventory value' in inv_prev.columns:
        prev_qty = float(inv_prev['On-hand'].sum())
        prev_val = float(inv_prev['Inventory value'].sum())
    else:
        prev_qty = 0.0
        prev_val = 0.0

    def pct_change(curr, prev):
        try:
            if prev == 0:
                return None
            return (curr - prev) / prev
        except Exception:
            return None

    qty_mom = pct_change(total_qty, prev_qty)
    val_mom = pct_change(total_val, prev_val)

    # Heuristic: identify Pads / Disc by Item group or item number
    pads_qty = pads_val = disc_qty = disc_val = 0.0
    if STORE.get('pads') is not None:
        pads_df = STORE['pads']
        if 'year_month' in pads_df.columns and month:
            pads_sel = pads_df[pads_df['year_month'] == month]
        else:
            pads_sel = pads_df
        # attempt common columns
        pads_qty = float(pads_sel.get('On-hand', pd.Series([0])).sum())
        pads_val = float(pads_sel.get('Inventory value', pd.Series([0])).sum())

    if STORE.get('disc') is not None:
        disc_df = STORE['disc']
        if 'year_month' in disc_df.columns and month:
            disc_sel = disc_df[disc_df['year_month'] == month]
        else:
            disc_sel = disc_df
        disc_qty = float(disc_sel.get('On-hand', pd.Series([0])).sum())
        disc_val = float(disc_sel.get('Inventory value', pd.Series([0])).sum())

    # fallback heuristics when pads/disc separate files missing: try group name or item number pattern
    if pads_val == 0 and 'Item - Item Group Full Name' in inv_curr.columns:
        mask_pad = inv_curr['Item - Item Group Full Name'].str.contains('PAD', case=False, na=False)
        pads_qty = float(inv_curr.loc[mask_pad, 'On-hand'].sum()) if 'On-hand' in inv_curr.columns else float(inv_curr.loc[mask_pad].shape[0])
        pads_val = float(inv_curr.loc[mask_pad, 'Inventory value'].sum()) if 'Inventory value' in inv_curr.columns else 0.0

    if disc_val == 0 and 'Item - Item Group Full Name' in inv_curr.columns:
        mask_disc = inv_curr['Item - Item Group Full Name'].str.contains('DISC', case=False, na=False)
        disc_qty = float(inv_curr.loc[mask_disc, 'On-hand'].sum()) if 'On-hand' in inv_curr.columns else float(inv_curr.loc[mask_disc].shape[0])
        disc_val = float(inv_curr.loc[mask_disc, 'Inventory value'].sum()) if 'Inventory value' in inv_curr.columns else 0.0

    # compute cost breakdown from sales data for the same month if available
    breakdown = []
    total_sales_amt = 0.0
    if STORE.get('df_store') is not None and not STORE['df_store'].empty:
        sales = STORE['df_store'].copy()
        # create year_month on sales
        if 'Date' in sales.columns:
            sales['year_month'] = pd.to_datetime(sales['Date'], errors='coerce').dt.strftime('%Y-%m')
        if month:
            sales_sel = sales[sales['year_month'] == month]
        else:
            sales_sel = sales
        df_break, total_sales_amt = compute_cost_breakdown(sales_sel)
        if not df_break.empty:
            breakdown = df_break[['Category', 'Percentage', 'Absolute Value']].to_dict(orient='records')

    resp = {
        'month': month,
        'prev_month': prev_month,
        'total_qty': total_qty,
        'total_value': total_val,
        'qty_mom': qty_mom,
        'val_mom': val_mom,
        'pads_qty': pads_qty,
        'pads_value': pads_val,
        'disc_qty': disc_qty,
        'disc_value': disc_val,
        'cost_breakdown': breakdown,
        'total_sales_amt': total_sales_amt
    }
    return jsonify(resp)


if __name__ == '__main__':
    # Attempt to load data from backend/data on startup
    try:
        load_data_from_disk()
    except Exception:
        pass
    app.run(debug=True, port=5001)
