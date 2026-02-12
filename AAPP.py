import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from fpdf import FPDF
import base64
import os
import plotly.graph_objects as go 
from datetime import datetime

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="PRIME Terminal Pro", page_icon="🛡️", layout="wide")

# =========================================================
# SYSTEM: DATA CACHING & ROBUSTNESS
# =========================================================

# Funcție pentru a extrage date chiar dacă Yahoo e supărat
@st.cache_data(ttl=600, show_spinner=False)
def get_robust_data(ticker):
    stock = yf.Ticker(ticker)
    
    # 1. ISTORIC (Merge 99% din timp)
    try:
        history = stock.history(period="2y") # Luăm 2 ani pentru SMA200
    except:
        history = pd.DataFrame()

    # 2. INFO (Pică des, folosim fallback)
    info = {}
    try:
        info = stock.info
    except:
        pass # Ignorăm eroarea, încercăm metoda Fast
    
    # 3. FAST INFO (Backup solid)
    # Dacă info e gol sau are puține chei, completăm cu fast_info
    if not info or len(info) < 5:
        try:
            fast = stock.fast_info
            # Reconstruim manual dicționarul info
            info['currentPrice'] = fast.last_price
            info['marketCap'] = fast.market_cap
            info['previousClose'] = fast.previous_close
            info['currency'] = fast.currency
            # Putem estima volumul mediu
            info['averageVolume'] = history['Volume'].mean() if not history.empty else 0
        except:
            pass

    return history, info

# =========================================================
# LOGICA DE CALCUL (COMPLEXĂ)
# =========================================================

def calculate_technicals(df):
    if df.empty: return {}
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # SMA (Medii Mobile)
    sma_50 = df['Close'].rolling(window=50).mean()
    sma_200 = df['Close'].rolling(window=200).mean()
    
    return {
        'RSI': rsi.iloc[-1],
        'SMA_50': sma_50.iloc[-1],
        'SMA_200': sma_200.iloc[-1],
        'Last_Close': df['Close'].iloc[-1]
    }

def calculate_prime_score(info, tech_data, history):
    score = 0
    reasons = []
    
    # A. ANALIZĂ TEHNICĂ (Mereu Disponibilă) - Max 50p
    if tech_data:
        # 1. Trend pe termen lung
        if tech_data['Last_Close'] > tech_data['SMA_200']:
            score += 15
            reasons.append("Trend Ascendent (Peste media de 200 zile)")
        else:
            reasons.append("Trend Descendent (Sub media de 200 zile)")
            
        # 2. Momentum RSI
        rsi = tech_data['RSI']
        if 40 < rsi < 70:
            score += 15
            reasons.append("Momentum Sănătos (RSI Neutru)")
        elif rsi <= 30:
            score += 10
            reasons.append("Posibil Oversold (RSI Mic - Oportunitate?)")
            
        # 3. Volatilitate (Risk)
        daily_ret = history['Close'].pct_change()
        vol = daily_ret.std() * np.sqrt(252)
        if vol < 0.35: # Volatilitate sub 35%
            score += 20
            reasons.append("Volatilitate Controlată")
        else:
            score += 5
            reasons.append("Volatilitate Ridicată")

    # B. ANALIZĂ FUNDAMENTALĂ (Dacă avem date) - Max 50p
    # Dacă nu avem info, redistribuim punctele tehnic
    has_fundamentals = 'trailingPE' in info or 'revenueGrowth' in info
    
    if has_fundamentals:
        pe = info.get('trailingPE', 100)
        if pe < 25: 
            score += 15
            reasons.append(f"Evaluare Bună (P/E {pe:.1f})")
            
        peg = info.get('pegRatio', 5)
        if peg < 1.5:
            score += 15
            reasons.append(f"Creștere Ieftină (PEG {peg:.2f})")
            
        profit = info.get('profitMargins', 0)
        if profit > 0.10:
            score += 20
            reasons.append(f"Companie Profitabilă (Marjă {profit*100:.0f}%)")
    else:
        # Mod de avarie: Dublăm punctajul tehnic pentru a umple golul
        score = score * 2
        reasons.append("⚠️ Scor bazat 100% pe Tehnic (Date fundamentale lipsă)")

    return min(score, 100), reasons

# =========================================================
# INTERFAȚĂ & STRUCTURĂ
# =========================================================

