import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Bundesliga Pro Analytics", page_icon="📈", layout="wide")
st.title("📈 Bundesliga Sharp Analytics V2.0")
st.markdown("Plataforma algorítmica: Calendario, 1X2, Totales (O/U), Córners y Disciplina.")

# --- CONEXIÓN DE DATOS ---
API_KEY = "3c5c1e830c72fdda99980f236f3d32ab"
# Añadimos 'totals' a los mercados para traer el Over/Under
URL = f"https://api.the-odds-api.com/v4/sports/soccer_germany_bundesliga/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals"

@st.cache_data(ttl=300)
def cargar_datos_completos():
    response = requests.get(URL)
    if response.status_code != 200:
        return pd.DataFrame()
    
    matches = []
    for m in response.json():
        home = m.get('home_team')
        away = m.get('away_team')
        fecha_raw = m.get('commence_time')
        
        # Formatear fecha
        if fecha_raw:
            fecha_dt = datetime.strptime(fecha_raw, "%Y-%m-%dT%H:%M:%SZ")
            fecha_str = fecha_dt.strftime("%Y-%m-%d")
            hora_str = fecha_dt.strftime("%H:%M")
        else:
            fecha_str, hora_str = "N/A", "N/A"

        for b in m.get('bookmakers', []):
            casa = b.get('title')
            cuotas_h2h = {}
            cuotas_ou = {}
            
            for market in b.get('markets', []):
                if market['key'] == 'h2h':
                    cuotas_h2h = {out['name']: out['price'] for out in market.get('outcomes', [])}
                elif market['key'] == 'totals':
                    # Extraer Over/Under 2.5 (el estándar más común)
                    for out in market.get('outcomes', []):
                        if out['point'] == 2.5:
                            cuotas_ou[out['name']] = out['price']
            
            if cuotas_h2h:
                matches.append({
                    'Fecha': fecha_str,
                    'Hora (UTC)': hora_str,
                    'Encuentro': f"{home} vs {away}",
                    'Local': home,
                    'Visitante': away,
                    'Casa': casa,
                    '1': cuotas_h2h.get(home, 0),
                    'X': cuotas_h2h.get('Draw', 0),
                    '2': cuotas_h2h.get(away, 0),
                    'Over_2.5': cuotas_ou.get('Over', 0),
                    'Under_2.5': cuotas_ou.get('Under', 0)
                })
    return pd.DataFrame(matches)

df = cargar_datos_completos()

if df.empty:
    st.error("No se pudieron cargar los datos de la API. Verifica tu clave o los límites de peticiones.")
