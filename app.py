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

# --- Configuração da Chave de API ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not api_key:
    st.error("❌ Chave da API do Google não encontrada. O app não pode funcionar.")
    st.stop()

genai.configure(api_key=api_key)
model = genai.ChatModel("models/gemini-pro-latest")

# --- Inicialização do estado da sessão ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "df_dados" not in st.session_state:
    st.session_state.df_dados = None
if "df_mapeamento" not in st.session_state:
    st.session_state.df_mapeamento = None
if "df_devolucao" not in st.session_state:
    st.session_state.df_devolucao = None
if "df_pagamento" not in st.session_state:
    st.session_state.df_pagamento = None

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
        return pd.read_excel(arquivo, engine='openpyxl' if nome_arquivo.endswith('xlsx') else 'xlrd')
    elif nome_arquivo.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except:
            pass
        arquivo.seek(0)
        outro_sep = ',' if separador_padrao == ';' else ';'
        df = pd.read_csv(arquivo, encoding='latin-1', sep=outro_sep, on_bad_lines='skip')
        return df
    return None

# --- Barra lateral para upload ---
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
        st.experimental_rerun()

# --- DASHBOARD ORDENS DE SERVIÇO ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Ordens de Serviço")
    df_analise = st.session_state.df_dados.copy()
    
    status_col = next((c for c in df_analise.columns if 'status' in c.lower()), None)
    city_col = next((c for c in df_analise.columns if 'cidade' in c.lower()), None)
    rep_col = next((c for c in df_analise.columns if 'representante' in c.lower() and 'id' not in c.lower()), None)
    
    # Filtros
    col1, col2 = st.columns(2)
    status_selec = col1.selectbox("Filtrar por Status:", options=["Exibir Todos"] + sorted(df_analise[status_col].dropna().unique()) if status_col else [])
    cidade_selec = col2.selectbox("Filtrar por Cidade:", options=["Exibir Todos"] + sorted(df_analise[city_col].dropna().unique()) if city_col else [])
    
    if status_selec != "Exibir Todos" and status_col: df_analise = df_analise[df_analise[status_col] == status_selec]
    if cidade_selec != "Exibir Todos" and city_col: df_analise = df_analise[df_analise[city_col] == cidade_selec]
    
    st.subheader("Top 10 Ordens por Cidade")
    if city_col: st.bar_chart(df_analise[city_col].value_counts().nlargest(10))
    
    st.subheader("Top 10 Ordens por Representante")
    if rep_col: st.bar_chart(df_analise[rep_col].value_counts().nlargest(10))
    
    with st.expander("Ver tabela completa"):
        st.dataframe(st.session_state.df_dados)

# --- CHAT DE IA (considerando dados carregados) ---
st.markdown("---")
st.header("💬 Pergunte à IA sobre os dados")

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Faça uma pergunta sobre os relatórios ou geral..."):
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        try:
            # Se houver dados, tenta analisar primeiro
            if st.session_state.df_dados is not None:
                df = st.session_state.df_dados.copy()
                prompt_df = f"""
                Você é um assistente especialista em Python e Pandas.
                As colunas disponíveis no dataframe `df` são: {', '.join(df.columns)}.
                Pergunta do usuário: "{prompt}"
                Gere o resultado usando apenas pandas.
                """
                response = model.chat(messages=[{"role":"user","content":prompt_df}])
                text_resp = response.last.message.get("content", "").strip()
                # Se for algo que gera tabela ou número, tenta executar
                try:
                    resultado = eval(text_resp, {"df": df, "pd": pd, "np": np})
                    if isinstance(resultado, (pd.DataFrame, pd.Series)):
                        st.dataframe(resultado)
                        text_resp = "✅ Resultado exibido acima."
                except:
                    pass
            else:
                # Chat genérico
                response = model.chat(messages=[{"role":"user","content":prompt}])
                text_resp = response.last.message.get("content", "").strip()
        except Exception as e:
            text_resp = f"❌ Erro ao processar a pergunta: {e}"
        
        st.markdown(text_resp)
        st.session_state.chat_history.append({"role": "assistant", "content": text_resp})
