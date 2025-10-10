import streamlit as st
import google.generativeai as genai
import pandas as pd

# Configura o título da página, layout e um ícone
st.set_page_config(
    page_title="Seu Analista de Dados com IA",
    page_icon="📊",
    layout="wide"
)

# --- Título Principal ---
st.title("📊 Mercury EEEEEEEEO")
st.write("Converse comigo ou faça o upload de um arquivo na barra lateral para começar a analisar!")

# --- Configuração da API Key ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error("Chave de API do Google não configurada. Por favor, adicione-a aos segredos do seu app no Streamlit.")
    st.stop()

# --- Barra Lateral para Upload ---
with st.sidebar:
    st.header("Adicionar Conhecimento")
    uploaded_file = st.sidebar.file_uploader(
        "Faça o upload de um arquivo CSV ou XLSX", 
        type=["csv", "xlsx"]
    )

    if 'dataframe' not in st.session_state:
        st.session_state.dataframe = None

    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file, encoding='latin-1', sep=';', on_bad_lines='skip')
            elif uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file, engine='openpyxl')
            st.session_state.dataframe = df
            st.success("Arquivo carregado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
    
    if st.button("Limpar Arquivo e Chat"):
        st.session_state.dataframe = None
        st.session_state.chat = model.start_chat(history=[])
        st.rerun()

# --- Corpo Principal da Aplicação ---
model = genai.GenerativeModel('gemini-pro-latest')
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])

if st.session_state.dataframe is not None:
    df = st.session_state.dataframe
    st.header("Dashboard do Arquivo")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Linhas", f"{df.shape[0]:,}".replace(",", "."), "linhas")
    col2.metric("Total de Colunas", f"{df.shape[1]}", "colunas")
    coluna_cliente = next((col for col in df.columns if 'cliente' in col.lower()), None)
    if coluna_cliente:
        clientes_unicos = df[coluna_cliente].nunique()
        col3.metric("Clientes Únicos", f"{clientes_unicos}", "clientes")
    with st.expander("Clique aqui para ver a pré-visualização dos dados"):
        st.dataframe(df)
    st.header("Converse com seus Dados")

# Exibição do Histórico da Conversa
for message in st.session_state.chat.history:
    role = "assistant" if message.role == 'model' else message.role
    with st.chat_message(role):
        st.markdown(message.parts[0].text)

def executar_analise_pandas(df, pergunta):
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas. Sua tarefa é converter uma pergunta em uma única linha de código Pandas que a responda.
    O dataframe está na variável `df`.
    Aqui estão as primeiras linhas do dataframe: {df.head().to_string()}

    REGRAS DE EXECUÇÃO (SIGA EM ORDEM):
    1. PRIMEIRO, verifique se a pergunta exige um filtro na coluna 'Status'. As palavras-chave são "agendadas", "realizadas", "não realizadas", "reagendadas".
       - "agendadas" -> `df['Status'] == 'Agendada'`
       - "realizadas" -> `df['Status'] == 'Realizada'`
       - "não realizadas" -> `df['Status'] == 'Nao Realizada'`
       - "reagendadas" -> `df['Status'] == 'Reagendamento'`
    2. SEGUNDO, aplique a operação principal (contar, somar, agrupar, etc.) ao dataframe JÁ FILTRADO (se a regra 1 se aplicar).

    Pergunta do usuário: "{pergunta}"
    
    Baseado na pergunta e nas REGRAS, gere apenas a linha de código Pandas necessária.
    Exemplos:
    - Pergunta: "top 3 cidades com ordens realizadas" -> Resposta: df[df['Status'] == 'Realizada'].groupby('Cidade Agendamento').size().nlargest(3)
    - Pergunta: "qual a soma do valor de deslocamento para ordens não realizadas?" -> Resposta: df[df['Status'] == 'Nao Realizada']['Valor Deslocamento'].sum()
    """
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        codigo_pandas = code_response.text.strip().replace('`', '').replace('python', '').strip()
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

if prompt := st.chat_input("Converse com a IA ou faça uma pergunta sobre seus dados..."):
    # Exibe a mensagem do usuário imediatamente
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Decide qual modo usar: Analista de Dados ou Chatbot Geral
    if st.session_state.dataframe is not None:
        # --- Modo Analista de Dados ---
        resultado_analise, erro = executar_analise_pandas(st.session_state.dataframe, prompt)
        
        if erro:
            st.error(erro)
            response_text = "Desculpe, não consegui analisar os dados. Tente uma pergunta mais simples ou verifique o arquivo."
            # Exibe a resposta de erro
            with st.chat_message("assistant"):
                st.markdown(response_text)
            # Adiciona ao histórico para não sumir
            st.session_state.chat.history.append({'role': 'user', 'parts': [{'text': prompt}]})
            st.session_state.chat.history.append({'role': 'assistant', 'parts': [{'text': response_text}]})
        else:
            # Resposta com base na análise
            response_container = st.chat_message("assistant")
            with response_container:
                if isinstance(resultado_analise, (pd.Series, pd.DataFrame)) and len(resultado_analise) > 1:
                    st.write("Aqui está uma visualização para sua pergunta:")
                    st.bar_chart(resultado_analise)
                    prompt_final = f"""A pergunta do usuário foi: "{prompt}". Para responder, um gráfico de barras já foi exibido na tela. Os dados são: {resultado_analise.to_string()}. Sua tarefa é escrever uma breve análise do gráfico. Não liste os dados novamente."""
                else:
                    prompt_final = f"""A pergunta foi: "{prompt}". O resultado da análise dos dados foi: {resultado_analise}. Com base nesse resultado, formule uma resposta amigável e direta."""
                
                response = st.session_state.chat.send_message([prompt, response_container.markdown(f"Analisando os dados...")])
                response_text = response.text
                response_container.markdown(response_text)
    else:
        # --- Modo Chatbot Geral (CORREÇÃO) ---
        # Se nenhum arquivo for carregado, apenas converse normalmente
        response = st.session_state.chat.send_message(prompt)
        response_text = response.text
        with st.chat_message("assistant"):
            st.markdown(response_text)
