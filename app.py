import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(page_title="Analiză PRIME v3.3", layout="wide")

# --- FUNCȚII DE CACHING ---
@st.cache_data(ttl=3600)
def get_all_data(ticker, ani):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=ani*365)
        df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
        t = yf.Ticker(ticker)
        return df, t.info, t.news
    except Exception:
        return None, None, None

# --- LOGICA EXPORT PDF DETALIAT ȘI PRIETENOS ---
def create_pdf_report(ds):
    pdf = FPDF()
    pdf.add_page()
    
    # Header profesional
    pdf.set_font("Arial", 'B', 18)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(200, 15, txt=f"Raport de Sanatate Financiara: {ds['Ticker']}", ln=True, align='C')
    pdf.ln(5)
    
    # 1. Scorul PRIME explicat
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(39, 174, 96)
    pdf.cell(200, 10, txt=f"Scor de Incredere PRIME: {ds['Scor PRIME']}", ln=True)
    
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 7, txt=(
        "Acest scor masoara cat de echilibrata este investitia pe o scara de la 0 la 100%. "
        "Un scor ridicat indica faptul ca actiunea are un istoric de crestere bun, pierderi controlate "
        "in momente de criza si o parere pozitiva din partea expertilor si a stirilor actuale."
    ))
    pdf.ln(5)

    # 2. Performanța (CAGR)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"Viteza de crestere (Randament Anual: {ds['Randament CAGR']})", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 7, txt=(
        f"Daca aceasta companie ar fi o masina, viteza ei medie de croaziera a fost de {ds['Randament CAGR']} pe an. "
        "Aceasta cifra reprezinta cat au castigat investitorii, in medie, in fiecare an din perioada analizata."
    ))
    pdf.ln(3)

    # 3. Riscul (Drawdown)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"Testul de stres (Cea mai mare scadere: {ds['Max Drawdown']})", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 7, txt=(
        f"In cel mai dificil moment al pietei, pretul a scazut temporar cu {ds['Max Drawdown']}. "
        "Este important de stiut: investitiile sunt ca un drum la munte - exista coborasuri, "
        "dar scopul este sa ajungi in varf pe termen lung."
    ))
    pdf.ln(5)

    # 4. Dividende și Obiectiv
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(41, 128, 185)
    pdf.cell(200, 10, txt="Planul tau de venit pasiv (Bani primiti lunar)", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 7, txt=(
        f"In baza sumei investite acum, primesti aproximativ {ds['Venit Lunar Estimat']} in fiecare luna. "
        f"Pentru a atinge obiectivul tau de libertate financiara si a primi {ds['Target Setaat']} pe luna, "
        f"tinta ta de investitie totala in aceasta companie ar fi de {ds['Necesar pentru Target']}."
    ))
    pdf.ln(10)

    # Disclaimer
    pdf.set_font("Arial", 'I', 8)
    pdf.set_text_color(149, 165, 166)
    pdf.multi_cell(0, 5, txt=(
        "Nota: Acest raport este generat automat pentru educatie financiara. Performanta trecuta nu este "
        "o garantie pentru viitor. Orice investitie implica riscul de a pierde bani. Consultati un "
        "specialist inainte de a investi sume importante."
    ))
    
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- INTERFAȚĂ UTILIZATOR ---
st.title("🛡️ Sistemul Analiză PRIME v3.3")

with st.sidebar:
    st.header("Configurare")
    ticker_input = st.text_input("Simbol Ticker", value="AAPL").upper()
    suma_investita = st.number_input("Suma investită acum (USD)", min_value=0.0, value=1000.0)
    ani_analiza = st.selectbox("Perioada de analiză", [1, 2, 3, 5], index=2)
    target_lunar = st.number_input("Cât vrei să primești pe lună? (USD)", min_value=0.0, value=100.0)

if st.button("🚀 Lansează Analiza și Generare Raport"):
    with st.spinner(f"Se procesează datele pentru {ticker_input}..."):
        data, info, news = get_all_data(ticker_input, ani_analiza)
    
    if data is not None and not data.empty:
        # Procesare tehnică date
        preturi = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
        randamente = preturi.pct_change().dropna()
        cagr = (float(preturi.iloc[-1]) / float(preturi.iloc[0])) ** (1/ani_analiza) - 1
        max_drawdown = float(((preturi / preturi.cummax()) - 1).min())
        
        # Dividende
        div_yield = info.get('dividendYield', 0) or 0
        venit_lunar = (suma_investita * div_yield) / 12
        necesar_investitie = (target_lunar * 12) / div_yield if div_yield > 0 else 0

        # Scorul PRIME
        target_price = info.get('targetMeanPrice', preturi.iloc[-1])
        upside = (target_price / preturi.iloc[-1]) - 1
        
        # Sentiment logic
        sentiment_points = 0
        if news:
            for n in news[:8]:
                title = n.get('title', '').lower()
                if any(w in title for w in ['beat', 'buy', 'growth', 'upgrade', 'strong']): sentiment_points += 15
                if any(w in title for w in ['miss', 'fall', 'risk', 'lawsuit', 'cut', 'weak']): sentiment_points -= 15
        
        s_score = max(0, min(100, 50 + sentiment_points))
        
        # Calcul PRIME (Conservator)
        score_risc = (1 + max_drawdown) * 100
        score_perf = min(100, cagr * 200)
        score_upside = max(0, min(100, upside * 100 + 50))
        
        prime_final = (score_risc * 0.35) + (score_perf * 0.25) + (score_upside * 0.20) + (s_score * 0.20)
        prime_final = max(0, min(100, prime_final))

        # --- AFIȘARE ÎN APLICAȚIE ---
        st.header(f"Scor PRIME Final: {prime_final:.1f}%")
        st.progress(prime_final / 100)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Viteza de creștere", f"{cagr*100:.2f}%")
        col2.metric("Nivel de Risc", f"{max_drawdown*100:.2f}%")
        col3.metric("Bani primiți acum / lună", f"{venit_lunar:.2f} USD")

        st.line_chart(preturi)

        # Date pentru PDF
        report_data = {
            "Ticker": ticker_input,
            "Scor PRIME": f"{prime_final:.1f}%",
            "Randament CAGR": f"{cagr*100:.2f}%",
            "Max Drawdown": f"{max_drawdown*100:.2f}%",
            "Venit Lunar Estimat": f"{venit_lunar:.2f} USD",
            "Target Setaat": f"{target_lunar:.2f} USD",
            "Necesar pentru Target": f"{necesar_investitie:,.2f} USD"
        }
        
        # Buton Export
        pdf_report = create_pdf_report(report_data)
        st.download_button(
            label="📥 Descarcă Raportul pe înțelesul tuturor (PDF)",
            data=pdf_report,
            file_name=f"Analiza_Simpla_{ticker_input}.pdf",
            mime="application/pdf"
        )
    else:
        st.error("Date indisponibile. Verifică ticker-ul.")