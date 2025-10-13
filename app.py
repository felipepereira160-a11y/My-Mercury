import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Seu Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

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
    data_file = st.sidebar.file_uploader("1. Upload dos Dados do Dia (OS)", type=["csv", "xlsx"])
    if data_file:
        try:
            if data_file.name.endswith('.csv'):
                df = pd.read_csv(data_file, encoding='latin-1', sep=';', on_bad_lines='skip')
            else:
                df = pd.read_excel(data_file)
            st.session_state.df_dados = df
            st.success("Dados de OS carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    st.markdown("---")
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

# --- SEÇÃO DE DADOS DO DIA (COM DASHBOARD COMPLETO) ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço (Custo Zero)")
    df_dados = st.session_state.df_dados.copy()
    
    # Prepara a coluna de data para o filtro
    date_col = 'Data Agendamento'
    if date_col in df_dados.columns:
        df_dados[date_col] = pd.to_datetime(df_dados[date_col], errors='coerce')

    # Nomes de coluna corretos
    status_col = 'Status'
    rep_col_dados = 'Representante Técnico'
    city_col_dados = 'Cidade Agendamento'
    motivo_fechamento_col = 'Tipo de Fechamento'
    cliente_col = 'Cliente'

    st.subheader("Filtros Interativos")
    f_col1, f_col2, f_col3 = st.columns(3)
    
    status_options = sorted(df_dados[status_col].dropna().unique()) if status_col in df_dados.columns else []
    status_selecionado = f_col1.multiselect("Filtrar por Status:", options=status_options)
    
    rep_options = sorted(df_dados[rep_col_dados].dropna().unique()) if rep_col_dados in df_dados.columns else []
    rep_selecionado = f_col2.selectbox("Filtrar por Representante:", options=rep_options, index=None, placeholder="Selecione um RT")
    
    data_selecionada = f_col3.date_input("Filtrar por Data de Agendamento:", value=None)

    # Aplica os filtros
    filtered_df_dados = df_dados
    if status_selecionado:
        filtered_df_dados = filtered_df_dados[filtered_df_dados[status_col].isin(status_selecionado)]
    if rep_selecionado:
        filtered_df_dados = filtered_df_dados[filtered_df_dados[rep_col_dados] == rep_selecionado]
    if data_selecionada:
        filtered_df_dados = filtered_df_dados[filtered_df_dados[date_col].dt.date == data_selecionada]

    st.dataframe(filtered_df_dados)
    st.info(f"Mostrando {len(filtered_df_dados)} resultados.")

    st.subheader("Análises Gráficas (Baseado nos filtros)")
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        st.write("**Top Clientes com Visitas Improdutivas:**")
        if motivo_fechamento_col in filtered_df_dados.columns and cliente_col in filtered_df_dados.columns:
            improdutivas_df = filtered_df_dados[filtered_df_dados[motivo_fechamento_col] == 'Visita Improdutiva']
            if not improdutivas_df.empty:
                st.bar_chart(improdutivas_df[cliente_col].value_counts().nlargest(10))
            else:
                st.info("Nenhuma visita improdutiva encontrada nos dados filtrados.")
    
    with b_col2:
        st.write("**Análise de Motivos de Reagendamento:**")
        if status_col in filtered_df_dados.columns and motivo_fechamento_col in filtered_df_dados.columns:
            reagendamentos_df = filtered_df_dados[filtered_df_dados[status_col] == 'Reagendamento']
            if not reagendamentos_df.empty:
                st.bar_chart(reagendamentos_df[motivo_fechamento_col].value_counts())
            else:
                st.info("Nenhum reagendamento encontrado nos dados filtrados.")


# --- Seção de Mapeamento (Funcional) ---
if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.success("Base de conhecimento de Representantes está ativa.")
    df_map = st.session_state.df_mapeamento.copy()
    st.header("🔎 Ferramenta de Consulta Interativa (Custo Zero)")
    city_col_map, rep_col_map, lat_col, lon_col, km_col = 'nm_cidade_atendimento', 'nm_representante', 'cd_latitude_atendimento', 'cd_longitude_atendimento', 'qt_distancia_atendimento_km'
    
    if all(col in df_map.columns for col in [city_col_map, rep_col_map, lat_col, lon_col, km_col]):
        col1, col2 = st.columns(2)
        cidade_selecionada = col1.selectbox("Filtrar Mapeamento por Cidade:", options=sorted(df_map[city_col_map].dropna().unique()), index=None, placeholder="Selecione uma cidade")
        rep_selecionado_map = col2.selectbox("Filtrar Mapeamento por Representante:", options=sorted(df_map[rep_col_map].dropna().unique()), index=None, placeholder="Selecione um representante")

        filtered_df_map = df_map
        if cidade_selecionada:
            filtered_df_map = df_map[df_map[city_col_map] == cidade_selecionada]
        elif rep_selecionado_map:
            filtered_df_map = df_map[df_map[rep_col_map] == rep_selecionado_map]

        st.write("Resultados da busca:")
        ordem_colunas = [rep_col_map, city_col_map, km_col]
        outras_colunas = [col for col in filtered_df_map.columns if col not in ordem_colunas]
        nova_ordem = ordem_colunas + outras_colunas
        st.dataframe(filtered_df_map[nova_ordem])

        st.write("Visualização no Mapa:")
        map_data = filtered_df_map.rename(columns={lat_col: 'lat', lon_col: 'lon'})
        map_data['lat'] = pd.to_numeric(map_data['lat'], errors='coerce')
        map_data['lon'] = pd.to_numeric(map_data['lon'], errors='coerce')
        map_data.dropna(subset=['lat', 'lon'], inplace=True)
        
        map_data['size'] = 1000 if cidade_selecionada or rep_selecionado_map else 100
        if not map_data.empty:
            st.map(map_data, color='#FF4B4B', size='size')
        else:
            st.warning("Nenhum resultado com coordenadas válidas para exibir no mapa.")

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
