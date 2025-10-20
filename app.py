import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
from haversine import haversine, Unit
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral!")

# --- Carregamento da Chave da API ---
api_key_status = "Não configurada"
api_key = st.secrets.get("GOOGLE_API_KEY", None) or os.environ.get("GOOGLE_API_KEY")
if api_key:
    api_key_status = "✔️ Carregada"
else:
    api_key_status = "❌ ERRO: Chave não encontrada."
st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")
if not api_key:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

# --- Configuração do Modelo ---
model = None
try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
except Exception as e:
    st.error(f"Erro ao configurar a API do Google: {e}")
    st.stop()

# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state and model:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
for df_name in ["df_dados", "df_mapeamento", "df_devolucao", "df_pagamento"]:
    if df_name not in st.session_state:
        st.session_state[df_name] = None

# --- Funções Utilitárias ---
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
        return pd.read_excel(arquivo, engine='openpyxl' if nome_arquivo.endswith('xlsx') else 'xlrd')
    elif nome_arquivo.endswith('.csv'):
        arquivo.seek(0)
        try:
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except Exception: pass
        arquivo.seek(0)
        outro_sep = ',' if separador_padrao == ';' else ';'
        df = pd.read_csv(arquivo, encoding='latin-1', sep=outro_sep, on_bad_lines='skip')
        return df
    return None

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Analise a pergunta do usuário.
    Colunas disponíveis: {', '.join(df.columns)}
    Pergunta: "{pergunta}"
    """
    try:
        response = model.generate_content(prompt_engenharia)
        resposta_ia = response.text.strip().replace('`', '').replace('python', '')
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

# --- Barra Lateral: Upload de Arquivos ---
with st.sidebar:
    st.header("Base de Conhecimento")
    tipos_permitidos = ["csv", "xlsx", "xls"]
    
    data_file = st.file_uploader("1. Upload de Agendamentos (OS)", type=tipos_permitidos)
    if data_file:
        st.session_state.df_dados = carregar_dataframe(data_file, separador_padrao=';')
        st.success("Agendamentos carregados!")
    
    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=tipos_permitidos)
    if map_file:
        st.session_state.df_mapeamento = carregar_dataframe(map_file, separador_padrao=',')
        st.success("Mapeamento carregado!")
    
    devolucao_file = st.file_uploader("3. Upload de Itens a Instalar (Devolução)", type=tipos_permitidos)
    if devolucao_file:
        st.session_state.df_devolucao = carregar_dataframe(devolucao_file, separador_padrao=';')
        st.success("Base de devolução carregada!")
    
    pagamento_file = st.file_uploader("4. Upload da Base de Pagamento (Duplicidade)", type=tipos_permitidos)
    if pagamento_file:
        st.session_state.df_pagamento = carregar_dataframe(pagamento_file, separador_padrao=';')
        st.success("Base de pagamento carregada!")
    
    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    df_type = 'chat'
    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        df_type = 'dados'
    
    with st.chat_message("assistant"):
        try:
            if df_type in ['mapeamento', 'dados']:
                current_df = st.session_state.get(f"df_{df_type}")
                df_hash = pd.util.hash_pandas_object(current_df).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
                
                if erro == "PERGUNTA_INVALIDA":
                    response_text = "Desculpe, só posso responder a perguntas relacionadas aos dados da planilha carregada."
                elif erro:
                    st.error(erro)
                    response_text = "Desculpe, não consegui analisar os dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da busca na base de '{df_type}':")
                        st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
            else:
                # Chat genérico com detecção de método Gemini
                if hasattr(st.session_state.chat, "send_message"):
                    response = st.session_state.chat.send_message(prompt)
                    response_text = response.last
                elif hasattr(st.session_state.chat, "generate_text"):
                    response = st.session_state.chat.generate_text(prompt)
                    response_text = response.text
                else:
                    response_text = "Erro: método de envio de mensagem não suportado nesta versão do Gemini."
        except Exception as e:
            response_text = f"Erro ao gerar resposta do Gemini: {e}"

        st.markdown(response_text)
        st.session_state.display_history.append({"role": "assistant", "content": response_text})
