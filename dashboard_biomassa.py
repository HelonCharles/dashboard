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
    # O arquivo deve estar na mesma pasta que o script
    gdf = gpd.read_file("dados_auditoria.geojson")
    return gdf

try:
    data = carregar_dados()

    # 3. Painel Lateral de Filtros
    with st.sidebar:
        st.header("🔍 Painel de Controle")
        # Seleção do ano
        ano = st.selectbox("Selecione o Ano de Auditoria", ["2022", "2023", "2024", "2025"])
        
        # Definição dinâmica das colunas conforme o seu GeoJSON (usando '2022', etc)
        col_exp = f"exploracao_{ano}" 
        col_saldo = f"saldo_{ano}"
        
        st.success(f"Dados conectados: {ano}")

    # 4. Cálculo e Exibição de Indicadores (KPIs)
    st.subheader(f"📊 Resumo Operacional - Ano {ano}")
    
    # Cálculos globais
    total_original = data['mudas_2020'].sum()
    saldo_atual = data[col_saldo].sum()
    extraido = total_original - saldo_atual
    progresso = (extraido / total_original) * 100

    c1, c2, c3 = st.columns(3)
    
    # Exibição com formatação brasileira (ponto como separador de milhar)
    c1.metric("Estoque Inicial (2020)", f"{total_original:,.0f}".replace(",", "."))
    c2.metric("Saldo Remanescente", f"{saldo_atual:,.0f}".replace(",", "."), 
              delta=f"-{extraido:,.0f}", delta_color="inverse")
    c3.metric("Progresso da Extração", f"{progresso:.1f}%")

    st.markdown("---")

    # 5. Mapa Interativo (Visualização Espacial)
    st.subheader("🗺️ Visualização dos Talhões")
    
    # Criar o mapa base
    m = leafmap.Map(center=[2.82, -60.67], zoom=12, google_map="SATELLITE")

    # Adicionar os dados com esquema 'UserDefined' (sem underline)
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

    # Renderização via buffer para evitar WinError 32 no Windows
    st_folium(m, width=1200, height=600, returned_objects=[])

    # 6. Relatório Detalhado (Tabela)
    st.markdown("---")
    st.subheader("📋 Detalhamento dos Dados")
    
    # Seleção segura de colunas
    colunas_tabela = ['fid', 'mudas_2020', col_saldo, col_exp]
    df_tabela = data[colunas_tabela].copy()
    
    # Renomear para exibição amigável
    df_tabela.columns = ['ID Talhão', 'Mudas (2020)', 'Saldo Atual', '% Extração']
    
    # Exibir a tabela ordenada pelos mais explorados
    st.dataframe(
        df_tabela.sort_values(by='% Extração', ascending=False), 
        use_container_width=True, 
        hide_index=True
    )

    # Botão para download do relatório
    csv = df_tabela.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar Relatório (CSV)",
        data=csv,
        file_name=f"auditoria_roraima_{ano}.csv",
        mime="text/csv",
    )

except Exception as e:
    st.error(f"⚠️ Erro ao processar os dados: {e}")
    st.info("Dica: Verifique se as colunas 'fid', 'mudas_2020', 'exploracao_2022' e 'saldo_2022' existem no seu GeoJSON.")