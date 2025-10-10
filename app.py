import streamlit as st
import google.generativeai as genai
import pandas as pd

# Configura o título da página e um ícone
st.set_page_config(page_title="Meu Chatbot com Gemini", page_icon="🤖")

# Título principal do aplicativo
st.title("Meu Chatbot Pessoal 🤖")

# --- Configuração da API Key ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error("Chave de API do Google não configurada. Por favor, adicione-a aos segredos do seu app no Streamlit.")
    st.stop()

# --- Upload e Processamento da Planilha ---
st.sidebar.header("Adicionar Conhecimento")
uploaded_file = st.sidebar.file_uploader("Faça o upload de um arquivo CSV", type=["csv"])

dataframe = None
if uploaded_file is not None:
    try:
        # Lê o arquivo CSV para um DataFrame do Pandas
        dataframe = pd.read_csv(uploaded_file)
        st.sidebar.success("Arquivo carregado com sucesso!")
        # Exibe as 5 primeiras linhas do arquivo na barra lateral
        st.sidebar.write("Pré-visualização dos Dados:")
        st.sidebar.dataframe(dataframe.head())
    except Exception as e:
        st.sidebar.error(f"Erro ao ler o arquivo: {e}")

# --- Inicialização do Modelo e do Chat ---
model = genai.GenerativeModel('gemini-pro-latest')
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

# --- Exibição do Histórico da Conversa ---
for message in st.session_state.chat.history:
    role = "assistant" if message.role == 'model' else message.role
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

# --- Entrada do Usuário ---
if prompt := st.chat_input("Digite sua mensagem..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Se um arquivo foi carregado, adicione o conteúdo dele ao prompt
    if dataframe is not None:
        contexto = dataframe.to_string()
        prompt_com_contexto = f"""
        Baseado nos seguintes dados de uma planilha:
        ---
        {contexto}
        ---
        Responda à seguinte pergunta: {prompt}
        """
        response = st.session_state.chat.send_message(prompt_com_contexto)
    else:
        # Se não houver arquivo, funciona como antes
        response = st.session_state.chat.send_message(prompt)

    with st.chat_message("assistant"):
        st.markdown(response.text)
