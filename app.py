import pandas as pd
import yfinance as yf
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import time

def analyze_liquidity_risk():
    st.title("Stock Liquidity Risk Analysis - Bulk Processing")
    
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
            
        # For Indian stocks, add '.NS' suffix if not already present
        if selected_sheet == 'NIFTY50':
            stock_list['Symbol'] = stock_list['Symbol'].apply(lambda x: x if x.endswith('.NS') else x + '.NS')
            
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
    
    # Function to fetch and analyze a single stock
    def analyze_single_stock(symbol):
        try:
            stock_data = yf.download(symbol, start=start_date, end=end_date, progress=False)
            if stock_data.empty:
                return None
            
            # Calculate liquidity metrics
            stock_data['Daily_Volume'] = stock_data['Volume']
            stock_data['Dollar_Volume'] = stock_data['Close'] * stock_data['Volume']
            stock_data['Bid_Ask_Spread'] = (stock_data['High'] - stock_data['Low']) / stock_data['Close'] * 100
            
            # Calculate averages
            avg_volume = stock_data['Daily_Volume'].mean()
            avg_dollar_volume = stock_data['Dollar_Volume'].mean()
            avg_spread = stock_data['Bid_Ask_Spread'].mean()
            
            # Calculate liquidity score
            volume_score = np.log10(avg_volume) / 7 if avg_volume > 0 else 0
            spread_score = 1 - (avg_spread / 10) if avg_spread > 0 else 0
            liquidity_score = (volume_score * 0.6 + spread_score * 0.4) * 100
            
            return {
                'Symbol': symbol,
                'Avg Volume': avg_volume,
                'Avg Dollar Volume': avg_dollar_volume,
                'Avg Spread (%)': avg_spread,
                'Liquidity Score': liquidity_score,
                'Risk Level': 'High Risk' if liquidity_score < 40 else 
                             'Medium Risk' if liquidity_score < 70 else 'Low Risk',
                'Latest Price': stock_data['Close'].iloc[-1]
            }
            
        except Exception as e:
            st.warning(f"Error analyzing {symbol}: {str(e)}")
            return None
    
    # Analyze all stocks with progress bar
    if st.button("Analyze All Stocks"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for symbol in stock_list['Symbol']:
                futures.append(executor.submit(analyze_single_stock, symbol))
            
            for i, future in enumerate(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    st.warning(f"Error processing stock: {str(e)}")
                
                # Update progress
                progress = (i + 1) / len(futures)
                progress_bar.progress(progress)
                status_text.text(f"Processing {i+1}/{len(futures)} stocks...")
                time.sleep(0.1)  # Small delay for UI update
        
        if not results:
            st.error("No data was retrieved for any stocks. Please check your inputs.")
            return
        
        # Create results dataframe
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('Liquidity Score', ascending=False)
        
        # Display results
        st.subheader("Liquidity Analysis Results")
        
        # Color coding for risk levels
        def color_risk(val):
            color = 'red' if val == 'High Risk' else 'orange' if val == 'Medium Risk' else 'green'
            return f'color: {color}'
        
        styled_df = results_df.style.applymap(color_risk, subset=['Risk Level'])
        st.dataframe(styled_df.format({
            'Avg Volume': '{:,.0f}',
            'Avg Dollar Volume': '${:,.2f}',
            'Avg Spread (%)': '{:.2f}%',
            'Liquidity Score': '{:.1f}',
            'Latest Price': '{:.2f}'
        }))
        
        # Summary statistics
        st.subheader("Summary Statistics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Stocks Analyzed", len(results))
        with col2:
            st.metric("Average Liquidity Score", f"{results_df['Liquidity Score'].mean():.1f}")
        with col3:
            high_risk = len(results_df[results_df['Risk Level'] == 'High Risk'])
            st.metric("High Risk Stocks", high_risk)
        
        # Visualization
        st.subheader("Liquidity Score Distribution")
        fig, ax = plt.subplots(figsize=(10, 6))
        results_df['Liquidity Score'].hist(bins=20, ax=ax, color='skyblue')
        ax.set_xlabel('Liquidity Score')
        ax.set_ylabel('Number of Stocks')
        ax.set_title('Distribution of Liquidity Scores')
        st.pyplot(fig)
        
        # Download results
        csv = results_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Results as CSV",
            data=csv,
            file_name='liquidity_analysis_results.csv',
            mime='text/csv'
        )

if __name__ == "__main__":
    analyze_liquidity_risk()
