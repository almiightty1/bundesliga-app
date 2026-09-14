import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Bundesliga Betting AI", page_icon="⚽", layout="wide")

st.title("⚽ Bundesliga Sharp Analytics & Line Shopping")
st.markdown("Plataforma para el análisis institucional de cuotas y detección de valor en la Bundesliga alemana.")

API_KEY = "3c5c1e830c72fdda99980f236f3d32ab"
url = f"https://api.the-odds-api.com/v4/sports/soccer_germany_bundesliga/odds/?apiKey={API_KEY}&regions=eu&markets=h2h"

@st.cache_data(ttl=300)
def cargar_datos():
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        matches = []
        for m in data:
            home = m.get('home_team')
            away = m.get('away_team')
            fecha = m.get('commence_time')
            for b in m.get('bookmakers', []):
                casa = b.get('title')
                markets = b.get('markets', [])
                if markets:
                    odds = {out['name']: out['price'] for out in markets[0].get('outcomes', [])}
                    matches.append({
                        'Fecha': fecha[:10] if fecha else '',
                        'Encuentro': f"{home} vs {away}",
                        'Local': home,
                        'Visitante': away,
                        'Casa': casa,
                        'Cuota_Local': odds.get(home),
                        'Cuota_Empate': odds.get('Draw'),
                        'Cuota_Visitante': odds.get(away)
                    })
        return pd.DataFrame(matches)
    return pd.DataFrame()

df = cargar_datos()

if df.empty:
    st.warning("No hay partidos activos con cuotas en este momento o la API no devolvió datos.")
else:
    st.sidebar.header("Filtros de Partido")
    partidos_disponibles = df['Encuentro'].unique()
    partido_seleccionado = st.sidebar.selectbox("Selecciona un partido:", partidos_disponibles)
    
    df_partido = df[df['Encuentro'] == partido_seleccionado]
    
    st.subheader(f"📊 Análisis de Cuotas para: {partido_seleccionado}")
    
    if not df_partido.empty:
        mejor_local = df_partido.loc[df_partido['Cuota_Local'].idxmax()]
        mejor_empate = df_partido.loc[df_partido['Cuota_Empate'].idxmax()]
        mejor_visitante = df_partido.loc[df_partido['Cuota_Visitante'].idxmax()]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label=f"Mejor Cuota Local ({mejor_local['Local']})", value=mejor_local['Cuota_Local'], delta=mejor_local['Casa'])
        with col2:
            st.metric(label="Mejor Cuota Empate", value=mejor_empate['Cuota_Empate'], delta=mejor_empate['Casa'])
        with col3:
            st.metric(label=f"Mejor Cuota Visitante ({mejor_visitante['Visitante']})", value=mejor_visitante['Cuota_Visitante'], delta=mejor_visitante['Casa'])
            
        st.markdown("---")
        st.markdown("### 📋 Comparativa completa entre todas las Casas de Apuestas")
        st.dataframe(df_partido[['Casa', 'Cuota_Local', 'Cuota_Empate', 'Cuota_Visitante']].reset_index(drop=True), use_container_width=True)
