import pandas as pd
import yfinance as yf
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np

def analyze_liquidity_risk():
    st.title("Stock Liquidity Risk Analysis")
    
    # Load stock list
    try:
        excel_file = pd.ExcelFile('stocklist.xlsx')
        
        # Get all sheet names
        sheet_names = excel_file.sheet_names
        selected_sheet = st.selectbox("Select a sheet", sheet_names)
        
        # Read the selected sheet
        stock_list = excel_file.parse(selected_sheet)
        
        # Assuming the sheet has a column named 'Symbol' containing stock tickers
        if 'Symbol' not in stock_list.columns:
            st.error("Error: The selected sheet must contain a 'Symbol' column with stock tickers.")
            return
            
        selected_stock = st.selectbox("Select a stock", stock_list['Symbol'])
        
    except FileNotFoundError:
        st.error("Error: stocklist.xlsx file not found. Please make sure stocklist.xlsx exists in the same directory.")
        return
    except Exception as e:
        st.error(f"Error reading Excel file: {str(e)}")
        return
    
    # Date range selection
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(months=6)
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start date", start_date)
    with col2:
        end_date = st.date_input("End date", end_date)
    
    if start_date >= end_date:
        st.error("Error: End date must be after start date.")
        return
    
    # For Indian stocks, add '.NS' suffix if not already present
    if selected_sheet == 'NIFTY50' and not selected_stock.endswith('.NS'):
        selected_stock += '.NS'
    
    # Fetch stock data
    try:
        stock_data = yf.download(selected_stock, start=start_date, end=end_date)
        if stock_data.empty:
            st.error(f"No data found for {selected_stock} in the selected date range.")
            return
    except Exception as e:
        st.error(f"Error fetching data for {selected_stock}: {str(e)}")
        return
    
    # Calculate liquidity metrics
    stock_data['Daily_Volume'] = stock_data['Volume']
    stock_data['Dollar_Volume'] = stock_data['Close'] * stock_data['Volume']
    stock_data['Bid_Ask_Spread'] = (stock_data['High'] - stock_data['Low']) / stock_data['Close'] * 100  # Percentage spread
    
    # Calculate rolling averages for smoother visualization
    window = 14  # 2-week rolling window
    stock_data['Rolling_Avg_Volume'] = stock_data['Daily_Volume'].rolling(window=window).mean()
    stock_data['Rolling_Avg_Dollar_Volume'] = stock_data['Dollar_Volume'].rolling(window=window).mean()
    stock_data['Rolling_Avg_Spread'] = stock_data['Bid_Ask_Spread'].rolling(window=window).mean()
    
    # Display metrics
    st.subheader(f"Liquidity Metrics for {selected_stock}")
    
    # Current metrics
    latest = stock_data.iloc[-1]
    prev_day = stock_data.iloc[-2]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Current Daily Volume", f"{latest['Daily_Volume']:,.0f}", 
                 f"{(latest['Daily_Volume'] - prev_day['Daily_Volume'])/prev_day['Daily_Volume']*100:.2f}%")
    with col2:
        st.metric("Current Dollar Volume", f"${latest['Dollar_Volume']/1e6:,.2f}M", 
                 f"{(latest['Dollar_Volume'] - prev_day['Dollar_Volume'])/prev_day['Dollar_Volume']*100:.2f}%")
    with col3:
        st.metric("Current Bid-Ask Spread", f"{latest['Bid_Ask_Spread']:.2f}%", 
                 f"{(latest['Bid_Ask_Spread'] - prev_day['Bid_Ask_Spread']):.2f}%")
    
    # Liquidity score (composite metric)
    avg_volume = stock_data['Daily_Volume'].mean()
    avg_spread = stock_data['Bid_Ask_Spread'].mean()
    
    # Normalize and weight metrics (higher volume and lower spread = better liquidity)
    volume_score = np.log10(avg_volume) / 7  # Normalize (log scale)
    spread_score = 1 - (avg_spread / 10)     # Normalize (assuming max 10% spread)
    
    liquidity_score = (volume_score * 0.6 + spread_score * 0.4) * 100  # Weighted average
    
    st.subheader("Liquidity Risk Assessment")
    
    # Display liquidity score with color coding
    if liquidity_score >= 70:
        risk_level = "Low Risk"
        color = "green"
    elif liquidity_score >= 40:
        risk_level = "Medium Risk"
        color = "orange"
    else:
        risk_level = "High Risk"
        color = "red"
    
    st.metric("Liquidity Score", f"{liquidity_score:.1f}/100", risk_level)
    st.progress(int(liquidity_score))
    
    # Visualizations
    st.subheader("Liquidity Trends")
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 12))
    
    # Volume plot
    ax1.plot(stock_data.index, stock_data['Rolling_Avg_Volume'], label='14-day Avg Volume', color='blue')
    ax1.set_ylabel('Volume')
    ax1.set_title('Trading Volume Trend')
    ax1.grid(True)
    
    # Dollar volume plot
    ax2.plot(stock_data.index, stock_data['Rolling_Avg_Dollar_Volume']/1e6, label='14-day Avg Dollar Volume', color='green')
    ax2.set_ylabel('Dollar Volume ($M)')
    ax2.set_title('Dollar Volume Trend')
    ax2.grid(True)
    
    # Spread plot
    ax3.plot(stock_data.index, stock_data['Rolling_Avg_Spread'], label='14-day Avg Spread', color='red')
    ax3.set_ylabel('Bid-Ask Spread (%)')
    ax3.set_title('Bid-Ask Spread Trend')
    ax3.grid(True)
    
    plt.tight_layout()
    st.pyplot(fig)
    
    # Display raw data
    if st.checkbox("Show raw data"):
        st.subheader("Raw Data")
        st.dataframe(stock_data[['Close', 'Volume', 'Daily_Volume', 'Dollar_Volume', 'Bid_Ask_Spread']].sort_index(ascending=False))
    
    # Interpretation
    st.subheader("Interpretation Guide")
    st.markdown("""
    - **Liquidity Score**: Composite metric (0-100) combining trading volume and bid-ask spread
        - 70-100: Low liquidity risk (easy to trade without significant price impact)
        - 40-69: Medium liquidity risk (moderate price impact possible)
        - 0-39: High liquidity risk (difficult to trade without moving the price)
    - **Trading Volume**: Higher is generally better for liquidity
    - **Dollar Volume**: Volume in dollar terms (accounts for stock price)
    - **Bid-Ask Spread**: Lower is better (percentage difference between highest bid and lowest ask)
    """)

if __name__ == "__main__":
    analyze_liquidity_risk()
