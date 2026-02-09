import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURARE ---
st.set_page_config(page_title="PRIME Analytics PRO", layout="wide")

# --- DESIGN CLEAN ---
st.markdown("""
    <style>
    .stApp { background-color: #ffffff; color: #000000; }
    .stButton>button { background-color: #ffffff; color: #000000; border: 1px solid #000000; }
    .stButton>button:hover { background-color: #000000; color: #ffffff; }
    .transparency-box { background-color: #f9f9f9; padding: 20px; border-radius: 10px; border: 1px solid #ddd; }
    </style>
    """, unsafe_allow_html=True)

# --- REPARARE CACHING ---
@st.cache_resource
def get_ticker_obj(ticker): return yf.Ticker(ticker)

@st.cache_data(ttl=3600)
def get_history(ticker, ani): return yf.Ticker(ticker).history(period=f"{ani}y")

# --- LOGICA NAVIGARE ---
if 'page' not in st.session_state: st.session_state.page = 'Main'
if 'audit_results' not in st.session_state: st.session_state.audit_results = []

def change_page(page_name): st.session_state.page = page_name

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ PRIME Terminal")
    ticker_symbol = st.text_input("Simbol Acțiune", value="NVDA").upper()
    ani_analiza = st.slider("Ani Analiză", 1, 10, 3)
    st.divider()
    st.button("📊 Dashboard Principal", on_click=change_page, args=('Main',))
    st.button("🛡️ Audit Economic", on_click=change_page, args=('Advanced',))
    st.divider()
    suma_investita = st.number_input("Investiție (USD)", min_value=0.0, value=1000.0)
    target_lunar = st.number_input("Țintă Lunară (USD)", min_value=0.0, value=100.0)

# --- DATE COMUNE & CALCULE ---
try:
    t_obj = get_ticker_obj(ticker_symbol)
    hist = get_history(ticker_symbol, ani_analiza)
    info = t_obj.info
    news = t_obj.news
    
    # 1. RISC (30%)
    preturi = hist['Close']
    m_drawdown = float(((preturi / preturi.cummax()) - 1).min())
    s_risc = max(0, (1 + m_drawdown) * 100)
    
    # CALCUL SHARPE RATIO (Necesare pentru Verdict)
    daily_returns = preturi.pct_change().dropna()
    sharpe = (daily_returns.mean() / daily_returns.std()) * (252**0.5) if daily_returns.std() > 0 else 0

    # 2. ISTORIC (30%)
    cagr = float(((preturi.iloc[-1] / preturi.iloc[0]) ** (1/ani_analiza)) - 1)
    s_istoric = min(100, max(0, cagr * 200))
    
    # 3. VIITOR / TARGET PRICE (20%)
    current_price = float(preturi.iloc[-1])
    target_price = float(info.get('targetMeanPrice', current_price))
    upside = (target_price / current_price) - 1
    s_viitor = max(0, min(100, upside * 100 + 50))
    
    # 4. SENTIMENT / ȘTIRI (20%)
    sentiment_score = 50 
    if news and len(news) > 0:
        pos_keywords = ['buy', 'growth', 'beat', 'up', 'bull', 'positive', 'high']
        neg_keywords = ['sell', 'risk', 'fall', 'down', 'bear', 'negative', 'low', 'miss']
        pos_count = 0
        neg_count = 0
        for n in news[:7]:
            title = n.get('title', '').lower()
            if any(word in title for word in pos_keywords): pos_count += 1
            if any(word in title for word in neg_keywords): neg_count += 1
        if pos_count > neg_count: sentiment_score = 100
        elif neg_count > pos_count: sentiment_score = 0
        else: sentiment_score = 50
    s_sentiment = sentiment_score

    # CALCUL FINAL SCOR PRIME
    score_final = (s_risc * 0.3) + (s_istoric * 0.3) + (s_viitor * 0.2) + (s_sentiment * 0.2)
    
    div_yield = info.get('dividendYield', 0) or 0
    venit_lunar_actual = (suma_investita * div_yield) / 12
    necesar_investitie = (target_lunar * 12) / div_yield if div_yield > 0 else 0

except Exception as e:
    st.error(f"Eroare procesare date: {e}")
    st.stop()

