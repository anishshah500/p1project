import os
import sys
import dash
import plotly.graph_objs as go
import flask
import dash_table as dt

from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from dash_table import DataTable

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from analytics import *

a = Analytics()
tickers = a.dc.get_tickers()

ticker_options = [{"label": ticker, "value": ticker} for ticker in tickers]
correlation_method_options = [
    {"label": "pearson", "value": "pearson"},
    {"label": "spearman", "value": "spearman"},
    {"label": "kalman", "value": "kalman"}
]

server = flask.Flask(__name__)
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])

# App layout
app.layout = dbc.Container(
    [
        dbc.Row(dbc.Col(html.H1("Equities Pair Trading Dashboard"), className="mb-4")),

        dbc.Row(dbc.Col(dbc.Card(
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(html.H4('Correlation Type'), width=2),
                            dbc.Col(dcc.Dropdown(id="correlation_method", options=correlation_method_options, value="pearson"), width=10)
                        ],
                        className="mb-3"
                    ),
                    dbc.Row(
                        [
                            dbc.Col(html.H4('Date Range'), width=2),
                            dbc.Col(dcc.DatePickerRange(id="date-picker", start_date="2023-01-01", end_date="2023-12-31"), width=10)
                        ],
                        className="mb-3"
                    ),
                    dbc.Row(
                        [
                            dbc.Col(html.H4('Top N'), width=2),
                            dbc.Col(dcc.Input(id="top_n", type="number", value=10), width=10)
                        ],
                        className="mb-3"
                    ),
                    dbc.Row(dbc.Col(dbc.Button("Submit", id="submit-button", n_clicks=0, color="primary"), className="d-flex justify-content-end"))
                ]
            ),
            className="mb-4"
        ))),

        dbc.Row(dbc.Col(html.Div(id='pairs'))),

        dbc.Row(dbc.Col(html.H6("Please Note: In case OU fit doesn't converge, mean reversion speed defaults to 0.5", className="mb-4"))),

        dbc.Row(dbc.Col(dbc.Card(
            dbc.CardBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(html.H4('Ticker1'), width=2),
                            dbc.Col(dcc.Dropdown(id="Ticker1", options=ticker_options, value="AAPL"), width=10)
                        ],
                        className="mb-3"
                    ),
                    dbc.Row(
                        [
                            dbc.Col(html.H4('Ticker2'), width=2),
                            dbc.Col(dcc.Dropdown(id="Ticker2", options=ticker_options, value="MSFT"), width=10)
                        ],
                        className="mb-3"
                    ),
                    dbc.Row(
                        [
                            dbc.Col(html.H4('Lookback Window for Ratio Quantile'), width=2),
                            dbc.Col(dcc.Input(id="lookback", type="number", value=63), width=10)
                        ],
                        className="mb-3"
                    ),
                    dbc.Row(
                        [
                            dbc.Col(html.H4('Price Ratio Z-score Quantile for Long'), width=2),
                            dbc.Col(dcc.Slider(id="long_q", min=-3, max=0, step=0.25, value=-1), width=10)
                        ],
                        className="mb-3"
                    ),
                    dbc.Row(
                        [
                            dbc.Col(html.H4('Price Ratio Z-score Quantile for Short'), width=2),
                            dbc.Col(dcc.Slider(id="short_q", min=0, max=3, step=0.25, value=1), width=10)
                        ],
                        className="mb-3"
                    ),
                    dbc.Row(
                        [
                            dbc.Col(html.H4('Hold Period for trade'), width=2),
                            dbc.Col(dcc.Input(id="hold_days", type="number", value=2), width=10)
                        ],
                        className="mb-3"
                    ),
                    dbc.Row(dbc.Col(dbc.Button("Backtest", id="submit-button1", n_clicks=0, color="primary"), className="d-flex justify-content-end"))
                ]
            ),
            className="mb-4"
        ))),

        dbc.Row(dbc.Col(html.Div(id='performance-metrics', className="mb-4"))),

        dbc.Row(dbc.Col(html.Div(dcc.Graph(id="correlation-graph"), className="mb-4"))),

        dbc.Row(dbc.Col(html.Div(dcc.Graph(id="backtest-graph"), className="mb-4")))
    ],
    fluid=True
)

@app.callback(
    Output("pairs", "children"),
    [Input("submit-button", "n_clicks")],
    [State("correlation_method", "value"), State("top_n", "value"), State("date-picker", "start_date"), State("date-picker", "end_date")]
)
def update_dashboard(n_clicks, corr_method, top_n, start_date, end_date):
    # Correlation app
    if n_clicks > 0:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Pull data
        a.set_data_df(start_date, end_date)
        
        top_pairs = a.get_output_df(corr_method, top_n).round(3)

        pairs = DataTable(
            columns=[{"name": i, "id": i} for i in top_pairs.columns],
            data=top_pairs.to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left',
                'padding': '5px'
            },
            style_header={
                'backgroundColor': 'lightgrey',
                'fontWeight': 'bold'
            },
            page_action='native',
            page_size=10,
            filter_action='native',
            sort_action='native'
        )

        return pairs

@app.callback(
    [Output("performance-metrics", "children"),
     Output("correlation-graph", "figure"),
     Output("backtest-graph", "figure")],
    [Input("submit-button1", "n_clicks")],
    [State("date-picker", "start_date"), State("date-picker", "end_date"),
     State("Ticker1", "value"), State("Ticker2", "value"),
     State("lookback", "value"), State("long_q", "value"),
     State("short_q", "value"), State("hold_days", "value")]
)
def update_dashboard1(n_bt_clicks, start_date, end_date, ticker1, ticker2, lookback, long_q, short_q, hold_days):
    # Backtest app
    if n_bt_clicks:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Pull data
        a.set_data_df((start_date - pd.offsets.BusinessDay(lookback)).date(), end_date)

        output = a.perform_backtest(ticker1, ticker2, lookback, long_q, short_q, hold_days)

        performance = pd.DataFrame(output["performance_metrics"]).round(2)
        performance_table = DataTable(
            columns=[{"name": i, "id": i} for i in performance.columns],
            data=performance.to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left',
                'padding': '5px'
            },
            style_header={
                'backgroundColor': 'lightgrey',
                'fontWeight': 'bold'
            },
            page_action='native',
            page_size=5,
            filter_action='native',
            sort_action='native'
        )

        ret_df = output["filtered_df"].loc[:, [ticker1, ticker2]]
        ret_df = (ret_df / ret_df.shift(1) - 1).dropna()
        ret_df["rolling_correlation"] = ret_df[ticker1].rolling(lookback).corr(ret_df[ticker2])
        ret_df.dropna(inplace=True)

        correlation_figure = go.Figure()
        correlation_figure.add_trace(go.Scatter(x=ret_df.index, y=ret_df["rolling_correlation"], name="Rolling Correlation"))
    
        backtest_figure = go.Figure()
        backtest_figure.add_trace(go.Scatter(x=output["filtered_df"].index, y=output["filtered_df"]["total_pnl"], name="Cumulative Returns"))

        return performance_table, correlation_figure, backtest_figure
    
    return [], go.Figure(), go.Figure()

if __name__ == '__main__':
    app.run_server(debug=True)
