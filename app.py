import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from fpdf import FPDF
import base64

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="PRIME Terminal", page_icon="🛡️", layout="wide")

# --- CSS SPECIAL PENTRU BUTON ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    
    /* Fortam stilizarea containerului de search */
    [data-testid="stForm"] {
        border: 1px solid #333;
        padding: 10px;
        border-radius: 10px;
    }
    
    /* Butonul GO sa fie verde si vizibil */
    [data-testid="stForm"] button {
        background-color: #00CC00 !important;
        color: black !important;
        border: none !important;
        font-weight: bold !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INIȚIALIZARE STATE ---
if 'favorites' not in st.session_state: st.session_state.favorites = [] 
if 'favorite_names' not in st.session_state: st.session_state.favorite_names = {} 
if 'active_ticker' not in st.session_state: st.session_state.active_ticker = "NVDA"

# --- SIDEBAR ---
st.sidebar.title("🔴 VERSIUNEA NOUA") # Asta iti confirma ca s-a updatat
st.sidebar.write(f"Activ: **{st.session_state.active_ticker}**")

st.sidebar.write("Caută companie:")

# --- FORMULAR COMPACT (Input + Buton pe aceeasi linie) ---
with st.sidebar.form(key='search_form'):
    # Coloane: 70% input, 30% buton
    c1, c2 = st.columns([0.7, 0.3])
    
    with c1:
        # Input fara eticheta (label_visibility="collapsed")
        new_ticker = st.text_input("S", placeholder="TSLA", label_visibility="collapsed")
    
    with c2:
        # Butonul submit
        submit = st.form_submit_button("GO")

    if submit and new_ticker:
        st.session_state.active_ticker = new_ticker.upper()
        st.rerun()

st.sidebar.markdown("---")

# Buton Adauga la Favorite (in afara form-ului)
if st.sidebar.button("❤️ Adaugă la Favorite"):
    t = st.session_state.active_ticker
    if t not in st.session_state.favorites:
        st.session_state.favorites.append(t)
        # Incercam sa luam numele lung
        try:
            inf = yf.Ticker(t).info
            st.session_state.favorite_names[t] = inf.get('longName', t)
        except:
            st.session_state.favorite_names[t] = t
        st.success("Adăugat!")
        st.rerun()

# Lista Favorite
if st.session_state.favorites:
    st.sidebar.write("Lista ta:")
    for fav in st.session_state.favorites:
        col_btn, col_del = st.sidebar.columns([0.8, 0.2])
        
        # Folosim callbacks pentru viteza
        def incarca(x=fav): st.session_state.active_ticker = x
        def sterge(x=fav): st.session_state.favorites.remove(x)

        col_btn.button(fav, key=f"go_{fav}", on_click=incarca)
        col_del.button("X", key=f"del_{fav}", on_click=sterge)


# --- RESTUL APLICATIEI (FUNCTIONALITATI) ---

def get_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")
        info = stock.info
        return stock, hist, info
    except: return None, None, None

stock, history, info = get_data(st.session_state.active_ticker)

st.title(f"Analiza: {st.session_state.active_ticker}")

if history is not None and not history.empty:
    price = history['Close'].iloc[-1]
    st.metric("Preț Curent", f"${price:.2f}")
    st.line_chart(history['Close'])
    
    # Tab-uri simple
    t1, t2, t3 = st.tabs(["Stiri", "Tehnic", "Despre"])
    
    with t1:
        st.write("Știri recente (Yahoo Finance):")
        try:
            news = stock.news
            for n in news[:3]:
                st.write(f"- [{n['title']}]({n['link']})")
        except: st.write("Indisponibil")
        
    with t2:
        st.write("Date tehnice simple:")
        st.dataframe(history.tail())
        
    with t3:
        long_summary = info.get('longBusinessSummary', 'N/A')
        st.write(long_summary)

else:
    st.error("Simbol invalid sau eroare de conexiune.")
