import dash
from dash import dcc, html, Output, Input, State, ctx, ALL
import dash_bootstrap_components as dbc
import pandas as pd
import io
import base64
import plotly.express as px
import uuid
import plotly.graph_objects as go
from dash import MATCH
import math
import numpy as np
from millify import millify

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

from dash import html, dcc, callback_context, Output, Input
import dash


def get_evenly_spaced_labels(series, count=6):
    n = len(series)
    if n <= count:
        indices = list(range(n))
    else:
        step = n / count
        indices = [int(round(i * step)) for i in range(count)]
        indices = sorted(set(min(i, n - 1) for i in indices))
    labels = []
    for i, val in enumerate(series):
        if i in indices:
            # 小于1000就完整显示，否则 millify
            if val < 1000:
                labels.append(f"{val:,.0f}")
            else:
                labels.append(millify(val, precision=0))
        else:
            labels.append("")
    return labels


# ✅ 1. 封装 Sales 页面内容
def sales_page_layout():
    return html.Div([
        html.Div(
            className='graph-row',
            children=[
                html.Div(
                    className='card-container',
                    id='total-sales-card',
                    style={'width': '400px', 'height': '355px'},
                    children=[
                        html.Div(className='card-header', children="Gross Sales Amount"),
                        dcc.Graph(id='total-sales-line', style={'width': '100%', 'height': '100%'})
                    ]
                ),
                html.Div(
                    className='card-container',
                    id='sales-qua-card',
                    style={'width': '400px', 'height': '355px'},
                    children=[
                        html.Div(className='card-header', children="Sales Quantity"),
                        dcc.Graph(id='sales-qua-line', style={'width': '100%', 'height': '100%'})
                    ]
                ),
                html.Div(
                    className='card-container',
                    id='unit-price-card',
                    style={'width': '400px', 'height': '355px'},
                    children=[
                        html.Div(className='card-header', children="Unit Price"),
                        dcc.Graph(id='unit-price-line', style={'width': '100%', 'height': '100%'})
                    ]
                )
            ],
            style={
                'display': 'flex',
                'flex-wrap': 'wrap',
                'justify-content': 'space-around',
                'gap': '20px',
                'padding': '20px'
            }
        ),
        html.Div([
            html.Div(
                className='card-container',
                id='cost-breakdown-card',
                style={'min-width': '400px', 'width': 'auto', 'height': '350px'},
                children=[
                    html.Div(
                        className='card-header',
                        children="Cost Breakdown",
                        style={
                            'font-family': 'Bahnschrift, sans-serif',
                            'margin-left': '45px'
                        }
                    ),
                    dcc.Graph(id='demo-ebit-figure'),
                    html.Div(id='dynamic-bubble-graph-container')
                ]
            )
        ]),
        html.Div(id='date-selectors'),
        html.Div([
            html.Div([
                html.Label("", style={
                    'font-family': 'Bahnschrift, sans-serif',
                    'margin-right': '10px'
                }),
                dcc.RadioItems(
                    id='aggregation-mode',
                    options=[
                        {'label': 'Monthly', 'value': 'monthly'},
                        {'label': 'Yearly', 'value': 'yearly'}
                    ],
                    value='monthly',
                    labelStyle={'display': 'inline-block', 'margin-right': '10px'}
                )
            ], style={'position': 'absolute', 'top': '90px', 'left': '10px', 'color': 'black'}),

            html.Div([
                html.Label("", style={
                    'font-family': 'Bahnschrift, sans-serif',
                    'margin-right': '10px'
                }),
                dcc.RadioItems(
                    id='currency-selector',
                    options=[
                        {'label': 'RMB ¥', 'value': 'RMB'},
                        {'label': 'EUR €', 'value': 'EUR'},
                        {'label': 'USD $', 'value': 'USD'}
                    ],
                    value='RMB',
                    labelStyle={'display': 'inline-block', 'margin-right': '10px'}
                )
            ], style={'position': 'absolute', 'top': '60px', 'left': '10px', 'color': 'black'}),
            html.Div([
                dcc.Checklist(
                    id='revenlia-toggle',
                    options=[{'label': 'Include Revelia', 'value': 'include'}],
                    value=['include'],
                    labelStyle={'display': 'inline-block', 'margin-right': '10px'},
                    style={'font-family': 'Bahnschrift, sans-serif', 'font-size': '13px'}
                )
            ], style={'position': 'absolute', 'top': '117px', 'left': '172px', 'color': 'black'}),
            html.Div([
                html.Button('➕', id='add-filter', n_clicks=0, className='icon-button')
            ], style={'position': 'absolute', 'top': '135px', 'left': '170px'})
        ]),

        html.Div(id='horizontal-line', style={
            'position': 'absolute',
            'top': '180px',
            'left': '123px',
            'width': '35px',
            'border': '2px solid black',
            'background-color': 'black'
        }),
        html.Div(
            className='card-container',
            id='ebit-percent-card',
            style={'width': '400px', 'height': '350px'},
            children=[
                html.Div(className='card-header', children="EBIT %"),
                dcc.Graph(id='ebit-percent-line', style={'width': '100%', 'height': '100%'}),
                html.Div(id='filter-labels-container')
            ]
        ),
        html.Div(
            "Filter 1",
            style={
                'font-weight': 'bold',
                'color': 'black',
                'font-family': 'Bahnschrift, sans-serif',
                'font-size': '16px',
                'position': 'absolute',
                'left': '10px',
                'top': '140px'
            }
        ),
        html.Div(id='filter-labels-container', style={'position': 'relative'}),
        html.Div(id='horizontal-line-container')
    ])


def cost_page_layout():
    if inventory_df.empty:
        return html.Div("❌ Inventory 数据为空")

    inventory_df['year_month'] = pd.to_datetime(inventory_df['year_month'], errors='coerce').dt.strftime('%Y-%m')
    all_months = sorted(inventory_df['year_month'].dropna().unique())
    month_options = [{"label": m, "value": m} for m in all_months]

    return html.Div([
        html.Div(
            children=[
                html.Div("Inventory Category:"),
                html.Ul([
                    html.Li([
                        html.Span("Quality Location:", style={"color": "red"}),
                        " Refers to the 'NC' and 'QC' Warehouse Location."
                    ]),
                    html.Li([
                        html.Span("Obsolete:", style={"color": "red"}),
                        " Items filtered out by cross-referencing against the Obsolete table."
                    ]),
                    html.Li([
                        html.Span("New Entry:", style={"color": "red"}),
                        " Any record whose created date is on or after January 1, 2024."
                    ]),
                    html.Li([
                        html.Span("Slow Moving:", style={"color": "red"}),
                        " Items whose on-hand quantity exceeds two years of sales but is less than four years."
                    ]),
                    html.Li([
                        html.Span("Excessive:", style={"color": "red"}),
                        " Items whose on-hand quantity exceeds four years of sales."
                    ]),
                    html.Li([
                        html.Span("Normal Goods:", style={"color": "red"}),
                        " Items whose on-hand quantity is less than two years of sales."
                    ]),
                    html.Li([
                        html.Span("Coverage:", style={"color": "red"}),
                        "It calculated as on-hand inventory quantity divided by average monthly sales over past 12months."
                    ])
                ])
            ],
            id="cost-note"
        ),
        html.Div([
            html.Label("Start Date:", style={"fontWeight": "bold", "color": "black"}),
            dcc.Dropdown(
                id="inv-start-date",
                options=[{"label": d, "value": d} for d in all_months],
                value=all_months[0] if all_months else None
            )
        ], id="start-date-container", className="dropdown-white-rounded",
            style={"position": "absolute", "top": "120px", "left": "10px"}),

        html.Div([
            html.Label("End Date:", style={"fontWeight": "bold", "color": "black"}),
            dcc.Dropdown(
                id="inv-end-date",
                options=[{"label": d, "value": d} for d in all_months],
                value=all_months[-1] if all_months else None
            )
        ], id="end-date-container", className="dropdown-white-rounded",
            style={"position": "absolute", "top": "180px", "left": "10px"}),

        html.Div([
            html.Label("Category:", style={"fontWeight": "bold", "color": "black"}),
            dcc.Dropdown(
                id="inv-category",
                options=[
                    {"label": "Total Inventory", "value": "Total Inventory"},
                    {"label": "Pads", "value": "Pads"},
                    {"label": "Disc", "value": "Disc"}
                ],
                value="Total Inventory"
            )
        ], id="category-container", className="dropdown-white-rounded",
            style={"position": "absolute", "top": "240px", "left": "10px"}),
        html.Div([
            html.Label("Inventory Balance Overview", style={"fontWeight": "bold", "color": "black"}),
            dcc.Dropdown(
                id="inventory-month-selector",
                options=month_options,
                placeholder="Select..."
            )
        ], id="inventory-month-container"),
        html.Div([
            dcc.RadioItems(
                id='pie-source-selector',
                options=[
                    {'label': 'Overall', 'value': 'Total'},
                    {'label': 'Pads', 'value': 'Pads'},
                    {'label': 'Disc', 'value': 'Disc'}
                ],
                value='Total',
                labelStyle={'display': 'block', 'marginRight': '12px', 'color': 'black'},
                inputStyle={'marginRight': '4px'}
            )
        ], style={'marginBottom': '20px'}),

        html.Div(id="inventory-cards", style={"display": "flex", "gap": "10px", "flexWrap": "wrap"}),
        html.Div([
            html.Div("Inventory Value & DIO", className="card-header"),
            html.Div(
                dcc.Graph(
                    id="dio-inventory-graph",
                    config={"displayModeBar": False}
                )
            )
        ], className="inv-card-container", style={
            "background": "white",
            "border": "1px solid white",
            "borderRadius": "16px",
            "backdropFilter": "blur(4px)",
            "margin": "20px",
            "padding": "0px",
            "transition": "transform 0.3s ease",
            "marginTop": "-13px",
            'width': '760px',
            'height': '550px',
            "position": "absolute",
            "top": "180px",
            "left": "265px"
        }),
        html.Div([
            dcc.RadioItems(
                id="normal-source-selector",
                options=[
                    {"label": "Overall", "value": "Overall"},
                    {"label": "Pads", "value": "Pads"},  # 合并后的选项
                    {"label": "Disc", "value": "Disc"}
                ],
                value="Overall",
                labelStyle={
                    "display": "block",
                    "marginRight": "12px",
                    "color": "black"
                },
                inputStyle={"marginRight": "4px"},
                style={"marginBottom": "8px", "marginLeft": "12px"}
            ),

            # 卡片（保持原样）
            html.Div([
                html.Div("Normal Inventory Coverage Breakdown", className="card-header"),
                html.Div(id="normal-coverage-container", className="inv-card narrow-card")
            ], className="inv-card-container", style={
                "width": "450px",
                "height": "280px",
                "position": "absolute",
                "top": "450px",
                "left": "1040px"
            })
        ])

    ])


