import streamlit as st
import pandas as pd
import numpy as np
from haversine import haversine, Unit
from datetime import datetime
import openai

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Mercúrio IA", page_icon="🧠", layout="wide")
st.title("🧠 Mercúrio IA - Dashboard e Chat Integrado")

# --- ESTADO DA SESSÃO ---
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None
if 'df_devolucao' not in st.session_state:
    st.session_state.df_devolucao = None
if 'df_pagamento' not in st.session_state:
    st.session_state.df_pagamento = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- FUNÇÕES ÚTEIS ---
@st.cache_data
def carregar_dataframe(arquivo, separador_padrao=','):
    nome_arquivo = arquivo.name.lower()
    if nome_arquivo.endswith('.xlsx') or nome_arquivo.endswith('.xls'):
        return pd.read_excel(arquivo, engine='openpyxl')
    elif nome_arquivo.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except Exception:
            pass
        arquivo.seek(0)
        outro_separador = ',' if separador_padrao == ';' else ';'
        df = pd.read_csv(arquivo, encoding='latin-1', sep=outro_separador, on_bad_lines='skip')
        return df
    return None

def safe_to_numeric(series):
    if series.dtype == 'object':
        series = series.astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    return pd.to_numeric(series, errors='coerce').fillna(0)

@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

# --- BARRA LATERAL PARA UPLOADS ---
with st.sidebar:
    st.header("📂 Upload de Arquivos")
    tipos_permitidos = ["csv", "xlsx", "xls"]

    data_file = st.file_uploader("1. Agendamentos (OS)", type=tipos_permitidos)
    if data_file:
        st.session_state.df_dados = carregar_dataframe(data_file, separador_padrao=';')
        st.success("Agendamentos carregados!")

    map_file = st.file_uploader("2. Mapeamento RT (Fixo)", type=tipos_permitidos)
    if map_file:
        st.session_state.df_mapeamento = carregar_dataframe(map_file)
        st.success("Mapeamento carregado!")

    devolucao_file = st.file_uploader("3. Devolução/Instalação", type=tipos_permitidos)
    if devolucao_file:
        st.session_state.df_devolucao = carregar_dataframe(devolucao_file, separador_padrao=';')
        st.success("Devolução carregada!")

    pagamento_file = st.file_uploader("4. Base de Pagamento", type=tipos_permitidos)
    if pagamento_file:
        st.session_state.df_pagamento = carregar_dataframe(pagamento_file, separador_padrao=';')
        st.success("Pagamento carregado!")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- DASHBOARD DE ORDENS DE SERVIÇO ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de OS")
    df_os = st.session_state.df_dados.copy()
    
    st.subheader("Preview dos Dados")
    st.dataframe(df_os.head(10))

    # Exemplo de métricas básicas
    st.subheader("Métricas Básicas")
    st.metric("Total de OS", len(df_os))
    status_col = next((c for c in df_os.columns if 'status' in c.lower()), None)
    if status_col:
        st.metric("OS Fechadas", (df_os[status_col]=='Fechada').sum())

# --- CHAT INTEGRADO ---
st.markdown("---")
st.header("💬 Chat com IA")

# Configurar chave da OpenAI
if 'OPENAI_API_KEY' not in st.secrets:
    st.warning("Insira sua chave OpenAI em st.secrets")
else:
    openai.api_key = st.secrets["OPENAI_API_KEY"]

user_input = st.text_input("Digite sua pergunta para a IA:")
if st.button("Enviar"):
    if user_input.strip() != "":
        prompt = f"""
Você é um assistente inteligente. Base de dados disponível: 
Agendamentos: {st.session_state.df_dados.head().to_dict() if st.session_state.df_dados is not None else "Não carregada"}
Mapeamento: {st.session_state.df_mapeamento.head().to_dict() if st.session_state.df_mapeamento is not None else "Não carregada"}
Devolução: {st.session_state.df_devolucao.head().to_dict() if st.session_state.df_devolucao is not None else "Não carregada"}
Pagamento: {st.session_state.df_pagamento.head().to_dict() if st.session_state.df_pagamento is not None else "Não carregada"}

Pergunta: {user_input}
"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            answer = response.choices[0].message.content
            st.session_state.chat_history.append({"user": user_input, "ai": answer})
        except Exception as e:
            answer = f"Erro ao gerar resposta: {e}"
            st.session_state.chat_history.append({"user": user_input, "ai": answer})

# Exibir histórico de chat
if st.session_state.chat_history:
    st.subheader("Histórico do Chat")
    for chat in reversed(st.session_state.chat_history):
        st.markdown(f"**Você:** {chat['user']}")
        st.markdown(f"**IA:** {chat['ai']}")
