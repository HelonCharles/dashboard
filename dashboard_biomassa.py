import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from streamlit_folium import st_folium
import pandas as pd
import folium
import plotly.express as px

# 1. Configuração da Interface
st.set_page_config(layout="wide", page_title="BioTrack Roraima", page_icon="🛰️")

# Título
st.title("🛰️ BioTrack - Gestão de Consumo e Estoque")
st.markdown("---")

# 2. Carregamento dos Dados
@st.cache_data
def carregar_dados():
    gdf = gpd.read_file("dados_auditoria.geojson")
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf

if 'map_state' not in st.session_state:
    st.session_state.map_state = {'center': [2.82, -60.67], 'zoom': 12}

try:
    data = carregar_dados()

    # 3. Painel Lateral
    with st.sidebar:
        st.header("🔍 Painel de Controle")
        ano = st.selectbox("Selecione o Ano de Referência", ["2022", "2023", "2024", "2025"], index=3)
        col_exp = f"exploracao_{ano}" 
        col_saldo = f"saldo_{ano}"
        
        st.markdown("---")
        st.subheader("🎯 Localização de Talhão")
        lista_talhoes = sorted(data['fid'].unique().tolist())
        talhao_selecionado = st.selectbox("Escolha o ID para Análise", ["Visão Geral"] + lista_talhoes)
        
        if st.button("🔄 Resetar Mapa"):
            st.session_state.map_state = {'center': [2.82, -60.67], 'zoom': 12}
            st.rerun()

    # 4. KPIs
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
        consumo_t = talhao_data['mudas_2020'] - talhao_data[col_saldo]
        col4.metric(f"% Consumo {ano}", f"{talhao_data[col_exp]:.1f}%", delta=f"-{consumo_t:,.0f}".replace(",", "."), delta_color="inverse")
        st.progress(talhao_data[col_exp] / 100)
        st.markdown("---")

    # 6. Visualização Espacial (Foco no Destaque Amarelo)
    st.subheader(f"🗺️ Mapa de Consumo: {talhao_selecionado} ({ano})")
    
    if talhao_selecionado != "Visão Geral":
        target = data[data['fid'] == talhao_selecionado].geometry.centroid.iloc[0]
        center, zoom = [target.y, target.x], 15
    else:
        center, zoom = st.session_state.map_state['center'], st.session_state.map_state['zoom']

    m = leafmap.Map(center=center, zoom=zoom, google_map="SATELLITE")

    # Camada de Dados
    m.add_data(
        data, column=col_exp, scheme="UserDefined", 
        classification_kwds=dict(bins=[1, 30, 70, 99, 100]),
        colors=["#228B22", "#ADFF2F", "#FFFF00", "#FF8C00", "#FF0000"],
        layer_name="Status Consumo",
        fields=["fid", "mudas_2020", col_saldo, col_exp],
        aliases=["ID", "Estoque 2020", "Saldo", "% Consumo"],
        info_mode="on_hover"
    )

    # ✅ Destaque Forçado (Borda Amarela Grossa)
    if talhao_selecionado != "Visão Geral":
        feature = data[data['fid'] == talhao_selecionado]
        folium.GeoJson(
            feature,
            name="Destaque Seleção",
            style_function=lambda x: {'fillColor': 'none', 'color': '#FAFF00', 'weight': 6}
        ).add_to(m)

    st_folium(m, key=f"map_{talhao_selecionado}_{ano}", width=1200, height=500)

    # 7. Tabela
    st.markdown("---")
    st.subheader("📋 Relatório de Consumo por Talhão")
    df_tab = data[['fid', 'mudas_2020', col_saldo, col_exp]].copy()
    df_tab.columns = ['ID Talhão', 'Estoque (2020)', 'Saldo Atual', '% Consumo']
    
    if talhao_selecionado != "Visão Geral":
        df_tab['ordem'] = df_tab['ID Talhão'].apply(lambda x: 1 if str(x) == str(talhao_selecionado) else 0)
        df_tab = df_tab.sort_values(['ordem', '% Consumo'], ascending=[False, False]).drop('ordem', axis=1)
    else:
        df_tab = df_tab.sort_values('% Consumo', ascending=False)

    def style_row(row):
        if talhao_selecionado != "Visão Geral" and str(row['ID Talhão']) == str(talhao_selecionado):
            return ['background-color: #FAFF00; color: black; font-weight: bold'] * len(row)
        return [''] * len(row)

    st.dataframe(df_tab.style.apply(style_row, axis=1).format({'Estoque (2020)': '{:,.0f}', 'Saldo Atual': '{:,.0f}', '% Consumo': '{:.1f}%'}), use_container_width=True, hide_index=True)

    # 8. Gráfico com Destaque Corrigido
    st.markdown("---")
    st.subheader("📈 Ranking de Consumo")
    
    df_graph = df_tab.copy()
    df_graph['Status'] = df_graph['ID Talhão'].apply(lambda x: 'Selecionado' if str(x) == str(talhao_selecionado) else 'Outros')
    
    # Forçamos as cores e a ordem para o gráfico respeitar a seleção
    fig = px.bar(
        df_graph, x='ID Talhão', y='% Consumo', color='Status',
        color_discrete_map={'Selecionado': '#FAFF00', 'Outros': '#A0A0A0'},
        category_orders={"ID Talhão": df_graph['ID Talhão'].tolist()}
    )
    fig.update_layout(showlegend=False, height=400)
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Erro: {e}")
