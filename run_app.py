import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import time
# A biblioteca para cálculo de distância está de volta!
from haversine import haversine, Unit

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Seu Assistente de Dados com IA")
st.write("Faça o upload de seus arquivos na barra lateral para começar a analisar!")

# --- Lógica para carregar a chave da API ---
api_key = None
api_key_status = "Não configurada"

try:
    api_key = st.secrets.get("GOOGLE_API_KEY")
    if api_key:
        api_key_status = "✔️ Carregada (Streamlit Secrets)"
except Exception:
    pass

if not api_key:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        api_key_status = "✔️ Carregada (Variável de Ambiente)"
    else:
        api_key_status = "❌ ERRO: Chave não encontrada."

# Exibe o status da chave de API na barra lateral para diagnóstico
st.sidebar.caption(f"**Status da Chave de API:** {api_key_status}")

model = None
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro-latest')
    except Exception as e:
        st.error(f"Erro ao configurar a API do Google: {e}")
        st.stop()
else:
    st.error("A chave da API do Google não foi encontrada. O aplicativo não pode funcionar.")
    st.stop()

# --- Inicialização do Estado da Sessão ---
if "chat" not in st.session_state and model:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções do Chat ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df_map = {'dados': st.session_state.df_dados, 'mapeamento': st.session_state.df_mapeamento}
    df = df_map.get(df_type)
    if df is None:
        return None, "O arquivo correspondente não foi carregado."

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
        response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        resposta_ia = response.text.strip().replace('`', '').replace('python', '')
        if resposta_ia == "PERGUNTA_INVALIDA":
            return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

# --- Barra Lateral ---
with st.sidebar:
    st.header("Upload de Arquivos")
    uploaded_dados = st.file_uploader("Carregar planilha de DADOS (.xlsx)", type="xlsx", key="dados_uploader")
    if uploaded_dados:
        st.session_state.df_dados = pd.read_excel(uploaded_dados)
        st.success("Arquivo de DADOS carregado!")

    uploaded_mapeamento = st.file_uploader("Carregar planilha de MAPEAMENTO (.xlsx)", type="xlsx", key="mapeamento_uploader")
    if uploaded_mapeamento:
        st.session_state.df_mapeamento = pd.read_excel(uploaded_mapeamento)
        st.success("Arquivo de MAPEAMENTO carregado!")

# --- Início do Corpo Principal ---

# --- OTIMIZADOR DE PROXIMIDADE (REINTEGRADO) ---
st.markdown("---")
st.header("📍 Otimizador de Proximidade")
st.write("Encontre o representante mais próximo com base nas coordenadas.")

if st.session_state.df_mapeamento is not None:
    # Assume que as colunas de coordenadas existem. Adapte se os nomes forem diferentes.
    # Verifica se as colunas necessárias existem
    if 'LATITUDE' in st.session_state.df_mapeamento.columns and 'LONGITUDE' in st.session_state.df_mapeamento.columns:
        col1, col2 = st.columns(2)
        with col1:
            lat_usr = st.number_input("Sua Latitude:", format="%.6f")
        with col2:
            lon_usr = st.number_input("Sua Longitude:", format="%.6f")

        if st.button("Encontrar Representante Mais Próximo"):
            ponto_usuario = (lat_usr, lon_usr)
            
            # Limpa dados inválidos
            df_temp = st.session_state.df_mapeamento.dropna(subset=['LATITUDE', 'LONGITUDE']).copy()

            # Calcula a distância para cada ponto
            df_temp['Distancia_KM'] = df_temp.apply(
                lambda row: haversine(ponto_usuario, (row['LATITUDE'], row['LONGITUDE']), unit=Unit.KILOMETERS),
                axis=1
            )
            
            # Encontra o índice do representante mais próximo
            idx_mais_proximo = df_temp['Distancia_KM'].idxmin()
            
            # Seleciona a linha inteira do representante
            representante_proximo = df_temp.loc[[idx_mais_proximo]]
            
            st.success("Busca finalizada!")
            st.write("Representante mais próximo encontrado:")
            st.dataframe(representante_proximo)
    else:
        st.error("O arquivo de mapeamento não contém as colunas 'LATITUDE' e 'LONGITUDE' necessárias.")
else:
    st.info("Por favor, carregue a planilha de 'MAPEAMENTO' na barra lateral para usar esta função.")


# --- Seção do Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA para análises personalizadas")

for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Faça uma pergunta sobre seus dados..."):
    st.session_state.display_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    df_type = None
    if st.session_state.df_dados is not None:
        df_type = 'dados'
    elif st.session_state.df_mapeamento is not None:
        df_type = 'mapeamento'

    with st.chat_message("assistant"):
        if df_type:
            with st.spinner(f"Analisando no arquivo de '{df_type}'..."):
                df_hash = pd.util.hash_pandas_object(st.session_state.get(f"df_{df_type}")).sum()
                resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)

                if erro == "PERGUNTA_INVALIDA":
                    response_text = "Desculpe, só posso responder a perguntas relacionadas aos dados da planilha carregada."
                elif erro:
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
            response_text = "Por favor, carregue uma planilha na barra lateral para que eu possa responder às suas perguntas."
            st.warning(response_text)

    st.session_state.display_history.append({"role": "assistant", "content": response_text})

