import streamlit as st
import google.generativeai as genai
import pandas as pd
from haversine import haversine, Unit
import time
import os
import subprocess

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Seu Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

# --- Configuração da API e do Modelo ---
try:
    # Tenta obter a chave da API dos segredos do Streamlit (para deploy na nuvem)
    api_key = st.secrets["GOOGLE_API_KEY"]
except (FileNotFoundError, KeyError):
    # Fallback para variável de ambiente (para execução local)
    api_key = os.environ.get("GOOGLE_API_KEY")

if not api_key:
    st.error("Chave de API do Google não configurada. Por favor, configure-a nos segredos do Streamlit ou como uma variável de ambiente (GOOGLE_API_KEY).")
    st.stop()

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-1.5-flash-latest') # Usando um modelo mais recente


# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    """
    Executa uma análise em um DataFrame do pandas usando um modelo generativo para criar o código.
    """
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    
    # --- MELHORIA: PROMPT MAIS INTELIGENTE ---
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Sua tarefa é analisar a pergunta do usuário.
    As colunas disponíveis no dataframe `df` são: {', '.join(df.columns)}.
    
    INSTRUÇÕES:
    1. Primeiro, determine se a pergunta do usuário PODE ser respondida usando os dados deste dataframe.
    2. Se a pergunta for genérica ou sobre um tópico não relacionado aos dados (ex: "quem descobriu o Brasil?"), responda APENAS com a palavra: "PERGUNTA_INVALIDA".
    3. Se a pergunta PUDER ser respondida com os dados, converta-a em uma única linha de código Pandas que gere o resultado. O código não deve ter quebras de linha.

    Pergunta do usuário: "{pergunta}"
    Sua resposta (apenas o código ou a palavra-chave):
    """
    
    try:
        code_response = genai.GenerativeModel('gemini-1.5-flash-latest').generate_content(prompt_engenharia)
        resposta_ia = code_response.text.strip()
        
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        else:
            codigo_pandas = resposta_ia.replace('`', '').replace('python', '').strip()
            # Usando um ambiente seguro para avaliação
            resultado = eval(codigo_pandas, {'df': df, 'pd': pd, 'haversine': haversine, 'Unit': Unit})
            return resultado, None
            
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}. Código tentado: {codigo_pandas}"

# --- Barra Lateral ---
with st.sidebar:
    st.header("Upload de Arquivos")
    st.write("Por favor, faça o upload dos seus arquivos .csv ou .xlsx aqui.")
    
    uploaded_file_dados = st.file_uploader("Arquivo de Dados (ex: Ordens de Serviço)", type=['csv', 'xlsx'])
    if uploaded_file_dados:
        try:
            if uploaded_file_dados.name.endswith('.csv'):
                st.session_state.df_dados = pd.read_csv(uploaded_file_dados)
            else:
                st.session_state.df_dados = pd.read_excel(uploaded_file_dados)
            st.success("Arquivo de Dados carregado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao ler o arquivo de dados: {e}")

    uploaded_file_mapeamento = st.file_uploader("Arquivo de Mapeamento (ex: RTs)", type=['csv', 'xlsx'])
    if uploaded_file_mapeamento:
        try:
            if uploaded_file_mapeamento.name.endswith('.csv'):
                st.session_state.df_mapeamento = pd.read_csv(uploaded_file_mapeamento)
            else:
                st.session_state.df_mapeamento = pd.read_excel(uploaded_file_mapeamento)
            st.success("Arquivo de Mapeamento carregado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao ler o arquivo de mapeamento: {e}")
            
    st.markdown("---")
    st.info("Este aplicativo usa IA para analisar dados. Os resultados podem não ser 100% precisos.")


# --- Seção do Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA para análises personalizadas")

# Exibe o histórico do chat
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Campo de entrada do usuário
if prompt := st.chat_input("Faça uma pergunta sobre seus dados..."):
    # Adiciona e exibe a mensagem do usuário
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Determina qual dataframe usar
    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    df_type = None
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        df_type = 'dados'
    
    # Gera e exibe a resposta do assistente
    with st.chat_message("assistant"):
        response_text = ""
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
                df_to_use = st.session_state.get(f"df_{df_type}")
                df_hash = pd.util.hash_pandas_object(df_to_use).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
                
                if erro == "PERGUNTA_INVALIDA":
                    response_text = "Desculpe, só posso responder a perguntas relacionadas aos dados da planilha carregada."
                elif erro:
                    st.error(erro)
                    response_text = "Desculpe, não consegui analisar os dados. Verifique se sua pergunta é clara."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da busca na base de '{df_type}':")
                        st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                st.markdown(response_text)
        else: # Se nenhum dataframe estiver carregado
             with st.spinner("Pensando..."):
                try:
                    response = st.session_state.chat.send_message(prompt)
                    response_text = response.text
                except Exception as e:
                    response_text = f"Ocorreu um erro ao contatar a IA: {e}"
                st.markdown(response_text)
    
    st.session_state.display_history.append({"role": "assistant", "content": response_text})
