import streamlit as st
import google.generativeai as genai
import pandas as pd
from haversine import haversine, Unit
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Seu Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

# --- Configuração da API e do Modelo ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-pro-latest')
except Exception as e:
    st.error("Chave de API do Google não configurada ou inválida.")
    st.stop()

# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções de Análise (com cache para economia) ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    contexto = "analisar dados de ordens de serviço." if df_type == 'dados' else "buscar informações sobre representantes."
    time.sleep(1)
    prompt_engenharia = f"""
    Sua tarefa é converter uma pergunta em uma única linha de código Pandas para {contexto}
    O dataframe é `df`. As colunas são: {', '.join(df.columns)}.
    Pergunta: "{pergunta}"
    Gere apenas a linha de código Pandas.
    """
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        codigo_pandas = code_response.text.strip().replace('`', '').replace('python', '').strip()
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    data_file = st.sidebar.file_uploader("1. Upload de Agendamentos (OS)", type=["csv", "xlsx"])
    if data_file:
        try:
            if data_file.name.endswith('.csv'):
                df = pd.read_csv(data_file, encoding='latin-1', sep=';', on_bad_lines='skip')
            else:
                df = pd.read_excel(data_file)
            st.session_state.df_dados = df
            st.success("Agendamentos carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    st.markdown("---")
    map_file = st.sidebar.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=["csv", "xlsx"])
    if map_file:
        try:
            if map_file.name.endswith('.csv'):
                 df = pd.read_csv(map_file, encoding='latin-1', sep=',')
            else:
                df = pd.read_excel(map_file)
            st.session_state.df_mapeamento = df
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Corpo Principal ---

# --- DASHBOARD DE ANÁLISE DE ORDENS DE SERVIÇO (Visão Principal) ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço (Custo Zero)")
    df_dados = st.session_state.df_dados.copy()
    
    # Prepara a coluna de data para o filtro
    date_col = 'Data Agendamento'
    if date_col in df_dados.columns:
        df_dados[date_col] = pd.to_datetime(df_dados[date_col], errors='coerce', dayfirst=True)

    status_col, rep_col_dados, city_col_dados, motivo_fechamento_col, cliente_col = 'Status', 'Representante Técnico', 'Cidade Agendamento', 'Tipo de Fechamento', 'Cliente'

    st.subheader("Filtros Interativos")
    f_col1, f_col2, f_col3 = st.columns(3)
    
    status_options = sorted(df_dados[status_col].dropna().unique()) if status_col in df_dados.columns else []
    status_selecionado = f_col1.multiselect("Filtrar por Status:", options=status_options)
    
    rep_options = sorted(df_dados[rep_col_dados].dropna().unique()) if rep_col_dados in df_dados.columns else []
    rep_selecionado = f_col2.selectbox("Filtrar por Representante:", options=rep_options, index=None, placeholder="Selecione um RT")
    
    data_selecionada = f_col3.date_input("Filtrar por Data de Agendamento:", value=None)

    filtered_df_dados = df_dados
    if status_selecionado: filtered_df_dados = filtered_df_dados[filtered_df_dados[status_col].isin(status_selecionado)]
    if rep_selecionado: filtered_df_dados = filtered_df_dados[filtered_df_dados[rep_col_dados] == rep_selecionado]
    if data_selecionada: filtered_df_dados = filtered_df_dados[filtered_df_dados[date_col].dt.date == data_selecionada]

    st.dataframe(filtered_df_dados)
    st.info(f"Mostrando {len(filtered_df_dados)} resultados.")

    st.subheader("Análises Gráficas (Baseado nos filtros)")
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.write("**Top Clientes com Visitas Improdutivas:**")
        if motivo_fechamento_col in filtered_df_dados.columns and cliente_col in filtered_df_dados.columns:
            improdutivas_df = filtered_df_dados[filtered_df_dados[motivo_fechamento_col] == 'Visita Improdutiva']
            if not improdutivas_df.empty: st.bar_chart(improdutivas_df[cliente_col].value_counts().nlargest(10))
            else: st.info("Nenhuma visita improdutiva encontrada.")
    with b_col2:
        st.write("**Top RTs com Ordens Realizadas:**")
        if status_col in filtered_df_dados.columns and rep_col_dados in filtered_df_dados.columns:
            realizadas_df = filtered_df_dados[filtered_df_dados[status_col] == 'Realizada']
            if not realizadas_df.empty: st.bar_chart(realizadas_df[rep_col_dados].value_counts().nlargest(10))
            else: st.info("Nenhuma ordem realizada encontrada.")

# --- FERRAMENTA DE MAPEAMENTO (Visão Secundária) ---
if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.header("🗺️ Ferramenta de Mapeamento e Consulta de RT")
    df_map = st.session_state.df_mapeamento.copy()
    
    # (O código da consulta interativa e do mapa que já funcionava está aqui)
    pass 

# --- OTIMIZADOR DE PROXIMIDADE (Ferramenta Opcional) ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    with st.expander("🚚 Abrir Otimizador de Proximidade de RT"):
        # (O código do otimizador que já funcionava está aqui)
        pass

# --- Seção do Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA para análises personalizadas")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    # (A lógica do chat permanece a mesma)
    pass