df_store = pd.DataFrame()
inventory_df = pd.DataFrame()
balance_df = pd.DataFrame()
pads_df = pd.DataFrame()
disc_df = pd.DataFrame()


# ========== Layout ========== #
app.layout = html.Div([
    # ✅ 灰色 Sidebar
    html.Div(
        id='sidebar-background-color',
        style={
            'position': 'fixed',
            'top': '0',
            'left': '0',
            'width': '400px',
            'height': '100vh',
            'backgroundColor': '#D3D3D3',
            'zIndex': '0',
            'display': 'block',  # ✅ 测试时打开
            'overflowY': 'auto'
        }
    ),

    # ✅ 页面主体，禁用页面滚动
    html.Div(
        style={
            'minHeight': '100vh',
            'position': 'relative',
            'overflow': 'hidden'  # ✅ 关键点：阻止主页面滚动
        },
        children=[
            dcc.Upload(
                id='upload-data',
                children=html.Button(
                    html.Img(src=app.get_asset_url("Logo.png"), className='upload-logo'),
                    style={
                        'border': 'none',
                        'background': 'none',
                        'cursor': 'pointer',
                        'padding': '0',
                        'position': 'absolute',
                        'top': '-30px',
                        'left': '35px'
                    }
                ),
                multiple=True
            ),
            html.Img(
                id='background-image',
                src='assets/Logo2.jpg',
                style={
                    'position': 'absolute',
                    'top': '50%',
                    'left': '50%',
                    'transform': 'translate(-50%, -50%)',
                    'width': '60%',
                    'border-radius': '20px',
                    'zIndex': '0'
                }
            ),
            html.Div(id='main-content', style={'position': 'relative', 'zIndex': '1'}),
            dbc.Offcanvas(
                id="sidebar",
                is_open=False,
                children=[html.Div(id='sidebar-content')],
                style={'background-color': 'rgba(0,0,0,0.4)', 'color': 'White'}
            ),
            dcc.Store(id='ebit-position-store', data='default'),
            dcc.Store(id='filter-count-store', data=0)

        ]
    )
]
)


# ========== Data Cleaning ========== #
def clean_data(df):
    df.columns = df.columns.str.strip()
    if 'Year' in df.columns and 'Month' in df.columns:
        df['Date'] = pd.to_datetime(
            df['Year'].astype(str) + '-' + df['Month'].astype(str).apply(lambda x: x.zfill(2)),
            format='%Y-%m'
        ).dt.strftime('%Y-%m')
        df = df.drop(columns=['Year', 'Month'])
    string_cols = ['Region', 'Sub Region', 'Country', 'Product Type',
                   'Item - Item Group Full Name', 'Customer - Name', 'Item - Code']
    for col in df.columns:
        if col in string_cols:
            df[col] = df[col].astype(str)
        elif col != 'Date':
            df[col] = pd.to_numeric(df[col], errors='coerce').where(pd.notnull(df[col]), None)
    cols = ['Date'] + [col for col in df.columns if col != 'Date']
    if 'Item - Item Group Full Name' in df.columns:
        df = df[df['Item - Item Group Full Name'] != '2900 - Packaging']
    return df[cols]


def calculate_mom(current, previous):
    if previous in [0, None] or pd.isna(previous):
        return None
    return (current - previous) / previous


@app.callback(
    [Output('main-content', 'children'),
     Output('sidebar-content', 'children'),
     Output('background-image', 'style')],
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    State('background-image', 'style')
)
def display_main_content(contents, filenames, img_style):
    global df_store, inventory_df, balance_df, pads_df, disc_df

    if contents is None:
        img_style['display'] = 'block'
        return None, None, img_style

    img_style['display'] = 'none'

    contents = contents if isinstance(contents, list) else [contents]
    filenames = filenames if isinstance(filenames, list) else [filenames]

    all_dfs = []
    inventory_df = pd.DataFrame()

    for content, filename in zip(contents, filenames):
        content_type, content_string = content.split(',')
        decoded = base64.b64decode(content_string)

        if 'inventory' in filename.lower():
            xls = pd.read_excel(io.BytesIO(decoded), sheet_name=None)
            df = pd.concat(xls.values(), ignore_index=True)

            inventory_df = df
            if 'year_month' in inventory_df.columns:
                inventory_df['year_month'] = pd.to_datetime(
                    inventory_df['year_month'], errors='coerce'
                ).dt.strftime('%Y-%m')
            if 'Item number' in inventory_df.columns:
                inventory_df['Item number'] = inventory_df['Item number'].astype(str).str.upper().str.strip()
        elif 'balance' in filename.lower():
            global balance_df

            xls = pd.read_excel(io.BytesIO(decoded), sheet_name=None)
            df = pd.concat(xls.values(), ignore_index=True)

            balance_df = df

            if 'year_month' in balance_df.columns:
                balance_df['year_month'] = pd.to_datetime(
                    balance_df['year_month'], errors='coerce'
                ).dt.strftime('%Y-%m')



        elif 'pads' in filename.lower():

            global pads_df

            xls_sheets = pd.read_excel(io.BytesIO(decoded), sheet_name=None)

            pads_df = pd.concat(xls_sheets.values(), ignore_index=True)


        elif 'disc' in filename.lower():

            global disc_df

            xls_sheets = pd.read_excel(io.BytesIO(decoded), sheet_name=None)

            disc_df = pd.concat(xls_sheets.values(), ignore_index=True)


        else:
            df = pd.read_excel(io.BytesIO(decoded))
            df_cleaned = clean_data(df)
            if 'Country' in df_cleaned.columns:
                df_cleaned['Country'] = df_cleaned['Country'].astype(str).str.upper()
            if 'Product Type' in df_cleaned.columns:
                df_cleaned['Product Type'] = df_cleaned['Product Type'].astype(str).str.upper()

            if 'Item - Item Group Full Name' in df_cleaned.columns:
                df_cleaned['Item - Item Group Full Name'] = df_cleaned['Item - Item Group Full Name'].astype(
                    str).str.upper()

            if 'Customer - Name' in df_cleaned.columns:
                df_cleaned['Customer - Name'] = df_cleaned['Customer - Name'].astype(str).str.upper()
            all_dfs.append(df_cleaned)

    df_store = pd.concat(all_dfs, ignore_index=True)

    year_options = sorted(df_store['Date'].apply(lambda x: x.split('-')[0]).unique())
    sidebar_content = [
        html.Div(id='dynamic-bubble-filters')
    ]
    main_content = html.Div([
        html.Div([
            html.Button("Sales", id='sales-btn', n_clicks=0, className='tab-button'),
            html.Button("Inventory", id='cost-btn', n_clicks=0, className='tab-button')
        ]),
        html.Div([
            html.Div(id="sales-page", children=sales_page_layout(), style={"display": "block"}),
            html.Div(id="cost-page", children=cost_page_layout(), style={"display": "none"}),
        ])
    ])
    return main_content, sidebar_content, img_style


