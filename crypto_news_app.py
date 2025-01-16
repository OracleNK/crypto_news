import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import re
import plotly.express as px

# Configure page settings
st.set_page_config(
    page_title="Crypto News Dashboard",
    page_icon="📰",
    layout="wide"
)

# Add custom CSS
st.markdown("""
    <style>
        .stTitle {
            font-size: 42px !important;
            font-weight: bold;
            color: #0e1117;
        }
        .news-box {
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        .source-tag {
            color: #666;
            font-size: 0.8em;
        }
        .time-tag {
            color: #666;
            font-size: 0.8em;
        }
        
        h4{
            font-family: "Source Sans Pro", sans-serif;
    font-weight: 600;
    color: #000000;
    letter-spacing: -0.005em;
    padding: 0.5rem 0px 1rem;
    margin: 0px;
    line-height: 1.2;
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_news():
    """Fetch crypto news from Google News RSS feed"""
    url = "https://news.google.com/rss/search?q=cryptocurrency+OR+bitcoin+OR+crypto&hl=en-US&gl=US&ceid=US:en"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, features='xml')
        items = soup.find_all('item')
        
        news_items = []
        for item in items:
            summary_html = item.description.text if item.description else ''
            
            # Extract source and clean summary
            source = ''
            if '</a>' in summary_html:
                source = BeautifulSoup(summary_html.split('</a>')[-1], 'html.parser').get_text().strip()
            
            # Extract link
            link = ''
            link_tag = BeautifulSoup(summary_html, 'html.parser').find('a')
            if link_tag:
                link = link_tag.get('href', '')
            
            news_item = {
                'title': item.title.text if item.title else '',
                'link': link,
                'source': source,
                'published_date': item.pubDate.text if item.pubDate else '',
                'timestamp': pd.to_datetime(item.pubDate.text) if item.pubDate else pd.Timestamp.now()
            }
            news_items.append(news_item)
            
        return pd.DataFrame(news_items)
            
    except Exception as e:
        st.error(f"Error fetching news: {str(e)}")
        return pd.DataFrame()

def main():
    # Header
    st.title("🚀 Crypto News Live Dashboard")
    
    # Fetch news
    news_df = fetch_news()
    
    if news_df.empty:
        st.warning("No news available at the moment. Please try again later.")
        return
    
    # Dashboard layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📰 Latest News")
        
        # News display with filtering
        sources = ['All'] + sorted(news_df['source'].unique().tolist())
        selected_source = st.selectbox("Filter by Source:", sources)
        
        filtered_df = news_df
        if selected_source != 'All':
            filtered_df = news_df[news_df['source'] == selected_source]
        
        for _, row in filtered_df.iterrows():
            with st.container():
                st.markdown(f"""
                    <div class="news-box">
                        <h4>{row['title']}</h4>
                        <p class="source-tag">Source: {row['source']}</p>
                        <p class="time-tag">Published: {row['published_date']}</p>
                        <a href="{row['link']}" target="_blank">Read more</a>
                    </div>
                """, unsafe_allow_html=True)
    
    with col2:
        st.subheader("📊 News Statistics")
        
        # News by source chart
        source_counts = news_df['source'].value_counts().reset_index()
        source_counts.columns = ['Source', 'Count']
        
        fig = px.pie(source_counts, values='Count', names='Source',
                    title='News Distribution by Source')
        st.plotly_chart(fig, use_container_width=True)
        
        # News timeline
        st.subheader("📅 Publication Timeline")
        timeline_df = news_df.copy()
        timeline_df['hour'] = timeline_df['timestamp'].dt.hour
        hourly_counts = timeline_df['hour'].value_counts().sort_index().reset_index()
        hourly_counts.columns = ['Hour', 'Count']
        
        fig = px.bar(hourly_counts, x='Hour', y='Count',
                    title='News Publication by Hour')
        st.plotly_chart(fig, use_container_width=True)
        
        # Stats
        st.subheader("📈 Quick Stats")
        total_news = len(news_df)
        total_sources = len(news_df['source'].unique())
        latest_update = news_df['timestamp'].max()
        
        st.metric("Total News Articles", total_news)
        st.metric("Total Sources", total_sources)
        st.metric("Latest Update", latest_update.strftime('%Y-%m-%d %H:%M:%S'))

    # Auto-refresh
    time_placeholder = st.empty()
    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.experimental_rerun()
    
    # Show last update time
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()