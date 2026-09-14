import streamlit as st
import requests
import pandas as pd
import numpy as np
from scipy.stats import poisson
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Bundesliga Pro Analytics", page_icon="🏟️", layout="wide")

# --- CABECERA VISUAL ---
st.image("https://images.unsplash.com/photo-1522778119026-d647f0596c20?ixlib=rb-1.2.1&auto=format&fit=crop&w=1200&q=80", use_container_width=True)
st.markdown("<h1 style='text-align: center; color: #4CAF50;'>⚽ Bundesliga Quant Model V3.5</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 18px; color: #aaaaaa;'>Dashboard Institucional: Poisson + Goles Esperados (xG) + Detección Visual de <i>Value Bets</i>.</p>", unsafe_allow_html=True)
st.markdown("---")

API_KEY = "3c5c1e830c72fdda99980f236f3d32ab"
URL = f"https://api.the-odds-api.com/v4/sports/soccer_germany_bundesliga/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals"

# --- 1. EXTRACCIÓN DE DATOS DE MERCADO ---
@st.cache_data(ttl=300)
def cargar_cuotas():
    response = requests.get(URL)
    if response.status_code != 200: return pd.DataFrame()
    matches = []
    for m in response.json():
        home, away = m.get('home_team'), m.get('away_team')
        for b in m.get('bookmakers', []):
            casa = b.get('title')
            c_h2h, c_ou = {}, {}
            for market in b.get('markets', []):
                if market['key'] == 'h2h':
                    c_h2h = {out['name']: out['price'] for out in market.get('outcomes', [])}
                elif market['key'] == 'totals':
                    for out in market.get('outcomes', []):
                        if out['point'] == 2.5: c_ou[out['name']] = out['price']
            if c_h2h:
                matches.append({
                    'Encuentro': f"{home} vs {away}", 'Local': home, 'Visitante': away, 'Casa': casa,
                    '1': c_h2h.get(home, 0), 'X': c_h2h.get('Draw', 0), '2': c_h2h.get(away, 0),
                    'Over_2.5': c_ou.get('Over', 0), 'Under_2.5': c_ou.get('Under', 0)
                })
    return pd.DataFrame(matches)

# --- 2. BASE DE DATOS ESTADÍSTICA (xG, Tarjetas, Córners) ---
@st.cache_data(ttl=86400)
def cargar_metricas_equipos():
    return {
        "Bayern Munich": {"xg_f": 2.6, "xg_c": 0.9, "corners": 7.5, "tarjetas": 1.8},
        "Bayer Leverkusen": {"xg_f": 2.3, "xg_c": 1.0, "corners": 6.8, "tarjetas": 2.1},
        "Borussia Dortmund": {"xg_f": 1.9, "xg_c": 1.3, "corners": 5.9, "tarjetas": 2.0},
        "RB Leipzig": {"xg_f": 2.0, "xg_c": 1.1, "corners": 5.5, "tarjetas": 1.9},
        "VfB Stuttgart": {"xg_f": 1.8, "xg_c": 1.2, "corners": 5.2, "tarjetas": 2.2},
        "Eintracht Frankfurt": {"xg_f": 1.5, "xg_c": 1.4, "corners": 4.8, "tarjetas": 2.4},
        "SC Freiburg": {"xg_f": 1.4, "xg_c": 1.5, "corners": 4.5, "tarjetas": 1.9},
        "TSG Hoffenheim": {"xg_f": 1.6, "xg_c": 1.7, "corners": 4.9, "tarjetas": 2.5},
        "DEFAULT": {"xg_f": 1.4, "xg_c": 1.4, "corners": 4.5, "tarjetas": 2.2}
    }

# --- 3. MOTOR MATEMÁTICO: POISSON ---
def calcular_poisson(local, visita, metricas):
    stats_l = metricas.get(local, metricas["DEFAULT"])
    stats_v = metricas.get(visita, metricas["DEFAULT"])
    
    xg_local_esperado = (stats_l["xg_f"] * stats_v["xg_c"]) / 1.4 * 1.1 
    xg_visita_esperado = (stats_v["xg_f"] * stats_l["xg_c"]) / 1.4 * 0.9
    
    max_goles = 7 
    matriz = np.zeros((max_goles, max_goles))
    
    for i in range(max_goles):
        for j in range(max_goles):
            matriz[i, j] = poisson.pmf(i, xg_local_esperado) * poisson.pmf(j, xg_visita_esperado)
            
    p_1 = np.sum(np.tril(matriz, -1)) 
    p_x = np.trace(matriz)            
    p_2 = np.sum(np.triu(matriz, 1))  
    
    p_under, p_over = 0, 0
    for i in range(max_goles):
        for j in range(max_goles):
            if i + j > 2.5: p_over += matriz[i, j]
            else: p_under += matriz[i, j]
            
    return {
        'p_1': p_1, 'f_1': 1/p_1, 'p_x': p_x, 'f_x': 1/p_x, 'p_2': p_2, 'f_2': 1/p_2,
        'p_over': p_over, 'f_over': 1/p_over, 'p_under': p_under, 'f_under': 1/p_under,
        'exp_corners': stats_l["corners"] + stats_v["corners"],
        'exp_tarjetas': stats_l["tarjetas"] + stats_v["tarjetas"],
        'xg_l': xg_local_esperado, 'xg_v': xg_visita_esperado
    }

df = cargar_cuotas()
metricas = cargar_metricas_equipos()

