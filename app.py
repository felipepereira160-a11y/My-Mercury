import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
from haversine import haversine, Unit
from datetime import datetime

# ------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ------------------------------------------------------------
st.set_page_config(
    page_title="Mercúrio IA",
    page_icon="🧠",
    layout="wide"
)
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral!")

# ------------------------------------------------------------
# CHAVE DE API
# ------------------------------------------------------------
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
api_status = "✔️ Carregada" if api_key else "❌ Não encontrada"
st.sidebar.caption(f"**Status da Chave de API:** {api_status}")

if not api_key:
    st.error("Chave da API do Google não encontrada. O aplicativo não pode funcionar.")
    st.stop()

# Configuração do modelo Gemini
genai.configure(api_key=api_key)
MODELO_PADRAO = "gemini-2.5-flash"

# ------------------------------------------------------------
# INICIALIZAÇÃO DO MODELO E SESSÃO
# ------------------------------------------------------------
if "model" not in st.session_state:
    try:
        st.session_state.model = genai.GenerativeModel(MODELO_PADRAO)
    except Exception as e:
        st.error(f"Erro ao inicializar o modelo Gemini: {e}")
        st.stop()

# Histórico de chat
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("display_history", [])

# DataFrames
for df_key in ['df_dados', 'df_mapeamento', 'df_devolucao', 'df_pagamento']:
    st.session_state.setdefault(df_key, None)

# ------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ------------------------------------------------------------
@st.cache_data
def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def safe_to_numeric(series: pd.Series) -> pd.Series:
    """Converte série para numérico de forma robusta."""
    if series.dtype == 'object':
        series = (
            series.astype(str)
            .str.replace('R$', '', regex=False)
            .str.replace('.', '', regex=False)
            .str.replace(',', '.', regex=False)
            .str.strip()
        )
    return pd.to_numeric(series, errors='coerce').fillna(0)

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta: str, df_type: str):
    """Executa análise usando Gemini e código Pandas."""
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    prompt = f"""
    Você é um especialista em Python e Pandas. Colunas disponíveis: {', '.join(df.columns)}.
    Pergunta: "{pergunta}"
    Retorne uma linha de código Pandas que gere o resultado ou "PERGUNTA_INVALIDA".
    """
    try:
        resp = st.session_state.model.generate_content(prompt)
        codigo = resp.text.strip().replace('`', '').replace('python', '')
        if codigo == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        resultado = eval(codigo, {'df': df, 'pd': pd, 'np': np})
        return resultado, None
    except Exception as e:
        return None, f"Erro ao executar a análise: {e}"

def carregar_dataframe(arquivo, separador_padrao=','):
    """Carrega CSV ou Excel de forma robusta."""
    nome_arquivo = arquivo.name.lower()
    try:
        if nome_arquivo.endswith(('.xlsx', '.xls')):
            return pd.read_excel(arquivo, engine='openpyxl' if nome_arquivo.endswith('xlsx') else 'xlrd')
        elif nome_arquivo.endswith('.csv'):
            arquivo.seek(0)
            try:
                return pd.read_csv(arquivo, sep=separador_padrao, encoding='latin-1', on_bad_lines='skip')
            except:
                outro_sep = ',' if separador_padrao == ';' else ';'
                arquivo.seek(0)
                return pd.read_csv(arquivo, sep=outro_sep, encoding='latin-1', on_bad_lines='skip')
    except Exception as e:
        st.error(f"Erro ao carregar arquivo {arquivo.name}: {e}")
        return None

def detectar_tipo_pergunta(texto: str) -> str:
    """Decide se a pergunta é sobre dados ou chat."""
    palavras_dados = ["tabela", "csv", "coluna", "quantos", "linhas", "ordem", "agendamento",
                      "representante", "rt", "valor", "duplicidade", "proximidade", "serviço",
                      "mapeamento", "quem atende", "telefone", "contato"]
    return "dados" if any(p in texto.lower() for p in palavras_dados) else "chat"

# ------------------------------------------------------------
# BARRA LATERAL - UPLOADS
# ------------------------------------------------------------
with st.sidebar:
    st.header("Base de Conhecimento")
    tipos_permitidos = ["csv", "xlsx", "xls"]

    def uploader(label, key, sep):
        arquivo = st.file_uploader(label, type=tipos_permitidos)
        if arquivo:
            df = carregar_dataframe(arquivo, separador_padrao=sep)
            if df is not None:
                st.session_state[key] = df
                st.success(f"{label.split('(')[0]} carregado com sucesso!")

    uploader("1. Upload Pesquisa de O.S (OS)", "df_dados", ';')
    st.markdown("---")
    uploader("2. Upload do Mapeamento de RT (Fixo)", "df_mapeamento", ',')
    st.markdown("---")
    uploader("3. Upload de Itens a Instalar (Devolução)", "df_devolucao", ';')
    st.markdown("---")
    uploader("4. Upload da Base de Pagamento (Duplicidade)", "df_pagamento", ';')
    st.markdown("---")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# ------------------------------------------------------------
# CORPO PRINCIPAL (dashboards, análises e ferramentas)
# ------------------------------------------------------------
# Aqui entraria todo o código de dashboard, análise de duplicidade, devolução, mapeamento e otimização
# Mantendo a lógica original do seu código, mas modularizada em funções separadas se necessário.

# ------------------------------------------------------------
# CHAT DE IA
# ------------------------------------------------------------
st.markdown("---")
st.header("💬 Converse com a IA")

for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

for msg in st.session_state.chat_history:
    if msg not in st.session_state.display_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

if prompt := st.chat_input("Envie uma pergunta ou mensagem..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    tipo = detectar_tipo_pergunta(prompt)
    resposta_final = ""
    if tipo == "chat":
        try:
            resp = st.session_state.model.generate_content(prompt)
            resposta_final = resp.text.strip()
        except Exception as e:
            resposta_final = f"Erro: {e}"
    else:
        resultado, erro = executar_analise_pandas("", prompt, "dados")
        resposta_final = str(resultado) if resultado is not None else erro

    st.session_state.display_history.append({"role": "assistant", "content": resposta_final})
    st.session_state.chat_history.append({"role": "assistant", "content": resposta_final})
    with st.chat_message("assistant"):
        st.markdown(resposta_final)
