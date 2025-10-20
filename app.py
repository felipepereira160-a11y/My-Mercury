import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
from haversine import haversine, Unit
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral!")

# --- Lógica robusta para carregar a chave da API ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
api_key_status = "✔️ Carregada" if api_key else "❌ ERRO: Chave não encontrada."
st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")

if not api_key:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

genai.configure(api_key=api_key)

# --- Escolha do modelo ---
modelo_disponivel = st.sidebar.selectbox(
    "Selecione o modelo de IA:",
    options=["gemini-2.5-flash", "gemini-2.5-pro"],
    index=0,
    help="Escolha entre o modelo Gemini 2.5 (versão flash) ou Pro"
)

# --- Inicialização do estado da sessão ---
if "chat" not in st.session_state:
    try:
        st.session_state.chat = genai.GenerativeModel(modelo_disponivel).start_chat(history=[])
    except Exception as e:
        st.error(f"Erro ao inicializar o chat: {e}")
        st.stop()

if "display_history" not in st.session_state:
    st.session_state.display_history = []

# Inicializa DataFrames
for df_name in ["df_dados", "df_mapeamento", "df_devolucao", "df_pagamento"]:
    if df_name not in st.session_state:
        st.session_state[df_name] = None

# --- Funções auxiliares ---
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def safe_to_numeric(series):
    if series.dtype == 'object':
        series = series.astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    return pd.to_numeric(series, errors='coerce').fillna(0)

def carregar_dataframe(arquivo, separador_padrao=','):
    nome_arquivo = arquivo.name.lower()
    if nome_arquivo.endswith(('.xlsx', '.xls')):
        engine = 'openpyxl' if nome_arquivo.endswith('.xlsx') else 'xlrd'
        return pd.read_excel(arquivo, engine=engine)
    elif nome_arquivo.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except Exception: pass
        arquivo.seek(0)
        outro_sep = ',' if separador_padrao == ';' else ';'
        df = pd.read_csv(arquivo, encoding='latin-1', sep=outro_sep, on_bad_lines='skip')
        return df
    return None

# --- Barra Lateral para upload ---
with st.sidebar:
    st.header("Base de Conhecimento")
    tipos_permitidos = ["csv", "xlsx", "xls"]

    # Upload de arquivos
    data_file = st.file_uploader("1. Upload de Agendamentos (OS)", type=tipos_permitidos)
    if data_file: st.session_state.df_dados = carregar_dataframe(data_file, ';')

    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=tipos_permitidos)
    if map_file: st.session_state.df_mapeamento = carregar_dataframe(map_file, ',')

    devolucao_file = st.file_uploader("3. Upload de Itens a Instalar (Devolução)", type=tipos_permitidos)
    if devolucao_file: st.session_state.df_devolucao = carregar_dataframe(devolucao_file, ';')

    pagamento_file = st.file_uploader("4. Upload da Base de Pagamento (Duplicidade)", type=tipos_permitidos)
    if pagamento_file: st.session_state.df_pagamento = carregar_dataframe(pagamento_file, ';')

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Função de análise de dados via IA ---
def executar_analise_pandas(prompt, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Responda apenas com código Pandas se a pergunta for sobre os dados.
    Colunas disponíveis: {', '.join(df.columns)}
    Pergunta: "{prompt}"
    """
    try:
        response = genai.GenerativeModel(modelo_disponivel).generate_content(prompt_engenharia)
        codigo_ia = response.text.strip().replace('`','').replace('python','')
        resultado = eval(codigo_ia, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

# --- Chat com IA ---
st.markdown("---")
st.header("💬 Converse com a IA")

# Histórico do chat
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    df_type = 'chat'

    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        df_type = 'dados'

    with st.chat_message("assistant"):
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
                resultado_analise, erro = executar_analise_pandas(prompt, df_type)
                if erro:
                    response_text = "Desculpe, não consegui analisar os dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                st.markdown(response_text)
        else:
            with st.spinner("Pensando..."):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)

    st.session_state.display_history.append({"role": "assistant", "content": response_text})