# --- CSS CUSTOM PENTRU UN LOOK PRO ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e2127; padding: 10px; border-radius: 5px; border: 1px solid #333; }
    div[data-testid="stForm"] button { border: 1px solid #00FF00; color: #00FF00; background: transparent; }
    div[data-testid="stForm"] button:hover { background: #00FF00; color: black; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR & AUTH ---
def check_access():
    if st.session_state.get('access_granted', False): return True
    st.sidebar.markdown("### 🔐 Login")
    pwd = st.sidebar.text_input("Parola", type="password")
    if st.sidebar.button("Login"):
        if pwd == st.secrets.get("ACCESS_PASSWORD", "1234"):
            st.session_state['access_granted'] = True
            st.rerun()
    return False

if not check_access():
    st.title("🔒 Terminal Blocat")
    st.stop()

# --- DATABASE FAVORITE ---
if 'favorites' not in st.session_state: st.session_state.favorites = ["NVDA", "TSLA", "AAPL"]
if 'active_ticker' not in st.session_state: st.session_state.active_ticker = "NVDA"

st.sidebar.title("NAVIGARE")
with st.sidebar.form("search"):
    t_input = st.text_input("Caută Simbol", value="")
    if st.form_submit_button("🔍 Caută") and t_input:
        st.session_state.active_ticker = t_input.upper()
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⭐ Favorite")
for fav in st.session_state.favorites:
    c1, c2 = st.sidebar.columns([3,1])
    if c1.button(fav, key=f"go_{fav}"):
        st.session_state.active_ticker = fav
        st.rerun()
    if c2.button("X", key=f"del_{fav}"):
        st.session_state.favorites.remove(fav)
        st.rerun()

add_fav = st.sidebar.button("➕ Adaugă curent la Favorite")
if add_fav and st.session_state.active_ticker not in st.session_state.favorites:
    st.session_state.favorites.append(st.session_state.active_ticker)
    st.rerun()

# --- MAIN APP ---
ticker = st.session_state.active_ticker
st.title(f"📊 Analiză: {ticker}")

# FETCH DATA
history, info = get_robust_data(ticker)

if history.empty:
    st.error(f"Nu s-au găsit date pentru {ticker}. Verifică simbolul.")
else:
    # PREPARARE DATE
    tech = calculate_technicals(history)
    current_price = tech['Last_Close']
    score, reasons = calculate_prime_score(info, tech, history)
    
    # HEADER METRICS
    m1, m2, m3, m4 = st.columns(4)
    price_delta = history['Close'].iloc[-1] - history['Close'].iloc[-2]
    m1.metric("Preț Curent", f"${current_price:.2f}", f"{price_delta:.2f}")
    
    verdict_color = "🟢" if score > 70 else "🟡" if score > 50 else "🔴"
    m2.metric("Scor PRIME", f"{score}/100", verdict_color)
    
    rsi_val = tech['RSI']
    m3.metric("RSI (14)", f"{rsi_val:.2f}", "Supra-cumpărat" if rsi_val > 70 else "Supra-vândut" if rsi_val < 30 else "Neutru", delta_color="off")
    
    mcap = info.get('marketCap', 0)
    m4.metric("Market Cap", f"${mcap/1e9:.1f} B" if mcap else "N/A")

    # TABS
    tab1, tab2, tab3 = st.tabs(["📈 Grafic & Tehnic", "📋 Raport Detaliat", "💰 Dividende"])
    
    with tab1:
        # GRAFIC CANDLESTICK CU MEDII MOBILE
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=history.index, open=history['Open'], high=history['High'], low=history['Low'], close=history['Close'], name='Preț'))
        fig.add_trace(go.Scatter(x=history.index, y=history['Close'].rolling(50).mean(), line=dict(color='orange', width=1), name='SMA 50'))
        fig.add_trace(go.Scatter(x=history.index, y=history['Close'].rolling(200).mean(), line=dict(color='blue', width=1), name='SMA 200'))
        
        fig.update_layout(height=500, template="plotly_dark", title=f"Evoluție {ticker} (1 An)", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # EXPLICATII SCOR
        st.markdown("### 🧠 De ce acest scor?")
        c_reasons = st.container()
        for r in reasons:
            c_reasons.info(r)

    with tab2:
        # TABEL DATE
        c_left, c_right = st.columns(2)
        
        with c_left:
            st.subheader("Date Fundamentale")
            df_fund = pd.DataFrame({
                "Indicator": ["P/E Ratio", "PEG Ratio", "Profit Margin", "Revenue Growth"],
                "Valoare": [
                    info.get('trailingPE', 'N/A'),
                    info.get('pegRatio', 'N/A'),
                    f"{info.get('profitMargins', 0)*100:.1f}%" if info.get('profitMargins') else 'N/A',
                    f"{info.get('revenueGrowth', 0)*100:.1f}%" if info.get('revenueGrowth') else 'N/A'
                ]
            })
            st.table(df_fund)
            
        with c_right:
            st.subheader("Date Tehnice")
            df_tech = pd.DataFrame({
                "Indicator": ["SMA 50 (Termen Mediu)", "SMA 200 (Termen Lung)", "Volatilitate Anuală", "Maxim 52 Săptămâni"],
                "Valoare": [
                    f"${tech['SMA_50']:.2f}",
                    f"${tech['SMA_200']:.2f}",
                    f"{history['Close'].pct_change().std()*np.sqrt(252)*100:.1f}%",
                    f"${history['High'].max():.2f}"
                ]
            })
            st.table(df_tech)

        # PDF GENERATION
        if st.button("📄 Descarcă Raport PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(40, 10, f"Raport Analiza: {ticker}")
            pdf.ln(20)
            pdf.set_font("Arial", '', 12)
            pdf.cell(40, 10, f"Pret: ${current_price:.2f} | Scor: {score}/100")
            pdf.ln(10)
            for r in reasons:
                # Curățare caractere speciale pentru PDF standard
                clean_r = r.replace("ă","a").replace("â","a").replace("ș","s").replace("ț","t").replace("î","i")
                pdf.cell(0, 10, f"- {clean_r}", ln=True)
                
            html = base64.b64encode(pdf.output(dest='S').encode('latin-1', 'ignore')).decode()
            st.markdown(f'<a href="data:application/pdf;base64,{html}" download="{ticker}_Report.pdf">⬇️ Click Aici</a>', unsafe_allow_html=True)

    with tab3:
        st.subheader("Calculator Venit Pasiv")
        div_yield = info.get('dividendYield', 0)
        
        if div_yield and div_yield > 0:
            st.success(f"Acest activ plătește dividende! Randament: {div_yield*100:.2f}%")
            invest = st.number_input("Suma Investită ($)", 1000, 1000000, 5000)
            st.metric("Venit Anual Estimat", f"${invest * div_yield:.2f}")
            st.metric("Venit Trimestrial", f"${(invest * div_yield)/4:.2f}")
        else:
            st.warning("Această companie NU plătește dividende sau datele lipsesc.")
            st.info("Companiile de tehnologie (growth) reinvestesc profitul în loc să dea dividende.")
