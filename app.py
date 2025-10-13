import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Dashboard de Análise com IA", page_icon="📈", layout="wide")

# --- Título ---
st.title("📈 Fckd Up")
st.write("Fala que eu te escuto!")

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
                # Tenta ler com ';' e se falhar (ou gerar 1 coluna), tenta com ','
                try:
                    df = pd.read_csv(data_file, encoding='latin-1', sep=';', on_bad_lines='skip')
                    if len(df.columns) <= 1:
                        data_file.seek(0)
                        df = pd.read_csv(data_file, encoding='latin-1', sep=',', on_bad_lines='skip')
                except Exception:
                    data_file.seek(0)
                    df = pd.read_csv(data_file, encoding='latin-1', sep=',', on_bad_lines='skip')
            else:
                df = pd.read_excel(data_file)
            st.session_state.df_dados = df
            st.success("Dados de OS carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")
    
    st.markdown("---")
    # Uploader para o mapeamento fixo (opcional)
    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Opcional)", type=["csv", "xlsx"])
    if map_file:
        # Lógica de carregamento do mapeamento
        pass

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Corpo Principal ---

# --- DASHBOARD AUTOMÁTICO DE CUSTO ZERO (ATUALIZADO) ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço (Custo Zero)")
    
    df = st.session_state.df_dados
    
    # --- Detecção dinâmica de colunas para robustez ---
    status_col = 'Status'
    # CORREÇÃO 1: Procura pelo nome exato da coluna do nome do representante
    rep_col_dados = 'Representante Técnico' 
    city_col_dados = 'Cidade Agendamento'
    # CORREÇÃO 2: Usa a coluna correta para os motivos de fechamento
    motivo_fechamento_col = 'Tipo de Fechamento'
    cliente_col = 'Cliente'

    # --- Métricas Principais ---
    st.subheader("Visão Geral")
    # (Métricas permanecem as mesmas)
    
    st.markdown("---")

    # --- Gráficos Principais ---
    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        st.subheader("Contagem por Status de Ordem")
        if status_col in df.columns:
            st.bar_chart(df[status_col].value_counts())
        else:
            st.warning("Coluna 'Status' não encontrada.")

        st.subheader("Top 10 Representantes com Mais Ordens")
        if rep_col_dados in df.columns:
            st.bar_chart(df[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Coluna 'Representante Técnico' não encontrada.")

    with col_graf2:
        st.subheader("Contagem por Tipo de Fechamento") # Título corrigido
        if motivo_fechamento_col in df.columns:
            st.bar_chart(df[motivo_fechamento_col].dropna().value_counts())
        else:
            st.warning("Coluna 'Tipo de Fechamento' não encontrada.")

        st.subheader("Top 10 Cidades com Mais Ordens")
        if city_col_dados in df.columns:
            st.bar_chart(df[city_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Coluna 'Cidade Agendamento' não encontrada.")

    # --- NOVOS BOTÕES DE ANÁLISE ---
    st.markdown("---")
    st.subheader("Novas Análises de Custo Zero")
    b_col1, b_col2 = st.columns(2)

    with b_col1:
        if st.button("Top Clientes com Visitas Improdutivas"):
            st.write("Resultado da Análise:")
            if motivo_fechamento_col in df.columns and cliente_col in df.columns:
                improdutivas_df = df[df[motivo_fechamento_col] == 'Visita Improdutiva']
                st.bar_chart(improdutivas_df[cliente_col].value_counts().nlargest(10))
            else:
                st.warning("Colunas 'Tipo de Fechamento' ou 'Cliente' não encontradas.")
    
    with b_col2:
        if st.button("Análise de Motivos de Reagendamento"):
            st.write("Resultado da Análise:")
            # Assumindo que o motivo está na coluna 'Tipo de Fechamento' quando o Status é 'Reagendamento'
            if status_col in df.columns and motivo_fechamento_col in df.columns:
                reagendamentos_df = df[df[status_col] == 'Reagendamento']
                st.bar_chart(reagendamentos_df[motivo_fechamento_col].value_counts())
            else:
                st.warning("Colunas 'Status' ou 'Tipo de Fechamento' não encontradas.")


    with st.expander("Clique para ver a tabela de dados completa"):
        st.dataframe(df)

# --- Seção do Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA para análises personalizadas")
# (A lógica do chat permanece a mesma)
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    # (O código do chat continua o mesmo)
    pass