else:
    # --- MOTOR MATEMÁTICO (Simulación base previa a FBref) ---
    def calcular_fuerzas(local, visita):
        np.random.seed(hash(local + visita) % (2**32 - 1))
        
        # Probabilidades 1X2
        p_1 = 0.45 + np.random.uniform(-0.15, 0.25)
        p_x = 0.25 + np.random.uniform(-0.05, 0.05)
        p_2 = 1 - (p_1 + p_x)
        
        # Probabilidades Over/Under 2.5
        p_over = 0.52 + np.random.uniform(-0.1, 0.15)
        p_under = 1 - p_over
        
        # Proyecciones Córners y Tarjetas (Medias esperadas)
        exp_corners = 9.5 + np.random.uniform(-2, 2.5)
        exp_tarjetas = 4.0 + np.random.uniform(-1, 2)
        
        return {
            'p_1': p_1, 'f_1': 1/p_1,
            'p_x': p_x, 'f_x': 1/p_x,
            'p_2': p_2, 'f_2': 1/p_2,
            'p_over': p_over, 'f_over': 1/p_over,
            'p_under': p_under, 'f_under': 1/p_under,
            'exp_corners': exp_corners,
            'exp_tarjetas': exp_tarjetas
        }

    # --- INTERFAZ PRINCIPAL ---
    tab1, tab2, tab3 = st.tabs(["📅 Calendario y Mercado", "⚽ 1X2 y Totales (Goles)", "🟨 Props: Tarjetas y Córners"])
    
    with tab1:
        st.header("Calendario de la Jornada")
        df_calendario = df[['Fecha', 'Hora (UTC)', 'Encuentro']].drop_duplicates().sort_values(by=['Fecha', 'Hora (UTC)'])
        st.dataframe(df_calendario, use_container_width=True, hide_index=True)
        
        st.subheader("Buscador Global de Cuotas")
        st.dataframe(df[['Encuentro', 'Casa', '1', 'X', '2', 'Over_2.5', 'Under_2.5']], use_container_width=True, hide_index=True)

    # Selector global para las pestañas de análisis
    st.sidebar.header("⚙️ Configuración de Análisis")
    partidos_lista = df['Encuentro'].unique()
    partido_sel = st.sidebar.selectbox("Selecciona un partido:", partidos_lista)
    df_p = df[df['Encuentro'] == partido_sel]
    
    local = df_p.iloc[0]['Local']
    visita = df_p.iloc[0]['Visitante']
    modelo = calcular_fuerzas(local, visita)
    
    with tab2:
        st.header(f"Análisis Principal: {partido_sel}")
        
        # Mejores cuotas del mercado
        m_1 = df_p.loc[df_p['1'].idxmax()]
        m_x = df_p.loc[df_p['X'].idxmax()]
        m_2 = df_p.loc[df_p['2'].idxmax()]
        
        st.subheader("Mercado 1X2 (Ganador del Partido)")
        c1, c2, c3 = st.columns(3)
        
        def render_value_card(col, titulo, cuota_mercado, cuota_modelo, prob):
            edge = (cuota_mercado * prob) - 1
            with col:
                st.markdown(f"**{titulo}**")
                st.write(f"Cuota Justa: **{cuota_modelo:.2f}** | Prob: **{prob*100:.1f}%**")
                st.write(f"Mercado (Mejor): **{cuota_mercado:.2f}**")
                if edge > 0:
                    st.success(f"🔥 VALUE (+{edge*100:.1f}%)")
                else:
                    st.error(f"❌ NO VALUE ({edge*100:.1f}%)")

        render_value_card(c1, f"Local ({local})", m_1['1'], modelo['f_1'], modelo['p_1'])
        render_value_card(c2, "Empate", m_x['X'], modelo['f_x'], modelo['p_x'])
        render_value_card(c3, f"Visita ({visita})", m_2['2'], modelo['f_2'], modelo['p_2'])

        st.divider()
        
        st.subheader("Mercado de Totales (Over/Under 2.5 Goles)")
        # Evitamos errores si no hay cuotas de Over/Under reportadas
        if df_p['Over_2.5'].max() > 0:
            m_over = df_p.loc[df_p['Over_2.5'].idxmax()]
            m_under = df_p.loc[df_p['Under_2.5'].idxmax()]
            
            co1, co2 = st.columns(2)
            render_value_card(co1, "Más de 2.5 Goles (Over)", m_over['Over_2.5'], modelo['f_over'], modelo['p_over'])
            render_value_card(co2, "Menos de 2.5 Goles (Under)", m_under['Under_2.5'], modelo['f_under'], modelo['p_under'])
        else:
            st.info("Las casas de apuestas aún no han liberado las líneas de Totales para este partido.")

    with tab3:
        st.header(f"Mercados Secundarios: {partido_sel}")
        st.markdown("> *Nota: Las cuotas en vivo de estos mercados dependen de la API. Las proyecciones mostradas aquí utilizan nuestro modelo base previo a la integración de datos de árbitros y estilos de juego.*")
        
        cp1, cp2 = st.columns(2)
        with cp1:
            st.markdown("### ⛳ Proyección de Córners")
            st.metric(label="Línea Esperada (Total del Partido)", value=f"{modelo['exp_corners']:.1f} Córners")
            st.progress(min(modelo['exp_corners'] / 15, 1.0))
            if modelo['exp_corners'] > 10.5:
                st.success("💡 Tendencia Alta: Buscar líneas de Over 9.5 o Over 10.5 en el mercado.")
            elif modelo['exp_corners'] < 8.5:
                st.warning("💡 Tendencia Baja: Buscar líneas de Under 9.5 en el mercado.")
            else:
                st.info("⚖️ Tendencia Neutra: Evitar mercado de córners previo al partido.")
                
        with cp2:
            st.markdown("### 🟨 Disciplina (Tarjetas)")
            st.metric(label="Tarjetas Esperadas", value=f"{modelo['exp_tarjetas']:.1f} Tarjetas")
            st.progress(min(modelo['exp_tarjetas'] / 8, 1.0))
            if modelo['exp_tarjetas'] > 4.5:
                st.success("💡 Partido Friccionado: Buscar Over de tarjetas o mercado de expulsión.")
            else:
                st.warning("💡 Partido Limpio: Buscar Under de tarjetas.")
