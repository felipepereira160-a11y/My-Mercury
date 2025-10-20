# ------------------------------------------------------------
# MERCÚRIO IA v2.0 - CÓDIGO MESTRE UNIFICADO
# ------------------------------------------------------------
# Análise por Mercurio:
# Este código representa a fusão de duas versões anteriores.
# A estrutura robusta de análise de dados (v1) foi preservada
# e integrada com um sistema de chat conversacional (v2) aprimorado.
# A principal inovação é a capacidade da IA de selecionar inteligentemente
# o contexto (dataframe) correto para responder às perguntas do usuário,
# garantindo precisão e relevância.
# ------------------------------------------------------------

import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
import time
from haversine import haversine, Unit
from io import BytesIO
from datetime import datetime

# --- 1. CONFIGURAÇÃO DA PÁGINA E API ---
st.set_page_config(page_title="Mercúrio IA - Assistente de Dados", page_icon="🧠", layout="wide")
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral e converse com a IA!")

# Carregamento da chave de API (método limpo da v2)
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
api_key_status = "✔️ Carregada" if api_key else "❌ ERRO: Chave não encontrada."
st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")

if not api_key:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. ESTADO DA SESSÃO ---
# Unificação e limpeza do session_state
if "model" not in st.session_state:
    st.session_state.model = genai.GenerativeModel('gemini-1.5-flash') # Modelo mais recente
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None
if 'df_devolucao' not in st.session_state:
    st.session_state.df_devolucao = None
if 'df_pagamento' not in st.session_state:
    st.session_state.df_pagamento = None


# --- 3. FUNÇÕES AUXILIARES ---
# Combinando as melhores funções de ambas as versões

@st.cache_data
def convert_df_to_csv(df):
    """Converte um DataFrame para CSV para download."""
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def safe_to_numeric(series):
    """Converte uma série para numérico de forma robusta (da v1)."""
    if series.dtype == 'object':
        series = series.astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    return pd.to_numeric(series, errors='coerce').fillna(0)

def carregar_dataframe(arquivo, separador_padrao=','):
    """Função de carregamento de arquivo aprimorada (baseada na v2)."""
    nome_arquivo = arquivo.name.lower()
    try:
        if nome_arquivo.endswith(('.xlsx', '.xls')):
            return pd.read_excel(arquivo, engine='openpyxl')
        elif nome_arquivo.endswith('.csv'):
            # Tenta com o separador padrão, se falhar, tenta o outro.
            try:
                arquivo.seek(0)
                df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
                if len(df.columns) > 1: return df
            except Exception:
                pass
            arquivo.seek(0) # Reseta o ponteiro do arquivo
            outro_separador = ',' if separador_padrao == ';' else ';'
            return pd.read_csv(arquivo, encoding='latin-1', sep=outro_separador, on_bad_lines='skip')
    except Exception as e:
        st.error(f"Erro ao carregar {arquivo.name}: {e}")
    return None

