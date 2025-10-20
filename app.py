# ==============================================================================
# MERCÚRIO IA - CÓDIGO FINAL E UNIFICADO
# Versão: 3.0
# Modelo IA: Gemini 1.5 Flash (Nome Estável)
# Autor: Mercurio
# ==============================================================================

import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
from haversine import haversine, Unit
from io import BytesIO
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Mercúrio IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral para iniciar a análise!")

# --- CONFIGURAÇÃO CENTRAL DO MODELO DE IA ---
# CORREÇÃO: Usando um nome de modelo moderno e estável.
# Se o erro 404 persistir, troque para "gemini-pro" para máxima compatibilidade.
GEMINI_MODEL = "gemini-1.5-flash"

# --- Lógica robusta para carregar a chave da API ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")

model = None
with st.sidebar:
    st.header("Configuração")
    if api_key:
        st.caption(f"✔️ Chave de API carregada.")
        st.caption(f"**Modelo de IA:** `{GEMINI_MODEL}`")
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(GEMINI_MODEL)
        except Exception as e:
            st.error(f"Erro ao configurar a API do Google: {e}")
            st.stop()
    else:
        st.error("❌ Chave de API não encontrada.")
        st.stop()

# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state and model:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
for key in ['df_dados', 'df_mapeamento', 'df_devolucao', 'df_pagamento']:
    if key not in st.session_state:
        st.session_state[key] = None

# --- Funções Auxiliares ---
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def safe_to_numeric(series):
    if pd.api.types.is_string_dtype(series):
        series = (series.str.replace('R$', '', regex=False)
                        .str.replace('.', '', regex=False)
                        .str.replace(',', '.', regex=False)
                        .str.strip())
    return pd.to_numeric(series, errors='coerce').fillna(0)

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df_map = {'dados': st.session_state.df_dados, 'mapeamento': st.session_state.df_mapeamento}
    df = df_map.get(df_type)
    if df is None: return None, "DataFrame não encontrado."

    prompt_engenharia = f"""
Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário. As colunas disponíveis são: {', '.join(df.columns)}.
INSTRUÇÕES: Se a pergunta for genérica (ex: "quem descobriu o Brasil?"), responda com "PERGUNTA_INVALIDA". Caso contrário, converta a pergunta em uma única linha de código Pandas que gere o resultado, sem usar a palavra 'python' ou acentos graves (`).
Pergunta: "{pergunta}"
Sua resposta:
"""
    try:
        response = model.generate_content(prompt_engenharia)
        resposta_ia = response.text.strip()
        if resposta_ia == "PERGUNTA_INVALIDA": return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

def carregar_dataframe(arquivo):
    nome_arquivo = arquivo.name.lower()
    try:
        if nome_arquivo.endswith('.xlsx'): return pd.read_excel(arquivo, engine='openpyxl')
        elif nome_arquivo.endswith('.xls'): return pd.read_excel(arquivo, engine='xlrd')
        elif nome_arquivo.endswith('.csv'):
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=';', on_bad_lines='skip')
            if len(df.columns) <= 1:
                arquivo.seek(0)
                df = pd.read_csv(arquivo, encoding='latin-1', sep=',', on_bad_lines='skip')
            return df
    except Exception as e:
        st.error(f"Erro ao ler o arquivo {arquivo.name}: {e}")
    return None

# --- Barra Lateral (Sidebar) ---
with st.sidebar:
    st.header("Base de Conhecimento")
    tipos_permitidos = ["csv", "xlsx", "xls"]
    arquivos_config = {
        'df_dados': "1. Upload de Agendamentos (OS)",
        'df_mapeamento': "2. Upload do Mapeamento de RT",
        'df_devolucao': "3. Upload de Itens a Instalar (Dev.)",
        'df_pagamento': "4. Upload Base de Pagamento (Duplic.)"
    }
    for key, label in arquivos_config.items():
        uploaded_file = st.file_uploader(label, type=tipos_permitidos, key=f"upload_{key}")
        if uploaded_file:
            st.session_state[key] = carregar_dataframe(uploaded_file)
            if st.session_state[key] is not None:
                st.caption(f"✔️ {label.split('(')[0].strip()} carregado.")
        st.markdown("---")
    if st.button("🗑️ Limpar Tudo e Reiniciar"):
        st.session_state.clear()
        st.rerun()

