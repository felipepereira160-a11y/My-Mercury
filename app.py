# ==============================================================================
# MERCÚRIO IA - CÓDIGO COMPLETO E REATORADO
# Versão: 2.1
# Modelo IA: Gemini 1.5 Pro (Configuração Centralizada)
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
# Para trocar o modelo (ex: para uma versão mais rápida como "gemini-1.5-flash-latest"),
# altere APENAS esta linha.
GEMINI_MODEL = "gemini-1.5-pro-latest"

# --- Lógica robusta para carregar a chave da API ---
# Tenta carregar dos secrets do Streamlit, se não encontrar, tenta das variáveis de ambiente.
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")

# --- Validação da API e Inicialização do Modelo ---
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

# --- Inicialização do Estado da Sessão (de forma otimizada) ---
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
    """Converte um DataFrame para CSV otimizado para Excel em português."""
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def safe_to_numeric(series):
    """Converte uma série para numérico de forma robusta, limpando símbolos monetários e de pontuação."""
    if pd.api.types.is_string_dtype(series):
        series = series.str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    return pd.to_numeric(series, errors='coerce').fillna(0)

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    """Usa a IA para converter uma pergunta em código Pandas e executá-lo."""
    df_map = {'dados': st.session_state.df_dados, 'mapeamento': st.session_state.df_mapeamento}
    df = df_map.get(df_type)
    if df is None:
        return None, "DataFrame não encontrado no estado da sessão."

    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário.
    As colunas disponíveis no dataframe `df` são: {', '.join(df.columns)}.

    INSTRUÇÕES:
    1. Determine se a pergunta do usuário PODE ser respondida usando os dados.
    2. Se a pergunta for genérica (ex: "quem descobriu o Brasil?"), responda APENAS com: "PERGUNTA_INVALIDA".
    3. Se a pergunta for sobre os dados, converta-a em uma única linha de código Pandas que gere o resultado. O código não deve conter a palavra 'python' nem acentos graves (`).

    Pergunta: "{pergunta}"
    Sua resposta:
    """
    try:
        local_model = genai.GenerativeModel(GEMINI_MODEL)
        response = local_model.generate_content(prompt_engenharia)
        resposta_ia = response.text.strip()
        
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
            
        resultado = eval(resposta_ia, {'df': df, 'pd': pd, 'np': np})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

def carregar_dataframe(arquivo):
    """Carrega arquivos CSV, XLSX ou XLS de forma inteligente."""
    nome_arquivo = arquivo.name.lower()
    try:
        if nome_arquivo.endswith('.xlsx'):
            return pd.read_excel(arquivo, engine='openpyxl')
        elif nome_arquivo.endswith('.xls'):
            return pd.read_excel(arquivo, engine='xlrd')
        elif nome_arquivo.endswith('.csv'):
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=';', on_bad_lines='warn')
            if len(df.columns) <= 1:
                arquivo.seek(0)
                df = pd.read_csv(arquivo, encoding='latin-1', sep=',', on_bad_lines='warn')
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
# --- Corpo Principal da Aplicação ---
# ==============================================================================

# [COLE AQUI OS SEUS MÓDULOS DE ANÁLISE 1 A 5]
# Os módulos de Dashboard, Analisador de Custos, Devolução, Mapeamento e 
# Otimizador permanecem os mesmos. Cole-os aqui.
# Para manter a resposta concisa, eles foram omitidos.

# --- MÓDULO 6: CHAT COM A IA (VERSÃO REFEITA) ---
st.markdown("---")
st.header("💬 Converse com a IA")

for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica sobre os dados ou converse comigo..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        response_text = ""
        contexto_analise = None

        # Determina o contexto da pergunta para análise de dados
        keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
        if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
            contexto_analise = 'mapeamento'
        elif st.session_state.df_dados is not None:
            # Se não for sobre mapeamento, mas houver dados de OS, assume que a análise é sobre eles.
            contexto_analise = 'dados'

        # Tenta a análise de dados primeiro, se houver um contexto
        if contexto_analise:
            with st.spinner(f"Analisando no arquivo de '{contexto_analise}'..."):
                current_df = st.session_state[f"df_{contexto_analise}"]
                df_hash = pd.util.hash_pandas_object(current_df, index=True).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, contexto_analise)

                if erro == "PERGUNTA_INVALIDA":
                    # Se a IA julgar que não é sobre dados, anula o contexto para cair no chat geral
                    contexto_analise = None 
                elif erro:
                    st.error(erro)
                    response_text = "Desculpe, encontrei um erro ao tentar analisar sua pergunta nos dados."
                elif resultado_analise is not None:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da sua consulta nos dados de '{contexto_analise}':")
                        st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                    st.markdown(response_text)
        
        # Se não havia contexto para análise, ou a análise falhou, usa o chat geral
        if not contexto_analise and not response_text:
            with st.spinner("Pensando..."):
                try:
                    response = st.session_state.chat.send_message(prompt)
                    response_text = response.text
                    st.markdown(response_text)
                except Exception as e:
                    st.error(f"Ocorreu um erro na comunicação com a IA. Detalhe: {e}")
                    response_text = "Não consegui processar sua solicitação no momento."

    # Adiciona a resposta final ao histórico, evitando duplicatas
    if response_text:
        st.session_state.display_history.append({"role": "assistant", "content": response_text})
