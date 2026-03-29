import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from streamlit_folium import st_folium
import pandas as pd
import folium
import plotly.express as px

# 1. Configuração da Interface
st.set_page_config(layout="wide", page_title="BioTrack Roraima", page_icon="🛰️")

# Título Atualizado
st.title("🛰️ BioTrack - Gestão de Consumo e Estoque")
st.markdown("---")

# 2. Carregamento dos Dados
@st.cache_data
def carregar_dados():
    gdf = gpd.read_file("dados_auditoria.geojson")
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf

# Inicializar estado do mapa
if 'map_state' not in st.session_state:
    st.session_state.map_state = {'center': [2.82, -60.67], 'zoom': 12}

try:
    data = carregar_dados()

    # 3. Painel Lateral (Nomenclatura atualizada)
    with st.sidebar:
        st.header("🔍 Painel de Controle")
        ano = st.selectbox("Selecione o Ano de Referência", ["2022", "2023", "2024", "2025"])
        col_exp = f"exploracao_{ano}" 
        col_saldo = f"saldo_{ano}"
        
        st.markdown("---")
        st.subheader("🎯 Localização de Talhão")
        lista_talhoes = sorted(data['fid'].unique().tolist())
        talhao_selecionado = st.selectbox("Escolha o ID para Análise", ["Visão Geral"] + lista_talhoes)
        
        if st.button("🔄 Resetar Mapa"):
            st.session_state.map_state = {'center': [2.82, -60.67], 'zoom': 12}
            st.rerun()

    # 4. KPIs (Consumo e Estoque)
    total_original = data['mudas_2020'].sum()
    saldo_atual = data[col_saldo].sum()
    consumo_total = total_original - saldo_atual
    progresso_consumo = (consumo_total / total_original) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Estoque Inicial (2020)", f"{total_original:,.0f}".replace(",", "."))
    c2.metric("Saldo em Estoque", f"{saldo_atual:,.0f}".replace(",", "."), delta=f"-{consumo_total:,.0f}", delta_color="inverse")
    c3.metric("Percentual de Consumo", f"{progresso_consumo:.1f}%")

    st.markdown("---")

    # 5. Informações do Talhão Selecionado
    if talhao_selecionado != "Visão Geral":
        st.subheader(f"📊 Detalhes de Consumo - Talhão {talhao_selecionado}")
        talhao_data = data[data['fid'] == talhao_selecionado].iloc[0]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ID Talhão", talhao_selecionado)
        col2.metric("Estoque 2020", f"{talhao_data['mudas_2020']:,.0f}".replace(",", "."))
        col3.metric(f"Saldo {ano}", f"{talhao_data[col_saldo]:,.0f}".replace(",", "."))
        
        consumo_talhao = talhao_data['mudas_2020'] - talhao_data[col_saldo]
        col4.metric(f"% Consumo {ano}", f"{talhao_data[col_exp]:.1f}%", 
                    delta=f"-{consumo_talhao:,.0f}".replace(",", ".") if consumo_talhao > 0 else None, 
                    delta_color="inverse")
        
        st.progress(talhao_data[col_exp] / 100, text="Progresso de Consumo do Talhão")
        st.markdown("---")

    # 6. Visualização Espacial
    st.subheader(f"🗺️ Mapa de Consumo: {talhao_selecionado} ({ano})")
    
    # Lógica de Foco
    if talhao_selecionado != "Visão Geral":
        geom = data[data['fid'] == talhao_selecionado].geometry.centroid.iloc[0]
        center = [geom.y, geom.x]
        zoom = 15
    else:
        center = st.session_state.map_state['center']
        zoom = st.session_state.map_state['zoom']

    m = leafmap.Map(center=center, zoom=zoom, google_map="SATELLITE")

    m.add_data(
        data, column=col_exp, scheme="UserDefined", 
        classification_kwds=dict(bins=[1, 30, 70, 99, 100]),
        colors=["#228B22", "#ADFF2F", "#FFFF00", "#FF8C00", "#FF0000"],
        layer_name=f"Status Consumo {ano}",
        fields=["fid", "mudas_2020", col_saldo, col_exp],
        aliases=["ID Talhão", "Estoque 2020", "Saldo Atual", "% Consumo"],
        info_mode="on_hover"
    )

    if talhao_selecionado != "Visão Geral":
        m.add_gdf(data[data['fid'] == talhao_selecionado], 
                  style={"color": "yellow", "weight": 5, "fillOpacity": 0.1},
                  layer_name="Destaque Seleção")

    st_folium(m, key=f"map_{talhao_selecionado}", width=1200, height=500)

    # 7. Tabela com Destaque e Ordenação
    st.markdown("---")
    st.subheader("📋 Relatório de Consumo por Talhão")
    
    df_tabela = data[['fid', 'mudas_2020', col_saldo, col_exp]].copy()
    df_tabela.columns = ['ID Talhão', 'Estoque (2020)', 'Saldo Atual', '% Consumo']
    
    # Ordenação: Selecionado sempre no topo
    if talhao_selecionado != "Visão Geral":
        df_tabela['ordem'] = df_tabela['ID Talhão'].apply(lambda x: 1 if str(x) == str(talhao_selecionado) else 0)
        df_tabela = df_tabela.sort_values(['ordem', '% Consumo'], ascending=[False, False]).drop('ordem', axis=1)
    else:
        df_tabela = df_tabela.sort_values('% Consumo', ascending=False)

    def style_row(row):
        if talhao_selecionado != "Visão Geral" and str(row['ID Talhão']) == str(talhao_selecionado):
            return ['background-color: #FAFF00; color: black; font-weight: bold; border: 2px solid black'] * len(row)
        return [''] * len(row)

    st.dataframe(df_tabela.style.apply(style_row, axis=1).format({'Estoque (2020)': '{:,.0f}', 'Saldo Atual': '{:,.0f}', '% Consumo': '{:.1f}%'}), use_container_width=True, hide_index=True)

    # 8. Gráfico com Destaque Real (Plotly)
    st.markdown("---")
    st.subheader("📈 Ranking de Consumo")
    
    # Criar coluna de cor para o gráfico
    df_tabela['Cor'] = df_tabela['ID Talhão'].apply(lambda x: 'Selecionado' if str(x) == str(talhao_selecionado) else 'Outros')
    
    fig = px.bar(
        df_tabela, x='ID Talhão', y='% Consumo',
        color='Cor',
        color_discrete_map={'Selecionado': '#FAFF00', 'Outros': '#A0A0A0'},
        category_orders={"ID Talhão": df_tabela.sort_values('% Consumo', ascending=False)['ID Talhão'].tolist()}
    )
    fig.update_layout(showlegend=False, margin=dict(l=20, r=20, t=20, b=20), height=400)
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Erro ao carregar dashboard: {e}")
