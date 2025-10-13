import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Dashboard de Análise com IA", page_icon="📈", layout="wide")

# --- Título ---
st.title("📈 Seu Dashboard de Análise com IA")
st.write("Faça o upload de seus arquivos na barra lateral. O dashboard será gerado automaticamente!")

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

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    # Uploader para os dados do dia a dia
    data_file = st.sidebar.file_uploader("1. Upload dos Dados do Dia (Ordens de Serviço)", type=["csv", "xlsx"])
    if data_file:
        try:
            if data_file.name.endswith('.csv'):
                df = pd.read_csv(data_file, encoding='latin-1', sep=';', on_bad_lines='skip')
            else:
                df = pd.read_excel(data_file)
            st.session_state.df_dados = df
            st.success("Dados de OS carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")
    
    st.markdown("---")
    # Uploader para o mapeamento fixo
    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=["csv", "xlsx"])
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

# --- NOVA SEÇÃO: DASHBOARD AUTOMÁTICO DE CUSTO ZERO ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço (Custo Zero)")
    
    df = st.session_state.df_dados
    
    # --- Métricas Principais ---
    st.subheader("Visão Geral")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Ordens na Planilha", f"{df.shape[0]:,}".replace(",", "."))
    
    try:
        agendadas_count = df[df['Status'] == 'Agendada'].shape[0]
        col2.metric("Total de Ordens Agendadas", f"{agendadas_count:,}".replace(",", "."))
    except KeyError:
        col2.metric("Total de Ordens Agendadas", "N/A")
        
    col3.metric("Representantes Únicos", f"{df['Representante Técnico'].nunique():,}".replace(",", "."))
    col4.metric("Cidades Únicas", f"{df['Cidade Agendamento'].nunique():,}".replace(",", "."))
    
    st.markdown("---")

    # --- Gráficos Principais ---
    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        st.subheader("Contagem por Status de Ordem")
        try:
            status_counts = df['Status'].value_counts()
            st.bar_chart(status_counts)
        except KeyError:
            st.warning("Coluna 'Status' não encontrada.")

        st.subheader("Top 10 Representantes com Mais Ordens")
        try:
            rep_counts = df['Representante Técnico'].value_counts().nlargest(10)
            st.bar_chart(rep_counts)
        except KeyError:
            st.warning("Coluna 'Representante Técnico' não encontrada.")

    with col_graf2:
        st.subheader("Contagem por Sub-Motivo de Fechamento")
        try:
            # Remove valores vazios (NaN) antes de contar
            submotivo_counts = df['Sub Motivo Fechamento'].dropna().value_counts()
            st.bar_chart(submotivo_counts)
        except KeyError:
            st.warning("Coluna 'Sub Motivo Fechamento' não encontrada.")

        st.subheader("Top 10 Cidades com Mais Ordens")
        try:
            cidade_counts = df['Cidade Agendamento'].value_counts().nlargest(10)
            st.bar_chart(cidade_counts)
        except KeyError:
            st.warning("Coluna 'Cidade Agendamento' não encontrada.")

    with st.expander("Clique para ver a tabela de dados completa"):
        st.dataframe(df)

# --- Seção do Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA para análises personalizadas")
# (A lógica do chat permanece a mesma para quando você precisar de uma pergunta específica)
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    # (O código do chat continua o mesmo)
    pass