# ========== Handle Upload ==========
#处理上传文件
@app.callback(
    Output('date-selectors', 'children'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename')
)
def handle_upload(contents, filenames):
    global df_store

@app.callback(
    Output('date-selectors', 'children'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename')
)
def handle_upload(contents, filenames):
    if contents is None or df_store.empty:
        return None

    # 数据清洗：确保 'year_month' 列被格式化为 '%Y-%m'
    df_store['year_month'] = pd.to_datetime(df_store['year_month'], errors='coerce').dt.strftime('%Y-%m')

    # 确保 'year_month' 列没有空值
    date_options = sorted(df_store['year_month'].dropna().unique())

    if not date_options:
        return None

    print(f"Date options: {date_options}")  # 打印日期选项

    return html.Div([
        dcc.Dropdown(
            id={'type': 'start-date', 'index': 'default'},
            options=[{'label': d, 'value': d} for d in date_options],
            value=date_options[0],  # 默认选择第一个日期
            className='start-date-default',
            placeholder="Start"
        ),
        dcc.Dropdown(
            id={'type': 'end-date', 'index': 'default'},
            options=[{'label': d, 'value': d} for d in date_options],
            value=date_options[-1],  # 默认选择最后一个日期
            className='end-date-default',
            placeholder="End"
        )
    ])

    
    if contents is None or df_store.empty:
        return None


    date_options = sorted(df_store['Date'].unique())
    region_options = ['ALL Region'] + sorted(df_store['Region'].dropna().unique())
    country_options = ['ALL Country'] + sorted(df_store['Country'].dropna().unique())
    product_options = ['ALL Product Type'] + sorted(df_store['Product Type'].dropna().unique())
    item_group_options = ['ALL Item Group'] + sorted(df_store['Item - Item Group Full Name'].dropna().unique())
    customer_name_options = ['ALL Customer'] + sorted(df_store['Customer - Name'].dropna().unique())
    item_code_options = ['ALL Item Code'] + sorted(df_store['Item - Code'].dropna().unique())

    return html.Div([
        dcc.Dropdown(
            id={'type': 'start-date', 'index': 'default'},
            options=[{'label': d, 'value': d} for d in date_options],
            value=date_options[0],
            className='start-date-default',
            placeholder="Start"
        ),
        dcc.Dropdown(
            id={'type': 'end-date', 'index': 'default'},
            options=[{'label': d, 'value': d} for d in date_options],
            value=date_options[-1],
            className='end-date-default',
            placeholder="End"
        ),
        html.Div(id='region-container', children=[
            dcc.Dropdown(
                id={'type': 'dynamic-region', 'index': 'default'},
                options=[{'label': r, 'value': r} for r in region_options],
                value=['ALL Region'],
                multi=True,
                className='transparent-dropdown',
                style={'color': 'Black'}
            )
        ]),
        html.Div(id='country-container', children=[
            dcc.Dropdown(
                id={'type': 'dynamic-country', 'index': 'default'},
                options=[{'label': c, 'value': c} for c in country_options],
                value=['ALL Country'],
                multi=True,
                className='transparent-dropdown'
            )
        ]),
        html.Div(id='product-type-container', children=[
            dcc.Dropdown(
                id={'type': 'dynamic-product-type', 'index': 'default'},
                options=[{'label': p, 'value': p} for p in product_options],
                value=['ALL Product Type'],
                multi=True,
                className='transparent-dropdown'
            )
        ]),
        html.Div(id='dynamic-filters'),
        html.Div(id='item-group-container', children=[
            dcc.Dropdown(
                id={'type': 'dynamic-item-group', 'index': 'default'},
                options=[{'label': p, 'value': p} for p in item_group_options],
                value=['ALL Item Group'],
                multi=True,
                className='transparent-dropdown'
            )
        ]),
        html.Div(id='customer-name-container', children=[
            dcc.Dropdown(
                id={'type': 'dynamic-customer-name', 'index': 'default'},
                options=[{'label': c, 'value': c} for c in customer_name_options],
                value=['ALL Customer'],
                multi=True,
                className='transparent-dropdown'
            )
        ]),
        html.Div(id='item-code-container', children=[
            dcc.Dropdown(
                id={'type': 'dynamic-item-code', 'index': 'default'},
                options=[{'label': c, 'value': c} for c in item_code_options],
                value=['ALL Item Code'],
                multi=True,
                className='transparent-dropdown'
            )
        ])
    ])


# ========== Manage Filters ==========


# ========== Update Charts ==========
@app.callback(
    [
        Output('total-sales-line', 'figure'),
        Output('sales-qua-line', 'figure'),
        Output('unit-price-line', 'figure'),
        Output('ebit-percent-line', 'figure')
    ],
    [
        Input({'type': 'start-date', 'index': ALL}, 'value'),
        Input({'type': 'end-date', 'index': ALL}, 'value'),
        Input({'type': 'dynamic-region', 'index': ALL}, 'value'),
        Input({'type': 'dynamic-country', 'index': ALL}, 'value'),
        Input({'type': 'dynamic-product-type', 'index': ALL}, 'value'),
        Input('aggregation-mode', 'value'),
        Input('currency-selector', 'value'),
        Input({'type': 'dynamic-item-group', 'index': ALL}, 'value'),
        Input({'type': 'dynamic-customer-name', 'index': ALL}, 'value'),
        Input({'type': 'dynamic-item-code', 'index': ALL}, 'value'),
        Input('revenlia-toggle', 'value')

    ],
    prevent_initial_call=True
)
def update_charts(start_dates, end_dates, regions_list, countries_list, products_list,
                  aggregation_mode, currency, item_groups_list, customers_list, item_codes_list,
                  revenlia_toggle):
    if df_store.empty or 'Total Sales Amt' not in df_store.columns or 'Sales Qua' not in df_store.columns \
            or 'EBIT' not in df_store.columns or 'Net Sales' not in df_store.columns:
        return {}, {}, {}, {}

    if currency == 'EUR':
        y_label_sales = 'Gross Sales Amount (€)'
        y_label_price = 'Unit Price (€)'
        y_label_ebit = 'EBIT % (€)'
        df_store['Adj Sales Amt'] = df_store['Total Sales Amt'] / df_store['RMB_rate']
        df_store['Adj EBIT'] = df_store['EBIT'] / df_store['RMB_rate']
        df_store['Adj Net Sales'] = df_store['Net Sales'] / df_store['RMB_rate']
    elif currency == 'USD':
        y_label_sales = 'Gross Sales Amount ($)'
        y_label_price = 'Unit Price ($)'
        y_label_ebit = 'EBIT % ($)'
        df_store['Adj Sales Amt'] = (df_store['Total Sales Amt'] / df_store['RMB_rate']) * df_store['USD_rate']
        df_store['Adj EBIT'] = (df_store['EBIT'] / df_store['RMB_rate']) * df_store['USD_rate']
        df_store['Adj Net Sales'] = (df_store['Net Sales'] / df_store['RMB_rate']) * df_store['USD_rate']
    else:
        y_label_sales = 'Gross Sales Amount (¥)'
        y_label_price = 'Unit Price (¥)'
        y_label_ebit = 'EBIT % (¥)'
        df_store['Adj Sales Amt'] = df_store['Total Sales Amt']
        df_store['Adj EBIT'] = df_store['EBIT']
        df_store['Adj Net Sales'] = df_store['Net Sales']

    fig_sales, fig_sales_qua, fig_unit_price, fig_ebit = go.Figure(), go.Figure(), go.Figure(), go.Figure()
    colors = ['red', 'green', 'purple', 'blue']

    point_counts = []
    all_years = []
    grouped_data_list = []

    for idx, (start, end, regions, countries, products, item_groups, customers, item_codes) in enumerate(
            zip(start_dates, end_dates, regions_list, countries_list, products_list,
                item_groups_list, customers_list, item_codes_list)
    ):
        temp = df_store.copy()

        if start:
            temp = temp[temp['Date'] >= start]
        if end:
            temp = temp[temp['Date'] <= end]
        if regions and 'ALL Region' not in regions:
            temp = temp[temp['Region'].isin(regions)]
        if countries and 'ALL Country' not in countries:
            temp = temp[temp['Country'].isin(countries)]
        if products and 'ALL Product Type' not in products:
            temp = temp[temp['Product Type'].isin(products)]
        if item_groups and 'ALL Item Group' not in item_groups:
            temp = temp[temp['Item - Item Group Full Name'].isin(item_groups)]
        if customers and 'ALL Customer' not in customers:
            temp = temp[temp['Customer - Name'].isin(customers)]
        if item_codes and 'ALL Item Code' not in item_codes:
            temp = temp[temp['Item - Code'].isin(item_codes)]
        if 'include' not in revenlia_toggle:
            temp = temp[temp['Sub Region'].str.upper() != 'REVELIA']

        if not temp.empty:
            if aggregation_mode == 'yearly':
                temp['Year'] = pd.to_datetime(temp['Date']).dt.year
                df_grouped = temp.groupby('Year').agg({
                    'Adj Sales Amt': 'sum',
                    'Sales Qua': 'sum',
                    'Adj EBIT': 'sum',
                    'Adj Net Sales': 'sum'
                }).reset_index()
                df_grouped['Unit Price'] = df_grouped['Adj Sales Amt'] / df_grouped['Sales Qua']
                df_grouped['EBIT %'] = np.where(
                    df_grouped['Adj Net Sales'] > 0,
                    df_grouped['Adj EBIT'] / df_grouped['Adj Net Sales'],
                    np.nan
                )
                df_grouped['MoM Sales Amt'] = df_grouped['Adj Sales Amt'].pct_change()
                df_grouped['MoM Sales Qua'] = df_grouped['Sales Qua'].pct_change()
                df_grouped['MoM Unit Price'] = df_grouped['Unit Price'].pct_change()
                df_grouped['MoM EBIT %'] = df_grouped['EBIT %'].pct_change()

                df_grouped['Year'] = pd.to_datetime(df_grouped['Year'], format='%Y')
                df_grouped = df_grouped.sort_values('Year')
                all_years.extend(df_grouped['Year'].dt.year.tolist())
                x_col = 'Year'

            else:
                temp['Date'] = pd.to_datetime(temp['Date'])
                df_grouped = temp.groupby('Date').agg({
                    'Adj Sales Amt': 'sum',
                    'Sales Qua': 'sum',
                    'Adj EBIT': 'sum',
                    'Adj Net Sales': 'sum'
                }).reset_index()
                df_grouped['Unit Price'] = df_grouped['Adj Sales Amt'] / df_grouped['Sales Qua']
                df_grouped['EBIT %'] = np.where(
                    df_grouped['Adj Net Sales'] > 0,
                    df_grouped['Adj EBIT'] / df_grouped['Adj Net Sales'],
                    np.nan
                )
                df_grouped['MoM Sales Amt'] = df_grouped['Adj Sales Amt'].pct_change()
                df_grouped['MoM Sales Qua'] = df_grouped['Sales Qua'].pct_change()
                df_grouped['MoM Unit Price'] = df_grouped['Unit Price'].pct_change()
                df_grouped['MoM EBIT %'] = df_grouped['EBIT %'].pct_change()

                x_col = 'Date'

            grouped_data_list.append((idx, df_grouped, x_col))

    if aggregation_mode == 'yearly':
        unique_years = sorted(set(all_years))
        if len(unique_years) <= 2:
            only_year = unique_years[0]
            dummy_years = [only_year - 2, only_year + 2]
            dummy_df = pd.DataFrame({
                'Year': pd.to_datetime(dummy_years, format='%Y'),
                'Adj Sales Amt': [0, 0],
                'Sales Qua': [0, 0],
                'Adj EBIT': [0, 0],
                'Adj Net Sales': [0, 0],
                'Unit Price': [0, 0],
                'EBIT %': [0, 0]
            })

            for i in range(len(grouped_data_list)):
                idx, df_grouped, x_col = grouped_data_list[i]
                df_grouped = pd.concat([df_grouped, dummy_df], ignore_index=True)
                df_grouped = df_grouped.sort_values(by=x_col)
                grouped_data_list[i] = (idx, df_grouped, x_col)
        bar_width = None
    for idx, df_grouped, x_col in grouped_data_list:
        color = colors[idx] if idx < len(colors) else None
        line_style = dict(color=color)

        if aggregation_mode == 'yearly':
            text_display = get_evenly_spaced_labels(df_grouped['Adj Sales Amt'])
            fig_sales.add_bar(
                x=df_grouped[x_col],
                y=df_grouped['Adj Sales Amt'],
                name=f'Filter {idx + 1}',
                marker_color=color,
                customdata=np.stack([df_grouped['MoM Sales Amt']], axis=-1),
                hovertemplate="%{x}<br>Sales Amount: %{y:,.2f}<br>MoM: %{customdata[0]:+.2%}<extra></extra>",
                width=bar_width,
                text=text_display,
                textposition="inside",
                texttemplate="%{text}"
            )

            text_display = get_evenly_spaced_labels(df_grouped['Sales Qua'])
            fig_sales_qua.add_bar(
                x=df_grouped[x_col],
                y=df_grouped['Sales Qua'],
                name=f'Filter {idx + 1}',
                marker_color=color,
                customdata=np.stack([df_grouped['MoM Sales Qua']], axis=-1),
                hovertemplate="%{x}<br>Sales Quantity: %{y:,.2f}<br>MoM: %{customdata[0]:+.2%}<extra></extra>",
                width=bar_width,
                text=text_display,
                textposition="inside",
                texttemplate="%{text}"
            )

            text_display = get_evenly_spaced_labels(df_grouped['Unit Price'])
            fig_unit_price.add_bar(
                x=df_grouped[x_col],
                y=df_grouped['Unit Price'],
                name=f'Filter {idx + 1}',
                marker_color=color,
                customdata=np.stack([df_grouped['MoM Unit Price']], axis=-1),
                hovertemplate="%{x}<br>Unit Price: %{y:,.2f}<br>MoM: %{customdata[0]:+.2%}<extra></extra>",
                width=bar_width,
                text=text_display,
                textposition="inside",
                texttemplate="%{text}"
            )

            text_display = get_evenly_spaced_labels(df_grouped['EBIT %'])
            fig_ebit.add_bar(
                x=df_grouped[x_col],
                y=df_grouped['EBIT %'],
                name=f'Filter {idx + 1}',
                marker_color=color,
                customdata=np.stack([df_grouped['MoM EBIT %']], axis=-1),
                hovertemplate="%{x}<br>EBIT %: %{y:.2%}<br>MoM: %{customdata[0]:+.2%}<extra></extra>",
                width=bar_width,
                text=text_display,
                textposition="inside",
                texttemplate="%{y:.0%}"
            )



        else:
            cols_to_convert = ['Adj Sales Amt', 'Sales Qua', 'Unit Price', 'EBIT %']
            df_grouped[cols_to_convert] = df_grouped[cols_to_convert].apply(pd.to_numeric, errors='coerce')

            text_display_sales = get_evenly_spaced_labels(df_grouped['Adj Sales Amt'])
            fig_sales.add_scatter(
                x=df_grouped[x_col],
                y=df_grouped['Adj Sales Amt'],
                mode='lines+markers+text',
                name=f'Filter {idx + 1}',
                line=line_style,
                marker=dict(size=5),
                text=text_display_sales,
                textposition="top center",
                customdata=np.stack([
                    df_grouped['MoM Sales Amt']
                ], axis=-1),
                hovertemplate="%{x}<br>Sales Amount: %{y:,.2f}<br>MoM: %{customdata[0]:+.2%}<extra></extra>"
            )

            text_display_qua = get_evenly_spaced_labels(df_grouped['Sales Qua'])
            fig_sales_qua.add_scatter(
                x=df_grouped[x_col],
                y=df_grouped['Sales Qua'],
                mode='lines+markers+text',
                name=f'Filter {idx + 1}',
                line=line_style,
                marker=dict(size=5),
                text=text_display_qua,
                textposition="top center",
                customdata=np.stack([df_grouped['MoM Sales Qua']], axis=-1),
                hovertemplate="%{x}<br>Sales Quantity: %{y:,.2f}<br>MoM: %{customdata[0]:+.2%}<extra></extra>"
            )

            text_display_price = get_evenly_spaced_labels(df_grouped['Unit Price'])
            fig_unit_price.add_scatter(
                x=df_grouped[x_col],
                y=df_grouped['Unit Price'],
                mode='lines+markers+text',
                name=f'Filter {idx + 1}',
                line=line_style,
                marker=dict(size=5),
                text=text_display_price,
                textposition="top center",
                customdata=np.stack([df_grouped['MoM Unit Price']], axis=-1),
                hovertemplate="%{x}<br>Unit Price: %{y:,.2f}<br>MoM: %{customdata[0]:+.2%}<extra></extra>"
            )

            n = len(df_grouped['EBIT %'])
            if n <= 6:
                ebit_indices = list(range(n))
            else:
                step = n / 6
                ebit_indices = [int(round(i * step)) for i in range(6)]
                ebit_indices = sorted(set(min(i, n - 1) for i in ebit_indices))

            text_display_ebit = [f"{x:.0%}" if i in ebit_indices else "" for i, x in enumerate(df_grouped['EBIT %'])]
            fig_ebit.add_scatter(
                x=df_grouped[x_col],
                y=df_grouped['EBIT %'],
                mode='lines+markers+text',
                name=f'Filter {idx + 1}',
                line=line_style,
                marker=dict(size=8),
                text=text_display_ebit,
                textposition="top center",
                customdata=np.stack([df_grouped['MoM EBIT %']], axis=-1),
                hovertemplate="%{x}<br>EBIT %: %{y:.2%}<br>MoM: %{customdata[0]:+.2%}<extra></extra>"
            )

    for fig in [fig_sales, fig_sales_qua, fig_unit_price, fig_ebit]:
        fig.update_layout(
            width=470,
            height=420,
            font=dict(family='Orbitron, sans-serif', size=10, color='Black'),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(x=0.8, y=0, orientation='v', bgcolor='rgba(255,255,255,0)',
                        font=dict(family="Bahnschrift, sans-serif", size=12, color="black")),
            hovermode='x unified'
        )
        fig.update_layout(
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor="white",
                font=dict(
                    color="black",
                    family="Bahnschrift"
                ),
                bordercolor="black"
            )
        )

        if aggregation_mode == 'yearly':
            fig.update_xaxes(tickformat='%Y')

        else:
            fig.update_xaxes(type='date', tickformat='%y-%m', tickangle=0, nticks=5)
        fig.update_yaxes(showgrid=False)

    fig_sales.update_layout(xaxis_title='Date/Year', yaxis_title=y_label_sales)
    fig_sales_qua.update_layout(xaxis_title='Date/Year', yaxis_title='Sales Quantity')
    fig_unit_price.update_layout(xaxis_title='Date/Year', yaxis_title=y_label_price)
    fig_ebit.update_layout(xaxis_title='Date/Year', yaxis_title=y_label_ebit, yaxis_tickformat=".2%")

    fig_sales.update_yaxes(tickformat=".0s", nticks=4)
    fig_sales_qua.update_yaxes(tickformat=".0s", nticks=4)
    fig_unit_price.update_yaxes(tickformat=".0s", nticks=4)
    fig_ebit.update_yaxes(tickformat=".0%", nticks=4)

    return fig_sales, fig_sales_qua, fig_unit_price, fig_ebit


# ========== Cost Breakdown Function ========== #
def compute_cost_breakdown(df):
    total_sales_amt = df["Total Sales Amt"].sum()
    net_sales_amt = df["Net Sales"].sum()

    if total_sales_amt == 0 or net_sales_amt == 0:
        return pd.DataFrame(), 0

    breakdown_df = pd.DataFrame({
        "Category": [
            "Rebate", "Freight Out", "Purchasing Material", "Warehouse Operation", "Commission", "Other SG&A", "EBIT"
        ],
        "Percentage": [
            df["Rebate Amount"].sum() / net_sales_amt,
            df["Freight Out"].sum() / net_sales_amt,
            df["Act Material Cost Total"].sum() / net_sales_amt,
            df["Contracted Work Total"].sum()/ net_sales_amt,
            df["Commission"].sum() / net_sales_amt,
            df["SG&A Total Exclud. Commission"].sum() / net_sales_amt,
            df["EBIT"].sum() / net_sales_amt
        ]
    })

    breakdown_df["Absolute Value"] = breakdown_df["Percentage"] * total_sales_amt
    breakdown_df["Absolute Value"] = breakdown_df["Absolute Value"].clip(lower=0)

    breakdown_df["Category"] = pd.Categorical(
        breakdown_df["Category"],
        categories=[
            "Rebate", "Freight Out", "Purchasing Material", "Warehouse Operation",
            "Commission", "Other SG&A", "EBIT"
        ],
        ordered=True
    )

    return breakdown_df, total_sales_amt


# ========== Sidebar Bubble Chart Callback ========== #
@app.callback(
    Output('demo-ebit-figure', 'figure'),
    [
        Input({'type': 'start-date', 'index': 'default'}, 'value'),
        Input({'type': 'end-date', 'index': 'default'}, 'value'),
        Input({'type': 'dynamic-region', 'index': 'default'}, 'value'),
        Input({'type': 'dynamic-country', 'index': 'default'}, 'value'),
        Input({'type': 'dynamic-product-type', 'index': 'default'}, 'value'),
        Input({'type': 'dynamic-item-group', 'index': 'default'}, 'value'),
        Input({'type': 'dynamic-customer-name', 'index': 'default'}, 'value'),
        Input({'type': 'dynamic-item-code', 'index': 'default'}, 'value'),
        Input('revenlia-toggle', 'value')
    ]
)
def update_sidebar_bubble_chart(start_date, end_date,
                                region_value, country_value, product_value,
                                item_group_value, customer_value, item_code_value, revenlia_toggle):
    if df_store.empty or 'EBIT' not in df_store.columns:
        return px.scatter(title='No Data')

    temp = df_store.copy()
    if start_date:
        temp = temp[temp['Date'] >= start_date]
    if end_date:
        temp = temp[temp['Date'] <= end_date]

    if isinstance(region_value, str):
        region_value = [region_value]
    if isinstance(country_value, str):
        country_value = [country_value]
    if isinstance(product_value, str):
        product_value = [product_value]

    if region_value and 'ALL Region' not in region_value:
        temp = temp[temp['Region'].isin(region_value)]
    if country_value and 'ALL Country' not in country_value:
        temp = temp[temp['Country'].isin(country_value)]
    if product_value and 'ALL Product Type' not in product_value:
        temp = temp[temp['Product Type'].isin(product_value)]
    if item_group_value and 'ALL Item Group' not in item_group_value:
        temp = temp[temp['Item - Item Group Full Name'].isin(item_group_value)]
    if customer_value and 'ALL Customer' not in customer_value:
        temp = temp[temp['Customer - Name'].isin(customer_value)]
    if item_code_value and 'ALL Item Code' not in item_code_value:
        temp = temp[temp['Item - Code'].isin(item_code_value)]
    if 'include' not in revenlia_toggle:
        temp = temp[temp['Sub Region'].str.upper() != 'REVELIA']

    breakdown_df, total_sales_amt = compute_cost_breakdown(temp)
    if breakdown_df.empty:
        return px.scatter(title='No Data')

    selected_filters = []
    if start_date:
        selected_filters.append(str(start_date))
    if end_date:
        selected_filters.append(str(end_date))
    if region_value:
        selected_filters.append('|'.join(region_value))
    if country_value:
        selected_filters.append('|'.join(country_value))
    if product_value:
        selected_filters.append('|'.join(product_value))

    title_text = 'All Data' if not selected_filters else '|'.join(selected_filters)

    category_order = {
        "Rebate": 6,
        "Freight Out": 5,
        "Purchasing Material": 4,
        "Warehouse Operation": 3,
        "Commission": 2,
        "Other SG&A": 1,
        "EBIT": 0
    }
    breakdown_df["Y_Pos"] = breakdown_df["Category"].map(category_order)
    breakdown_df["X"] = 0.3  # 所有 bubble 在同一列

    fig = px.scatter(
        breakdown_df,
        x="X",
        y="Y_Pos",
        size="Absolute Value",
        color="Category",
        color_discrete_map=category_colors,
        text=breakdown_df["Percentage"].apply(lambda x: f"{x:.2%}")
    )

    desired_max_marker_size = 55
    sizeref = 2. * max(breakdown_df['Absolute Value']) / (desired_max_marker_size ** 2)

    fig.update_traces(
        marker=dict(sizemode='area', sizeref=sizeref, sizemin=4, opacity=0.8),
        textposition='middle center'
    )

    fig.update_layout(
        xaxis={'visible': False, 'showgrid': False, 'range': [-0.1, 0.5]},
        yaxis=dict(
            tickvals=list(category_order.values()),
            ticktext=list(category_order.keys()),
            showgrid=False,
            title="Category"
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        font=dict(color='black', family='Orbitron, sans-serif'),
        height=450
    )

    return fig


##############################

category_colors = {
    'Rebate': '#636EFA',
    'Freight Out': '#EF553B',
    'Purchasing Material': '#00CC96',
    'Warehouse Operation': '#AB63FA',
    'Commission': '#FFA15A',
    'Other SG&A': '#19D3F3',
    'EBIT': '#FF6692'
}


##########################################
@app.callback(
    [
        Output('dynamic-filters', 'children'),
        Output('cost-breakdown-card', 'style'),
        Output('dynamic-bubble-graph-container', 'children'),
        Output('filter-labels-container', 'children')  # ✅ 额外输出 label
    ],
    Input('add-filter', 'n_clicks'),
    Input({'type': 'delete-filter', 'index': ALL}, 'n_clicks'),
    State('dynamic-filters', 'children'),
    State('cost-breakdown-card', 'style'),
    State('dynamic-bubble-graph-container', 'children'),
    prevent_initial_call=True
)
def manage_filters_and_bubbles(add_clicks, delete_clicks, current_children, card_style, current_bubble_graphs):
    triggered = ctx.triggered_id

    if card_style is None:
        card_style = {'width': '400px'}
    if current_children is None:
        current_children = []
    if current_bubble_graphs is None:
        current_bubble_graphs = []

    filter_labels = []

    try:
        current_width = int(str(card_style.get('width', '400px')).replace('px', '').strip())
    except ValueError:
        current_width = 400

    # === 删除逻辑 ===
    if isinstance(triggered, dict) and triggered.get('type') == 'delete-filter':
        delete_id = triggered['index']
        updated_children = [child for child in current_children if child['props']['id'] != delete_id]
        updated_bubble_graphs = [g for g in current_bubble_graphs if g['props']['id'] != f"bubble-graph-{delete_id}"]

        # 👇 更新剩下的 Filter 文字
        for child in updated_children:
            label_id = f"filter-label-{child['props']['id']}"
            filter_labels.append(
                html.Div("Filter 2", id=label_id, style={
                    'position': 'absolute',
                    'top': '215px',
                    'left': '10px',
                    'color': 'black',
                    'font-family': 'Bahnschrift, sans-serif',
                    'font-size': '16px',
                    'font-weight': 'bold'
                })
            )

        if current_width > 400:
            card_style['width'] = f'{max(400, current_width - 405)}px'

        return updated_children, card_style, updated_bubble_graphs, filter_labels

    # === 添加逻辑 ===
    if triggered == 'add-filter' and len(current_children) < 1:
        new_id = f"dynamic-sales-filter-{len(current_children)}"

        region_options = [{'label': r, 'value': r} for r in ['ALL Region'] + sorted(df_store['Region'].unique())]
        country_options = [{'label': c, 'value': c} for c in ['ALL Country'] + sorted(df_store['Country'].unique())]
        product_options = [{'label': p, 'value': p} for p in
                           ['ALL Product Type'] + sorted(df_store['Product Type'].unique())]
        item_group_options = [{'label': p, 'value': p} for p in
                              ['ALL Item Group'] + sorted(df_store['Item - Item Group Full Name'].unique())]
        customer_name_options = [{'label': c, 'value': c} for c in
                                 ['ALL Customer'] + sorted(df_store['Customer - Name'].unique())]
        item_code_options = [{'label': c, 'value': c} for c in
                             ['ALL Item Code'] + sorted(df_store['Item - Code'].unique())]
        # 👇 添加 Filter 2 文字
        filter_labels.extend([
            html.Div("Filter 1", id="filter-label-1", style={
                'position': 'absolute',
                'top': '350px',
                'left': '545px',
                'color': 'black',
                'font-family': 'Bahnschrift, sans-serif',
                'font-size': '14px',
                'font-weight': 'bold',
                'zIndex': '3'
            }),
            html.Div("Filter 2", id="filter-label-2", style={
                'position': 'absolute',
                'top': '350px',
                'left': '856px',
                'color': 'black',
                'font-family': 'Bahnschrift, sans-serif',
                'font-size': '14px',
                'font-weight': 'bold',
                'zIndex': '3'
            })
        ])
        horizontal_lines = [
            html.Div(style={
                'position': 'absolute',
                'top': '435px',
                'left': '123px',
                'width': '35px',
                'border': '2px solid black',
                'background-color': 'black',
                'zIndex': '2'
            })
        ]

        new_group = html.Div(
            id=new_id,
            className='dynamic-filter-group',
            children=[
                html.Div(
                    f"Filter {len(current_children) + 2}",
                    style={
                        'font-weight': 'bold',
                        'color': 'black',
                        'margin-top': '-5px',
                        'font-family': 'Bahnschrift, sans-serif'
                    }
                ),

                html.Div(
                    style={'display': 'flex', 'gap': '60px'},
                    children=[
                        dcc.Dropdown(
                            id={'type': 'start-date', 'index': new_id},
                            options=[{'label': d, 'value': d} for d in sorted(df_store['Date'].unique())],
                            value=sorted(df_store['Date'].unique())[0],
                            className='start-date-dynamic',
                            placeholder="Start",
                            style={'color': 'black'}
                        ),
                        dcc.Dropdown(
                            id={'type': 'end-date', 'index': new_id},
                            options=[{'label': d, 'value': d} for d in sorted(df_store['Date'].unique())],
                            value=sorted(df_store['Date'].unique())[-1],
                            className='end-date-dynamic',
                            placeholder="End",
                            style={'color': 'black'}
                        )
                    ]
                ),

                dcc.Dropdown(
                    id={'type': 'dynamic-region', 'index': new_id},
                    options=region_options,
                    value=['ALL Region'],
                    multi=True,
                    className='transparent-dropdown'
                ),
                dcc.Dropdown(
                    id={'type': 'dynamic-country', 'index': new_id},
                    options=country_options,
                    value=['ALL Country'],
                    multi=True,
                    className='transparent-dropdown'
                ),
                dcc.Dropdown(
                    id={'type': 'dynamic-product-type', 'index': new_id},
                    options=product_options,
                    value=['ALL Product Type'],
                    multi=True,
                    className='transparent-dropdown'
                ),
                dcc.Dropdown(
                    id={'type': 'dynamic-item-group', 'index': new_id},
                    options=item_group_options,
                    value=['ALL Item Group'],
                    multi=True,
                    className='transparent-dropdown'
                ),
                dcc.Dropdown(
                    id={'type': 'dynamic-customer-name', 'index': new_id},
                    options=customer_name_options,
                    value=['ALL Customer'],
                    multi=True,
                    className='transparent-dropdown'
                ),

                html.Button(
                    '➖',
                    id={'type': 'delete-filter', 'index': new_id},
                    className='icon-button delete-button',
                    style={
                        'backgroundColor': 'white',
                        'border': '1px solid #ccc',
                        'color': '#333',
                        'fontSize': '16px',
                        'fontWeight': 'bold',
                        'padding': '2px 8px',
                        'borderRadius': '6px',
                        'cursor': 'pointer',
                        'height': '28px',
                        'lineHeight': '1',
                        'transition': 'background-color 0.2s, border-color 0.2s',
                        'position': 'absolute',
                        'top': '-300px',
                        'left': '220px',
                        'zIndex': '5'
                    }
                ),
                dcc.Dropdown(
                    id={'type': 'dynamic-item-code', 'index': new_id},
                    options=item_code_options,
                    value=['ALL Item Code'],
                    multi=True,
                    className='transparent-dropdown'
                )
            ]
        )

        current_children.append(new_group)

        current_bubble_graphs.append(
            html.Div(
                id=f"bubble-graph-{new_id}",
                children=[dcc.Graph(id={'type': 'dynamic-bubble-graph', 'index': new_id}, figure=go.Figure())]
            )
        )

        if current_width <= 400:
            card_style['width'] = '805px'

        return current_children, card_style, current_bubble_graphs, filter_labels + horizontal_lines

    return current_children, card_style, current_bubble_graphs, filter_labels


###############################################

###############################################
@app.callback(
    Output('sidebar-background-color', 'style'),
    Input('upload-data', 'contents')
)
def toggle_sidebar_background(contents):
    if contents:
        return {
            'position': 'absolute',
            'top': '0',
            'left': '0',
            'width': '280px',
            'height': '100vh',
            'backgroundColor': '#A0A0A0',
            'zIndex': '0',
            'display': 'block',
            'overflowY': 'auto'
        }
    else:
        return {
            'position': 'absolute',
            'top': '0',
            'left': '0',
            'width': '400px',
            'height': '100vh',
            'backgroundColor': '#D3D3D3',
            'zIndex': '0',
            'display': 'none'
        }


#######################################

###########################################


@app.callback(
    Output('dynamic-filters', 'style'),
    Input('add-filter', 'n_clicks'),
    prevent_initial_call=True
)
def move_dynamic_filter_container(n_clicks):
    if n_clicks is None:
        raise dash.exceptions.PreventUpdate

    if n_clicks % 2 == 1:
        top = '435px'
    else:
        top = '435px'

    return {'position': 'absolute', 'top': top, 'left': '10px', 'zIndex': 4}


#########################################
from dash import MATCH


@app.callback(
    Output({'type': 'dynamic-bubble-graph', 'index': MATCH}, 'figure'),
    [
        Input({'type': 'start-date', 'index': MATCH}, 'value'),
        Input({'type': 'end-date', 'index': MATCH}, 'value'),
        Input({'type': 'dynamic-region', 'index': MATCH}, 'value'),
        Input({'type': 'dynamic-country', 'index': MATCH}, 'value'),
        Input({'type': 'dynamic-product-type', 'index': MATCH}, 'value'),
        Input({'type': 'dynamic-item-group', 'index': MATCH}, 'value'),
        Input({'type': 'dynamic-customer-name', 'index': MATCH}, 'value'),
        Input({'type': 'dynamic-item-code', 'index': MATCH}, 'value'),
        Input('revenlia-toggle', 'value')
    ]

)
def update_dynamic_bubble_chart(start_date, end_date,
                                region_value, country_value, product_value,
                                item_group_value, customer_value, item_code_value, revenlia_toggle):
    if df_store.empty or 'EBIT' not in df_store.columns:
        return px.scatter(title='No Data')

    temp = df_store.copy()
    if start_date:
        temp = temp[temp['Date'] >= start_date]
    if end_date:
        temp = temp[temp['Date'] <= end_date]
    if isinstance(region_value, str):
        region_value = [region_value]
    if isinstance(country_value, str):
        country_value = [country_value]
    if isinstance(product_value, str):
        product_value = [product_value]

    if region_value and 'ALL Region' not in region_value:
        temp = temp[temp['Region'].isin(region_value)]
    if country_value and 'ALL Country' not in country_value:
        temp = temp[temp['Country'].isin(country_value)]
    if product_value and 'ALL Product Type' not in product_value:
        temp = temp[temp['Product Type'].isin(product_value)]
    if item_group_value and 'ALL Item Group' not in item_group_value:
        temp = temp[temp['Item - Item Group Full Name'].isin(item_group_value)]

    if customer_value and 'ALL Customer' not in customer_value:
        temp = temp[temp['Customer - Name'].isin(customer_value)]
    if item_code_value and 'ALL Item Code' not in item_code_value:
        temp = temp[temp['Item - Code'].isin(item_code_value)]
    if 'include' not in revenlia_toggle:
        temp = temp[temp['Sub Region'].str.upper() != 'REVELIA']

    breakdown_df, total_sales_amt = compute_cost_breakdown(temp)
    if breakdown_df.empty:
        return px.scatter(title='No Data')

    # 拼接标题
    selected_filters = []
    if region_value:
        selected_filters.append('|'.join(region_value))
    if country_value:
        selected_filters.append('|'.join(country_value))
    if product_value:
        selected_filters.append('|'.join(product_value))
    title_text = 'All Data' if not selected_filters else '|'.join(selected_filters)

    category_order = {
        "Rebate": 6,
        "Freight Out": 5,
        "Purchasing Material": 4,
        "Warehouse Operation": 3,
        "Commission": 2,
        "Other SG&A": 1,
        "EBIT": 0
    }
    breakdown_df["Y_Pos"] = breakdown_df["Category"].map(category_order)
    breakdown_df["X"] = 0.3

    fig = px.scatter(
        breakdown_df,
        x="X",
        y="Y_Pos",
        size="Absolute Value",
        color="Category",
        color_discrete_map=category_colors,
        text=breakdown_df["Percentage"].apply(lambda x: f"{x:.2%}")
    )

    desired_max_marker_size = 55
    sizeref = 2. * max(breakdown_df["Absolute Value"]) / (desired_max_marker_size ** 2)

    fig.update_traces(
        marker=dict(sizemode="area", sizeref=sizeref, sizemin=4, opacity=0.8),
        textposition="middle center"
    )

    fig.update_layout(
        title=None,
        xaxis=dict(visible=False, showgrid=False, range=[-0.1, 0.5]),
        yaxis=dict(
            visible=False,
            showgrid=False,
            tickvals=list(category_order.values()),
            ticktext=list(category_order.keys())
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        font=dict(color='black', family='Orbitron, sans-serif'),
        height=450
    )

    return fig


#################################
@app.callback(
    Output('filter-count-store', 'data'),
    Input({'type': 'delete-filter', 'index': ALL}, 'n_clicks'),
    State('filter-count-store', 'data')
)
def update_filter_count(delete_clicks, current_count):
    return len(delete_clicks)


@app.callback(
    Output('ebit-position-store', 'data'),
    [
        Input('add-filter', 'n_clicks'),
        Input('filter-count-store', 'data')
    ],
    State('ebit-position-store', 'data')
)
def update_ebit_position(add_clicks, current_filter_count, current_position):
    ctx_id = ctx.triggered_id

    if ctx_id == 'add-filter' and add_clicks > 0:
        return 'moved'

    if ctx_id == 'filter-count-store' and current_filter_count == 0:
        return 'default'

    return dash.no_update


@app.callback(
    Output('ebit-percent-card', 'className'),
    Input('ebit-position-store', 'data')
)
def update_ebit_class(pos_state):
    return 'card-container moved-ebit' if pos_state == 'moved' else 'card-container'


######################################
@app.callback(
    Output('dashboard-page', 'children'),
    Input('sales-btn', 'n_clicks'),
    Input('cost-btn', 'n_clicks')
)
def render_dashboard_page(sales_clicks, cost_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return sales_page_layout()

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id == 'sales-btn':
        return sales_page_layout()
    elif button_id == 'cost-btn':
        if inventory_df.empty:
            return html.Div("❌ Inventory 数据为空")

        all_months = sorted(inventory_df['year_month'].dropna().unique())
        month_options = [{"label": m.strftime('%Y-%m'), "value": m.strftime('%Y-%m')} for m in all_months]
        return html.Div([
            html.Div([
                html.Label("Select Year-Month:", style={"fontWeight": "bold"}),
                dcc.Dropdown(
                    id="inventory-month-selector",
                    options=month_options,
                    placeholder="e.g. 2025-01"
                )
            ]),

            html.Div(
                id="inventory-cards",
                style={
                    "position": "relative"
                }
            )

        ])


##########################
@app.callback(
    Output("inventory-cards", "children"),
    [
        Input("inventory-month-selector", "value"),
        Input("pie-source-selector",      "value")
    ]
)
def update_inventory_cards(selected_month, pie_source):
    import pandas as pd
    import plotly.express as px
    from dash import html, dcc
    global inventory_df, balance_df, pads_df, disc_df

    # 如果没选月份或数据空，直接返回
    if not selected_month or inventory_df.empty:
        return []

    # 本月和上月数据
    df_curr = inventory_df[inventory_df["year_month"] == selected_month]
    try:
        prev_month = (pd.to_datetime(selected_month) - pd.DateOffset(months=1)).strftime("%Y-%m")
        df_prev   = inventory_df[inventory_df["year_month"] == prev_month]
        bal_prev  = balance_df[ balance_df["year_month"] == prev_month ]
    except:
        df_prev  = pd.DataFrame()
        bal_prev = pd.DataFrame()
    bal_curr = balance_df[ balance_df["year_month"] == selected_month ]

    # —— 计算 MoM 值 —— #
    def mom(curr, prev):
        if prev in [0, None] or pd.isna(prev):
            return None
        return (curr - prev) / prev

    # —— 按 category/type 聚合当前和上月数据的辅助函数 —— #
    def sum_curr_prev(field, starts, df1, df2):
        mask1 = df1["Item number"].astype(str).str.startswith(starts)
        curr  = df1.loc[mask1, field].sum()
        if df2 is None or df2.empty:
            prev = 0
        else:
            mask2 = df2["Item number"].astype(str).str.startswith(starts)
            prev  = df2.loc[mask2, field].sum()
        return curr, prev

    # Overall & WIP & GIT
    total_amt,      total_amt_prev  = (
        bal_curr.get("1400-INVENTORY", pd.Series([0])).sum(),
        bal_prev.get("1400-INVENTORY", pd.Series([0])).sum()
    )
    git_disc,       git_disc_prev   = (
        bal_curr.get("102011101 - 在途物资—产成品 刹车盘", pd.Series([0])).sum(),
        bal_prev.get("102011101 - 在途物资—产成品 刹车盘", pd.Series([0])).sum()
    )
    git_pads,       git_pads_prev   = (
        bal_curr.get("102011102 - 在途物资—产成品 刹车片", pd.Series([0])).sum(),
        bal_prev.get("102011102 - 在途物资—产成品 刹车片", pd.Series([0])).sum()
    )

    # Disc / Pads / Brake / Moto 数量 & 金额
    disc_qty,      disc_qty_prev   = sum_curr_prev("On-hand", ("08","09","14"), df_curr, df_prev)
    disc_amt,      disc_amt_prev   = sum_curr_prev("Inventory value",    ("08","09","14"), df_curr, df_prev)
    pads_qty,      pads_qty_prev   = sum_curr_prev("On-hand", ("P","S"),       df_curr, df_prev)
    pads_amt,      pads_amt_prev   = sum_curr_prev("Inventory value",    ("P","S"),       df_curr, df_prev)
    brake_qty,     brake_qty_prev  = sum_curr_prev("On-hand", ("L",),          df_curr, df_prev)
    brake_amt,     brake_amt_prev  = sum_curr_prev("Inventory value",    ("L",),          df_curr, df_prev)

    moto_curr = df_curr[df_curr["Cost center"].isin(["34N00037","34N00039"])]
    moto_prev = df_prev[df_prev["Cost center"].isin(["34N00037","34N00039"])]
    moto_qty,      moto_qty_prev   = (
        moto_curr["On-hand"].sum(),
        moto_prev["On-hand"].sum() if not moto_prev.empty else 0
    )
    moto_amt,      moto_amt_prev   = (
        moto_curr["Inventory value"].sum(),
        moto_prev["Inventory value"].sum()   if not moto_prev.empty else 0
    )

    # —— 渲染卡片的辅助函数 —— #
    def value_only_card(title, amount, mom_pct):
        mom_div = ""
        if mom_pct is not None:
            clr = "red" if mom_pct > 0 else "green"
            arr = "▲" if mom_pct > 0 else "▼"
            mom_div = html.Div(f"{arr} {mom_pct:.1%} MoM", style={"fontSize": "12px", "color": clr})
        return html.Div(
            [
                html.Div(title,
                         style={"fontWeight": "bold", "fontSize": "14px", "marginBottom": "6px", "color": "black"}),
                html.Div(f"¥{amount:,.0f}", style={"color": "red", "fontSize": "16px", "fontWeight": "bold"}),
                mom_div
            ],
            style={"padding": "12px", "borderRadius": "8px", "backgroundColor": "#f5f5f5",
                   "boxShadow": "0 1px 4px rgba(0,0,0,0.1)", "maxHeight": "80px"}
        )

    def qty_value_card(title, quantity, amount, mom_pct):
        if mom_pct is not None:
            clr = "red" if mom_pct > 0 else "green"
            arr = "▲" if mom_pct > 0 else "▼"
            mom_div = html.Div(f"{arr} {mom_pct:.1%} MoM",
                               style={"fontSize": "12px", "color": clr})
        else:
            mom_div = html.Span("")

        header = html.Div(
            [
                html.Div(title, style={
                    "fontWeight": "bold",
                    "fontSize": "12px",
                    "color": "black"
                }),
                mom_div
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "6px",
                "width":'138px',
                "height": "30px"
            }
        )

        qty = html.Div(f"Qty: {quantity:,.0f}",
                       style={"fontSize": "12px", "color": "#555", "marginBottom": "4px"})

        amt = html.Div(f"¥{amount:,.0f}",
                       style={"color": "red", "fontSize": "14px", "fontWeight": "bold"})
        return html.Div(
            [header, qty, amt],
            style={
                "padding": "12px",
                "borderRadius": "8px",
                "backgroundColor": "#f5f5f5",
                "boxShadow": "0 1px 4px rgba(0,0,0,0.1)"
            }
        )

    def value_mom_card(title, amount, mom_pct):

        if mom_pct is not None:
            color = "red" if mom_pct > 0 else "green"
            arrow = "▲" if mom_pct > 0 else "▼"
            mom_div = html.Div(
                f"{arrow} {mom_pct:.1%} MoM",
                style={"fontSize": "12px", "color": color}
            )
        else:
            mom_div = html.Span("")

        header = html.Div(
            [
                html.Div(title, style={
                    "fontWeight": "bold",
                    "fontSize": "12px",
                    "color": "black"
                }),
                mom_div
            ],
            style={
                "display": "flex",
                "justifyContent": "space-between",
                "alignItems": "center",
                "marginBottom": "25px",
                "width": '138px',
                "height": "30px"
            }
        )

        amt = html.Div(
            f"¥{amount:,.0f}",
            style={"color": "red", "fontSize": "14px", "fontWeight": "bold"}
        )

        return html.Div(
            [header, amt],
            style={
                "padding": "12px",
                "borderRadius": "8px",
                "backgroundColor": "#f5f5f5",
                "boxShadow": "0 1px 4px rgba(0,0,0,0.1)"
            }
        )

    # —— 构造 Overview 卡片 —— #
    overview_card = html.Div(
        className="inv-card-container inventory-overview",
        children=[
            html.Div("Inventory Balance Overview", className="card-header"),
            # —— 第一行：Disc/Pads/Moto/Brake 都显示 MoM —— #
            html.Div(
                style={"display": "flex",  "gap": "12px",
                       "marginTop": "-10px", "paddingLeft": "8px", "paddingRight": "8px"},
                children=[
                    value_mom_card("Overall", total_amt, mom(total_amt, total_amt_prev)),
                    qty_value_card("Disc", disc_qty, disc_amt, mom(disc_amt, disc_amt_prev)),
                    qty_value_card("Pads", pads_qty, pads_amt, mom(pads_amt, pads_amt_prev)),
                    qty_value_card("Moto", moto_qty, moto_amt, mom(moto_amt, moto_amt_prev)),
                    qty_value_card("Fluid", brake_qty, brake_amt, mom(brake_amt, brake_amt_prev)),
                    value_mom_card("GIT Disc", git_disc, mom(git_disc, git_disc_prev)),
                    value_mom_card("GIT Pads", git_pads, mom(git_pads, git_pads_prev)),
                ]
            )
        ]
    )

    # —— Pie 部分（保持原有设定） —— #
    if pie_source == "Pads":
        df_pie = pads_df[pads_df["year_month"] == selected_month]
    elif pie_source == "Disc":
        df_pie = disc_df[disc_df["year_month"] == selected_month]
    else:
        df_pie = pd.concat([pads_df, disc_df], ignore_index=True)
        df_pie = df_pie[df_pie["year_month"] == selected_month]

    pie_df = df_pie.groupby("category", as_index=False)["Inventory value"].sum()
    fig = px.pie(
        pie_df,
        names='category',
        values='Inventory value',
        hole=0.4
    )
    fig.update_traces(textinfo='label+percent',
                      textfont_size=14)
    fig.update_layout(
        margin=dict(t=40, b=0, l=0, r=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )

    pie_div = html.Div(
        [
            html.Div("Inventory Category Breakdown", className="card-header"),
            html.Div(dcc.Graph(
                id="inventory-pie-graph",
                figure=fig,
                config={"displayModeBar": False},
                style={"marginTop":"-120px",'marginLeft':'40px'},
                className="pie-chart-graph"
            ))
        ],
        className="inv-card-container",
        id="card-pie"
    )

    return [overview_card, pie_div]



@app.callback(
    Output("sales-page", "style"),
    Output("cost-page", "style"),
    Input("sales-btn", "n_clicks"),
    Input("cost-btn", "n_clicks")
)
def switch_page(sales_clicks, cost_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return {"display": "block"}, {"display": "none"}

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    return {
        "sales-btn": ({"display": "block"}, {"display": "none"}),
        "cost-btn": ({"display": "none"}, {"display": "block"})
    }.get(button_id, ({"display": "block"}, {"display": "none"}))


import math


@app.callback(
    Output("dio-inventory-graph", "figure"),
    Input("inv-start-date", "value"),
    Input("inv-end-date", "value"),
    Input("inv-category", "value")
)
def update_dio_inventory_chart(start_date, end_date, category):
    if inventory_df.empty or df_store.empty:
        return go.Figure()

    def filter_by_category(df, col, category):
        s = df[col].astype(str)
        if category == "Pads":
            return df[s.str.startswith("2000")]
        elif category == "Disc":
            return df[s.str.startswith(("2330","2300"))]
        elif category == "Total Inventory":
            return df
        return df

    # ==== 数据准备 ====
    if category == "Total Inventory":
        if "1400-INVENTORY" not in balance_df.columns:
            return go.Figure()

        bal_filtered = balance_df[
            (balance_df["year_month"] >= start_date) &
            (balance_df["year_month"] <= end_date)
            ].copy()

        summary_df = bal_filtered[["year_month", "1400-INVENTORY"]].copy()
        summary_df = summary_df.rename(columns={"1400-INVENTORY": "Inventory value"})
        summary_df = summary_df.sort_values("year_month")

        qty_df = inventory_df.groupby("year_month")["On-hand"].sum().reset_index()
        qty_df = qty_df[qty_df["year_month"].between(start_date, end_date)]

        summary_df = pd.merge(summary_df, qty_df, on="year_month", how="left")

        sales_df = df_store.copy()
        sales_df["Date"] = pd.to_datetime(sales_df["Date"], errors="coerce")
        sales_df["year_month"] = sales_df["Date"].dt.strftime('%Y-%m')
        sales_monthly = sales_df.groupby("year_month")["Net Sales"].sum().reset_index()

    else:
        inv_df = filter_by_category(inventory_df.copy(), "Item group", category)
        inv_df = inv_df[inv_df["Cost center"] == "34N00001"]
        sales_df = filter_by_category(df_store.copy(), "Item - Item Group Full Name", category)

        summary_df = inv_df.groupby("year_month").agg({
            "On-hand": "sum",
            "Inventory value": "sum"
        }).reset_index().sort_values("year_month")

    sales_df["Date"] = pd.to_datetime(sales_df["Date"], errors="coerce")
    sales_df["year_month"] = sales_df["Date"].dt.strftime('%Y-%m')
    sales_monthly = sales_df.groupby("year_month")["Net Sales"].sum().reset_index()
    sales_dict = sales_df.groupby("year_month")["Net Sales"].sum().to_dict()
    summary_df = pd.merge(summary_df, sales_monthly, on="year_month", how="left")

    # ==== 计算 DIO ====
    summary_df["DIO"] = None
    for i, row in summary_df.iterrows():
        ym = row["year_month"]
        try:
            dt = pd.to_datetime(ym)
            prev_12 = [(dt - pd.DateOffset(months=m)).strftime("%Y-%m") for m in range(0, 12)]
            monthly_sales = [sales_dict.get(m, 0) for m in prev_12]
            if len(monthly_sales) == 12 and all(s > 0 for s in monthly_sales):
                total_sales = sum(monthly_sales)
                dio = round((row["Inventory value"] / total_sales) * 360, 2)
                summary_df.at[i, "DIO"] = dio
        except:
            continue

    # ==== 打印 DIO ====
    filtered_dio = summary_df[
        (summary_df["year_month"] >= start_date) &
        (summary_df["year_month"] <= end_date) &
        (summary_df["DIO"].notna())
        ][["year_month", "DIO"]]

    # ==== 筛选时间范围用于绘图 ====
    summary_df = summary_df[
        (summary_df["year_month"] >= start_date) &
        (summary_df["year_month"] <= end_date)
        ]
    # ==== 绘图 ====
    fig = go.Figure()

    # 库存数量柱状图
    fig.add_trace(go.Bar(
        x=summary_df["year_month"],
        y=summary_df["Net Sales"],
        name="Net Sales",
        marker_color="lightsteelblue",
        hovertemplate="Sales: %{y:,.2f}<br>Date: %{x}"
    ))

    fig.add_trace(go.Scatter(
        x=summary_df["year_month"],
        y=summary_df["Inventory value"],
        name="Inventory Value",
        mode="lines+markers",
        yaxis="y2",
        line=dict(color="dimgray", width=2),
        fill='tozeroy',
        fillcolor='rgba(128,128,128,0)',
        hovertemplate="Amount: %{y:,.2f}<br>Date: %{x}"
    ))

    fig.add_trace(go.Scatter(
        x=summary_df["year_month"],
        y=summary_df["DIO"],
        name="DIO",
        mode="lines+markers+text",
        text=summary_df["DIO"].apply(lambda x: f"{x:.0f}" if pd.notnull(x) else ""),
        textposition="top center",
        yaxis="y3",
        textfont=dict(color="firebrick"),
        line=dict(color="firebrick", width=2, dash="dot"),
        fill='tozeroy',
        fillcolor='rgba(178,34,34,0.2)',
        hovertemplate="DIO: %{y:,.2f}<br>Date: %{x}"
    ))

    x_vals = summary_df["year_month"].tolist()
    tickvals = [x_vals[i] for i in np.linspace(0, len(x_vals) - 1, 5).astype(int)] if len(x_vals) > 5 else x_vals
    dio_min = summary_df["DIO"].min()
    dio_max = summary_df["DIO"].max()
    inventory_min = summary_df["Inventory value"].min()
    inventory_max = summary_df["Inventory value"].max()
    offset_min2= 2000000
    offset_max2 = 20000000
    offset_min = 10
    offset_max = 10
    fig.update_layout(
        margin=dict(t=0, b=0),
        paper_bgcolor='white',
        plot_bgcolor='white',
        legend=dict(
            x=0.0,
            y=1.15,
            font=dict(size=8),
            bgcolor='rgba(255,255,255,0.6)',
            borderwidth=0
        ),
        xaxis=dict(
            title="Time",
            tickfont=dict(size=10),
            tickvals=tickvals,
            ticktext=tickvals
        ),
        yaxis=dict(
            title="Net Sales",
            tickfont=dict(size=10)
        ),
        yaxis2=dict(
            title="Inventory Value",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(size=10),
            range=[-50000000, inventory_max]
        ),
        yaxis3=dict(
            overlaying="y",
            side="right",
            position=0.95,
            showticklabels=False,
            showgrid=False,
            ticks="",
            title="",
            zeroline=False,
            range=[dio_min - offset_min, dio_max + offset_max]
        )
    )

    return fig


################################
@app.callback(
   Output('sales-btn', 'style'),
    Output('cost-btn', 'style'),
    Input('sales-btn', 'n_clicks'),
    Input('cost-btn', 'n_clicks')
)
def update_tab_button_style(sales_clicks, cost_clicks):
    ctx_id = callback_context.triggered[0]['prop_id'].split('.')[0]

    common_style_sales = {
        'width': '139px',
        'height': '20px',
        'border': '0.5px solid #222',
        'borderRight': 'none',
        'fontFamily': 'Bahnschrift, sans-serif',
        'fontSize': '13px',
        'fontWeight': '600',
        'textTransform': 'uppercase',
        'padding': '0',
        'margin': '0',
        'cursor': 'pointer',
        'position': 'fixed',
        'top': '55px',
        'left': '0px',
        'zIndex': '2'
    }

    common_style_cost = common_style_sales.copy()
    common_style_cost['left'] = '141px'

    if ctx_id == 'cost-btn':
        # Cost 被点击，Cost 黑色，Sales 灰色
        active = {'backgroundColor': '#000000', 'color': 'white'}
        inactive = {'backgroundColor': '#D3D3D3', 'color': 'black'}
        return {**common_style_sales, **inactive}, {**common_style_cost, **active}
    else:
        # 默认 Sales 黑色
        active = {'backgroundColor': '#000000', 'color': 'white'}
        inactive = {'backgroundColor': '#D3D3D3', 'color': 'black'}
        return {**common_style_sales, **active}, {**common_style_cost, **inactive}


@app.callback(
    Output("normal-coverage-container", "children"),
    Input("inventory-month-selector", "value"),
    Input("normal-source-selector", "value")
)
def update_normal_coverage(selected_month, selected_source):
    if not selected_month:
        return html.Div("")
    if selected_source == "Pads":
        df = pads_df
    elif selected_source == "Disc":
        df = disc_df
    else:
        df = pd.concat([pads_df,disc_df],ignore_index=True)
    df = df[
        (df['year_month'] == selected_month) &
        (df['category'] == 'Normal')
    ].copy()
    if df.empty:
        return html.Div("")

    # 1. 定义所有可能的分类标签（顺序可按需调整）
    all_labels = [
        "Other",
        "Less than 3m",
        "3-6m",
        "6-12m",
        "over1year",
        "no sales 6m"
    ]

    # 2. 初始化一个等长的空分类列
    df["cov_bin"] = pd.Categorical(
        [pd.NA] * len(df),
        categories=all_labels,
        ordered=True
    )

    # 3. coverage == ∞ → "no sales 6 months"
    df.loc[np.isinf(df["coverage"]), "cov_bin"] = "no sales 6m"

    # 4. 有限且 ≥0 的值分箱
    finite = (~np.isinf(df["coverage"])) & (df["coverage"] >= 0)
    bins   = [0, 3, 6, 12, float("inf")]
    labels = ["Less than 3m", "3-6m", "6-12m", "over1year"]
    df.loc[finite, "cov_bin"] = pd.cut(
        df.loc[finite, "coverage"],
        bins=bins,
        labels=labels,
        right=False
    ).astype(str)

    # 5. 其余（coverage < 0 或其它未命中）归 "Other"
    df["cov_bin"] = df["cov_bin"].fillna("Other")

    # 6. 聚合并绘图
    cov_pie = (
        df
        .groupby("cov_bin", as_index=False)["Inventory value"]
        .sum()
        .rename(columns={"cov_bin": "Coverage", "Inventory value": "Value"})
    )
    fig = px.pie(
        cov_pie,
        names="Coverage",
        values="Value",
        hole=0.4
    )
    fig.update_traces(textinfo="label+percent", textposition="outside",texttemplate='%{label}:%{percent:.1%}',direction = 'clockwise',domain={'x':[0,1],'y':[0,1]})
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        width=350,
        height=400,
        showlegend=False,
        margin=dict(t=0,b=0,l=0,r=0),
    )

    return dcc.Graph(
        id="coverage-pie-graph",
        figure=fig,
        config={"displayModeBar": False},
        style={
            "width": "350px",
            "height": "400px",
            "marginTop": "-100px",
            "marginLeft": "50px"
        },
        className="pie-chart-graph"
    )






@app.callback(
    Output("inventory-pie-graph", "figure"),
    [
        Input("inventory-month-selector", "value"),
        Input("pie-source-selector",      "value")
    ]
)
def update_pie_figure(selected_month, selected_category):
    global inventory_df, pads_df, disc_df

    if not selected_month or inventory_df.empty:
        return go.Figure()

    if selected_category == 'Pads':
        df = pads_df[pads_df['year_month'] == selected_month]
    elif selected_category == 'Disc':
        df = disc_df[disc_df['year_month'] == selected_month]
    else:  # Total
        df = pd.concat([pads_df, disc_df], ignore_index=True)
        df = df[df['year_month'] == selected_month]

    pie_df = df.groupby('category', as_index=False)['Inventory value'].sum()
    vals = pie_df['Inventory value']
    pct = vals / vals.sum()
    textpos = ['outside' if p < 0.05 else 'outside' for p in pct]
    fig = go.Figure(go.Pie(
        labels=pie_df['category'],
        values=pie_df['Inventory value'],
        hole=0.4,
        textinfo='label+percent',
        direction = 'clockwise',
        textposition=textpos,
        textfont=dict(size=12),
        hovertemplate="<b>%{label}</b><br>Value: ¥%{value:,.0f}<br>Percent: %{percent:.2%}<extra></extra>",
        texttemplate='%{label}:%{percent:.1%}'
    ))
    fig.update_layout(
        width=350,
        height=400,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False
    )
    fig.update_traces(insidetextorientation='horizontal')
    return fig




# ========== Run ==========
if __name__ == '__main__':
    app.run(debug=True)

