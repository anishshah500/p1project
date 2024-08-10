import dash
import plotly.graph_objs as go

from dash import dcc, html, Input, Output, State
from dash_table import DataTable
from datetime import datetime

a = Analytics()
data = a.returns_df

ticker_options = [{"label": ticker, "value": ticker} for ticker in list(data.columns)]
correlation_method_options = [
    {"label": "pearson", "value": "pearson"},
    {"label": "spearman", "value": "spearman"},
    {"label": "OLS", "value": "OLS"},
    {"label": "kalman", "value": "kalman"}
]

app = dash.Dash(__name__)
server = app.server

# App layout
app.layout = html.Div(
    [
        html.H1("Equities Pair Trading Dashboard"),
        html.Div(id='input-section', children = 
                [
                    html.H4('Correlation Name',style={'display':'inline-block','margin-right':20}),
                    dcc.Dropdown(id="correlation_method", options=correlation_method_options, value="pearson"),
                    html.H4('Date Range',style={'display':'inline-block','margin-right':20}),
                    dcc.DatePickerRange(id="date-picker", start_date="2023-01-01", end_date="2023-12-31"),
                    html.Br(),
                    html.H4('Top N',style={'display':'inline-block','margin-right':20}),
                    dcc.Input(id="top_n", type="number", value=10),
                    html.Br(),
                    html.Button(id="submit-button", n_clicks=0, children="Submit")
                ]),
        html.Div(id='pairs'),
        html.Div(id='input-section1', children = 
                [
                    html.H4('Ticker1',style={'display':'inline-block','margin-right':20}),
                    dcc.Dropdown(id="Ticker1", options=ticker_options, value="AAPL"),
                    html.H4('Ticker2',style={'display':'inline-block','margin-right':20}),
                    dcc.Dropdown(id="Ticker2", options=ticker_options, value="MSFT"),
                    html.H4('Lookback Window for Ratio Quantile',style={'display':'inline-block','margin-right':20}),
                    dcc.Input(id="lookback", type="number", value=63),
                    html.Br(),
                    html.H4('Long Ratio Z-score Quantile',style={'display':'inline-block','margin-right':20}),
                    dcc.Slider(id="long_q", min=-3, max=0, step=0.25, value=-1),
                    html.H4('Short Ratio Z-score Quantile',style={'display':'inline-block','margin-right':20}),
                    dcc.Slider(id="short_q", min=0, max=3, step=0.25, value=1),
                    html.H4('Hold Period for trade',style={'display':'inline-block','margin-right':20}),
                    dcc.Input(id="hold_days", type="number", value=2),
                    html.Br(),
                    html.Button(id="submit-button1", n_clicks=0, children="Backtest")
                ]),
        html.H4('Performance Metrics',style={'display':'inline-block','margin-right':20}),
        html.Div(id='performance-metrics'),
        html.H4('Rolling Correlation',style={'display':'inline-block','margin-right':20}),
        dcc.Graph(id="correlation-graph"),
        html.H4('Cumulative PnL from backtest',style={'display':'inline-block','margin-right':20}),
        dcc.Graph(id="backtest-graph")
    ])

@app.callback(
    Output("pairs", "children"),
    [Input("submit-button", "n_clicks")],
    [dash.dependencies.State("correlation_method", "value"), 
     dash.dependencies.State("top_n", "value"), 
     dash.dependencies.State("date-picker", "start_date"), 
     dash.dependencies.State("date-picker", "end_date")] 
)
def update_dashboard(n_clicks, corr_method, top_n, start_date, end_date):
	# Correlation app
    if n_clicks > 0:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        top_pairs = a.get_output_df(corr_method, start_date, end_date, 10).round(3)

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
            page_size=5,
            filter_action='native',
            sort_action='native'
        )

        return pairs

@app.callback(
    [Output("performance-metrics", "children"),
    Output("correlation-graph", "figure"), 
    Output("backtest-graph", "figure")],
    [Input("input-section1", "n_clicks")],
    [dash.dependencies.State("date-picker", "start_date"), 
     dash.dependencies.State("date-picker", "end_date"),
     dash.dependencies.State("Ticker1", "value"),
     dash.dependencies.State("Ticker2", "value"),
     dash.dependencies.State("lookback", "value"),
     dash.dependencies.State("long_q", "value"), 
     dash.dependencies.State("short_q", "value"),
     dash.dependencies.State("hold_days", "value")]
)
def update_dashboard1(n_bt_clicks, start_date, end_date, ticker1, ticker2, lookback, long_q, short_q, hold_days):
	# Backtest app
    if n_bt_clicks:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        output = a.perform_backtest(ticker1, ticker2, start_date, end_date, lookback, long_q, short_q, hold_days)

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