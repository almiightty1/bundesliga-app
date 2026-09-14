import streamlit as st
import requests
import pandas as pd
import numpy as np

st.set_page_config(page_title="Bundesliga Betting AI", page_icon="⚽", layout="wide")

st.title("⚽ Bundesliga Sharp Analytics & Predicciones")
st.markdown("Plataforma institucional: Cruce de cuotas en vivo vs. Probabilidades del Modelo Algorítmico.")

API_KEY = "3c5c1e830c72fdda99980f236f3d32ab"
url = f"https://api.the-odds-api.com/v4/sports/soccer_germany_bundesliga/odds/?apiKey={API_KEY}&regions=eu&markets=h2h"

@st.cache_data(ttl=300)
def cargar_datos_cuotas():
    response = requests.get(url)
    if response.status_code == 200:
        matches = []
        for m in response.json():
            home, away, fecha = m.get('home_team'), m.get('away_team'), m.get('commence_time')
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
                        'Cuota_Local': odds.get(home, 0),
                        'Cuota_Empate': odds.get('Draw', 0),
                        'Cuota_Visitante': odds.get(away, 0)
                    })
        return pd.DataFrame(matches)
    return pd.DataFrame()

# Función que simula el motor de xG (Aquí conectaremos FBref a fondo luego)
def calcular_probabilidades_modelo(equipo_local, equipo_visitante):
    # Por ahora, usamos una distribución base estadística de la Bundesliga (45% Local, 25% Empate, 30% Visita)
    # y le agregamos varianza aleatoria controlada para simular el peso de los xG y bajas por lesión.
    # En la siguiente iteración, estos números vendrán exactos del web scraping de FBref.
    np.random.seed(hash(equipo_local + equipo_visitante) % (2**32 - 1))
    fuerza_local = 0.45 + np.random.uniform(-0.1, 0.2)
    fuerza_empate = 0.25 + np.random.uniform(-0.05, 0.05)
    fuerza_visitante = 1 - (fuerza_local + fuerza_empate)
    
    # Retornamos la Cuota Justa (1 / Probabilidad)
    return {
        'Prob_Local': fuerza_local, 'FairOdd_Local': 1/fuerza_local,
        'Prob_Empate': fuerza_empate, 'FairOdd_Empate': 1/fuerza_empate,
        'Prob_Visita': fuerza_visitante, 'FairOdd_Visita': 1/fuerza_visitante
    }

df = cargar_datos_cuotas()

if df.empty:
    st.warning("No hay cuotas disponibles ahora mismo.")
else:
    st.sidebar.header("🎯 Centro de Predicciones")
    partidos_disponibles = df['Encuentro'].unique()
    partido_seleccionado = st.sidebar.selectbox("Selecciona un partido para analizar:", partidos_disponibles)
    
    df_partido = df[df['Encuentro'] == partido_seleccionado]
    equipo_local = df_partido.iloc[0]['Local']
    equipo_visitante = df_partido.iloc[0]['Visitante']
    
    st.header(f"Análisis Algorítmico: {partido_seleccionado}")
    
    # --- 1. DATOS DEL MERCADO (LINE SHOPPING) ---
    mejor_local = df_partido.loc[df_partido['Cuota_Local'].idxmax()]
    mejor_empate = df_partido.loc[df_partido['Cuota_Empate'].idxmax()]
    mejor_visitante = df_partido.loc[df_partido['Cuota_Visitante'].idxmax()]
    
    # --- 2. DATOS DEL MODELO ---
    modelo = calcular_probabilidades_modelo(equipo_local, equipo_visitante)
    
    # --- 3. CÁLCULO DE VALOR (EXPECTED VALUE) ---
    # Si la cuota de la casa de apuestas es MAYOR a la cuota justa de nuestro modelo, HAY VALOR.
    edge_local = (mejor_local['Cuota_Local'] * modelo['Prob_Local']) - 1
    edge_empate = (mejor_empate['Cuota_Empate'] * modelo['Prob_Empate']) - 1
    edge_visitante = (mejor_visitante['Cuota_Visitante'] * modelo['Prob_Visita']) - 1
    
    st.subheader("💡 Pronóstico Deportivo y Detección de Valor")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    
    def mostrar_tarjeta_pronostico(col, titulo, cuota_mercado, cuota_modelo, prob_modelo, edge):
        with col:
            st.markdown(f"**{titulo}**")
            st.write(f"📈 Prob. del Modelo: **{prob_modelo*100:.1f}%**")
            st.write(f"⚖️ Cuota Justa (Fair): **{cuota_modelo:.2f}**")
            st.write(f"🏦 Mejor Cuota Mercado: **{cuota_mercado:.2f}**")
            
            if edge > 0:
                st.success(f"🔥 VALUE BET DETECTADA\n\nVentaja (Edge): +{edge*100:.1f}%")
            else:
                st.error(f"❌ Sin valor matemático\n\nVentaja (Edge): {edge*100:.1f}%")
                
    mostrar_tarjeta_pronostico(col_p1, f"Gana {equipo_local}", mejor_local['Cuota_Local'], modelo['FairOdd_Local'], modelo['Prob_Local'], edge_local)
    mostrar_tarjeta_pronostico(col_p2, "Empate", mejor_empate['Cuota_Empate'], modelo['FairOdd_Empate'], modelo['Prob_Empate'], edge_empate)
    mostrar_tarjeta_pronostico(col_p3, f"Gana {equipo_visitante}", mejor_visitante['Cuota_Visitante'], modelo['FairOdd_Visita'], modelo['Prob_Visita'], edge_visitante)

    st.markdown("---")
    st.markdown("### 📋 Comparador de Casas de Apuestas (Mercado Real)")
    st.dataframe(df_partido[['Casa', 'Cuota_Local', 'Cuota_Empate', 'Cuota_Visitante']].reset_index(drop=True), use_container_width=True)
