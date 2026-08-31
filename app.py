import os
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import timedelta

# Configuração da Página
st.set_page_config(page_title="Painel de Reincidência & Risco de Churn", layout="wide")

st.title("📊 Painel de Reincidência & Risco de Churn (ISP)")
st.markdown("Monitoramento operacional de ofensores, reincidências e risco de cancelamento.")

# Busca automaticamente qualquer arquivo Excel (.xlsx) na pasta
arquivos_excel = [f for f in os.listdir('.') if f.endswith('.xlsx') and not f.startswith('~$')]
ARQUIVO_PADRAO = arquivos_excel[0] if arquivos_excel else None

# 1. Carregamento da Base (Automático ou por Upload manual)
st.sidebar.markdown("### 📂 Fonte de Dados")
uploaded_file = st.sidebar.file_uploader("Substituir planilha temporariamente (.xlsx/.csv):", type=["xlsx", "csv"])

df = None
try:
    if uploaded_file is not None:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        st.sidebar.success("Arquivo manual carregado!")
    elif os.path.exists(ARQUIVO_PADRAO):
        df = pd.read_excel(ARQUIVO_PADRAO)
        st.sidebar.info(f"Base conectada: `{ARQUIVO_PADRAO}`")
    else:
        st.error(f"Planilha `{ARQUIVO_PADRAO}` não encontrada no GitHub e nenhum arquivo foi enviado.")
        st.stop()
except Exception as e:
    st.error(f"Erro ao carregar os dados: {e}")
    st.stop()

# 2. Tratamento dos Dados
df_clean = df.dropna(subset=['PROTOCOLO', 'CODIGO_CLIENTE']).copy()
df_clean['Data_Fechamento'] = pd.to_datetime(df_clean['Data_Fechamento'])
df_clean['Data_Abertura'] = pd.to_datetime(df_clean['Data_Abertura'])

min_date = df_clean['Data_Fechamento'].min().date()
max_date = df_clean['Data_Fechamento'].max().date()

# 3. Filtros Laterais
st.sidebar.markdown("---")
st.sidebar.header("🔍 Filtros de Análise")

periodo_opcoes = [
    "Últimos 30 dias", 
    "Últimos 15 dias", 
    "Últimos 60 dias", 
    "Últimos 90 dias", 
    "Todo o Período", 
    "📅 Período Personalizado (De / Até)"
]
periodo_selecionado = st.sidebar.selectbox("Filtro de Data", periodo_opcoes)

if periodo_selecionado == "Últimos 15 dias":
    data_inicio = max_date - timedelta(days=15)
    data_fim = max_date
elif periodo_selecionado == "Últimos 30 dias":
    data_inicio = max_date - timedelta(days=30)
    data_fim = max_date
elif periodo_selecionado == "Últimos 60 dias":
    data_inicio = max_date - timedelta(days=60)
    data_fim = max_date
elif periodo_selecionado == "Últimos 90 dias":
    data_inicio = max_date - timedelta(days=90)
    data_fim = max_date
elif periodo_selecionado == "Todo o Período":
    data_inicio = min_date
    data_fim = max_date
else:
    data_intervalo = st.sidebar.date_input(
        "Selecione o intervalo de datas:",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY"
    )
    if isinstance(data_intervalo, tuple) and len(data_intervalo) == 2:
        data_inicio, data_fim = data_intervalo
    else:
        data_inicio, data_fim = min_date, max_date

# Filtragem de Data
df_filtered = df_clean[
    (df_clean['Data_Fechamento'].dt.date >= data_inicio) & 
    (df_clean['Data_Fechamento'].dt.date <= data_fim)
].copy()

# Filtro de Cidade
cidades_disponiveis = ["Todas"] + sorted(df_filtered['Cidade'].dropna().unique().tolist())
cidade_selecionada = st.sidebar.selectbox("Cidade", cidades_disponiveis)
if cidade_selecionada != "Todas":
    df_filtered = df_filtered[df_filtered['Cidade'] == cidade_selecionada]

# Filtro de Técnico
tecnicos_disponiveis = ["Todos"] + sorted(df_filtered['Usuario_Fechamento'].dropna().unique().tolist())
tecnico_selecionado = st.sidebar.selectbox("Técnico / Usuário Fechamento", tecnicos_disponiveis)
if tecnico_selecionado != "Todos":
    df_filtered = df_filtered[df_filtered['Usuario_Fechamento'] == tecnico_selecionado]

# 4. Métricas Principais
st.subheader(f"📌 Visão Geral ({data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')})")
col1, col2, col3, col4 = st.columns(4)
total_os = len(df_filtered)
clientes_unicos = df_filtered['CODIGO_CLIENTE'].nunique()
media_dias = df_filtered['DIAS_ATE_REINCIDENCIA'].mean() if total_os > 0 else 0
reinc_rapida = len(df_filtered[df_filtered['DIAS_ATE_REINCIDENCIA'] <= 3])

