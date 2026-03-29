import streamlit as st
import leafmap.foliumap as leafmap
import geopandas as gpd
from streamlit_folium import st_folium
import pandas as pd
import folium
from folium import Element
import json
import plotly.express as px

# 1. Configuração da Interface
st.set_page_config(layout="wide", page_title="BioTrack Roraima", page_icon="🛰️")

st.title("🛰️ BioTrack - Gestão de Consumo e Estoque")
st.markdown("---")

# 2. Carregamento dos Dados
@st.cache_data
def carregar_dados():
    gdf = gpd.read_file("dados_auditoria.geojson")
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    # Converter fid para string para garantir consistência
    gdf['fid'] = gdf['fid'].astype(str)
    return gdf

# Inicializar estado do mapa na sessão
if 'map_state' not in st.session_state:
    st.session_state.map_state = {
        'center': [2.82, -60.67],
        'zoom': 12,
        'bounds': None
    }

# Inicializar estado do talhão selecionado
if 'selected_talhao' not in st.session_state:
    st.session_state.selected_talhao = "Visão Geral"

try:
    data = carregar_dados()

    # 3. Painel Lateral
    with st.sidebar:
        st.header("🔍 Painel de Controle")
        ano = st.selectbox("Selecione o ano de referência", ["2022", "2023", "2024", "2025"])
        col_exp = f"exploracao_{ano}" 
        col_saldo = f"saldo_{ano}"
        
        st.markdown("---")
        st.subheader("🎯 Focar em Talhão")
        lista_talhoes = sorted(data['fid'].unique().tolist())
        talhao_selecionado = st.selectbox("Escolha o ID para Inspeção", ["Visão Geral"] + lista_talhoes)
        
        # Atualizar estado do talhão selecionado
        if talhao_selecionado != st.session_state.selected_talhao:
            st.session_state.selected_talhao = talhao_selecionado
            st.rerun()
        
        # Botão para resetar o mapa
        if st.button("🔄 Resetar Visualização do Mapa"):
            st.session_state.map_state = {
                'center': [2.82, -60.67],
                'zoom': 12,
                'bounds': None
            }
            st.rerun()

        # Botão para focar no talhão selecionado
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
    c1.metric("Estoque Inicial de Acácias (2020)", f"{total_original:,.0f}".replace(",", "."))
    c2.metric("Saldo Remanescente", f"{saldo_atual:,.0f}".replace(",", "."), delta=f"-{extraido:,.0f}", delta_color="inverse")
    c3.metric("Progresso da Extração", f"{progresso:.1f}%")

    st.markdown("---")

    # 5. Informações do Talhão Selecionado (Quadro Fora do Mapa)
    if talhao_selecionado != "Visão Geral":
        st.subheader(f"📊 Informações Detalhadas - Talhão {talhao_selecionado}")
        
        # Buscar dados do talhão selecionado
        talhao_data = data[data['fid'] == talhao_selecionado].iloc[0]
        
        # Criar colunas para informações
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "ID do Talhão", 
                talhao_selecionado,
                help="Identificador único do talhão"
            )
        
        with col2:
            st.metric(
                "Mudas (2020)", 
                f"{talhao_data['mudas_2020']:,.0f}".replace(",", "."),
                help="Quantidade inicial de mudas em 2020"
            )
        
        with col3:
            st.metric(
                f"Saldo {ano}", 
                f"{talhao_data[col_saldo]:,.0f}".replace(",", "."),
                help=f"Saldo remanescente em {ano}"
            )
        
        with col4:
            extraido_talhao = talhao_data['mudas_2020'] - talhao_data[col_saldo]
            st.metric(
                f"% Extração {ano}", 
                f"{talhao_data[col_exp]:.1f}%",
                delta=f"-{extraido_talhao:,.0f}".replace(",", ".") if extraido_talhao > 0 else None,
                delta_color="inverse",
                help="Percentual de biomassa extraída"
            )
        
        # Adicionar barra de progresso para o talhão específico
        st.progress(talhao_data[col_exp] / 100, text="Progresso de Extração do Talhão")
        
        # Status baseado no percentual de extração
        perc_extracao = talhao_data[col_exp]
        if perc_extracao < 30:
            status = "🟢 Baixa Extração"
            status_color = "green"
        elif perc_extracao < 70:
            status = "🟡 Extração Moderada"
            status_color = "orange"
        else:
            status = "🔴 Alta Extração"
            status_color = "red"
        
        st.markdown(f"**Status:** <span style='color:{status_color}; font-weight:bold'>{status}</span>", unsafe_allow_html=True)
        
        st.markdown("---")

    # 6. Visualização Espacial
    st.subheader(f"🗺️ Mapa: {talhao_selecionado} ({ano})")
    
    # Determinar centro e zoom baseado no estado salvo
    center = st.session_state.map_state['center']
    zoom = st.session_state.map_state['zoom']
    
    # Criar mapa
    m = leafmap.Map(center=center, zoom=zoom, google_map="SATELLITE")

    # Preparar dados para hover (criar GeoJSON com propriedades)
    # Converter dados para GeoJSON com todas as propriedades
    data_geojson = data.copy()
    
    # Adicionar informações extras para o hover
    data_geojson['properties'] = data_geojson.apply(lambda row: {
        'ID Talhão': row['fid'],
        'Mudas 2020': f"{row['mudas_2020']:,.0f}",
        f'Saldo {ano}': f"{row[col_saldo]:,.0f}",
        f'% Extração {ano}': f"{row[col_exp]:.1f}%",
        'Status': 'Alta Extração' if row[col_exp] >= 70 else ('Média Extração' if row[col_exp] >= 30 else 'Baixa Extração')
    }, axis=1)
    
    # Adicionar camada principal com estilo baseado no percentual
    m.add_data(
        data,
        column=col_exp,
        scheme="UserDefined", 
        classification_kwds=dict(bins=[1, 30, 70, 99, 100]),
        colors=["#228B22", "#ADFF2F", "#FFFF00", "#FF8C00", "#FF0000"],
        layer_name=f"Status {ano}",
        fields=["fid", "mudas_2020", col_saldo, col_exp],
        aliases=["ID Talhão", "Mudas 2020", "Saldo Atual", "% Extraído"],
        info_mode="on_hover"  # Ativar hover para mostrar informações
    )

    # Se houver um talhão específico selecionado, destacar com borda amarela
    if talhao_selecionado != "Visão Geral":
        geom_talhao = data[data['fid'] == talhao_selecionado].geometry.iloc[0]
        # Criar um estilo destacado para o polígono selecionado
        m.add_gdf(
            gpd.GeoDataFrame(geometry=[geom_talhao], crs="EPSG:4326"),
            style={
                "color": "yellow", 
                "weight": 5, 
                "fillOpacity": 0.1,
                "dashArray": "5, 5"  # Linha pontilhada para destacar
            },
            layer_name=f"✨ Talhão {talhao_selecionado} (Selecionado)",
            info_mode=None  # Não mostrar popup para evitar duplicação
        )
        
        # Adicionar marcador com informações no centro do polígono
        centroid = geom_talhao.centroid
        row = data[data['fid'] == talhao_selecionado].iloc[0]
        
        # Criar popup mais informativo
        popup_html = f"""
        <div style="font-family: monospace; min-width: 200px;">
            <h4 style="margin: 0 0 5px 0;">📍 Talhão {talhao_selecionado}</h4>
            <hr style="margin: 5px 0;">
            <b>🌱 Mudas 2020:</b> {row['mudas_2020']:,.0f}<br>
            <b>📊 Saldo {ano}:</b> {row[col_saldo]:,.0f}<br>
            <b>⚡ Extração {ano}:</b> {row[col_exp]:.1f}%<br>
            <b>📈 Extraído:</b> {row['mudas_2020'] - row[col_saldo]:,.0f}<br>
            <hr style="margin: 5px 0;">
            <b>🎯 Status:</b> 
            <span style="color: {'red' if row[col_exp] >= 70 else 'orange' if row[col_exp] >= 30 else 'green'}">
                {'Crítico' if row[col_exp] >= 70 else 'Atenção' if row[col_exp] >= 30 else 'Normal'}
            </span>
        </div>
        """
        
        # Adicionar marcador com popup
        folium.Marker(
            [centroid.y, centroid.x],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color="red", icon="info-sign", prefix='glyphicon')
        ).add_to(m)

    # Exibir mapa e capturar interações
    output = st_folium(
        m, 
        key=f"map_instance_{ano}_{talhao_selecionado}", 
        width=1200, 
        height=600,
        returned_objects=["last_center", "last_bounds", "last_zoom", "last_object_clicked"]
    )
    
    # Atualizar o estado do mapa baseado nas interações do usuário
    if output and output.get('last_center') and output.get('last_zoom'):
        new_center = [output['last_center']['lat'], output['last_center']['lng']]
        new_zoom = output['last_zoom']
        
        if (new_center != st.session_state.map_state['center'] or 
            new_zoom != st.session_state.map_state['zoom']):
            st.session_state.map_state['center'] = new_center
            st.session_state.map_state['zoom'] = new_zoom
            
            if output.get('last_bounds'):
                st.session_state.map_state['bounds'] = output['last_bounds']

    # 7. Relatório Detalhado
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
    
    # 8. Estatísticas Gerais e Gráficos
    st.markdown("---")
    with st.expander("📊 Estatísticas e Evolução do Consumo", expanded=True):
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            criticos = len(df_tabela[df_tabela[col_exp] >= 70])
            st.metric("Talhões com Alto Consumo", criticos, f"{(criticos/len(df_tabela)*100):.1f}%")
        
        with col_m2:
            atencao = len(df_tabela[(df_tabela[col_exp] >= 30) & (df_tabela[col_exp] < 70)])
            st.metric("Talhões com Consumo Moderado", atencao, f"{(atencao/len(df_tabela)*100):.1f}%")
        
        with col_m3:
            normais = len(df_tabela[df_tabela[col_exp] < 30])
            st.metric("Talhões com Baixo Consumo", normais, f"{(normais/len(df_tabela)*100):.1f}%")

        st.markdown("---")
        st.subheader(f"📈 Ranking de Consumo - Foco: {talhao_selecionado}")

        df_grafico = df_tabela.copy()
        id_selecionado_str = str(talhao_selecionado)
        df_grafico['fid_str'] = df_grafico['fid'].astype(str)

        if talhao_selecionado != "Visão Geral":
            df_grafico['Destaque'] = df_grafico['fid_str'].apply(
                lambda x: 'Selecionado' if x == id_selecionado_str else 'Outros Talhões'
            )
            idx_list = df_grafico.index[df_grafico['fid_str'] == id_selecionado_str].tolist()
            if idx_list:
                idx = idx_list[0]
                start, end = max(0, idx - 5), min(len(df_grafico), idx + 5)
                df_zoom = df_grafico.iloc[start:end].copy()
                if id_selecionado_str not in df_zoom['fid_str'].values:
                    df_zoom = pd.concat([df_zoom, df_grafico[df_grafico['fid_str'] == id_selecionado_str]])
            else:
                df_zoom = df_grafico.copy()
        else:
            df_grafico['Destaque'] = 'Todos'
            df_zoom = df_grafico.copy()

        fig_bar = px.bar(
            df_zoom, x='fid_str', y=col_exp, color='Destaque',
            color_discrete_map={'Selecionado': '#FAFF00', 'Outros Talhões': '#A0A0A0', 'Todos': '#0083B8'},
            category_orders={'fid_str': df_zoom['fid_str'].tolist()}
        )

        if talhao_selecionado != "Visão Geral":
            try:
                valor_y = df_zoom.loc[df_zoom['fid_str'] == id_selecionado_str, col_exp].values[0]
                fig_bar.add_annotation(
                    x=id_selecionado_str, y=valor_y, text="🎯 SELECIONADO",
                    showarrow=True, arrowhead=2, ax=0, ay=-40,
                    bgcolor="#FAFF00", bordercolor="black",
                    font=dict(color="black", size=12, weight="bold"),
                    xref="x", yref="y"
                )
            except: pass

        fig_bar.update_layout(
            showlegend=False, height=400, xaxis_title="ID do Talhão", yaxis_title="% de Consumo",
            xaxis={'type': 'category'}, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=10, b=10)
        )

        fig_bar.update_traces(marker_line_color="black", marker_line_width=2, selector=dict(marker_color='#FAFF00'))
        st.plotly_chart(fig_bar, use_container_width=True)

        if talhao_selecionado != "Visão Geral":
            st.markdown("---")
            st.subheader(f"📉 Histórico de Exploração: Talhão {talhao_selecionado}")
            anos = ["2022", "2023", "2024", "2025"]
            dados_talhao = data[data['fid'] == talhao_selecionado].iloc[0]
            df_hist = pd.DataFrame([{"Ano": a, "% Consumo": dados_talhao[f"exploracao_{a}"]} for a in anos if f"exploracao_{a}" in data.columns])
            fig_line = px.line(df_hist, x="Ano", y="% Consumo", markers=True, text=[f"{v:.1f}%" for v in df_hist["% Consumo"]])
            fig_line.update_traces(line_color='#FAFF00', line_width=4, marker=dict(size=12, color="black", symbol="diamond"), textposition="top center")
            fig_line.update_layout(height=350, yaxis_range=[0, 105], xaxis_title="Evolução por Ano", yaxis_title="Consumo Acumulado (%)", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_line, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Erro ao carregar dashboard: {e}")
    st.exception(e)

            st.plotly_chart(fig_line, use_container_width=True)

except Exception as e:
    st.error(f"⚠️ Erro ao carregar dashboard: {e}")
    st.exception(e)
