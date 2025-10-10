import streamlit as st
import google.generativeai as genai
import pandas as pd

# Configura o título da página, layout e um ícone
st.set_page_config(
    page_title="Seu Analista de Dados com IA",
    page_icon="📊",
    layout="wide"  # Usa a largura total da página
)

# --- Título Principal ---
st.title("📊 Seu Analista de Dados com IA")
st.write("Faça o upload de um arquivo CSV na barra lateral e comece a fazer perguntas!")

# --- Configuração da API Key ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error("Chave de API do Google não configurada. Por favor, adicione-a aos segredos do seu app no Streamlit.")
    st.stop()

# --- Barra Lateral para Upload ---
with st.sidebar:
    st.header("Adicionar Conhecimento")
    uploaded_file = st.sidebar.file_uploader("Faça o upload de um arquivo CSV", type=["csv"])

    if 'dataframe' not in st.session_state:
        st.session_state.dataframe = None

    if uploaded_file is not None:
        try:
            # Tenta ler o CSV com diferentes configurações
            st.session_state.dataframe = pd.read_csv(uploaded_file, encoding='latin-1', sep=';')
            st.success("Arquivo carregado com sucesso!")
        except Exception:
            try:
                uploaded_file.seek(0)
                st.session_state.dataframe = pd.read_csv(uploaded_file, encoding='latin-1', sep=',')
                st.success("Arquivo carregado com sucesso!")
            except Exception as e2:
                st.error(f"Erro ao ler o arquivo: {e2}")
    
    # Adiciona um botão para limpar o arquivo e o chat
    if st.button("Limpar Arquivo e Chat"):
        st.session_state.dataframe = None
        st.session_state.chat = model.start_chat(history=[])
        st.rerun()

# --- Corpo Principal da Aplicação ---
# Inicialização do Modelo e do Chat
model = genai.GenerativeModel('gemini-pro-latest')
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

# Se um arquivo foi carregado, mostra o dashboard e o chat
if st.session_state.dataframe is not None:
    df = st.session_state.dataframe
    
    st.header("Dashboard do Arquivo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Linhas", f"{df.shape[0]:,}".replace(",", "."), "linhas")
    col2.metric("Total de Colunas", f"{df.shape[1]}", "colunas")
    
    # Calcula o número de clientes únicos, se a coluna existir
    if 'ClienteNome' in df.columns:
        clientes_unicos = df['ClienteNome'].nunique()
        col3.metric("Clientes Únicos", f"{clientes_unicos}", "clientes")
    
    with st.expander("Clique aqui para ver a pré-visualização dos dados"):
        st.dataframe(df)
    
    st.header("Converse com seus Dados")

# Exibição do Histórico da Conversa
for message in st.session_state.chat.history:
    role = "assistant" if message.role == 'model' else message.role
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

# --- Função para gerar e executar código Pandas ---
def executar_analise_pandas(df, pergunta):
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Sua tarefa é converter uma pergunta em uma única linha de código Pandas que a responda.
    O dataframe está na variável `df`.
    Aqui estão as primeiras linhas do dataframe para referência das colunas: {df.head().to_string()}
    Pergunta do usuário: "{pergunta}"
    Baseado na pergunta, gere apenas a linha de código Pandas necessária.
    """
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        codigo_pandas = code_response.text.strip().replace('`', '').replace('python', '').strip()
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

# --- Entrada do Usuário ---
if prompt := st.chat_input("Faça uma pergunta sobre seus dados..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    
    if st.session_state.dataframe is not None:
        resultado_analise, erro = executar_analise_pandas(st.session_state.dataframe, prompt)
        
        if erro:
            st.error(erro)
            response_text = "Desculpe, não consegui analisar os dados. Tente uma pergunta mais simples ou verifique o arquivo."
        else:
            prompt_final = f"""
            A pergunta foi: "{prompt}"
            O resultado da análise dos dados foi: {resultado_analise}
            Com base nesse resultado, formule uma resposta amigável, direta e clara para o usuário.
            """
            response = st.session_state.chat.send_message(prompt_final)
            response_text = response.text
    else:
        response_text = "Por favor, carregue um arquivo CSV na barra lateral para começar a análise."

    with st.chat_message("assistant"):
        st.markdown(response_text)