# ==============================================================================
# --- Corpo Principal da Aplicação (MÓDULOS RESTAURADOS) ---
# ==============================================================================

# --- Módulo 1: Dashboard de Análise de Ordens de Serviço ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço")
    df_analise = st.session_state.df_dados.copy()
    status_col = next((col for col in df_analise.columns if 'status' in col.lower()), None)
    rep_col_dados = next((col for col in df_analise.columns if 'representante' in col.lower() and 'id' not in col.lower()), None)
    city_col_dados = next((col for col in df_analise.columns if 'cidade' in col.lower()), None)
    motivo_fechamento_col = next((col for col in df_analise.columns if 'tipo de fechamento' in col.lower()), None)

    st.subheader("Filtros de Análise")
    col1, col2 = st.columns(2)
    
    if status_col:
        opcoes_status = ["Exibir Todos"] + sorted(df_analise[status_col].dropna().unique())
        status_selecionado = col1.selectbox("Filtrar por Status:", opcoes_status)
        if status_selecionado and status_selecionado != "Exibir Todos":
            df_analise = df_analise[df_analise[status_col] == status_selecionado]

    if motivo_fechamento_col:
        opcoes_fechamento = ["Exibir Todos"] + sorted(df_analise[motivo_fechamento_col].dropna().unique())
        fechamento_selecionado = col2.selectbox("Filtrar por Tipo de Fechamento:", opcoes_fechamento)
        if fechamento_selecionado and fechamento_selecionado != "Exibir Todos":
            df_analise = df_analise[df_analise[motivo_fechamento_col] == fechamento_selecionado]

    st.subheader("Análises Gráficas")
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        st.write("**Ordens Agendadas por Cidade (Top 10)**")
        if status_col and city_col_dados:
            st.bar_chart(df_analise[df_analise[status_col] == 'Agendada'][city_col_dados].value_counts().nlargest(10))
    with g_col2:
        st.write("**Total de Ordens por RT (Top 10)**")
        if rep_col_dados:
            st.bar_chart(df_analise[rep_col_dados].value_counts().nlargest(10))

# --- (COLE AQUI O RESTANTE DOS SEUS MÓDULOS 2, 3, 4 e 5) ---
# Exemplo:
# if st.session_state.df_pagamento is not None:
#    ... seu código de duplicidade ...
# if st.session_state.df_devolucao is not None:
#    ... seu código de devolução ...

# ==============================================================================
# --- Módulo 6: Chat com a IA (Funcional e Unificado) ---
# ==============================================================================

st.markdown("---")
st.header("💬 Converse com a IA")

for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica sobre os dados ou converse comigo..."):
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
        response_text = ""
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
                current_df = st.session_state.get(f"df_{df_type}")
                df_hash = pd.util.hash_pandas_object(current_df).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
                if erro == "PERGUNTA_INVALIDA": df_type = 'chat'
                elif erro:
                    st.error(erro); response_text = "Desculpe, não consegui analisar sua pergunta nos dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da busca na base de '{df_type}':"); st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                    st.markdown(response_text)
        
        if df_type == 'chat':
            with st.spinner("Pensando..."):
                try:
                    if st.session_state.chat:
                        response = st.session_state.chat.send_message(prompt)
                        response_text = response.text
                        st.markdown(response_text)
                    else:
                        response_text = "O serviço de chat não foi inicializado corretamente."
                        st.error(response_text)
                except Exception as e:
                    st.error(f"Erro ao comunicar com a IA: {e}"); response_text = "Desculpe, não consegui processar sua solicitação."
    
    st.session_state.display_history.append({"role": "assistant", "content": response_text})
