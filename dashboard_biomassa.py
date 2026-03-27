import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import os

# 1. Configuração da Página
st.set_page_config(layout="wide", page_title="BioTrack Roraima")

# Título
st.title("🌲 Monitoramento de Biomassa - Roraima")

# 2. Carregamento Seguro de Dados
@st.cache_data
def load_data():
    # Verifica se o arquivo existe na pasta atual (evita erro de caminho)
    file_path = "dados_auditoria.geojson"
    if not os.path.exists(file_path):
        st.error(f"Arquivo {file_path} não encontrado na pasta do projeto!")
        return None
    
    gdf = gpd.read_file(file_path)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf

data = load_data()

if data is not None:
    # --- BARRA LATERAL ---
    st.sidebar.header("🎮 Painel de Controle")
    ano = st.sidebar.selectbox("📅 Selecionar Ano", [2022, 2023, 2024, 2025], index=3)
    col_saldo = f"saldo_{ano}"
    col_exp = f"exploracao_{ano}"

    lista_talhoes = ["Visão Geral"] + sorted(data['fid'].unique().tolist())
    talhao_selecionado = st.sidebar.selectbox("📍 Localizar Talhão", lista_talhoes)

    # --- KPIs NO TOPO ---
    t_2020 = data['mudas_2020'].sum()
    s_atual = data[col_saldo].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("🌱 Estoque 2020", f"{t_2020:,.0f}")
    c2.metric("📉 Saldo Atual", f"{s_atual:,.0f}")
    c3.metric("⚡ % Extraído", f"{( (t_2020 - s_atual)/t_2020 )*100:.1f}%")

    # --- MAPA ---
    st.subheader(f"🗺️ Mapa: {talhao_selecionado}")
    
    # Lógica de Centro e Zoom
    if talhao_selecionado != "Visão Geral":
        target = data[data['fid'] == talhao_selecionado].geometry.centroid.iloc[0]
        center = [target.y, target.x]
        zoom = 15
    else:
        center = [2.82, -60.67]
        zoom = 10

    m = leafmap.Map(center=center, zoom=zoom, google_map="SATELLITE")

    # Camada colorida
    m.add_data(
        data, column=col_exp, scheme="UserDefined",
        classification_kwds=dict(bins=[1, 30, 70, 99, 100]),
        colors=["#228B22", "#ADFF2F", "#FFFF00", "#FF8C00", "#FF0000"],
        layer_name="Status Extração"
    )

    # Destaque se selecionado
    if talhao_selecionado != "Visão Geral":
        m.add_gdf(data[data['fid'] == talhao_selecionado], 
                  style={"color": "yellow", "weight": 5, "fillOpacity": 0},
                  layer_name="Destaque")

    st_folium(m, width=1200, height=500, key=f"mapa_{talhao_selecionado}_{ano}")

    # --- TABELA COM DESTAQUE ---
    st.subheader("📋 Tabela de Dados")
    
    def destacar_linha(row):
        if talhao_selecionado != "Visão Geral" and str(row['fid']) == str(talhao_selecionado):
            return ['background-color: yellow; color: black'] * len(row)
        return [''] * len(row)

    df_mostrar = data[['fid', 'mudas_2020', col_saldo, col_exp]].copy()
    st.dataframe(df_mostrar.style.apply(destacar_linha, axis=1), use_container_width=True)

    # --- GRÁFICO ---
    st.subheader("📊 Ranking de Extração")
    st.bar_chart(data.set_index('fid')[col_exp])
