import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from streamlit_folium import st_folium

# 1. Configuração da Interface
st.set_page_config(layout="wide", page_title="BioTrack Roraima", page_icon="🛰️")

st.title("🛰️ BioTrack - Auditoria de Biomassa")
st.markdown("---")

# 2. Carregamento dos Dados
@st.cache_data
def carregar_dados():
    gdf = gpd.read_file("dados_auditoria.geojson")
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf

try:
    data = carregar_dados()

    # 3. Painel Lateral
    with st.sidebar:
        st.header("🔍 Painel de Controle")
        ano = st.selectbox("Selecione o Ano de Auditoria", ["2022", "2023", "2024", "2025"])
        col_exp = f"exploracao_{ano}" 
        col_saldo = f"saldo_{ano}"
        
        st.markdown("---")
        st.subheader("🎯 Focar em Talhão")
        lista_talhoes = sorted(data['fid'].unique().tolist())
        talhao_selecionado = st.selectbox("Escolha o ID para Inspeção", ["Visão Geral"] + lista_talhoes)

        # DEFINIÇÃO RÍGIDA DE COORDENADAS
        if talhao_selecionado != "Visão Geral":
            geom = data[data['fid'] == talhao_selecionado].geometry.centroid.iloc[0]
            lat, lon, zoom = geom.y, geom.x, 16
        else:
            lat, lon, zoom = 2.82, -60.67, 12

    # 4. KPIs (Seu cálculo original)
    total_original = data['mudas_2020'].sum()
    saldo_atual = data[col_saldo].sum()
    extraido = total_original - saldo_atual
    progresso = (extraido / total_original) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Estoque Inicial (2020)", f"{total_original:,.0f}".replace(",", "."))
    c2.metric("Saldo Remanescente", f"{saldo_atual:,.0f}".replace(",", "."), delta=f"-{extraido:,.0f}", delta_color="inverse")
    c3.metric("Progresso da Extração", f"{progresso:.1f}%")

    st.markdown("---")

    # 5. Visualização Espacial (O truque da KEY ÚNICA)
    st.subheader(f"🗺️ Mapa: {talhao_selecionado} ({ano})")
    
    m = leafmap.Map(center=[lat, lon], zoom=zoom, google_map="SATELLITE")

    m.add_data(
        data,
        column=col_exp,
        scheme="UserDefined", 
        classification_kwds=dict(bins=[1, 30, 70, 99, 100]),
        colors=["#228B22", "#ADFF2F", "#FFFF00", "#FF8C00", "#FF0000"],
        layer_name=f"Status {ano}",
        fields=["fid", "mudas_2020", col_saldo, col_exp],
        aliases=["ID Talhão", "Mudas 2020", "Saldo Atual", "% Extraído"]
    )

    # A KEY abaixo é o que impede o mapa de "voltar para a origem"
    # Toda vez que você muda o ano ou o talhão, o Streamlit cria um mapa "novo"
    st_folium(
        m, 
        key=f"map_instance_{ano}_{talhao_selecionado}", 
        width=1200, 
        height=600,
        returned_objects=[] # Ignoramos o retorno para não gerar loops
    )

    # 6. Relatório Detalhado (Tabela)
    st.markdown("---")
    st.subheader("📋 Detalhamento dos Dados")
    colunas_tabela = ['fid', 'mudas_2020', col_saldo, col_exp]
    df_tabela = data[colunas_tabela].copy()
    df_tabela.columns = ['ID Talhão', 'Mudas (2020)', 'Saldo Atual', '% Extração']
    st.dataframe(df_tabela.sort_values(by='% Extração', ascending=False), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ Erro: {e}")