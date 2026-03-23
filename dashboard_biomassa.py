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

# Inicializar estado do mapa na sessão
if 'map_state' not in st.session_state:
    st.session_state.map_state = {
        'center': [2.82, -60.67],
        'zoom': 12,
        'bounds': None
    }

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
        
        # Botão para resetar o mapa
        if st.button("🔄 Resetar Visualização do Mapa"):
            st.session_state.map_state = {
                'center': [2.82, -60.67],
                'zoom': 12,
                'bounds': None
            }
            st.rerun()

        # Botão para focar no talhão selecionado (opcional)
        if talhao_selecionado != "Visão Geral":
            if st.button("🎯 Centralizar no Talhão"):
                geom = data[data['fid'] == talhao_selecionado].geometry.centroid.iloc[0]
                st.session_state.map_state['center'] = [geom.y, geom.x]
                st.session_state.map_state['zoom'] = 16
                st.rerun()

    # 4. KPIs
    total_original = data['mudas_2020'].sum()
    saldo_atual = data[col_saldo].sum()
    extraido = total_original - saldo_atual
    progresso = (extraido / total_original) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("Estoque Inicial (2020)", f"{total_original:,.0f}".replace(",", "."))
    c2.metric("Saldo Remanescente", f"{saldo_atual:,.0f}".replace(",", "."), delta=f"-{extraido:,.0f}", delta_color="inverse")
    c3.metric("Progresso da Extração", f"{progresso:.1f}%")

    st.markdown("---")

    # 5. Visualização Espacial
    st.subheader(f"🗺️ Mapa: {talhao_selecionado} ({ano})")
    
    # Determinar centro e zoom baseado no estado salvo
    # Mas se mudou o talhão via filtro, mantém o estado atual
    center = st.session_state.map_state['center']
    zoom = st.session_state.map_state['zoom']
    
    # Criar mapa
    m = leafmap.Map(center=center, zoom=zoom, google_map="SATELLITE")

    # Adicionar dados ao mapa
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

    # Se houver um talhão específico selecionado e o usuário não está usando o controle manual,
    # podemos adicionar um marcador destacado
    if talhao_selecionado != "Visão Geral":
        geom_talhao = data[data['fid'] == talhao_selecionado].geometry.iloc[0]
        # Criar um estilo destacado para o polígono selecionado
        m.add_gdf(
            gpd.GeoDataFrame(geometry=[geom_talhao], crs="EPSG:4326"),
            style={"color": "yellow", "weight": 4, "fillOpacity": 0.1},
            layer_name=f"Talhão {talhao_selecionado} (Destacado)"
        )
        
        # Adicionar um popup com informações
        row = data[data['fid'] == talhao_selecionado].iloc[0]
        popup_html = f"""
        <div style="font-family: monospace;">
            <b>ID Talhão:</b> {talhao_selecionado}<br>
            <b>Mudas 2020:</b> {row['mudas_2020']:,.0f}<br>
            <b>Saldo {ano}:</b> {row[col_saldo]:,.0f}<br>
            <b>% Extração:</b> {row[col_exp]:.1f}%
        </div>
        """
        
        # Adicionar marcador no centro do polígono
        centroid = geom_talhao.centroid
        m.add_marker([centroid.y, centroid.x], popup=popup_html)

    # Exibir mapa e capturar interações
    output = st_folium(
        m, 
        key=f"map_instance_{ano}_{talhao_selecionado}", 
        width=1200, 
        height=600,
        returned_objects=["last_center", "last_bounds", "last_zoom"]
    )
    
    # Atualizar o estado do mapa baseado nas interações do usuário
    if output and output.get('last_center') and output.get('last_zoom'):
        # Verificar se houve mudança significativa (evita loops)
        new_center = [output['last_center']['lat'], output['last_center']['lng']]
        new_zoom = output['last_zoom']
        
        # Atualizar estado apenas se o centro ou zoom mudaram
        if (new_center != st.session_state.map_state['center'] or 
            new_zoom != st.session_state.map_state['zoom']):
            st.session_state.map_state['center'] = new_center
            st.session_state.map_state['zoom'] = new_zoom
            
            # Se houver bounds, salvar também
            if output.get('last_bounds'):
                st.session_state.map_state['bounds'] = output['last_bounds']
    
    # 6. Relatório Detalhado
    st.markdown("---")
    st.subheader("📋 Detalhamento dos Dados")
    colunas_tabela = ['fid', 'mudas_2020', col_saldo, col_exp]
    df_tabela = data[colunas_tabela].copy()
    df_tabela.columns = ['ID Talhão', 'Mudas (2020)', 'Saldo Atual', '% Extração']
    st.dataframe(df_tabela.sort_values(by='% Extração', ascending=False), use_container_width=True, hide_index=True)
    
    # Opção para exportar dados
    st.markdown("---")
    if st.button("📊 Exportar Dados para CSV"):
        csv = df_tabela.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"biotrack_dados_{ano}.csv",
            mime="text/csv"
        )

except Exception as e:
    st.error(f"⚠️ Erro: {e}")
    st.exception(e)