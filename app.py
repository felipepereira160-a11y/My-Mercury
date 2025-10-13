import streamlit as st
import google.generativeai as genai
import pandas as pd
from haversine import haversine, Unit
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
    data_file = st.sidebar.file_uploader("1. Upload de Agendamentos (OS)", type=["csv", "xlsx"])
    if data_file:
        try:
            if data_file.name.endswith('.csv'):
                df = pd.read_csv(data_file, encoding='latin-1', sep=';', on_bad_lines='skip')
            else:
                df = pd.read_excel(data_file)
            st.session_state.df_dados = df
            st.success("Agendamentos carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    st.markdown("---")
    map_file = st.sidebar.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=["csv", "xlsx"])
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

# --- OTIMIZADOR DE PROXIMIDADE ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.header("🚚 Otimizador de Proximidade de RT (Custo Zero)")
    
    df_dados = st.session_state.df_dados
    df_map = st.session_state.df_mapeamento
    
    os_city_col = 'Cidade Agendamento'
    os_rep_col = 'Representante Técnico'
    os_status_col = 'Status'
    
    map_city_col = 'nm_cidade_atendimento'
    map_lat_atendimento_col = 'cd_latitude_atendimento'
    map_lon_atendimento_col = 'cd_longitude_atendimento'
    map_rep_col = 'nm_representante'
    map_rep_lat_col = 'cd_latitude_representante'
    map_rep_lon_col = 'cd_longitude_representante'

    if not all(col in df_dados.columns for col in [os_city_col, os_rep_col, os_status_col]):
        st.warning(f"Para usar o otimizador, a planilha de agendamentos precisa ter as colunas essenciais (Cidade Agendamento, Representante Técnico, Status).")
    elif not all(col in df_map.columns for col in [map_city_col, map_lat_atendimento_col, map_lon_atendimento_col, map_rep_col, map_rep_lat_col, map_rep_lon_col]):
        st.warning(f"Para usar o otimizador, a planilha de mapeamento precisa ter todas as colunas de cidade e coordenadas.")
    else:
        df_agendadas = df_dados[df_dados[os_status_col] == 'Agendada'].copy()
        
        if df_agendadas.empty:
            st.info("Nenhuma ordem com o status 'Agendada' foi encontrada na planilha de dados para otimização.")
        else:
            lista_cidades_agendadas = sorted(df_agendadas[os_city_col].dropna().unique())
            cidade_selecionada = st.selectbox("Selecione uma cidade com agendamentos para otimizar:", options=lista_cidades_agendadas, index=None, placeholder="Escolha uma cidade")

            if cidade_selecionada:
                ordem_selecionada = df_agendadas[df_agendadas[os_city_col] == cidade_selecionada].iloc[0]
                rt_atual = ordem_selecionada[os_rep_col]
                
                cidade_info = df_map[df_map[map_city_col] == cidade_selecionada]
                if cidade_info.empty:
                    st.error(f"Não foi possível encontrar as coordenadas para a cidade '{cidade_selecionada}' na sua planilha de Mapeamento.")
                else:
                    ponto_atendimento = (cidade_info.iloc[0][map_lat_atendimento_col], cidade_info.iloc[0][map_lon_atendimento_col])

                    distancias = []
                    for _, rt_map in df_map.iterrows():
                        ponto_base_rt = (rt_map[map_rep_lat_col], rt_map[map_rep_lon_col])
                        distancia = haversine(ponto_base_rt, ponto_atendimento, unit=Unit.KILOMETERS)
                        distancias.append({'Representante': rt_map[map_rep_col], 'Distancia (km)': distancia})
                    
                    df_distancias = pd.DataFrame(distancias).drop_duplicates(subset=['Representante']).reset_index(drop=True)
                    rt_sugerido = df_distancias.loc[df_distancias['Distancia (km)'].idxmin()]
                    
                    st.subheader(f"Análise de Proximidade para: {cidade_selecionada}")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**RT Atualmente Agendado:** {rt_atual}")
                        dist_atual_df = df_distancias[df_distancias['Representante'] == rt_atual]
                        if not dist_atual_df.empty:
                            dist_atual = dist_atual_df['Distancia (km)'].values[0]
                            st.metric("Distância do RT Agendado", f"{dist_atual:.1f} km")
                        else:
                            st.warning(f"O RT '{rt_atual}' não foi encontrado no arquivo de Mapeamento.")
                            dist_atual = float('inf')

                    with col2:
                        st.success(f"**Sugestão de RT Mais Próximo:** {rt_sugerido['Representante']}")
                        economia = dist_atual - rt_sugerido['Distancia (km)']
                        st.metric("Distância do RT Sugerido", f"{rt_sugerido['Distancia (km)']:.1f} km", delta=f"{economia:.1f} km de economia" if economia > 0 and economia != float('inf') else None)

# --- Seção de Mapeamento (Funcional) ---
if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.success("Base de conhecimento de Representantes está ativa.")
    df_map = st.session_state.df_mapeamento.copy()
    st.header("🔎 Ferramenta de Consulta Interativa (Custo Zero)")
    city_col_map, rep_col_map, lat_col, lon_col, km_col = 'nm_cidade_atendimento', 'nm_representante', 'cd_latitude_atendimento', 'cd_longitude_atendimento', 'qt_distancia_atendimento_km'
    
    if all(col in df_map.columns for col in [city_col_map, rep_col_map, lat_col, lon_col, km_col]):
        col1, col2 = st.columns(2)
        cidade_selecionada_map = col1.selectbox("Filtrar Mapeamento por Cidade:", options=sorted(df_map[city_col_map].dropna().unique()), index=None, placeholder="Selecione uma cidade")
        rep_selecionado_map = col2.selectbox("Filtrar Mapeamento por Representante:", options=sorted(df_map[rep_col_map].dropna().unique()), index=None, placeholder="Selecione um representante")

        filtered_df_map = df_map
        if cidade_selecionada_map:
            filtered_df_map = df_map[df_map[city_col_map] == cidade_selecionada_map]
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
        
        map_data['size'] = 1000 if cidade_selecionada_map or rep_selecionado_map else 100
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
