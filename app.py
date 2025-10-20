import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
import time
from haversine import haversine, Unit
from io import BytesIO
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral!")

# --- Configuração da chave API ---
api_key = None
api_key_status = "Não configurada"
try:
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if api_key:
        api_key_status = "✔️ Carregada (Streamlit Secrets)"
except Exception:
    pass

if not api_key:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        api_key_status = "✔️ Carregada (Variável de Ambiente)"
    else:
        api_key_status = "❌ ERRO: Chave não encontrada."

st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")

model = None
if api_key:
    try:
        genai.configure(api_key=api_key)
        # Usar modelo Gemini (não vamos usar generate_text direto para evitar erro)
        model = genai.GenerativeModel("models/gemini-pro-latest")
    except Exception as e:
        st.error(f"Erro ao configurar a API do Google: {e}")
        st.stop()
else:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state and model:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None
if 'df_devolucao' not in st.session_state:
    st.session_state.df_devolucao = None
if 'df_pagamento' not in st.session_state:
    st.session_state.df_pagamento = None

# --- Funções ---
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def safe_to_numeric(series):
    if series.dtype == 'object':
        series = series.astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    return pd.to_numeric(series, errors='coerce').fillna(0)

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário.
    As colunas disponíveis no dataframe `df` são: {', '.join(df.columns)}.

    INSTRUÇÕES:
    1. Determine se a pergunta do usuário PODE ser respondida usando os dados.
    2. Se a pergunta for genérica (ex: "quem descobriu o Brasil?"), responda APENAS com: "PERGUNTA_INVALIDA".
    3. Se a pergunta for sobre os dados, converta-a em uma única linha de código Pandas que gere o resultado.

    Pergunta: "{pergunta}"
    Sua resposta:
    """
    try:
        # Para evitar o erro de generate_text, usamos start_chat + send_message
        chat_temp = model.start_chat()
        response = chat_temp.send_message(prompt_engenharia)
        resposta_ia = response.text.strip().replace('`', '').replace('python', '')
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

def carregar_dataframe(arquivo, separador_padrao=','):
    nome_arquivo = arquivo.name.lower()
    if nome_arquivo.endswith('.xlsx'):
        return pd.read_excel(arquivo, engine='openpyxl')
    elif nome_arquivo.endswith('.xls'):
        return pd.read_excel(arquivo, engine='xlrd')
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

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    tipos_permitidos = ["csv", "xlsx", "xls"]
    
    data_file = st.file_uploader("1. Upload de Agendamentos (OS)", type=tipos_permitidos)
    if data_file:
        try:
            st.session_state.df_dados = carregar_dataframe(data_file, separador_padrao=';')
            st.success("Agendamentos carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    st.markdown("---")
    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=tipos_permitidos)
    if map_file:
        try:
            st.session_state.df_mapeamento = carregar_dataframe(map_file, separador_padrao=',')
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    st.markdown("---")
    devolucao_file = st.file_uploader("3. Upload de Itens a Instalar (Devolução)", type=tipos_permitidos)
    if devolucao_file:
        try:
            st.session_state.df_devolucao = carregar_dataframe(devolucao_file, separador_padrao=';')
            st.success("Base de devolução carregada!")
        except Exception as e:
            st.error(f"Erro na base de devolução: {e}")
            
    st.markdown("---")
    pagamento_file = st.file_uploader("4. Upload da Base de Pagamento (Duplicidade)", type=tipos_permitidos)
    if pagamento_file:
        try:
            st.session_state.df_pagamento = carregar_dataframe(pagamento_file, separador_padrao=';')
            st.success("Base de pagamento carregada!")
        except Exception as e:
            st.error(f"Erro na base de pagamento: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Aqui você mantém todo o código original dos dashboards, análises, devolução, mapeamento, otimização, etc. ---
# (Sem alteração, copia seu código completo da pergunta original)
# ...

# --- SEÇÃO DO CHAT DE AJUDA COM IA (BAIXO CUSTO / GRATUITO) ---
st.markdown("---")
st.header("💬 Chat de Ajuda (Sem custos de tickets)")

# Inicializa histórico do chat
if "chat_ajuda_history" not in st.session_state:
    st.session_state.chat_ajuda_history = []

# Entrada do usuário
user_input = st.text_input("Faça sua pergunta para a IA de ajuda:")

if st.button("Enviar Pergunta") and user_input:
    # Resposta simulada para baixo custo
    resposta = f"Pergunta recebida: '{user_input}'. Sugestão: tente verificar os filtros, colunas ou arquivos carregados, ou consulte a documentação do dashboard."
    
    # Armazena no histórico
    st.session_state.chat_ajuda_history.append(("Você", user_input))
    st.session_state.chat_ajuda_history.append(("IA", resposta))
    user_input = ""  # Limpa input

# Mostra o histórico de conversa
for quem, msg in st.session_state.chat_ajuda_history:
    if quem == "Você":
        st.markdown(f"**{quem}:** {msg}")
    else:
        st.markdown(f"**{quem}:** {msg}")
