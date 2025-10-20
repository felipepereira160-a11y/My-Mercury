import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import os
from datetime import datetime
from haversine import haversine, Unit

# ============================================================
# CONFIGURAÇÃO GERAL DO APP
# ============================================================
st.set_page_config(page_title="Mercúrio IA", page_icon="🧠", layout="wide")
st.title("🧠 Mercúrio IA")
st.write("Faça o upload de seus arquivos na barra lateral e converse com a IA!")

# ------------------------------------------------------------
# CONFIGURAÇÃO DA CHAVE DE API
# ------------------------------------------------------------
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
api_key_status = "✔️ Carregada" if api_key else "❌ ERRO: Chave não encontrada."
# --- Configuração do modelo atualizado ---
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5')  # Versão atualizada da API
    except Exception as e:
        st.error(f"Erro ao configurar a API do Google: {e}")
        st.stop()
else:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

# --- Inicialização do estado do chat ---
if "chat" not in st.session_state and model:
    st.session_state.chat = model.start_chat()  # start_chat() continua válido

# --- Função de análise de Pandas atualizada ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    prompt_engenharia = f"""
Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário.
As colunas disponíveis no dataframe `df` são: {', '.join(df.columns)}.

INSTRUÇÕES:
1. Determine se a pergunta do usuário PODE ser respondida usando os dados.
2. Se a pergunta for genérica (ex: "quem descobriu o Brasil?"), responda APENAS com: "PERGUNTA_INVALIDA".
3. Se a pergunta for sobre os dados, converta-a em uma única linha de código Pandas que gere o resultado.

Pergunta: "{pergunta}"
Sua resposta:
"""
    try:
        response = model.generate_text(input=prompt_engenharia, max_output_tokens=800)
        resposta_ia = response.output_text.strip().replace('`', '').replace('python', '')
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        # Avaliando a resposta com segurança
        resultado = eval(resposta_ia, {'df': df, 'pd': pd, 'np': np})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"


# ============================================================
# CHAT INTERATIVO MERCÚRIO IA
# ============================================================
st.markdown("---")
st.header("💬 Chat com o Assistente Mercúrio IA")

# Exibir histórico do chat
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
                df = st.session_state.df_dados or st.session_state.df_mapeamento
                if df is not None:
                    resposta_final = executar_analise(prompt, df)
                else:
                    resposta_final = "Nenhum arquivo foi carregado ainda para análise de dados."
            else:
                resposta = st.session_state.model.generate_content(prompt)
                resposta_final = resposta.text.strip()

            st.markdown(resposta_final)

    st.session_state.chat_history.append({"role": "assistant", "content": resposta_final})
