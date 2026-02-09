import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from fpdf import FPDF
import base64

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="PRIME Terminal", page_icon="🛡️", layout="wide")

# --- CSS PENTRU BUTON SI ALINIERE ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    
    /* Stil pentru butonul GO - Verde si vizibil */
    div[data-testid="column"] button {
        background-color: #00cc00 !important;
        color: black !important;
        border: none !important;
        font-weight: bold !important;
        height: 46px !important; /* Aceeasi inaltime cu input-ul */
        margin-top: 0px !important;
    }
    
    /* Ajustare input ca sa se alinieze cu butonul */
    div[data-testid="stTextInput"] {
        margin-top: 0px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INIȚIALIZARE STATE ---
if 'favorites' not in st.session_state: st.session_state.favorites = [] 
if 'favorite_names' not in st.session_state: st.session_state.favorite_names = {} 
if 'active_ticker' not in st.session_state: st.session_state.active_ticker = "NVDA"

# --- FUNCȚII UTILITARE ---
def get_stock_data(ticker, period="1y"):
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period=period)
        info = stock.info
        return stock, history, info
    except:
        return None, None, None

def calculate_prime_score(info, history):
    score = 0
    reasons = []
    
    # 1. Trend
    if not history.empty:
        sma = history['Close'].mean() 
        current = history['Close'].iloc[-1]
        if current > sma:
            score += 20
            reasons.append("Trend Ascendent")
    
    # 2. Profitabilitate
    pm = info.get('profitMargins', 0) or 0
    if pm > 0.15: 
        score += 20
        reasons.append(f"Marja Profit: {pm*100:.1f}%")
        
    # 3. Creștere
    rg = info.get('revenueGrowth', 0) or 0
    if rg > 0.10: 
        score += 20
        reasons.append(f"Crestere Venituri: {rg*100:.1f}%")
        
    # 4. Evaluare
    pe = info.get('trailingPE', 0) or 0
    if 0 < pe < 40:
        score += 20
        reasons.append(f"P/E Ratio: {pe:.2f}")
    
    # 5. Cash
    cash = info.get('totalCash', 0) or 0
    debt = info.get('totalDebt', 0) or 0
    if cash > debt:
        score += 20
        reasons.append("Cash > Datorii")
        
    return score, reasons

# --- SIDEBAR (NOUL DESIGN) ---
st.sidebar.title(f"🔍 {st.session_state.active_ticker}")
st.sidebar.caption("Terminal Financiar")

st.sidebar.write("Caută companie:")

# --- FORMULAR SEARCH CU BUTON LANGA ---
# Folosim columns pentru a pune Input si Buton pe aceeasi linie
c1, c2 = st.sidebar.columns([0.7, 0.3])

with c1:
    # Input
    new_ticker = st.text_input("Simbol", placeholder="TSLA", label_visibility="collapsed")

with c2:
    # Butonul GO
    go_btn = st.button("GO", key="search_go")

# Logica de executare a cautarii
if go_btn and new_ticker:
    st.session_state.active_ticker = new_ticker.upper()
    st.rerun()

st.sidebar.markdown("---")

# --- BUTON ADAUGARE FAVORITE (REPARAT) ---
if st.sidebar.button("➕ Adaugă la Favorite"):
    t = st.session_state.active_ticker
    if t not in st.session_state.favorites:
        st.session_state.favorites.append(t)
        # Salvam si numele complet daca putem
        try:
            inf = yf.Ticker(t).info
            st.session_state.favorite_names[t] = inf.get('longName', t)
        except:
            st.session_state.favorite_names[t] = t
        st.sidebar.success(f"{t} Adăugat!")
        # NU mai dam rerun aici ca sa evitam eroarea "Adaugat! Eroare!"
    else:
        st.sidebar.warning("Deja există.")

# --- LISTA FAVORITE ---
st.sidebar.subheader("Lista Mea")
if st.session_state.favorites:
    for fav in st.session_state.favorites:
        full_n = st.session_state.favorite_names.get(fav, fav)
        
        col_name, col_del = st.sidebar.columns([0.7, 0.3])
        
        # Butonul cu numele incarca compania
        if col_name.button(f"{fav}", key=f"btn_{fav}", help=full_n):
            st.session_state.active_ticker = fav
            st.rerun()
            
        # Butonul X sterge
        if col_del.button("X", key=f"del_{fav}"):
            st.session_state.favorites.remove(fav)
            st.rerun()
else:
    st.sidebar.info("Lista este goală.")

# --- MAIN APP ---
try:
    stock, history, info = get_stock_data(st.session_state.active_ticker)
    
    if stock and not history.empty:
        curr_price = history['Close'].iloc[-1]
        score, reasons = calculate_prime_score(info, history)
        
        # Titlu si Pret
        st.title(f"{st.session_state.active_ticker}")
        st.metric("Preț Curent", f"${curr_price:.2f}", f"Scor: {score}/100")
        
        # Grafic
        st.line_chart(history['Close'])
        
        # Tab-uri
        t1, t2, t3 = st.tabs(["📊 Analiză", "📰 Știri", "🏢 Despre"])
        
        with t1:
            st.subheader("De ce acest scor?")
            if reasons:
                for r in reasons:
                    st.success(f"✅ {r}")
            else:
                st.warning("Nu există motive majore de creștere detectate automat.")
                
            c_a, c_b = st.columns(2)
            c_a.info(f"Sector: {info.get('sector', 'N/A')}")
            c_b.info(f"Industry: {info.get('industry', 'N/A')}")

        with t2:
            st.subheader("Știri Recente")
            try:
                news = stock.news
                if news:
                    for n in news[:5]:
                        st.markdown(f"- [{n.get('title')}]({n.get('link')})")
                else:
                    st.write("Nu sunt știri disponibile.")
            except:
                st.write("Indisponibil.")

        with t3:
            st.write(info.get('longBusinessSummary', 'Descriere indisponibilă.'))

    else:
        st.error(f"Nu am găsit date pentru {st.session_state.active_ticker}. Verifică simbolul.")

except Exception as e:
    st.error(f"A apărut o eroare: {e}")
