import streamlit as st
import google.generativeai as genai
import pandas as pd

# Configura o título da página e um ícone
st.set_page_config(page_title="Meu Chatbot Analista", page_icon="📊")

# Título principal do aplicativo
st.title("Meu Chatbot Analista de Dados 📊")

# --- Configuração da API Key ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error("Chave de API do Google não configurada. Por favor, adicione-a aos segredos do seu app no Streamlit.")
    st.stop()

# --- Upload e Processamento da Planilha ---
st.sidebar.header("Adicionar Conhecimento")
uploaded_file = st.sidebar.file_uploader("Faça o upload de um arquivo CSV", type=["csv"])

# Inicializa o dataframe na sessão para que persista
if 'dataframe' not in st.session_state:
    st.session_state.dataframe = None

if uploaded_file is not None:
    try:
        # Tenta ler o CSV com diferentes configurações
        st.session_state.dataframe = pd.read_csv(uploaded_file, encoding='latin-1', sep=';')
        st.sidebar.success("Arquivo carregado com sucesso!")
    except Exception as e:
        # Tenta ler com vírgula como separador se o ponto e vírgula falhar
        try:
            uploaded_file.seek(0) # Volta ao início do arquivo para tentar ler de novo
            st.session_state.dataframe = pd.read_csv(uploaded_file, encoding='latin-1', sep=',')
            st.sidebar.success("Arquivo carregado com sucesso!")
        except Exception as e2:
            st.sidebar.error(f"Erro ao ler o arquivo: {e2}")

if st.session_state.dataframe is not None:
    st.sidebar.write("Pré-visualização dos Dados:")
    st.sidebar.dataframe(st.session_state.dataframe.head())

# --- Inicialização do Modelo e do Chat ---
model = genai.GenerativeModel('gemini-pro-latest')
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

# --- Função para gerar e executar código Pandas ---
def executar_analise_pandas(df, pergunta):
    """Usa o Gemini para converter uma pergunta em código Pandas e executá-lo."""
    
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Sua tarefa é converter uma pergunta em uma única linha de código Pandas que a responda.
    O dataframe está na variável `df`.
    
    Aqui estão as primeiras linhas do dataframe para referência das colunas:
    {df.head().to_string()}
    
    Pergunta do usuário: "{pergunta}"
    
    Baseado na pergunta, gere apenas a linha de código Pandas necessária. Não use print(), não atribua a variáveis, apenas o comando.
    Exemplos:
    - Pergunta: "quantas linhas existem?" -> Resposta: df.shape[0]
    - Pergunta: "quais os valores únicos na coluna 'Cliente'?" -> Resposta: df['Cliente'].unique()
    - Pergunta: "filtre as linhas onde a cidade é 'São Paulo'" -> Resposta: df[df['Cidade'] == 'São Paulo']
    """
    
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        
        # --- AQUI ESTÁ A CORREÇÃO ---
        # Limpa o código recebido da IA antes de executar
        codigo_pandas = code_response.text.strip()
        codigo_pandas = codigo_pandas.replace('`', '')
        if codigo_pandas.lower().startswith('python'):
            codigo_pandas = codigo_pandas[6:].strip()
        
        st.info(f"Código Pandas gerado pela IA: `{codigo_pandas}`")
        
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

# --- Exibição do Histórico da Conversa ---
for message in st.session_state.chat.history:
    role = "assistant" if message.role == 'model' else message.role
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

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
            A seguinte pergunta foi feita sobre uma planilha: "{prompt}"
            Uma análise nos dados foi executada e o resultado foi:
            ---
            {resultado_analise}
            ---
            Com base nesse resultado, formule uma resposta amigável e clara para o usuário.
            """
            response = st.session_state.chat.send_message(prompt_final)
            response_text = response.text
    else:
        response = st.session_state.chat.send_message(prompt)
        response_text = response.text

    with st.chat_message("assistant"):
        st.markdown(response_text)
