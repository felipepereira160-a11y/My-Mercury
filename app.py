import streamlit as st
import google.generativeai as genai

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

# --- Inicialização do Modelo e do Chat ---
# Usando o nome de modelo correto e estável para seu plano
model = genai.GenerativeModel('gemini-pro-latest')

# Inicializa o histórico do chat na sessão do Streamlit
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

    response = st.session_state.chat.send_message(prompt)

    with st.chat_message("assistant"):
        st.markdown(response.text)
