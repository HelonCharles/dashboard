import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import folium

# 1. Configuração da Página
st.set_page_config(page_title="Monitoramento Acácia - Roraima", layout="wide")

@st.cache_data
def load_data():
    # Carrega o GeoJSON
    gdf = gpd.read_file("dados_auditoria.geojson")
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf

try:
    data = load_data()

    # 2. Título e Painel Lateral
    st.title("🌳 Dashboard de Monitoramento: Exploração de Acácia")
    st.sidebar.header("Painel de Controle")
    
    ano_ref = st.sidebar.selectbox("Ano de Referência", ["2022", "2023", "2024", "2025"], index=3)
    
    # Definição das colunas baseadas no ano
    col_exp = f"exploracao_{ano_ref}"
    col_saldo = f"saldo_{ano_ref}"
    
    lista_talhoes = sorted(data['fid'].unique().tolist())
    talhao_selecionado = st.sidebar.selectbox("Focar em Talhão", ["Visão Geral"] + lista_talhoes)

    # 3. Métricas de Resumo
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    total_2020 = data['mudas_2020'].sum()
    saldo_atual = data[col_saldo].sum()
    consumo_total = (1 - (saldo_atual / total_2020)) * 100

    with m1:
        st.metric("Estoque Inicial (2020)", f"{total_2020:,.0f}")
    with m2:
        st.metric(f"Saldo em Estoque ({ano_ref})", f"{saldo_atual:,.0f}", f"-{(total_2020 - saldo_atual):,.0f}")
    with m3:
        st.metric("Percentual de Consumo", f"{consumo_total:.2f}%")

    # 4. Mapa e Detalhes
    col_mapa, col_info = st.columns([2, 1])

    with col_mapa:
        m = leafmap.Map(center=[2.82, -60.67], zoom=12, google_map="HYBRID")
        
        def style_function(feature):
            consumo = feature['properties'][col_exp]
            return {
                'fillOpacity': 0.7,
                'weight': 1,
                'color': 'white',
                'fillColor': '#ff0000' if consumo >= 70 else '#ffff00' if consumo >= 30 else '#00ff00'
            }

        m.add_gdf(data, layer_name="Talhões", style_function=style_function)

        if talhao_selecionado != "Visão Geral":
            selected_gdf = data[data['fid'] == talhao_selecionado]
            m.add_gdf(selected_gdf, layer_name="Destaque", 
                      style={'color': '#FAFF00', 'weight': 4, 'fillOpacity': 0})
            centroid = selected_gdf.geometry.centroid.iloc[0]
            folium.Marker([centroid.y, centroid.x], popup=f"Talhão {talhao_selecionado}").add_to(m)

        m.to_streamlit(height=500)

    with col_info:
        if talhao_selecionado != "Visão Geral":
            st.subheader(f"📍 Talhão {talhao_selecionado}")
            row_data = data[data['fid'] == talhao_selecionado].iloc[0]
            prog = float(row_data[col_exp])
            st.write(f"**Consumo Atual:** {prog:.1f}%")
            st.progress(min(prog/100, 1.0))
            st.write(f"**Saldo:** {row_data[col_saldo]:,.0f}")
        else:
            st.info("Selecione um talhão para ver os dados específicos aqui.")

    # 5. Relatório em Tabela
    st.markdown("---")
    st.subheader("📋 Relatório por Talhão")
    
    df_tabela = data[['fid', 'mudas_2020', col_saldo, col_exp]].copy()
    
    if talhao_selecionado != "Visão Geral":
        df_tabela['is_selected'] = df_tabela['fid'].apply(lambda x: 1 if str(x) == str(talhao_selecionado) else 0)
        df_tabela = df_tabela.sort_values(by=['is_selected', col_exp], ascending=[False, False]).drop(columns=['is_selected'])
    else:
        df_tabela = df_tabela.sort_values(by=col_exp, ascending=False)
    
    def color_rows(row):
        if talhao_selecionado != "Visão Geral" and str(row['fid']) == str(talhao_selecionado):
            return ['background-color: #FAFF00; color: black; font-weight: bold'] * len(row)
        return [''] * len(row)

    st.dataframe(
        df_tabela.style.apply(color_rows, axis=1).format({
            'mudas_2020': '{:,.0f}',
            col_saldo: '{:,.0f}',
            col_exp: '{:.1f}%'
        }),
        column_config={"fid": "ID", "mudas_2020": "Estoque", col_saldo: "Saldo", col_exp: "% Consumo"},
        use_container_width=True, hide_index=True
    )

    # 6. Gráficos de Ranking e Evolução
    st.markdown("---")
    with st.expander("📊 Análise Gráfica Detalhada", expanded=True):
        
        # Ranking de Barras
        df_grafico = df_tabela.copy()
        id_sel_str = str(talhao_selecionado)
        df_grafico['fid_str'] = df_grafico['fid'].astype(str)
        df_grafico['Destaque'] = df_grafico['fid_str'].apply(lambda x: 'Sim' if x == id_sel_str else 'Não')

        fig_bar = px.bar(
            df_grafico, x='fid_str', y=col_exp, color='Destaque',
            color_discrete_map={'Sim': '#FAFF00', 'Não': '#A0A0A0'},
            category_orders={"fid_str": df_grafico['fid_str'].tolist()}
        )
        
        fig_bar.update_layout(showlegend=False, height=350, xaxis_title="Talhão", yaxis_title="% Consumo", plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)

        # Gráfico de Linhas (Evolução Temporal)
        if talhao_selecionado != "Visão Geral":
            st.markdown("---")
            st.subheader(f"📈 Evolução do Consumo - Talhão {talhao_selecionado}")
            
            anos = ["2022", "2023", "2024", "2025"]
            dados_h = data[data['fid'] == talhao_selecionado].iloc[0]
            df_hist = pd.DataFrame([{"Ano": a, "Consumo": dados_h[f"exploracao_{a}"]} for a in anos])
            
            fig_line = px.line(df_hist, x="Ano", y="Consumo", markers=True, text=[f"{v:.1f}%" for v in df_hist["Consumo"]])
            fig_line.update_traces(line_color='#FAFF00', line_width=4, marker=dict(size=10, color="black"))
            fig_line.update_layout(height=300, yaxis_range=[0, 105], plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_line, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Erro: {e}")
