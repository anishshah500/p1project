import pandas as pd
import numpy as np
import statsmodels.api as sm
import warnings

from pymongo import MongoClient
from statsmodels.tsa.stattools import adfuller
from statsmodels.regression.rolling import RollingOLS
from matplotlib import pyplot as plt
from sklearn.linear_model import LinearRegression
from pykalman import KalmanFilter
from scipy.stats import zscore

warnings.simplefilter(action='ignore', category=FutureWarning)

class Analytics():
    """
    A class to analyze the data. 
    """
    
    def __init__(self, force_refresh=False):
        """
        Initialize the Analyzer.
        """
        self.dc = DataLoader(start_date_limit, end_date_limit)
        self.df = self.dc.get_equities_data(force_refresh)
        self.df.set_index("Date", inplace=True)
        self.df.index = pd.to_datetime(self.df.index).date
        
        self.returns_df = self.df / self.df.shift(1) - 1

    def calculate_correlations_pearson(self, start_date, end_date):
        """
        Calculate the correlations between the securities.
        """
        filtered_df = self.returns_df.loc[start_date:end_date]
        
        # Calculate the correlation matrix
        corr_matrix = filtered_df.corr()
    
        # Get pairwise correlations
        corr_pairs = pd.DataFrame(corr_matrix.unstack())
        corr_pairs.columns = ["corr"]
        corr_pairs.index.names = ["Ticker1", "Ticker2"]
        corr_pairs = corr_pairs.reset_index().dropna()
    
        # Remove duplicate pairs and self-correlations
        corr_pairs = corr_pairs[corr_pairs['Ticker1'] != corr_pairs['Ticker2']]
        corr_pairs = corr_pairs.drop_duplicates(subset=["Ticker1", "Ticker2"])
        corr_pairs = corr_pairs[corr_pairs['Ticker1'] < corr_pairs['Ticker2']]
    
        corr_pairs = corr_pairs.sort_values(by="corr", key = lambda x: abs(x), ascending=False)
        return corr_pairs

    def calculate_correlations_spearman(self, start_date, end_date):
        """
        Calculate the correlations between the securities.
        """
        filtered_df = self.returns_df.loc[start_date:end_date]
        
        # Calculate the correlation matrix using Spearman rank
        corr_matrix = filtered_df.corr(method="spearman")
        
        # Get pairwise correlations
        corr_pairs = pd.DataFrame(corr_matrix.unstack())
        corr_pairs.columns = ["corr"]
        corr_pairs.index.names = ["Ticker1", "Ticker2"]
        corr_pairs = corr_pairs.reset_index().dropna()
        
        # Remove duplicate pairs and self-correlations
        corr_pairs = corr_pairs[corr_pairs['Ticker1'] != corr_pairs['Ticker2']]
        corr_pairs = corr_pairs.drop_duplicates(subset=["Ticker1", "Ticker2"])
        corr_pairs = corr_pairs[corr_pairs['Ticker1'] < corr_pairs['Ticker2']]
        
        corr_pairs = corr_pairs.sort_values(by="corr", key = lambda x: abs(x), ascending=False)
        return corr_pairs

    def get_t_statistics(self, dependent, independent):
        """
        Calculate the t-statistics for the coefficients.
        """
        # Add a constant to the independent variable for the intercept
        X = sm.add_constant(independent)
        
        # Fit the OLS model
        model = sm.OLS(dependent, X).fit()
        
        # Extract t-statistics for coefficients
        t_stats = model.tvalues
        return t_stats

    def calculate_correlations_OLS(self, start_date, end_date):
        """
        Calculate the correlations between the securities using OLS.
        """
        filtered_df = self.returns_df.loc[start_date:end_date]
        filtered_df = filtered_df.dropna(axis=1, how='all')

        cov = filtered_df.cov()
        var = np.diag(cov)
        
        # Calculate Betas for each pair of assets (X vs Y)
        betas = []
        assets = cov.index

        for i, asset_x in enumerate(assets):
            for j, asset_y in enumerate(assets):
                if i != j:
                    cov_xy = cov.values[i, j]
                    var_y = var[j]
                    beta_xy = cov_xy / var_y
                    betas.append([asset_x, asset_y, beta_xy])

        betas = pd.DataFrame(betas, columns = ["stock1", "stock2", "beta"])
        
        results = betas.sort_values(by="beta", key = lambda x: abs(x), ascending=False)
        return results

    def kalman_filter_analysis(self, stock_a, stock_b, filtered_df):
        """
        Perform Kalman filter analysis on the data.
        """
        data = filtered_df.loc[:, [stock_a, stock_b]].dropna()

        # Initialize Kalman Filter
        initial_state_mean = np.array([data[stock_a].iloc[0], data[stock_b].iloc[0]])
        transition_matrix = np.eye(2)
        observation_matrix = np.array([[1, 0], [0, 1]])
        observation_variance = np.diag([0.1, 0.1])

        # Perform Kalman Filter
        kf = KalmanFilter(
            initial_state_mean=initial_state_mean,
            observation_matrices=observation_matrix,
            observation_covariance=observation_variance,
            transition_matrices=transition_matrix
        )
        state_means, _ = kf.filter(data.values)

        # Extract correlation from smooth prices
        estimated_prices = pd.DataFrame(state_means, columns=[stock_a, stock_b], index=data.index)
        correlation = estimated_prices[stock_a].corr(estimated_prices[stock_b])
        return correlation

    def calculate_correlations_kalman(self, start_date, end_date):
        """
        Calculate the correlations between the securities using Kalman filter.
        """
        filtered_df = self.returns_df.loc[start_date:end_date]

        # Compute kalman means for all pairs
        results, calced = [], set()
        
        for stock1 in filtered_df.columns:
            for stock2 in filtered_df.columns:
              key = sorted([stock1, stock2])
              if tuple(key) not in calced:
                if stock1 != stock2:
                  calced.add(tuple(key))
                  kalman_corr = self.kalman_filter_analysis(stock1, stock2, filtered_df)
                  results.append([stock1, stock2, kalman_corr])

        results = pd.DataFrame(results, columns=["stock1", "stock2", "kalman_corr"])
        results = results.sort_values(by="kalman_corr", key = lambda x: abs(x), ascending=False)
        return results

    def calculate_mean_reversion_speed(self, ticker1, ticker2, start_date, end_date):
        """
        Calculate the mean reversion speed between two securities.
        """
        filtered_df = self.returns_df.loc[start_date:end_date]

        returns1 = filtered_df[ticker1]
        returns2 = filtered_df[ticker2]

        # Create time lagged return spread
        spread = returns1 - returns2
        spread_lagged = spread.shift(1).dropna()
        spread = spread[1:]
        X = sm.add_constant(spread_lagged)
        y = spread

        # Estimate speed of mean reversion
        model = sm.OLS(y, X).fit()
        beta = model.params[0]
        delta_t = 1
        theta = (1 - beta) / delta_t
        
        return theta

    def get_output_df(self, method, start_date, end_date, num_pairs):
        """
        Get the outputs dataframe.
        """
        if method == "pearson":
            corr_pairs = self.calculate_correlations_pearson(start_date, end_date)
        elif method == "spearman":
            corr_pairs = self.calculate_correlations_spearman(start_date, end_date)
        elif method == "OLS":
            corr_pairs = self.calculate_correlations_OLS(start_date, end_date)
        elif method == "kalman":
            corr_pairs = self.calculate_correlations_kalman(start_date, end_date)
        else:
            raise ValueError("Invalid method. Must be 'pearson', 'spearman', or 'OLS'.")

        # Get the top num_pairs pairs
        top_pairs = corr_pairs.head(num_pairs)
        top_pairs = top_pairs.rename(columns = {"corr": "corr_" + method})
        # top_pairs['mean_reversion_speed'] = top_pairs.apply(lambda row: 
        #                                                     self.calculate_mean_reversion_speed(row['Ticker1'], row['Ticker2'], 
        #                                                                                         start_date, end_date), 
        #                                                     axis=1)

        return top_pairs


    def calculate_performance_metrics(self, cumulative_pnl_series):
        """
        Calc Metrics
        """
        # Calculate daily returns
        returns = cumulative_pnl_series.diff().dropna()
    
        # # Total Return
        # total_return = cumulative_pnl_series.iloc[-1] / cumulative_pnl_series.iloc[0] - 1
    
        # Annualized Return
        annualized_return = np.mean(returns) * np.sqrt(252)
    
        # # Annualized Volatility
        annualized_volatility = returns.std() * np.sqrt(252)
    
        # Sharpe Ratio (Assuming risk-free rate is 0 for simplicity)
        sharpe_ratio = annualized_return / annualized_volatility if annualized_volatility != 0 else np.nan
    
        # Sortino Ratio (Assuming risk-free rate is 0 for simplicity)
        downside_returns = returns[returns < 0]
        downside_volatility = downside_returns.std() * np.sqrt(252) if not downside_returns.empty else np.nan
        sortino_ratio = annualized_return / downside_volatility if downside_volatility != 0 else np.nan
    
        # Maximum Drawdown
        cumulative_returns = cumulative_pnl_series / cumulative_pnl_series.cummax() - 1
        max_drawdown = cumulative_returns.min()
    
        # Create a DataFrame with the results
        metrics = pd.DataFrame({
            'Sharpe Ratio': [sharpe_ratio],
            'Sortino Ratio': [sortino_ratio],
            'Maximum Drawdown': [max_drawdown]
        })
    
        return metrics

    def perform_backtest(self, ticker1, ticker2, start_date, end_date, lookback, low_quantile, high_quantile, hold_days):
        """
        Perform backtesting on the data.
        """
        # Calculate rolling z-score for ratio
        filtered_df = a.df.loc[(start_date - pd.offsets.BusinessDay(lookback)).date():end_date].loc[:,[ticker1, ticker2]]
        filtered_df["ret_" + ticker1] = filtered_df[ticker1].diff()
        filtered_df["ret_" + ticker2] = filtered_df[ticker2].diff()
        filtered_df["tomm_PnL_" + ticker1] = filtered_df["ret_" + ticker1].shift(-1)
        filtered_df["tomm_PnL_" + ticker2] = filtered_df["ret_" + ticker2].shift(-1)
        filtered_df["ratio"] = filtered_df[ticker1] / filtered_df[ticker2]
        filtered_df["rolling_mean"] = filtered_df["ratio"].rolling(window=lookback).mean()
        filtered_df["rolling_std"] = filtered_df["ratio"].rolling(window=lookback).std()
        filtered_df["rolling_zscore"] = (filtered_df["ratio"] - filtered_df["rolling_mean"]) / filtered_df["rolling_std"]
        filtered_df = filtered_df.dropna()
        
        # Calculate long and short signals
        filtered_df["long_signal"] = np.where(filtered_df["rolling_zscore"] < low_quantile, 1, 0)
        filtered_df["short_signal"] = np.where(filtered_df["rolling_zscore"] > high_quantile, 1, 0)
        
        filtered_df["long_signal1"] = filtered_df["long_signal"]
        filtered_df["short_signal1"] = filtered_df["short_signal"]
        
        # Adjust for hold_days
        for i in range(len(filtered_df)):
            if filtered_df['long_signal'].iloc[i] == 1:
                end_date = pd.to_datetime(filtered_df.index[i] + pd.offsets.BusinessDay(hold_days-1)).date()
                mask = (filtered_df.index >= filtered_df.index[i]) & (filtered_df.index <= end_date)
                filtered_df.loc[mask, 'long_signal1'] = 1
            if filtered_df['short_signal'].iloc[i] == 1:
                end_date = pd.to_datetime(filtered_df.index[i] + pd.offsets.BusinessDay(hold_days-1)).date()
                mask = (filtered_df.index >= filtered_df.index[i]) & (filtered_df.index <= end_date)
                filtered_df.loc[mask, 'short_signal1'] = 1
        
        filtered_df["long_signal"] = filtered_df["long_signal1"]
        filtered_df["short_signal"] = filtered_df["short_signal1"]
        filtered_df.drop(columns=["long_signal1", "short_signal1"], inplace=True)
        
        # Calculate PnL
        filtered_df["long_pnl"] = 0
        filtered_df["long_pnl"] = filtered_df["tomm_PnL_" + ticker1] * filtered_df["long_signal"]
        filtered_df["long_pnl"] -= filtered_df["tomm_PnL_" + ticker2] * filtered_df["long_signal"]
        filtered_df["short_pnl"] = -filtered_df["tomm_PnL_" + ticker1] * filtered_df["short_signal"] 
        filtered_df["short_pnl"] += filtered_df["tomm_PnL_" + ticker2] * filtered_df["short_signal"]
        filtered_df["pnl"] = filtered_df["long_pnl"] + filtered_df["short_pnl"]
        
        filtered_df["total_pnl"] = filtered_df["pnl"].cumsum()

        performance_metrics = self.calculate_performance_metrics(filtered_df["total_pnl"])
        return {"performance_metrics": performance_metrics, "filtered_df": filtered_df}