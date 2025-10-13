import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Dashboard de Análise com IA", page_icon="📈", layout="wide")

# --- Título ---
st.title("📈 Seu Dashboard de Análise com IA")
st.write("Faça o upload de seus arquivos na barra lateral. O dashboard será gerado automaticamente!")

# --- Configuração da API e do Modelo ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-pro-latest')
except Exception as e:
    st.error("Chave de API do Google não configurada ou inválida.")
    st.stop()

# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções de Análise (com cache para economia) ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    contexto = "analisar dados de ordens de serviço." if df_type == 'dados' else "buscar informações sobre representantes."
    time.sleep(1)
    prompt_engenharia = f"""
    Sua tarefa é converter uma pergunta em uma única linha de código Pandas para {contexto}
    O dataframe é `df`. As colunas são: {', '.join(df.columns)}.
    Pergunta: "{pergunta}"
    Gere apenas a linha de código Pandas.
    """
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        codigo_pandas = code_response.text.strip().replace('`', '').replace('python', '').strip()
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    # Uploader para os dados do dia a dia
    data_file = st.sidebar.file_uploader("1. Upload dos Dados do Dia (Ordens de Serviço)", type=["csv", "xlsx"])
    if data_file:
        try:
            if data_file.name.endswith('.csv'):
                # Tenta ler com ';' e se falhar (ou gerar 1 coluna), tenta com ','
                try:
                    df = pd.read_csv(data_file, encoding='latin-1', sep=';', on_bad_lines='skip')
                    if len(df.columns) <= 1:
                        data_file.seek(0)
                        df = pd.read_csv(data_file, encoding='latin-1', sep=',', on_bad_lines='skip')
                except Exception:
                    data_file.seek(0)
                    df = pd.read_csv(data_file, encoding='latin-1', sep=',', on_bad_lines='skip')
            else:
                df = pd.read_excel(data_file)
            st.session_state.df_dados = df
            st.success("Dados de OS carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")
    
    st.markdown("---")
    # Uploader para o mapeamento fixo
    map_file = st.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=["csv", "xlsx"])
    if map_file:
        try:
            if map_file.name.endswith('.csv'):
                 df = pd.read_csv(map_file, encoding='latin-1', sep=',')
            else:
                df = pd.read_excel(map_file)
            st.session_state.df_mapeamento = df
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Corpo Principal ---

# --- DASHBOARD AUTOMÁTICO DE CUSTO ZERO (CORRIGIDO) ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço (Custo Zero)")
    
    df = st.session_state.df_dados
    
    # --- Detecção dinâmica de colunas para robustez ---
    status_col = next((col for col in df.columns if 'status' in col.lower()), None)
    rep_col_dados = next((col for col in df.columns if 'representante técnico' in col.lower()), None)
    city_col_dados = next((col for col in df.columns if 'cidade agendamento' in col.lower()), None)
    submotivo_col = next((col for col in df.columns if 'sub motivo fechamento' in col.lower()), None)
    
    # --- Métricas Principais ---
    st.subheader("Visão Geral")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Ordens na Planilha", f"{df.shape[0]:,}".replace(",", "."))
    
    if status_col:
        agendadas_count = df[df[status_col] == 'Agendada'].shape[0]
        col2.metric("Total de Ordens Agendadas", f"{agendadas_count:,}".replace(",", "."))
    else:
        col2.metric("Total de Ordens Agendadas", "N/A")
        
    if rep_col_dados:
        col3.metric("Representantes Únicos", f"{df[rep_col_dados].nunique():,}".replace(",", "."))
    else:
        col3.metric("Representantes Únicos", "N/A")

    if city_col_dados:
        col4.metric("Cidades Únicas", f"{df[city_col_dados].nunique():,}".replace(",", "."))
    else:
        col4.metric("Cidades Únicas", "N/A")
    
    st.markdown("---")

    # --- Gráficos Principais ---
    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        st.subheader("Contagem por Status de Ordem")
        if status_col:
            st.bar_chart(df[status_col].value_counts())
        else:
            st.warning("Coluna 'Status' não encontrada.")

        st.subheader("Top 10 Representantes com Mais Ordens")
        if rep_col_dados:
            st.bar_chart(df[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Coluna 'Representante Técnico' não encontrada.")

    with col_graf2:
        st.subheader("Contagem por Sub-Motivo de Fechamento")
        if submotivo_col:
            st.bar_chart(df[submotivo_col].dropna().value_counts())
        else:
            st.warning("Coluna 'Sub Motivo Fechamento' não encontrada.")

        st.subheader("Top 10 Cidades com Mais Ordens")
        if city_col_dados:
            st.bar_chart(df[city_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Coluna 'Cidade Agendamento' não encontrada.")

    with st.expander("Clique para ver a tabela de dados completa"):
        st.dataframe(df)

# --- Seção do Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA para análises personalizadas")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta específica..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    keywords_mapeamento = ["quem atende", "representante de", "contato do rt", "telefone de", "rt para", "mapeamento"]
    df_type = 'chat'
    if any(keyword in prompt.lower() for keyword in keywords_mapeamento) and st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'
    elif st.session_state.df_dados is not None:
        df_type = 'dados'

    with st.chat_message("assistant"):
        if df_type in ['mapeamento', 'dados']:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
                df_hash = pd.util.hash_pandas_object(st.session_state.get(f"df_{df_type}")).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
                if erro:
                    st.error(erro)
                    response_text = "Desculpe, não consegui analisar os dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da busca na base de '{df_type}':")
                        st.dataframe(resultado_analise)
                        response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                st.markdown(response_text)
        else:
            with st.spinner("Pensando..."):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
    
    st.session_state.display_history.append({"role": "assistant", "content": response_text})
