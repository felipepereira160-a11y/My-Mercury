import streamlit as st
import google.generativeai as genai
import os

# --- Configuração da página ---
st.set_page_config(page_title="Modelos Google Generative AI", layout="wide")
st.title("🔍 Modelos Disponíveis para sua Chave API")

# --- Carregar chave ---
api_key = st.text_input("Digite sua chave API do Google Generative AI", type="password")
if not api_key:
    st.warning("Insira a chave para continuar.")
    st.stop()

genai.configure(api_key=api_key)

# --- Listar modelos ---
st.header("Modelos Disponíveis")
try:
    modelos = genai.list_models()
    for modelo in modelos:
        st.markdown(f"**Nome:** `{modelo.name}`  \n**Métodos Disponíveis:** {', '.join(modelo.available_methods)}")
except Exception as e:
    st.error(f"Erro ao listar modelos: {e}")
