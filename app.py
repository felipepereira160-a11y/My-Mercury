import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
from haversine import haversine, Unit
from io import BytesIO
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral!")

# --- Carregamento da Chave da API ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
api_key_status = "✔️ Carregada" if api_key else "❌ ERRO: Chave não encontrada."
st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")

if not api_key:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

# --- Configuração do modelo Gemini 2.5 Pro ---
try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-pro')
except Exception as e:
    st.error(f"Erro ao configurar a API do Google: {e}")
    st.stop()

# --- Inicialização do estado da sessão ---
if "display_history" not in st.session_state:
    st.session_state.display_history = []

for df_name in ["df_dados", "df_mapeamento", "df_devolucao", "df_pagamento"]:
    if df_name not in st.session_state:
        st.session_state[df_name] = None

# --- Funções utilitárias ---
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
    if df is None:
        return None, "SEM_DADOS"
    
    prompt_engenharia = f"""
Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário.
As colunas disponíveis no dataframe `df` são: {', '.join(df.columns)}.

INSTRUÇÕES:
1. Determine se a pergunta do usuário PODE ser respondida usando os dados.
2. Se a pergunta for genérica, responda apenas: "PERGUNTA_INVALIDA".
3. Se a pergunta for sobre os dados, converta-a em uma linha de código Pandas que gere o resultado.

Pergunta: "{pergunta}"
Responda apenas com o código Pandas ou "PERGUNTA_INVALIDA".
"""
    try:
        response = model.generate_message(prompt_engenharia)
        resposta_ia = response.text.strip().replace('`', '').replace('python', '')
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {"df": df, "pd": pd, "np": np})
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
        outro_separador = ',' if separador_padrao == ';' else ';'
        df = pd.read_csv(arquivo, encoding='latin-1', sep=outro_separador, on_bad_lines='skip')
        return df
    return None

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    tipos_permitidos = ["csv", "xlsx", "xls"]
    
    for label, key, sep in [
        ("1. Upload de Agendamentos (OS)", "df_dados", ';'),
        ("2. Upload do Mapeamento de RT (Fixo)", "df_mapeamento", ','),
        ("3. Upload de Itens a Instalar (Devolução)", "df_devolucao", ';'),
        ("4. Upload da Base de Pagamento (Duplicidade)", "df_pagamento", ';')
    ]:
        file = st.file_uploader(label, type=tipos_permitidos)
        if file:
            try:
                st.session_state[key] = carregar_dataframe(file, separador_padrao=sep)
                st.success(f"{label.split('Upload')[-1]} carregado!")
            except Exception as e:
                st.error(f"Erro ao carregar {label}: {e}")
    
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
    
    df_type = None
    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
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
                        st.write(f"Resultado da busca na base de '{df_type}':")
                        st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                st.markdown(response_text)
        else:  # Chat genérico
            with st.spinner("Pensando..."):
                response = model.generate_message(prompt)
                response_text = response.text
                st.markdown(response_text)
    
    st.session_state.display_history.append({"role": "assistant", "content": response_text})
