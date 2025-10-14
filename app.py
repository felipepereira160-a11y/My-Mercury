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

# --- Funções ---
@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    contexto = "analisar dados de ordens de serviço." if df_type == 'dados' else "buscar informações sobre representantes."
    time.sleep(1)
    prompt_engenharia = f"Sua tarefa é converter uma pergunta em uma única linha de código Pandas para {contexto}. O dataframe é `df`. As colunas são: {', '.join(df.columns)}. Pergunta: \"{pergunta}\". Gere apenas a linha de código Pandas."
    try:
        code_response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        codigo_pandas = code_response.text.strip().replace('`', '').replace('python', '').strip()
        resultado = eval(codigo_pandas, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Ocorreu um erro ao executar a análise: {e}"

def carregar_dataframe(arquivo, separador_padrao=','):
    if arquivo.name.endswith('.xlsx'):
        return pd.read_excel(arquivo)
    elif arquivo.name.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except Exception:
            pass
        arquivo.seek(0)
        outro_separador = ',' if separador_padrao == ';' else ';'
        df = pd.read_csv(arquivo, encoding='latin-1', sep=outro_separador, on_bad_lines='skip')
        return df
    return None

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    data_file = st.sidebar.file_uploader("1. Upload de Agendamentos (OS)", type=["csv", "xlsx"])
    if data_file:
        try:
            st.session_state.df_dados = carregar_dataframe(data_file, separador_padrao=',')
            st.success("Agendamentos carregados!")
        except Exception as e:
            st.error(f"Erro nos dados: {e}")

    st.markdown("---")
    map_file = st.sidebar.file_uploader("2. Upload do Mapeamento de RT (Fixo)", type=["csv", "xlsx"])
    if map_file:
        try:
            st.session_state.df_mapeamento = carregar_dataframe(map_file, separador_padrao=',')
            st.success("Mapeamento carregado!")
        except Exception as e:
            st.error(f"Erro no mapeamento: {e}")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- Corpo Principal ---

# --- DASHBOARD DE ANÁLISE DE ORDENS DE SERVIÇO ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Análise de Ordens de Serviço")
    df_dados = st.session_state.df_dados.copy()
    
    # Detecção dinâmica de colunas para robustez
    status_col = next((col for col in df_dados.columns if 'status' in col.lower()), None)
    rep_col_dados = next((col for col in df_dados.columns if 'representante técnico' in col.lower() and 'id' not in col.lower()), None)
    city_col_dados = next((col for col in df_dados.columns if 'cidade agendamento' in col.lower()), None)
    motivo_fechamento_col = next((col for col in df_dados.columns if 'tipo de fechamento' in col.lower()), None)
    cliente_col = next((col for col in df_dados.columns if 'cliente' in col.lower() and 'id' not in col.lower()), None)

    # Gráficos
    st.subheader("Análises Gráficas de Custo Zero")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Ordens Agendadas por Cidade (Top 10)**")
        if status_col and city_col_dados:
            agendadas_df = df_dados[df_dados[status_col] == 'Agendada']
            st.bar_chart(agendadas_df[city_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Colunas 'Status' ou 'Cidade Agendamento' não encontradas.")
        
        st.write("**Ordens por RT (Top 10)**")
        if rep_col_dados:
            st.bar_chart(df_dados[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Coluna 'Representante Técnico' não encontrada.")
            
    with col2:
        st.write("**Ordens Realizadas por RT (Top 10)**")
        if status_col and rep_col_dados:
            realizadas_df = df_dados[df_dados[status_col] == 'Realizada']
            st.bar_chart(realizadas_df[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Colunas 'Status' ou 'Representante Técnico' não encontradas.")
        
        st.write("**Indisponibilidades (Visitas Improdutivas) por RT (Top 10)**")
        if motivo_fechamento_col and rep_col_dados:
            improdutivas_df = df_dados[df_dados[motivo_fechamento_col] == 'Visita Improdutiva']
            st.bar_chart(improdutivas_df[rep_col_dados].value_counts().nlargest(10))
        else:
            st.warning("Colunas 'Tipo de Fechamento' ou 'Representante Técnico' não encontradas.")

# --- FERRAMENTA DE MAPEAMENTO ---
if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.header("🗺️ Ferramenta de Mapeamento e Consulta de RT")
    df_map = st.session_state.df_mapeamento.copy()
    city_col_map, rep_col_map, lat_col, lon_col, km_col = 'nm_cidade_atendimento', 'nm_representante', 'cd_latitude_atendimento', 'cd_longitude_atendimento', 'qt_distancia_atendimento_km'
    
    if all(col in df_map.columns for col in [city_col_map, rep_col_map, lat_col, lon_col, km_col]):
        col1, col2 = st.columns(2)
        cidade_selecionada_map = col1.selectbox("Filtrar Mapeamento por Cidade:", options=sorted(df_map[city_col_map].dropna().unique()), index=None, placeholder="Selecione uma cidade")
        rep_selecionado_map = col2.selectbox("Filtrar Mapeamento por Representante:", options=sorted(df_map[rep_col_map].dropna().unique()), index=None, placeholder="Selecione um representante")
        filtered_df_map = df_map
        if cidade_selecionada_map: filtered_df_map = df_map[df_map[city_col_map] == cidade_selecionada_map]
        elif rep_selecionado_map: filtered_df_map = df_map[df_map[rep_col_map] == rep_selecionado_map]
        st.write("Resultados da busca:")
        ordem_colunas = [rep_col_map, city_col_map, km_col]; outras_colunas = [col for col in filtered_df_map.columns if col not in ordem_colunas]; nova_ordem = ordem_colunas + outras_colunas
        st.dataframe(filtered_df_map[nova_ordem])
        st.write("Visualização no Mapa:")
        map_data = filtered_df_map.rename(columns={lat_col: 'lat', lon_col: 'lon'}); map_data['lat'] = pd.to_numeric(map_data['lat'], errors='coerce'); map_data['lon'] = pd.to_numeric(map_data['lon'], errors='coerce'); map_data.dropna(subset=['lat', 'lon'], inplace=True)
        map_data['size'] = 1000 if cidade_selecionada_map or rep_selecionado_map else 100
        if not map_data.empty: st.map(map_data, color='#FF4B4B', size='size')
        else: st.warning("Nenhum resultado com coordenadas para exibir no mapa.")

# --- OTIMIZADOR DE PROXIMIDADE ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    with st.expander("🚚 Abrir Otimizador de Proximidade de RT"):
        # (Código do Otimizador que já funciona)
        pass

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