col1.metric("Total de OS Reincidentes", total_os)
col2.metric("Clientes Únicos", clientes_unicos)
col3.metric("Média Dias até Reincidir", f"{media_dias:.1f} dias")
col4.metric("Reincidência Crítica (≤ 3 dias)", f"{reinc_rapida} ({reinc_rapida/total_os*100:.1f}%)" if total_os > 0 else "0")

# 5. Painel de Risco de Churn
st.markdown("---")
st.subheader("🔴 Painel de Risco de Cancelamento (Churn)")

client_grp = df_filtered.groupby(['CODIGO_CLIENTE', 'NOME_CLIENTE', 'Cidade']).agg(
    Qtd_OS=('PROTOCOLO', 'count'),
    Media_Dias=('DIAS_ATE_REINCIDENCIA', 'mean'),
    Tipos_OS=('TIPO_OS', lambda x: ', '.join(x.unique())),
    Tecnicos=('Usuario_Fechamento', lambda x: ', '.join(x.dropna().unique()))
).reset_index()

def calc_score(row):
    if row['Qtd_OS'] >= 4:
        pts_vol = 50
    elif row['Qtd_OS'] == 3:
        pts_vol = 35
    elif row['Qtd_OS'] == 2:
        pts_vol = 20
    else:
        pts_vol = 0
        
    if row['Media_Dias'] <= 3:
        pts_vel = 50
    elif row['Media_Dias'] <= 7:
        pts_vel = 35
    elif row['Media_Dias'] <= 15:
        pts_vel = 20
    else:
        pts_vel = 10
        
    return pts_vol + pts_vel

if not client_grp.empty:
    client_grp['Score'] = client_grp.apply(calc_score, axis=1)
    
    def classify(score):
        if score >= 75:
            return "🔴 Crítico"
        elif score >= 50:
            return "🟡 Alto"
        else:
            return "🟢 Moderado"
            
    client_grp['Nivel_Risco'] = client_grp['Score'].apply(classify)
    client_grp = client_grp.sort_values(by=['Score', 'Qtd_OS'], ascending=[False, False])
    
    tab1, tab2 = st.tabs(["🔥 Clientes com 2+ OS (Foco Retenção)", "📋 Todos os Atendidos"])
    with tab1:
        st.dataframe(client_grp[client_grp['Qtd_OS'] >= 2][[
            'Nivel_Risco', 'Score', 'CODIGO_CLIENTE', 'NOME_CLIENTE', 'Cidade', 'Qtd_OS', 'Media_Dias', 'Tipos_OS', 'Tecnicos'
        ]].round({'Media_Dias': 1}), use_container_width=True)
    with tab2:
        st.dataframe(client_grp[[
            'Nivel_Risco', 'Score', 'CODIGO_CLIENTE', 'NOME_CLIENTE', 'Cidade', 'Qtd_OS', 'Media_Dias', 'Tipos_OS', 'Tecnicos'
        ]].round({'Media_Dias': 1}), use_container_width=True)

# 6. Gráficos e Diagnósticos
st.markdown("---")
st.subheader("📈 Diagnóstico Operacional")
c1, c2 = st.columns(2)

with c1:
    st.markdown("**Top Tipos de OS Mais Frequentes**")
    tipo_df = df_filtered['TIPO_OS'].value_counts().reset_index()
    tipo_df.columns = ['Tipo_OS', 'Qtd']
    fig_tipo = px.bar(tipo_df.head(8), x='Qtd', y='Tipo_OS', orientation='h', color='Qtd', color_continuous_scale='Oranges')
    fig_tipo.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, height=350)
    st.plotly_chart(fig_tipo, use_container_width=True)

with c2:
    st.markdown("**Ranking de Fechamento por Técnico**")
    tec_df = df_filtered['Usuario_Fechamento'].value_counts().reset_index()
    tec_df.columns = ['Tecnico', 'Qtd']
    fig_tec = px.bar(tec_df.head(8), x='Qtd', y='Tecnico', orientation='h', color='Qtd', color_continuous_scale='Blues')
    fig_tec.update_layout(yaxis={'categoryorder':'total ascending'}, showlegend=False, height=350)
    st.plotly_chart(fig_tec, use_container_width=True)

st.markdown("**Matriz: Técnico × Tipo de OS**")
matriz = pd.crosstab(df_filtered['Usuario_Fechamento'], df_filtered['TIPO_OS'], margins=True)
st.dataframe(matriz, use_container_width=True)
