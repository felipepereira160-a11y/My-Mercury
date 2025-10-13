import streamlit as st
import google-generativeai as genai
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

# --- Funções ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    contexto = "analisar dados de ordens de serviço." if df_type == 'dados' else "buscar informações sobre representantes."
    time.sleep(1)
    prompt_engenharia = f"""
    Sua tarefa é converter uma pergunta em uma única linha de código Pandas para {contexto}
    O dataframe é `df`. As colunas são: {', '.join(df.columns)}. Pergunta: "{pergunta}". Gere apenas a linha de código Pandas.
    """
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        codigo_pandas = code_response.text.strip().replace('`', '').replace('python', '').strip()
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

def carregar_dataframe(arquivo):
    """Lê um arquivo CSV ou XLSX de forma robusta."""
    if arquivo.name.endswith('.csv'):
        try: # Tenta com ponto e vírgula
            df = pd.read_csv(arquivo, encoding='latin-1', sep=';', on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except Exception:
            pass
        arquivo.seek(0)
        try: # Tenta com vírgula
            df = pd.read_csv(arquivo, encoding='latin-1', sep=',', on_bad_lines='skip')
            return df
        except Exception as e:
            raise e
    elif arquivo.name.endswith('.xlsx'):
        return pd.read_excel(arquivo)
    return None

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    data_file = st.sidebar.file_uploader("1. Upload de Agendamentos (OS)", type=["csv", "xlsx"])
    if data_file:
        try:
            st.session_state.df_dados = carregar_dataframe(data_file)
            st.success("Agendamentos carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    st.markdown("---")
    map_file = st.sidebar.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=["csv", "xlsx"])
    if map_file:
        try:
            st.session_state.df_mapeamento = carregar_dataframe(map_file)
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Corpo Principal ---

# --- OTIMIZADOR DE PROXIMIDADE (VERSÃO APRIMORADA) ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    with st.expander("🚚 Abrir Otimizador de Proximidade de RT", expanded=True):
        df_dados = st.session_state.df_dados; df_map = st.session_state.df_mapeamento
        
        # Detecção dinâmica de colunas
        os_id_col = next((col for col in df_dados.columns if 'número da o.s' in col.lower() or 'numeropedido' in col.lower()), None)
        os_cliente_col = next((col for col in df_dados.columns if 'cliente' in col.lower() and 'id' not in col.lower()), None)
        os_date_col = next((col for col in df_dados.columns if 'data agendamento' in col.lower()), None)
        os_city_col = next((col for col in df_dados.columns if 'cidade agendamento' in col.lower()), None)
        os_rep_col = next((col for col in df_dados.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()), None)
        os_status_col = next((col for col in df_dados.columns if 'status' in col.lower()), None)
        map_city_col = next((col for col in df_map.columns if 'nm_cidade_atendimento' in col.lower()), None)
        map_lat_atendimento_col = next((col for col in df_map.columns if 'cd_latitude_atendimento' in col.lower()), None)
        map_lon_atendimento_col = next((col for col in df_map.columns if 'cd_longitude_atendimento' in col.lower()), None)
        map_rep_col = next((col for col in df_map.columns if 'nm_representante' in col.lower()), None)
        map_rep_lat_col = next((col for col in df_map.columns if 'cd_latitude_representante' in col.lower()), None)
        map_rep_lon_col = next((col for col in df_map.columns if 'cd_longitude_representante' in col.lower()), None)

        required_cols = [os_id_col, os_cliente_col, os_date_col, os_city_col, os_rep_col, os_status_col, map_city_col, map_lat_atendimento_col, map_lon_atendimento_col, map_rep_col, map_rep_lat_col, map_rep_lon_col]

        if not all(required_cols):
            st.warning("Para usar o otimizador, ambas as planilhas devem ser carregadas e conter todas as colunas necessárias.")
        else:
            df_agendadas = df_dados[df_dados[os_status_col] == 'Agendada'].copy()
            if df_agendadas.empty:
                st.info("Nenhuma ordem com o status 'Agendada' foi encontrada para otimização.")
            else:
                lista_cidades_agendadas = sorted(df_agendadas[os_city_col].dropna().unique())
                cidade_selecionada = st.selectbox("Selecione uma cidade com agendamentos para otimizar:", options=lista_cidades_agendadas, index=None, placeholder="Escolha uma cidade")
                if cidade_selecionada:
                    ordens_na_cidade = df_agendadas[df_agendadas[os_city_col] == cidade_selecionada]
                    st.subheader(f"Ordens 'Agendadas' em {cidade_selecionada}:")
                    st.dataframe(ordens_na_cidade[[os_id_col, os_cliente_col, os_date_col, os_rep_col]])
                    
                    st.subheader(f"Análise de Proximidade para cada Ordem:")
                    cidade_info = df_map[df_map[map_city_col] == cidade_selecionada]
                    if cidade_info.empty:
                        st.error(f"Coordenadas para '{cidade_selecionada}' não encontradas no Mapeamento.")
                    else:
                        ponto_atendimento = (cidade_info.iloc[0][map_lat_atendimento_col], cidade_info.iloc[0][map_lon_atendimento_col])
                        distancias = [{'Representante': rt_map[map_rep_col], 'Distancia (km)': haversine((rt_map[map_rep_lat_col], rt_map[map_rep_lon_col]), ponto_atendimento, unit=Unit.KILOMETERS)} for _, rt_map in df_map.iterrows()]
                        df_distancias = pd.DataFrame(distancias).drop_duplicates(subset=['Representante']).reset_index(drop=True)
                        rt_sugerido = df_distancias.loc[df_distancias['Distancia (km)'].idxmin()]
                        
                        for index, ordem in ordens_na_cidade.iterrows():
                            rt_atual = ordem[os_rep_col]
                            with st.expander(f"**OS: {ordem[os_id_col]}** | Cliente: {ordem[os_cliente_col]}"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.info(f"**RT Agendado:** {rt_atual}")
                                    dist_atual_df = df_distancias[df_distancias['Representante'] == rt_atual]
                                    if not dist_atual_df.empty:
                                        dist_atual = dist_atual_df['Distancia (km)'].values[0]
                                        st.metric("Distância do RT Agendado", f"{dist_atual:.1f} km")
                                    else:
                                        st.warning(f"O RT '{rt_atual}' não foi encontrado no Mapeamento."); dist_atual = float('inf')
                                with col2:
                                    st.success(f"**Sugestão (Mais Próximo):** {rt_sugerido['Representante']}")
                                    economia = dist_atual - rt_sugerido['Distancia (km)']
                                    st.metric("Distância do RT Sugerido", f"{rt_sugerido['Distancia (km)']:.1f} km", delta=f"{economia:.1f} km de economia" if economia > 0 and economia != float('inf') else None)

# --- Seção de Mapeamento (Funcional) ---
# (O código da consulta interativa e do mapa que já funcionava está aqui)

# --- Seção do Chat de IA ---
st.markdown("---")
st.header("💬 Converse com a IA para análises personalizadas")
# (O resto do seu código de chat permanece o mesmo)
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
                    st.error(erro); response_text = "Desculpe, não consegui analisar os dados."
                else:
                    if isinstance(resultado_analise, (pd.Series, pd.DataFrame)):
                        st.write(f"Resultado da busca na base de '{df_type}':"); st.dataframe(resultado_analise); response_text = "A informação que você pediu está na tabela acima."
                    else:
                        response_text = f"O resultado da sua análise é: **{resultado_analise}**"
                st.markdown(response_text)
        else:
            with st.spinner("Pensando..."):
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
    st.session_state.display_history.append({"role": "assistant", "content": response_text})
