import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
from datetime import datetime
from haversine import haversine, Unit

# ------------------------------------------------------------
# CONFIGURAÇÃO INICIAL
# ------------------------------------------------------------
st.set_page_config(page_title="Mercúrio IA", page_icon="🧠", layout="wide")
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral e converse com a IA!")

# ------------------------------------------------------------
# CHAVE DE API
# ------------------------------------------------------------
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
api_key_status = "✔️ Carregada" if api_key else "❌ ERRO: Chave não encontrada."
st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")

if not api_key:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

genai.configure(api_key=api_key)
modelo_padrao = "gemini-2.5-flash"

# ------------------------------------------------------------
# ESTADO DA SESSÃO
# ------------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "model" not in st.session_state:
    st.session_state.model = genai.GenerativeModel(modelo_padrao)
if "df_dados" not in st.session_state:
    st.session_state.df_dados = None
if "df_mapeamento" not in st.session_state:
    st.session_state.df_mapeamento = None
if "df_devolucao" not in st.session_state:
    st.session_state.df_devolucao = None
if "df_pagamento" not in st.session_state:
    st.session_state.df_pagamento = None

# ------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ------------------------------------------------------------
@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def carregar_dataframe(arquivo, sep=','):
    nome = arquivo.name.lower()
    try:
        if nome.endswith(('.xlsx', '.xls')):
            return pd.read_excel(arquivo, engine='openpyxl')
        elif nome.endswith('.csv'):
            arquivo.seek(0)
            return pd.read_csv(arquivo, encoding='latin-1', sep=sep, on_bad_lines='skip')
    except Exception as e:
        st.error(f"Erro ao carregar {arquivo.name}: {e}")
    return None

# ------------------------------------------------------------
# UPLOAD DE ARQUIVOS
# ------------------------------------------------------------
st.sidebar.header("📂 Base de Conhecimento")
tipos = ["csv", "xlsx", "xls"]

with st.sidebar:
    data_file = st.file_uploader("1️⃣ Agendamentos (OS)", type=tipos)
    if data_file: 
        st.session_state.df_dados = carregar_dataframe(data_file, ';')

    map_file = st.file_uploader("2️⃣ Mapeamento de RT", type=tipos)
    if map_file: 
        st.session_state.df_mapeamento = carregar_dataframe(map_file, ',')

    dev_file = st.file_uploader("3️⃣ Itens a Instalar (Devolução)", type=tipos)
    if dev_file: 
        st.session_state.df_devolucao = carregar_dataframe(dev_file, ';')

    pag_file = st.file_uploader("4️⃣ Base de Pagamento (Duplicidade)", type=tipos)
    if pag_file: 
        st.session_state.df_pagamento = carregar_dataframe(pag_file, ';')

    if st.button("🧹 Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# ------------------------------------------------------------
# DETECÇÃO DE INTENÇÃO (CHAT x DADOS)
# ------------------------------------------------------------
def detectar_tipo_pergunta(texto):
    texto = texto.lower()
    palavras_dados = [
        "tabela", "csv", "coluna", "quantos", "linhas", "ordem",
        "agendamento", "representante", "rt", "valor", "duplicidade",
        "proximidade", "serviço", "status", "cliente", "cidade"
    ]
    if any(p in texto for p in palavras_dados):
        return "dados"
    return "chat"

# ------------------------------------------------------------
# ANÁLISE DE DADOS (MELHORADA)
# ------------------------------------------------------------
def executar_analise(prompt, df):
    try:
        if df is None or df.empty:
            return "Nenhum arquivo foi carregado ainda para análise de dados."

        # Gera um resumo pequeno do DataFrame para contexto
        resumo = df.head(10).to_dict(orient='records')

        prompt_engenharia = f"""
        Você é um assistente especialista em análise de dados com Python e Pandas.
        Use o seguinte DataFrame chamado `df`, que contém colunas: {', '.join(df.columns)}.
        Abaixo estão as primeiras linhas da base de dados: {resumo}

        Responda à seguinte pergunta com base nesses dados:
        "{prompt}"

        Retorne apenas o resultado direto, de forma clara e natural.
        """

        resposta = st.session_state.model.generate_content(prompt_engenharia)
        return resposta.text.strip()

    except Exception as e:
        return f"Erro na análise: {e}"

# ------------------------------------------------------------
# ÁREA DO CHAT
# ------------------------------------------------------------
st.markdown("---")
st.header("💬 Converse com a IA")

# Exibe o histórico
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Entrada do usuário
if prompt := st.chat_input("Envie uma pergunta ou mensagem..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    tipo = detectar_tipo_pergunta(prompt)
    resposta_final = ""

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            if tipo == "dados":
                # Prioriza o arquivo principal, mas permite outros
                df = st.session_state.df_dados or st.session_state.df_mapeamento or st.session_state.df_pagamento
                resposta_final = executar_analise(prompt, df)
            else:
                resposta = st.session_state.model.generate_content(prompt)
                resposta_final = resposta.text.strip()

            st.markdown(resposta_final)

    st.session_state.chat_history.append({"role": "assistant", "content": resposta_final})
