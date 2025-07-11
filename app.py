import pandas as pd
import yfinance as yf
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import time
import warnings

# Suppress yfinance warnings
warnings.filterwarnings("ignore", category=FutureWarning)

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
            # Explicitly set auto_adjust to avoid warning
            stock_data = yf.download(
                symbol, 
                start=start_date, 
                end=end_date, 
                progress=False,
                auto_adjust=True
            )
            
            if stock_data.empty:
                return None
            
            # Calculate liquidity metrics using Close
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
            
            latest_price = stock_data['Close'].iloc[-1] if not pd.isna(stock_data['Close'].iloc[-1]) else None
            
            return {
                'Symbol': symbol,
                'Avg Volume': avg_volume,
                'Avg Dollar Volume': avg_dollar_volume,
                'Avg Spread (%)': avg_spread,
                'Liquidity Score': liquidity_score,
                'Risk Level': 'High Risk' if liquidity_score < 40 else 
                             'Medium Risk' if liquidity_score < 70 else 'Low Risk',
                'Latest Price': latest_price
            }
            
        except Exception as e:
            return {
                'Symbol': symbol,
                'Avg Volume': None,
                'Avg Dollar Volume': None,
                'Avg Spread (%)': None,
                'Liquidity Score': None,
                'Risk Level': 'Error',
                'Latest Price': None
            }
    
    # Analyze all stocks with progress bar
    if st.button("Analyze All Stocks"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        
        # Process stocks in batches to avoid overwhelming the system
        batch_size = 10
        total_stocks = len(stock_list['Symbol'])
        
        for i in range(0, total_stocks, batch_size):
            batch = stock_list['Symbol'][i:i+batch_size]
            
            # Use ThreadPoolExecutor for parallel processing within the batch
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(analyze_single_stock, symbol) for symbol in batch]
                
                for future in futures:
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        st.warning(f"Error processing stock: {str(e)}")
            
            # Update progress
            progress = min((i + batch_size) / total_stocks, 1.0)
            progress_bar.progress(progress)
            status_text.text(f"Processed {min(i + batch_size, total_stocks)}/{total_stocks} stocks...")
            time.sleep(0.5)  # Small delay between batches
        
        if not results:
            st.error("No data was retrieved for any stocks. Please check your inputs and try again.")
            return
        
        # Create results dataframe
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('Liquidity Score', ascending=False)
        
        # Display results
        st.subheader("Liquidity Analysis Results")
        
        # Create a copy for display purposes
        display_df = results_df.copy()
        
        # Format numeric columns safely
        def safe_format(x, fmt):
            try:
                if pd.isna(x) or x is None:
                    return "N/A"
                return fmt.format(x)
            except:
                return "N/A"
        
        display_df['Avg Volume'] = display_df['Avg Volume'].apply(lambda x: safe_format(x, "{:,.0f}"))
        display_df['Avg Dollar Volume'] = display_df['Avg Dollar Volume'].apply(lambda x: safe_format(x, "${:,.2f}"))
        display_df['Avg Spread (%)'] = display_df['Avg Spread (%)'].apply(lambda x: safe_format(x, "{:.2f}%"))
        display_df['Liquidity Score'] = display_df['Liquidity Score'].apply(lambda x: safe_format(x, "{:.1f}"))
        display_df['Latest Price'] = display_df['Latest Price'].apply(lambda x: safe_format(x, "{:.2f}"))
        
        # Color coding for risk levels
        def color_risk(val):
            if val == 'High Risk':
                return 'color: red'
            elif val == 'Medium Risk':
                return 'color: orange'
            elif val == 'Low Risk':
                return 'color: green'
            else:
                return 'color: gray'  # For errors
        
        styled_df = display_df.style.applymap(color_risk, subset=['Risk Level'])
        st.dataframe(styled_df)
        
        # Summary statistics (only for successful analyses)
        valid_results = results_df[results_df['Risk Level'].isin(['High Risk', 'Medium Risk', 'Low Risk'])]
        
        st.subheader("Summary Statistics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Stocks Analyzed", len(results))
        with col2:
            avg_score = valid_results['Liquidity Score'].mean()
            st.metric("Average Liquidity Score", f"{avg_score:.1f}" if not pd.isna(avg_score) else "N/A")
        with col3:
            high_risk = len(valid_results[valid_results['Risk Level'] == 'High Risk'])
            st.metric("High Risk Stocks", high_risk)
        
        # Visualization (only for successful analyses)
        if not valid_results.empty:
            st.subheader("Liquidity Score Distribution")
            fig, ax = plt.subplots(figsize=(10, 6))
            valid_results['Liquidity Score'].hist(bins=20, ax=ax, color='skyblue')
            ax.set_xlabel('Liquidity Score')
            ax.set_ylabel('Number of Stocks')
            ax.set_title('Distribution of Liquidity Scores')
            st.pyplot(fig)
        else:
            st.warning("No valid data available for visualization")
        
        # Download results (original data without formatting)
        csv = results_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Results as CSV",
            data=csv,
            file_name='liquidity_analysis_results.csv',
            mime='text/csv'
        )

if __name__ == "__main__":
    analyze_liquidity_risk()