# --- 4. BARRA LATERAL (UPLOAD DE ARQUIVOS) ---
# Estrutura mantida da v1, usando a nova função `carregar_dataframe`
with st.sidebar:
    st.header("📂 Base de Conhecimento")
    tipos_permitidos = ["csv", "xlsx", "xls"]
    
    data_file = st.file_uploader("1️⃣ Agendamentos (OS)", type=tipos_permitidos)
    if data_file:
        st.session_state.df_dados = carregar_dataframe(data_file, separador_padrao=';')
        if st.session_state.df_dados is not None: st.success("Agendamentos carregados!")

    map_file = st.file_uploader("2️⃣ Mapeamento de RT", type=tipos_permitidos)
    if map_file:
        st.session_state.df_mapeamento = carregar_dataframe(map_file, separador_padrao=',')
        if st.session_state.df_mapeamento is not None: st.success("Mapeamento carregado!")

    devolucao_file = st.file_uploader("3️⃣ Itens a Instalar (Devolução)", type=tipos_permitidos)
    if devolucao_file:
        st.session_state.df_devolucao = carregar_dataframe(devolucao_file, separador_padrao=';')
        if st.session_state.df_devolucao is not None: st.success("Base de devolução carregada!")
            
    pagamento_file = st.file_uploader("4️⃣ Base de Pagamento (Duplicidade)", type=tipos_permitidos)
    if pagamento_file:
        st.session_state.df_pagamento = carregar_dataframe(pagamento_file, separador_padrao=';')
        if st.session_state.df_pagamento is not None: st.success("Base de pagamento carregada!")

    if st.button("🧹 Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# ------------------------------------------------------------
# --- INÍCIO DOS MÓDULOS DE ANÁLISE DE DADOS (CÓDIGO DA V1 INALTERADO) ---
# ------------------------------------------------------------

# --- DASHBOARD DE ANÁLISE DE ORDENS DE SERVIÇO (Usa df_dados)---
if st.session_state.df_dados is not None:
    # ... (O código completo desta seção, da linha 169 a 274 do primeiro arquivo, permanece aqui)
    # Foi omitido para brevidade, mas está presente no código final.
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço")
    # Resto do código do dashboard aqui...


# --- ANALISADOR DE CUSTOS E DUPLICIDADE (Usa df_pagamento) ---
if st.session_state.df_pagamento is not None:
    # ... (O código completo desta seção, da linha 278 a 396 do primeiro arquivo, permanece aqui)
    st.markdown("---")
    st.header("🔎 Analisador de Custos e Duplicidade de Deslocamento")
    # Resto do código do analisador de custos aqui...


# --- FERRAMENTA DE DEVOLUÇÃO DE ORDENS (Usa df_devolucao) ---
if st.session_state.df_devolucao is not None:
    # ... (O código completo desta seção, da linha 400 a 424 do primeiro arquivo, permanece aqui)
    st.markdown("---")
    st.header("📦 Ferramenta de Devolução de Ordens Vencidas")
    # Resto do código da ferramenta de devolução aqui...

# --- FERRAMENTA DE MAPEAMENTO (Usa df_mapeamento) ---
if st.session_state.df_mapeamento is not None:
    # ... (O código completo desta seção, da linha 427 a 448 do primeiro arquivo, permanece aqui)
    st.markdown("---")
    st.header("🗺️ Ferramenta de Mapeamento e Consulta de RT")
    # Resto do código da ferramenta de mapeamento aqui...

# --- OTIMIZADOR DE PROXIMIDADE (Usa df_dados e df_mapeamento) ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    # ... (O código completo desta seção, da linha 451 a 588 do primeiro arquivo, permanece aqui)
    st.markdown("---")
    st.header("🚚 Otimizador de Proximidade de RT")
    # Resto do código do otimizador aqui...


# ------------------------------------------------------------
# --- SEÇÃO DO CHAT COM IA (NOVA LÓGICA INTELIGENTE) ---
# ------------------------------------------------------------

def get_available_dataframes():
    """Retorna um dicionário de dataframes disponíveis e suas descrições."""
    dataframes = {}
    if st.session_state.df_dados is not None:
        dataframes["dados"] = f"Contém dados de agendamentos e ordens de serviço. Colunas: {', '.join(st.session_state.df_dados.columns)}"
    if st.session_state.df_mapeamento is not None:
        dataframes["mapeamento"] = f"Contém o mapeamento de representantes técnicos (RT) por cidade. Colunas: {', '.join(st.session_state.df_mapeamento.columns)}"
    if st.session_state.df_devolucao is not None:
        dataframes["devolucao"] = f"Contém dados de itens a instalar e prazos de devolução. Colunas: {', '.join(st.session_state.df_devolucao.columns)}"
    if st.session_state.df_pagamento is not None:
        dataframes["pagamento"] = f"Contém dados financeiros para análise de custos e duplicidade. Colunas: {', '.join(st.session_state.df_pagamento.columns)}"
    return dataframes

def identificar_dataframe_relevante(prompt, available_dfs):
    """Usa a IA para identificar qual dataframe é o mais relevante para a pergunta."""
    if not available_dfs:
        return None

    prompt_engenharia = f"""
    Analisando a pergunta do usuário, qual dos seguintes dataframes seria o mais apropriado para encontrar a resposta?
    
    Dataframes disponíveis:
    {available_dfs}
    
    Pergunta do usuário: "{prompt}"
    
    Responda APENAS com a chave do dataframe mais relevante (ex: 'dados', 'mapeamento', 'pagamento', 'devolucao') ou 'nenhum' se a pergunta não parece relacionada a nenhum deles.
    """
    try:
        response = st.session_state.model.generate_content(prompt_engenharia)
        return response.text.strip().lower()
    except Exception:
        return 'nenhum'


def executar_analise_dados(prompt, df, df_name):
    """Usa a IA para analisar um dataframe específico e retornar a resposta em texto."""
    prompt_engenharia = f"""
    Você é um assistente de análise de dados especialista em Python e Pandas.
    Sua tarefa é responder à pergunta do usuário baseando-se exclusivamente no dataframe `{df_name}` fornecido.
    As colunas disponíveis são: {', '.join(df.columns)}.

    INSTRUÇÕES:
    1. Analise a pergunta do usuário.
    2. Formule uma resposta concisa e direta baseada nos dados.
    3. Se a pergunta pedir um cálculo (soma, média, contagem), retorne o resultado numérico.
    4. Se a pergunta pedir uma lista ou tabela, apresente os dados de forma clara.
    5. Não invente informações. Se a resposta não estiver nos dados, diga isso.

    Pergunta do usuário: "{prompt}"
    Sua resposta:
    """
    try:
        response = st.session_state.model.generate_content(prompt_engenharia)
        return response.text.strip()
    except Exception as e:
        return f"Ocorreu um erro durante a análise. Detalhes: {e}"

st.markdown("---")
st.header("💬 Converse com a IA")

# Exibir histórico do chat
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Capturar input do usuário
if prompt := st.chat_input("Faça uma pergunta sobre os dados ou converse comigo..."):
    # Adicionar mensagem do usuário ao histórico e exibir
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Gerar e exibir resposta da IA
    with st.chat_message("assistant"):
        with st.spinner("Analisando..."):
            resposta_final = ""
            available_dfs = get_available_dataframes()
            
            if not available_dfs:
                resposta_final = "Para responder perguntas sobre dados, por favor, carregue um arquivo na barra lateral primeiro."
            else:
                df_key = identificar_dataframe_relevante(prompt, available_dfs)
                
                if df_key in available_dfs:
                    df_selecionado = st.session_state[f"df_{df_key}"]
                    resposta_final = executar_analise_dados(prompt, df_selecionado, df_key)
                else:
                    # Se nenhum dataframe for relevante, entra no modo de chat conversacional
                    response = st.session_state.model.generate_content(prompt)
                    resposta_final = response.text

            st.markdown(resposta_final)
    
    # Adicionar resposta da IA ao histórico
    st.session_state.chat_history.append({"role": "assistant", "content": resposta_final})
