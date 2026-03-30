import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
import pandas as pd
import plotly.express as px
from streamlit_folium import st_folium
import folium

# Configuração da página
st.set_page_config(page_title="Monitoramento de Acácia - Roraima", layout="wide")

# Estilo CSS para melhorar o visual
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def load_data():
    # Certifique-se de que o nome do arquivo abaixo é EXATAMENTE igual ao que está no GitHub
    gdf = gpd.read_file("dados_auditoria.geojson")
    if gdf.crs is None:
        gdf.set_crs(epsg=4326, inplace=True)
    elif gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf

try:
    data = load_data()

    # 1. Título e Barra Lateral
    st.title("🌳 Dashboard de Monitoramento: Exploração de Acácia")
    st.sidebar.header("Painel de Controle")
    
    ano_ref = st.sidebar.selectbox("Ano de Referência", ["2022", "2023", "2024", "2025"], index=3)
    
    # Mapeamento dinâmico de colunas baseado no ano
    col_exp = f"exploracao_{ano_ref}"
    col_saldo = f"saldo_{ano_ref}"
    
    # Filtro de Talhão
    lista_talhoes = sorted(data['fid'].unique().tolist())
    talhao_selecionado = st.sidebar.selectbox("Focar em Talhão", ["Visão Geral"] + lista_talhoes)

    # 2. Métricas Principais (Topo)
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    
    total_2020 = data['mudas_2020'].sum()
    saldo_atual = data[col_saldo].sum()
    consumo_percent = (1 - (saldo_atual / total_2020)) * 100

    with c1:
        st.metric("Estoque Inicial (2020)", f"{total_2020:,.0f} mudas")
    with c2:
        st.metric(f"Saldo em Estoque ({ano_ref})", f"{saldo_atual:,.0f}", f"-{(total_2020 - saldo_atual):,.0f}")
    with c3:
        st.metric("Percentual de Consumo", f"{consumo_percent:.2f}%")

    # 3. Layout Principal (Mapa e Detalhes)
    col_mapa, col_info = st.columns([2, 1])

    with col_info:
        if talhao_selecionado != "Visão Geral":
            st.subheader(f"📍 Detalhes: Talhão {talhao_selecionado}")
            row = data[data['fid'] == talhao_selecionado].iloc[0]
            
            st.write(f"**Estoque 2020:** {row['mudas_2020']:,.0f}")
            st.write(f"**Saldo {ano_ref}:** {row[col_saldo]:,.0f}")
            
            progresso = float(row[col_exp])
            st.progress(min(progresso/100, 1.0))
            st.write(f"**Consumo:** {progresso:.1f}%")
            
            if progresso >= 70:
                st.error("Status: Exploração Avançada")
            elif progresso >= 30:
                st.warning("Status: Exploração Moderada")
            else:
                st.success("Status: Preservado / Inicial")
        else:
            st.info("💡 Selecione um talhão no menu lateral para ver detalhes específicos.")

    with col_mapa:
        m = leafmap.Map(center=[2.82, -60.67], zoom=12, google_map="HYBRID")
        
        # Estilização do Mapa
        def style_function(feature):
            consumo = feature['properties'][col_exp]
            return {
                'fillOpacity': 0.7,
                'weight': 2,
                'color': 'white',
                'fillColor': '#ff0000' if consumo >= 70 else '#ffff00' if consumo >= 30 else '#00ff00'
            }

        m.add_gdf(data, layer_name="Talhões", style_function=style_function)

        # Destacar Talhão Selecionado
        if talhao_selecionado != "Visão Geral":
            selected_gdf = data[data['fid'] == talhao_selecionado]
            m.add_gdf(selected_gdf, layer_name="Destaque", 
                      style={'color': '#FAFF00', 'weight': 4, 'fillOpacity': 0})
            
            centroid = selected_gdf.geometry.centroid.iloc[0]
            folium.Marker([centroid.y, centroid.x], popup=f"Talhão {talhao_selecionado}").add_to(m)

        m.to_streamlit(height=500)

    # 4. Relatório Detalhado (Tabela)
    st.markdown("---")
    st.subheader("📋 Relatório de Consumo por Talhão")
    
    df_tabela = data[['fid', 'mudas_2020', col_saldo, col_exp]].copy()
    
    if talhao_selecionado != "Visão Geral":
        df_tabela['is_selected'] = df_tabela['fid'].apply(lambda x: 1 if str(x) == str(talhao_selecionado) else 0)
        df_tabela = df_tabela.sort_values(by=['is_selected', col_exp], ascending=[False, False]).drop(columns=['is_selected'])
    else:
        df_tabela = df_tabela.sort_values(by=col_exp, ascending=False)
    
    def highlight_selected(row):
        if talhao_selecionado != "Visão Geral" and str(row['fid']) == str(talhao_selecionado):
            return ['background-color: #FAFF00; color: black; font-weight: bold; border: 2px solid black'] * len(row)
        if row[col_exp] >= 70:
            return ['background-color: #FFCDD2; color: black'] * len(row)
        elif row[col_exp] >= 30:
            return ['background-color: #FFF9C4; color: black'] * len(row)
        else:
            return ['background-color: #C8E6C9; color: black'] * len(row)
    
    st.dataframe(
        df_tabela.style.apply(highlight_selected, axis=1).format({
            'mudas_2020': '{:,.0f}',
            col_saldo: '{:,.0f}',
            col_exp: '{:.1f}%'
        }),
        column_config={
            "fid": "ID Talhão",
            "mudas_2020": "Estoque (2020)",
            col_saldo: "Saldo Atual",
            col_exp: "% Consumo"
        },
        use_container_width=True,
        hide_index=True,
        height=400
    )

    # 5. Estatísticas e Gráficos (Ranking e Evolução)
    st.markdown("---")
    with st.expander("📊 Estatísticas e Evolução do Consumo", expanded=True):
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            criticos = len(df_tabela[df_tabela[col_exp] >= 70])
            st.metric("Talhões em Alerta", criticos)
        with col_m2:
            atencao = len(df_tabela[(df_tabela[col_exp] >= 30) & (df_tabela[col_exp] < 70)])
            st.metric("Talhões em Atenção", atencao)
        with col_m3:
            normais = len(df_tabela[df_tabela[col_exp] < 30])
            st.metric("Talhões Estáveis", normais)

        st.markdown("---")
        st.subheader(f"📈 Ranking de Consumo - Foco: {talhao_selecionado}")

        # Preparação do Gráfico de Barras com Zoom
        df_grafico = df_tabela.copy()
        id_sel_str = str(talhao_selecionado)
        df_grafico['fid_str'] = df_grafico['fid'].astype(str)

        if talhao_selecionado != "Visão Geral":
            df_grafico['Destaque'] = df_grafico['fid_str'].apply(lambda x: 'Selecionado' if x == id_sel_str else 'Outros')
            idx_list = df_grafico.index[df_grafico['fid_str'] == id_sel_str].tolist()
            if idx_list:
                idx = idx_list[0]
                df_zoom = df_grafico.iloc[max(0, idx-5):min(len(df_grafico), idx+5)].copy()
                if id_sel_str not in df_zoom['fid_str'].values:
                    df_zoom = pd.concat([df_zoom, df_grafico[df_grafico['fid_str'] == id_sel_str]])
            else:
                df_zoom = df_grafico.copy()
        else:
            df_grafico['Destaque'] = 'Todos'
            df_zoom = df_grafico.copy()

        fig_bar = px.bar(
            df_zoom, x='fid_str', y=col_exp, color='Destaque',
            color_discrete_map={'Selecionado': '#FAFF00', 'Outros': '#A0A0A0', 'Todos': '#0083B8'},
            category_orders={'fid_str': df_zoom['fid_str'].tolist()}
        )

        if talhao_selecionado != "Visão Geral":
            try:
                v_y = df_zoom.loc[df_zoom['fid_str'] == id_sel_str, col_exp].values[0]
                fig_bar.add_annotation(x=id_sel_str, y=v_y, text="🎯 SELECIONADO", showarrow=True, 
                                      arrowhead=2, ay=-40, bgcolor="#FAFF00", bordercolor="black",
                                      xref="x", yref="y")
            except: pass

        fig_bar.update_layout(showlegend=False, height=400, xaxis={'type': 'category'}, 
                             plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        fig_bar.update_traces(marker_line_color="black", marker_line_width=2, selector=dict(marker_color='#FAFF00'))
        st.plotly_chart(fig_bar, use_container_width=True)

        # 6. GRÁFICO DE LINHAS (Evolução Temporal)
        if talhao_selecionado != "Visão Geral":
            st.markdown("---")
            st.subheader(f"📉 Histórico de Exploração: Talhão {talhao_selecionado}")
            
            anos = ["2022", "2023", "2024", "2025"]
            dados_t = data[data['fid'] == talhao_selecionado].iloc[0]
            
            df_hist = pd.DataFrame([
                {"Ano": a, "% Consumo": dados_t[f"exploracao_{a}"]} 
                for a in anos if f"exploracao_{a}" in data.columns
            ])

            fig_line = px.line(df_hist, x="Ano", y="% Consumo", markers=True, 
                              text=[f"{v:.1f}%" for v in df_hist["% Consumo"]])
            
            fig_line.update_traces(line_color='#FAFF00', line_width=4, 
                                  marker=dict(size=12, color="black", symbol="diamond"),
                                  textposition="top center")

            fig_line.update_layout(height=350, yaxis_range=[0, 105], 
                                  plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_line, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Erro ao carregar dashboard: {e}")
    st.exception(e)
