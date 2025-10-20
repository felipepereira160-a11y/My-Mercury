# ==============================================================================
# MERCÚRIO IA - CÓDIGO COMPLETO E OTIMIZADO
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

# --- Configuração da Página ---
st.set_page_config(page_title="Mercúrio IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral para iniciar a análise!")

# --- CONFIGURAÇÃO CENTRAL DO MODELO DE IA ---
# Para trocar o modelo (ex: para "gemini-1.5-flash-latest"), altere APENAS esta linha.
GEMINI_MODEL = "gemini-1.5-pro-latest"

# --- Lógica robusta para carregar a chave da API ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")

with st.sidebar:
    st.header("Configuração")
    if api_key:
        st.caption(f"✔️ Chave de API carregada.")
        st.caption(f"**Modelo de IA:** `{GEMINI_MODEL}`")
    else:
        st.caption("❌ ERRO: Chave de API não encontrada.")

# --- Inicialização do Modelo e Validação da API ---
model = None
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)
        # Testa a conexão fazendo uma chamada simples e barata
        model.generate_content("Teste", generation_config=genai.types.GenerationConfig(max_output_tokens=1))
    except Exception as e:
        st.error(f"Erro Crítico ao conectar com a API do Google. Verifique as permissões no Cloud.")
        st.error(f"Detalhe técnico: {e}")
        st.stop()
else:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state and model:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
# ... (demais inicializações de estado)
for key in ['df_dados', 'df_mapeamento', 'df_devolucao', 'df_pagamento']:
    if key not in st.session_state:
        st.session_state[key] = None

# --- Funções Auxiliares ---
@st.cache_data
def convert_df_to_csv(df):
    """Converte um DataFrame para CSV otimizado para Excel em português."""
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')

def safe_to_numeric(series):
    """Converte uma série para numérico de forma robusta."""
    if pd.api.types.is_string_dtype(series):
        series = series.str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    return pd.to_numeric(series, errors='coerce').fillna(0)

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    """Usa a IA para converter uma pergunta em código Pandas e executá-lo."""
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário sobre os dados.
    As colunas disponíveis no dataframe `df` são: {', '.join(df.columns)}.

    INSTRUÇÕES:
    1. Se a pergunta for genérica (ex: "quem descobriu o Brasil?"), responda APENAS com: "PERGUNTA_INVALIDA".
    2. Se a pergunta for sobre os dados, converta-a em uma ÚNICA linha de código Pandas que gere o resultado. O código não deve ter quebras de linha, acentos graves (`) ou a palavra 'python'.

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
            # Tenta com ';' primeiro, comum no Brasil
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
    
    # Dicionário para simplificar o upload
    arquivos_config = {
        'df_dados': ("1. Agendamentos (OS)", ';'),
        'df_mapeamento': ("2. Mapeamento de RT", ','),
        'df_devolucao': ("3. Itens a Instalar (Dev.)", ';'),
        'df_pagamento': ("4. Base de Pagamento (Duplic.)", ';')
    }

    for key, (label, sep) in arquivos_config.items():
        arquivo_upado = st.file_uploader(label, type=tipos_permitidos, key=f"upload_{key}")
        if arquivo_upado:
            st.session_state[key] = carregar_dataframe(arquivo_upado)
            if st.session_state[key] is not None:
                st.caption(f"✔️ {label.split('(')[0].strip()} carregado.")
        st.markdown("---")

    if st.button("🗑️ Limpar Tudo e Reiniciar"):
        st.session_state.clear()
        st.rerun()

# ==============================================================================
# --- Corpo Principal da Aplicação ---
# (O código para os módulos de análise permanece funcional)
# ==============================================================================

# --- [O CÓDIGO DOS SEUS MÓDULOS DE ANÁLISE VAI AQUI] ---
# (Dashboard, Analisador de Custos, Devolução, Mapeamento, Otimizador)
# Cole aqui os blocos `if st.session_state.df_dados is not None:`, etc.
# Eles não precisam de alteração.

# --- MÓDULO FINAL: CHAT COM A IA ---
st.markdown("---")
st.header("💬 Converse com a IA")

# Exibe o histórico do chat
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta sobre os dados ou converse comigo..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Determina o contexto da pergunta
    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    contexto = 'chat'
    if any(k in prompt.lower() for k in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        contexto = 'mapeamento'
    elif st.session_state.df_dados is not None:
        # Assume que qualquer outra pergunta pode ser sobre os dados principais, se carregados
        contexto = 'dados'
        
    with st.chat_message("assistant"):
        response_text = ""
        # Se há um contexto de dados, tenta a análise via Pandas
        if contexto in ['dados', 'mapeamento']:
            with st.spinner(f"Analisando nos dados de '{contexto}'..."):
                df_atual = st.session_state[f"df_{contexto}"]
                df_hash = pd.util.hash_pandas_object(df_atual, index=True).sum()
                resultado, erro = executar_analise_pandas(df_hash, prompt, contexto)

                if erro == "PERGUNTA_INVALIDA":
                    # A IA julgou que não é sobre os dados, então passa para o chat normal
                    contexto = 'chat' 
                elif erro:
                    st.error(erro)
                    response_text = "Desculpe, encontrei um erro ao tentar analisar sua pergunta nos dados."
                elif resultado is not None:
                    if isinstance(resultado, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da sua consulta nos dados de '{contexto}':")
                        st.dataframe(resultado)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado}**"
                    st.markdown(response_text)

        # Se o contexto é chat (ou falhou a análise de dados), usa a conversa normal
        if contexto == 'chat' and not response_text:
            with st.spinner("Pensando..."):
                try:
                    response = st.session_state.chat.send_message(prompt)
                    response_text = response.text
                    st.markdown(response_text)
                except Exception as e:
                    st.error(f"Ocorreu um erro na comunicação com a IA. Detalhe: {e}")
                    response_text = "Não consegui processar sua solicitação no momento."
    
    # Adiciona a resposta final ao histórico
    if response_text:
        st.session_state.display_history.append({"role": "assistant", "content": response_text})