# --- PANEL LATERAL CON ENLACES ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/thumb/d/df/Bundesliga_logo_%282017%29.svg/300px-Bundesliga_logo_%282017%29.svg.png", width=150)
st.sidebar.header("⚙️ Configuración")

if df.empty:
    st.error("Esperando datos de la API de cuotas...")
else:
    partido_sel = st.sidebar.selectbox("Selecciona un partido:", df['Encuentro'].unique())
    df_p = df[df['Encuentro'] == partido_sel]
    
    local, visita = df_p.iloc[0]['Local'], df_p.iloc[0]['Visitante']
    modelo = calcular_poisson(local, visita, metricas)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔗 Recursos Útiles")
    st.sidebar.markdown("[📊 Estadísticas en FBref](https://fbref.com/en/comps/20/Bundesliga-Stats)")
    st.sidebar.markdown("[📡 The Odds API](https://the-odds-api.com/)")
    st.sidebar.markdown("[📖 Guía del Modelo de Poisson](https://es.wikipedia.org/wiki/Distribuci%C3%B3n_de_Poisson)")

    # --- DISEÑO DE TARJETAS HTML/CSS ---
    def render_card(col, titulo, cuota_mercado, cuota_modelo, prob):
        edge = (cuota_mercado * prob) - 1
        with col:
            if edge > 0.02:
                bg = "linear-gradient(135deg, #0a2e0a, #1b5e20)" # Verde oscuro elegante
                border = "#4CAF50"
                badge = f"🔥 VALUE DETECTADO (+{edge*100:.1f}%)"
                badge_color = "#4CAF50"
            else:
                bg = "linear-gradient(135deg, #2b0b0b, #5c1616)" # Rojo oscuro elegante
                border = "#E53935"
                badge = f"❌ EV NEGATIVO ({edge*100:.1f}%)"
                badge_color = "#ef9a9a"

            html = f"""
            <div style="background: {bg}; border: 1px solid {border}; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.4); text-align: center; margin-bottom: 20px;">
                <h4 style="color: #ffffff; margin-top: 0; font-weight: 300;">{titulo}</h4>
                <h1 style="color: #ffffff; margin: 10px 0; font-size: 3rem; font-weight: bold;">{cuota_mercado:.2f}</h1>
                <p style="color: #b0bec5; font-size: 14px; margin-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px;">
                    Cuota Justa: <b style="color:white;">{cuota_modelo:.2f}</b> &nbsp;|&nbsp; Prob: <b style="color:white;">{prob*100:.1f}%</b>
                </p>
                <div style="background-color: rgba(0,0,0,0.5); padding: 8px; border-radius: 6px;">
                    <strong style="color: {badge_color}; font-size: 15px;">{badge}</strong>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)

    # --- DASHBOARD PRINCIPAL ---
    st.markdown(f"<h3 style='text-align: center;'>Análisis del Partido</h3>", unsafe_allow_html=True)
    
    # Caja central con los xG
    st.markdown(f"""
    <div style="background-color: #1e1e1e; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 30px; border: 1px solid #333;">
        <h2 style="margin: 0; color: #fff;">{local} <span style="color:#4CAF50;">({modelo['xg_l']:.2f} xG)</span> 🆚 <span style="color:#E53935;">({modelo['xg_v']:.2f} xG)</span> {visita}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🎯 Predicción 1X2", "🥅 Totales (Goles)", "🟨 Mercados Alternos"])
    
    with tab1:
        st.info("💡 **Cómo leer esto:** Si la tarjeta es VERDE, la cuota del mercado paga más de lo que el algoritmo de Goles Esperados dicta. Es una apuesta rentable a largo plazo.")
        m_1, m_x, m_2 = df_p.loc[df_p['1'].idxmax()], df_p.loc[df_p['X'].idxmax()], df_p.loc[df_p['2'].idxmax()]
        c1, c2, c3 = st.columns(3)
        render_card(c1, f"Local: {local}", m_1['1'], modelo['f_1'], modelo['p_1'])
        render_card(c2, "Empate", m_x['X'], modelo['f_x'], modelo['p_x'])
        render_card(c3, f"Visita: {visita}", m_2['2'], modelo['f_2'], modelo['p_2'])

    with tab2:
        if df_p['Over_2.5'].max() > 0:
            m_over, m_under = df_p.loc[df_p['Over_2.5'].idxmax()], df_p.loc[df_p['Under_2.5'].idxmax()]
            co1, co2 = st.columns(2)
            render_card(co1, "Más de 2.5 Goles", m_over['Over_2.5'], modelo['f_over'], modelo['p_over'])
            render_card(co2, "Menos de 2.5 Goles", m_under['Under_2.5'], modelo['f_under'], modelo['p_under'])
        else:
            st.warning("⏳ Las casas de apuestas aún no han abierto líneas de totales para este partido.")

    with tab3:
        st.markdown("### 📊 Proyecciones Estadísticas (Fase de Pruebas)")
        cp1, cp2 = st.columns(2)
        with cp1:
            st.metric(label="🚩 Córners Esperados", value=f"{modelo['exp_corners']:.1f}", delta="Tendencia de Línea Alta" if modelo['exp_corners'] > 10.5 else "Tendencia de Línea Baja" if modelo['exp_corners'] < 8.5 else None)
        with cp2:
            st.metric(label="🟨 Tarjetas Esperadas", value=f"{modelo['exp_tarjetas']:.1f}", delta="Partido Friccionado" if modelo['exp_tarjetas'] > 4.5 else "Partido Limpio" if modelo['exp_tarjetas'] < 3.5 else None, delta_color="inverse")