# =========================================================
# PAGINA 1: DASHBOARD
# =========================================================
if st.session_state.page == 'Main':
    st.title(f"📈 {info.get('longName', ticker_symbol)}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Randament Anual (CAGR)", f"{cagr*100:.2f}%")
    c2.metric("Risc (Max Drawdown)", f"{m_drawdown*100:.2f}%")
    c3.metric("Venit Lunar Actual", f"{venit_lunar_actual:.2f} USD")

    st.line_chart(preturi)

    # --- VERDICT CONSERVATOR (REINTRODUS) ---
    st.subheader("📢 Verdict Conservator")
    if sharpe > 0.8 and m_drawdown > -0.20:
        st.success(f"🟢 VERDICT: Investiție robustă. Randament bun cu risc de scădere controlat. (Sharpe: {sharpe:.2f})")
    elif sharpe > 0.4 and m_drawdown > -0.35:
        st.warning(f"🟡 VERDICT: Investiție moderată. Acceptabilă, dar pregătește-te pentru volatilitate. (Sharpe: {sharpe:.2f})")
    else:
        st.error(f"🔴 VERDICT: Risc ridicat. Istoricul arată scăderi mari sau randament mic față de risc. (Sharpe: {sharpe:.2f})")

    st.divider()
    if st.button(f"🌟 Scor PRIME: {score_final:.1f}% (Vezi Matematica Detaliată)"):
        st.markdown(f"""
        <div class="transparency-box">
            <h4>Formula de Calcul Scor PRIME (30/30/20/20)</h4>
            <p>1. <b>Risc (30%):</b> Bazat pe scăderea maximă istorică. Punctaj: <b>{s_risc:.1f}</b></p>
            <p>2. <b>Istoric (30%):</b> Bazat pe randamentul compus (CAGR). Punctaj: <b>{s_istoric:.1f}</b></p>
            <p>3. <b>Viitor (20%):</b> Bazat pe prețul țintă al analiștilor. Punctaj: <b>{s_viitor:.1f}</b></p>
            <p>4. <b>Sentiment (20%):</b> Analiza știrilor recente (7 zile). Punctaj: <b>{s_sentiment:.1f}</b></p>
            <hr>
            <b>Scor Final: ({s_risc:.1f}*0.3) + ({s_istoric:.1f}*0.3) + ({s_viitor:.1f}*0.2) + ({s_sentiment:.1f}*0.2) = {score_final:.1f}%</b>
        </div>
        """, unsafe_allow_html=True)
    st.progress(score_final / 100)

# =========================================================
# PAGINA 2: AUDIT ECONOMIC
# =========================================================
elif st.session_state.page == 'Advanced':
    st.title("🛡️ Audit Economic Fundamental")
    
    col1, col2 = st.columns(2)
    with col1:
        c_debt = st.checkbox("Datorii (Debt to Equity)")
        c_margin = st.checkbox("Marja de Profit")
        c_roe = st.checkbox("ROE (Eficiență Capital)")
    with col2:
        c_curr = st.checkbox("Lichiditate (Current Ratio)")
        c_fcf = st.checkbox("Cash Flow Liber (FCF)")
        c_pe = st.checkbox("Evaluare P/E Ratio")

    if st.button("📊 Calculează și Interpretează Auditul"):
        res = []
        if c_debt:
            v = info.get('debtToEquity', 0) / 100
            interp = "Sustenabil" if v < 1.5 else "Grad mare de îndatorare"
            res.append(["Datorii (D/E)", f"{v:.2f}", interp])
        if c_margin:
            v = info.get('profitMargins', 0)
            interp = "Foarte profitabilă" if v > 0.15 else "Marje strânse, risc competitiv"
            res.append(["Marja Profit", f"{v*100:.2f}%", interp])
        if c_roe:
            v = info.get('returnOnEquity', 0)
            interp = "Management eficient" if v > 0.15 else "Randament slab al capitalului"
            res.append(["ROE", f"{v*100:.2f}%", interp])
        if c_curr:
            v = info.get('currentRatio', 0)
            interp = "Lichiditate sănătoasă" if v > 1.2 else "Potențiale probleme de cash"
            res.append(["Lichiditate", f"{v:.2f}", interp])
        if c_fcf:
            v = info.get('freeCashflow', 0)
            interp = "Generare solidă de cash" if v > 0 else "Arde cash, risc de capital"
            res.append(["Free Cash Flow", f"{v:,.0f} USD", interp])
        if c_pe:
            v = info.get('trailingPE', 0)
            interp = "Evaluare corectă" if v < 25 else "Supraevaluată (Premium)"
            res.append(["P/E Ratio", f"{v:.2f}", interp])
        
        st.session_state.audit_results = res
        st.table(pd.DataFrame(res, columns=["Indicator", "Valoare", "Interpretare"]))

# =========================================================
# EXPORT PDF (FIX ENCODING)
# =========================================================
def generate_pdf():
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"RAPORT ANALIZA: {ticker_symbol}", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Randament CAGR ({ani_analiza} ani): {cagr*100:.2f}%", ln=True)
    pdf.cell(0, 8, f"Venit Lunar la investitie: {venit_lunar_actual:.2f} USD", ln=True)
    pdf.cell(0, 8, f"Risc (Sharpe Ratio): {sharpe:.2f}", ln=True) # Adaugat Sharpe si aici
    
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Matematica Scorului PRIME (30/30/20/20):", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 7, f"- Risc (30%): {s_risc:.1f} puncte", ln=True)
    pdf.cell(0, 7, f"- Istoric (30%): {s_istoric:.1f} puncte", ln=True)
    pdf.cell(0, 7, f"- Viitor (20%): {s_viitor:.1f} puncte", ln=True)
    pdf.cell(0, 7, f"- Sentiment (20%): {s_sentiment:.1f} puncte", ln=True)
    pdf.cell(0, 7, f"SCOR FINAL: {score_final:.1f}%", ln=True)

    if st.session_state.audit_results:
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Audit Economic Detaliat:", ln=True)
        pdf.set_font("Arial", size=10)
        for item in st.session_state.audit_results:
            line = f"{item[0]}: {item[1]} -> {item[2]}"
            clean_line = line.encode('ascii', 'ignore').decode('ascii')
            pdf.cell(0, 7, txt=f"- {clean_line}", ln=True)
    
    return pdf.output(dest='S').encode('latin-1', 'replace')

st.sidebar.divider()
if st.sidebar.button("📥 Descarcă Raport PDF"):
    pdf_bytes = generate_pdf()
    st.sidebar.download_button("Salvare PDF", pdf_bytes, f"Analiza_{ticker_symbol}.pdf", "application/pdf")
