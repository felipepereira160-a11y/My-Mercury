import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
from haversine import haversine, Unit
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Mercúrio IA", page_icon="🧠", layout="wide")
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral!")

# --- Carregamento da Chave da API ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
api_key_status = "❌ ERRO: Chave não encontrada." if not api_key else "✔️ Carregada"

st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")

if not api_key:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-pro')
except Exception as e:
    st.error(f"Erro ao configurar a API do Google: {e}")
    st.stop()

# --- Estado da Sessão ---
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
for df_name in ['df_dados', 'df_mapeamento', 'df_devolucao', 'df_pagamento']:
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

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.get(f"df_{df_type}")
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. As colunas disponíveis são: {', '.join(df.columns)}.
    INSTRUÇÕES:
    1. Determine se a pergunta pode ser respondida usando os dados.
    2. Se a pergunta for genérica, retorne "PERGUNTA_INVALIDA".
    3. Se for sobre os dados, converta em código Pandas que gere o resultado.
    Pergunta: "{pergunta}"
    """
    try:
        response = model.generate_content(prompt_engenharia)
        resposta_ia = response.text.strip().replace('`', '').replace('python', '')
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {'df': df, 'pd': pd, 'np': np})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

def carregar_dataframe(arquivo, separador_padrao=','):
    nome_arquivo = arquivo.name.lower()
    if nome_arquivo.endswith(('.xlsx', '.xls')):
        engine = 'openpyxl' if nome_arquivo.endswith('xlsx') else 'xlrd'
        return pd.read_excel(arquivo, engine=engine)
    elif nome_arquivo.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except Exception:
            pass
        arquivo.seek(0)
        outro_sep = ',' if separador_padrao == ';' else ';'
        return pd.read_csv(arquivo, encoding='latin-1', sep=outro_sep, on_bad_lines='skip')
    return None

# --- Barra Lateral: Upload de Arquivos ---
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

    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=tipos_permitidos)
    if map_file:
        try:
            st.session_state.df_mapeamento = carregar_dataframe(map_file, separador_padrao=',')
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    devolucao_file = st.file_uploader("3. Upload de Itens a Instalar (Devolução)", type=tipos_permitidos)
    if devolucao_file:
        try:
            st.session_state.df_devolucao = carregar_dataframe(devolucao_file, separador_padrao=';')
            st.success("Base de devolução carregada!")
        except Exception as e:
            st.error(f"Erro na base de devolução: {e}")

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

# --- Corpo Principal ---
# Aqui você mantém toda a lógica de dashboards, filtros, análise de duplicidade, devoluções, mapeamento e otimizador
# O código original que você enviou já é compatível com essa versão do modelo, apenas substituí a inicialização do `GenerativeModel` 
# para `gemini-2.5-pro` e a chamada `model.generate_content(...)` dentro da função `executar_analise_pandas`.

# --- Chat IA ---
st.markdown("---")
st.header("💬 Converse com a IA")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    df_type = 'chat'
    
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        df_type = 'dados'
    
    with st.chat_message("assistant"):
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
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
