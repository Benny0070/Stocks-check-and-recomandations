import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from fpdf import FPDF
import base64
import re

# --- 1. CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="PRIME Terminal", page_icon="🛡️", layout="wide")

# --- CSS PERSONALIZAT (Design Curat) ---
st.markdown("""
    <style>
    /* Fundal general */
    .main { background-color: #0e1117; color: #ffffff; }
    
    /* Eliminare fundal cutii metrics */
    div[data-testid="stMetricValue"] {
        background-color: transparent !important;
    }
    div[data-testid="stMetricLabel"] {
        background-color: transparent !important;
    }
    .stMetric {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    
    /* Stil pentru butoane sidebar */
    .stButton button {
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --- INIȚIALIZARE LISTĂ FAVORITE & INPUT ---
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'active_ticker' not in st.session_state:
    st.session_state.active_ticker = "NVDA"

# --- 2. FUNCȚII UTILITARE ---

def clean_text_for_pdf(text):
    """Elimină emoji-urile și caracterele speciale pentru a nu crăpa PDF-ul"""
    # Înlocuim emoji-urile comune cu text
    text = text.replace("🔴", "[ROSU]").replace("🟢", "[VERDE]").replace("🟡", "[GALBEN]").replace("⚪", "[NEUTRU]")
    # Eliminăm orice alt caracter non-latin
    return text.encode('latin-1', 'ignore').decode('latin-1')

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period="5y")
        info = stock.info
        return stock, history, info
    except:
        return None, None, None

def calculate_prime_score(info, history):
    score = 0
    reasons = []
    
    # 1. Trend
    if not history.empty:
        sma200 = history['Close'].rolling(window=200).mean().iloc[-1]
        current_price = history['Close'].iloc[-1]
        if current_price > sma200:
            score += 20
            reasons.append("Pret peste media de 200 zile (Trend Ascendent)")
    
    # 2. Profitabilitate
    profit_margin = info.get('profitMargins', 0) or 0
    if profit_margin > 0.15: 
        score += 20
        reasons.append(f"Marja de profit solida: {profit_margin*100:.1f}%")
        
    # 3. Creștere
    rev_growth = info.get('revenueGrowth', 0) or 0
    if rev_growth > 0.10: 
        score += 20
        reasons.append(f"Crestere venituri: {rev_growth*100:.1f}%")
        
    # 4. Evaluare
    pe_ratio = info.get('trailingPE', 0) or 0
    if 0 < pe_ratio < 40:
        score += 20
        reasons.append(f"P/E Ratio rezonabil: {pe_ratio:.2f}")
    elif pe_ratio > 40:
        score += 10
        reasons.append(f"P/E Ratio ridicat ({pe_ratio:.2f}), acceptabil pt growth")

    # 5. Cash vs Datorii
    cash = info.get('totalCash', 0) or 0
    debt = info.get('totalDebt', 0) or 0
    if cash > debt:
        score += 20
        reasons.append("Bilant Fortareata (Cash > Datorii)")
        
    return score, reasons

def get_news_sentiment(stock):
    try:
        news = stock.news
        if not news:
            return "Neutru", []
        
        # Colectăm doar titlurile valide
        headlines = []
        for n in news[:5]:
            title = n.get('title', '')
            if title and title not in headlines:
                headlines.append(title)
        
        if not headlines:
            return "Neutru", ["Nu există știri recente relevante."]

        # Analiză sentiment
        positive_keywords = ['beat', 'rise', 'jump', 'high', 'buy', 'growth', 'up', 'record', 'strong', 'surge']
        negative_keywords = ['miss', 'fall', 'drop', 'low', 'sell', 'weak', 'down', 'loss', 'crash', 'plunge']
        
        score_sent = 0
        for h in headlines:
            h_lower = h.lower()
            if any(k in h_lower for k in positive_keywords): score_sent += 1
            if any(k in h_lower for k in negative_keywords): score_sent -= 1
            
        if score_sent > 0: return "Pozitiv 🟢", headlines
        elif score_sent < 0: return "Negativ 🔴", headlines
        else: return "Neutru ⚪", headlines
    except Exception as e:
        return "Indisponibil", [f"Eroare date: {e}"]

def create_audit_pdf(ticker, current_price, score, reasons, verdict, risk_data):
    pdf = FPDF()
    pdf.add_page()
    
    # Titlu
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"Raport Audit PRIME: {ticker}", ln=True, align='C')
    pdf.ln(10)
    
    # Curățăm verdictul de emoji
    clean_verdict = clean_text_for_pdf(verdict)
    
    # Detalii
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Data: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    pdf.cell(0, 10, f"Pret: ${current_price:.2f}", ln=True)
    pdf.cell(0, 10, f"Scor: {score}/100", ln=True)
    pdf.cell(0, 10, f"Verdict: {clean_verdict}", ln=True)
    pdf.ln(10)
    
    # Motive
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Factori Cheie:", ln=True)
    pdf.set_font("Arial", '', 12)
    for reason in reasons:
        pdf.cell(0, 10, f"- {clean_text_for_pdf(reason)}", ln=True)
    
    pdf.ln(10)
    
    # Risc
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Analiza Risc:", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Volatilitate: {risk_data['volatility']:.2f}%", ln=True)
    pdf.cell(0, 10, f"Cadere Maxima (Drawdown): {risk_data['drawdown']:.2f}%", ln=True)
    
    return pdf.output(dest='S').encode('latin-1', 'ignore')

# --- SIDEBAR ---
st.sidebar.header("🔍 Control Panel")

# Input care se actualizează dacă apăsăm pe butoanele de jos
ticker_input = st.sidebar.text_input("Simbol Bursier", value=st.session_state.active_ticker).upper()

# Dacă userul scrie manual, actualizăm state-ul
if ticker_input != st.session_state.active_ticker:
    st.session_state.active_ticker = ticker_input

# Adăugare la Favorite
if st.sidebar.button("➕ Adaugă la Favorite"):
    if ticker_input not in st.session_state.favorites:
        st.session_state.favorites.append(ticker_input)
        st.sidebar.success(f"{ticker_input} salvat!")

st.sidebar.markdown("---")
st.sidebar.header("⭐ Favorite")

# Logică pentru lista de favorite (Click to Load)
if st.session_state.favorites:
    for fav in st.session_state.favorites:
        c1, c2 = st.sidebar.columns([3, 1])
        
        # Butonul de nume încarcă tickerul
        if c1.button(f"📂 {fav}", key=f"load_{fav}"):
            st.session_state.active_ticker = fav
            st.rerun()
            
        # Butonul X șterge
        if c2.button("❌", key=f"del_{fav}"):
            st.session_state.favorites.remove(fav)
            st.rerun()
else:
    st.sidebar.info("Lista e goală.")

# --- MAIN APP ---
st.title(f"🛡️ PRIME Terminal: {st.session_state.active_ticker}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Analiză", "📰 Știri", "💰 Dividende", "📋 Audit PDF", "⚔️ Comparație"])

if st.session_state.active_ticker:
    stock, history, info = get_stock_data(st.session_state.active_ticker)
    
    if stock and not history.empty:
        # Calcule
        current_price = history['Close'].iloc[-1]
        score, reasons = calculate_prime_score(info, history)
        
        # Risc
        daily_ret = history['Close'].pct_change().dropna()
        volatility = daily_ret.std() * np.sqrt(252) * 100
        max_drawdown = ((history['Close'] / history['Close'].cummax()) - 1).min() * 100
        
        # Logica Verdict
        if max_drawdown < -40:
            verdict = "Risc Ridicat 🔴"
            color_box = "error" # Rosu
            msg_box = "Atenție! Istoric de scăderi masive."
        elif score >= 70:
            verdict = "Oportunitate 🟢"
            color_box = "success" # Verde
            msg_box = "Fundamente solide și risc controlat."
        else:
            verdict = "Neutru / Risc Mediu 🟡"
            color_box = "warning" # Galben
            msg_box = "Potențial moderat, necesită atenție."

        # TAB 1: ANALIZĂ
        with tab1:
            # Afișare Metrics Fără Fundal
            col1, col2, col3 = st.columns(3)
            col1.metric("Preț", f"${current_price:.2f}")
            col2.metric("Scor", f"{score}/100")
            col3.metric("Risc (Volatilitate)", f"{volatility:.1f}%")

            # Afișare Verdict Mare (Colorat)
            if color_box == "success":
                st.success(f"### Verdict: {verdict}\n{msg_box}")
            elif color_box == "warning":
                st.warning(f"### Verdict: {verdict}\n{msg_box}")
            else:
                st.error(f"### Verdict: {verdict}\n{msg_box}")

            st.line_chart(history['Close'])
            
            with st.expander("Detalii Scor"):
                for r in reasons: st.write(f"✅ {r}")

        # TAB 2: ȘTIRI
        with tab2:
            st.subheader("Analiză Media")
            sentiment, headlines = get_news_sentiment(stock)
            st.write(f"**Sentiment General:** {sentiment}")
            st.markdown("---")
            for h in headlines:
                st.markdown(f"• {h}")

        # TAB 3: DIVIDENDE
        with tab3:
            div = info.get('dividendYield', 0) or 0
            if div > 0:
                st.metric("Randament", f"{div*100:.2f}%")
                inv = st.number_input("Investiție ($)", 1000, 1000000, 10000)
                st.success(f"Venit anual estimat: **${inv*div:.2f}**")
            else:
                st.info("Această companie nu plătește dividende.")

        # TAB 4: PDF
        with tab4:
            st.write("Descarcă raportul complet (compatibil PC/Mobile).")
            if st.button("Generează PDF"):
                try:
                    risk_data = {"volatility": volatility, "drawdown": max_drawdown}
                    pdf_data = create_audit_pdf(st.session_state.active_ticker, current_price, score, reasons, verdict, risk_data)
                    b64 = base64.b64encode(pdf_data).decode()
                    href = f'<a href="data:application/octet-stream;base64,{b64}" download="Audit_{st.session_state.active_ticker}.pdf">📥 Download PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Eroare PDF: {e}")

    else:
        st.error("Nu s-au găsit date. Verifică simbolul.")

# TAB 5: COMPARATIE (FIXED)
with tab5:
    st.header("Comparație Randamente")
    if len(st.session_state.favorites) > 0:
        to_compare = st.multiselect("Alege companii:", st.session_state.favorites, default=st.session_state.favorites[:3])
        
        if st.button("Compară Acum"):
            df_comp = pd.DataFrame()
            st.write("Se descarcă datele...")
            
            # Descărcare individuală sigură (Safe Fetch)
            for t in to_compare:
                try:
                    tmp = yf.Ticker(t).history(period="1y")['Close']
                    # Normalizare la 0%
                    if not tmp.empty:
                        tmp = (tmp / tmp.iloc[0] - 1) * 100
                        df_comp[t] = tmp
                except:
                    st.warning(f"Nu am putut descărca {t}")
            
            if not df_comp.empty:
                st.line_chart(df_comp)
                
                # Clasament final
                st.write("### Top Performanță (1 An):")
                final = df_comp.iloc[-1].sort_values(ascending=False)
                for ticker, val in final.items():
                    c = "green" if val > 0 else "red"
                    st.markdown(f"**{ticker}**: :{c}[{val:.1f}%]")
    else:
        st.info("Adaugă companii la Favorite pentru a compara.")
