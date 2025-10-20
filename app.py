# ==============================================================================
# MERCÚRIO IA - CÓDIGO FINAL UNIFICADO
# Versão: 5.0
# Modelo IA: Gemini 1.5 Pro Latest (Configuração Otimizada)
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
st.write("Faça o upload de seus arquivos na barra lateral para análises e converse com a IA!")

# --- CONFIGURAÇÃO CENTRAL DA API E MODELO ---
# CORREÇÃO: Usando o alias para o melhor modelo Pro disponível publicamente.
# Garante que você sempre use a versão mais poderosa e atual.
GEMINI_MODEL = "gemini-1.5-pro-latest"

# Carrega a chave da API de forma segura
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")

model = None
with st.sidebar:
    st.header("Configuração")
    if api_key:
        st.caption(f"✔️ Chave de API carregada.")
        st.caption(f"**Modelo de IA:** `{GEMINI_MODEL}`")
        # Adiciona a versão da biblioteca para facilitar o debug
        if 'google.generativeai' in globals():
            st.caption(f"**Versão da Lib:** `{genai.__version__}`")
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(GEMINI_MODEL)
        except Exception as e:
            st.error(f"Erro fatal na inicialização da API: {e}")
            st.stop()
    else:
        st.error("❌ Chave de API não encontrada. A aplicação não pode funcionar.")
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
INSTRUÇÕES:
1. Se a pergunta for genérica (ex: "quem descobriu o Brasil?"), responda APENAS com: "PERGUNTA_INVALIDA".
2. Se a pergunta for sobre os dados, converta-a em uma única linha de código Pandas que gere o resultado. O código não deve conter a palavra 'python' nem acentos graves (`).
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

# --- Barra Lateral (Sidebar) com Uploads ---
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
# --- Corpo Principal da Aplicação (MÓDULOS DE ANÁLISE) ---
# ==============================================================================

### COLE AQUI OS SEUS MÓDULOS COMPLETOS DE 1 A 5 ###
# (Dashboard, Duplicidade, Devolução, Mapeamento e Otimizador)

# Exemplo de como eles devem ser:
# if st.session_state.df_dados is not None:
#     ... seu código completo do Dashboard ...

# if st.session_state.df_pagamento is not None:
#     ... seu código completo do Analisador de Custos ...

# (e assim por diante para os outros módulos)

# ==============================================================================
# --- Módulo Final: Chat com a IA (UNIFICADO E FUNCIONAL) ---
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

    # Lógica para determinar o contexto da pergunta
    df_type = 'chat'
    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        # Se um arquivo de dados geral foi carregado, ele se torna o contexto padrão para análise
        df_type = 'dados'

    with st.chat_message("assistant"):
        response_text = ""
        # 1. Tenta a análise de dados primeiro, se houver um contexto apropriado
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
                current_df = st.session_state.get(f"df_{df_type}")
                df_hash = pd.util.hash_pandas_object(current_df).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
                
                # Se a IA julgar que não é sobre dados, muda o tipo para 'chat' para o fallback
                if erro == "PERGUNTA_INVALIDA":
                    df_type = 'chat'
                elif erro:
                    st.error(erro)
                    response_text = "Desculpe, não consegui analisar sua pergunta nos dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da busca na base de '{df_type}':")
                        st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                    st.markdown(response_text)
        
        # 2. Se o tipo for 'chat' (seja desde o início ou após o fallback), executa o chat conversacional
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
                    st.error(f"🚨 ERRO CRÍTICO NA COMUNICAÇÃO COM A API 🚨")
                    st.exception(e) # Exibe o erro completo para debug
                    response_text = "Falha na comunicação com a API. Verifique o erro detalhado acima."
    
    # Adiciona a resposta final ao histórico, evitando mensagens de erro vazias
    if response_text:
        st.session_state.display_history.append({"role": "assistant", "content": response_text})
