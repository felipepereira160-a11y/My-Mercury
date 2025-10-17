import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from haversine import haversine, Unit

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

st.title("🧠 Seu Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

# --- Blacklist ---
BLACKLIST = ["FCA", "CHRYSLER", "STELLANTIS", "CEABS"]
def aplicar_blacklist(df):
    df_filtrado = df.copy()
    for col in df_filtrado.select_dtypes(include='object').columns:
        mask = df_filtrado[col].astype(str).str.upper().str.contains("|".join(BLACKLIST))
        df_filtrado = df_filtrado[~mask]
    return df_filtrado

# --- API Google ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not api_key:
    st.error("Chave da API do Google não encontrada.")
    st.stop()
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-pro-latest')

# --- Estado da Sessão ---
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções ---
def localizar_coluna_nome(df, keyword):
    for col in df.columns:
        if keyword in col.lower() and 'id' not in col.lower():
            return col
    for col in df.columns:
        if keyword in col.lower():
            return col
    return None

@st.cache_data(ttl=3600)
def executar_analise_pandas(_df_hash, pergunta, df_type):
    df = st.session_state.df_dados if df_type == 'dados' else st.session_state.df_mapeamento
    df = aplicar_blacklist(df)
    prompt_engenharia = f"""
    Você é um assistente especialista em Python e Pandas.
    Colunas disponíveis: {', '.join(df.columns)}.
    INSTRUÇÕES:
    1. Determine se a pergunta do usuário PODE ser respondida usando os dados.
    2. Se for genérica, responda "PERGUNTA_INVALIDA".
    3. Caso contrário, converta em uma única linha de código Pandas.
    Pergunta: "{pergunta}"
    """
    try:
        response = genai.GenerativeModel('gemini-pro-latest').generate_content(prompt_engenharia)
        resposta_ia = response.text.strip().replace('`','').replace('python','')
        if resposta_ia == "PERGUNTA_INVALIDA": return None, "PERGUNTA_INVALIDA"
        resultado = eval(resposta_ia, {'df': df, 'pd': pd})
        return resultado, None
    except Exception as e:
        return None, f"Erro na análise: {e}"

def carregar_dataframe(arquivo, separador_padrao=','):
    if arquivo.name.endswith('.xlsx'):
        return pd.read_excel(arquivo)
    elif arquivo.name.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1: return df
        except: pass
        arquivo.seek(0)
        outro_sep = ',' if separador_padrao == ';' else ';'
        return pd.read_csv(arquivo, encoding='latin-1', sep=outro_sep, on_bad_lines='skip')
    return None

def grafico_ordens(df, filtro_col=None, filtro_val=None, group_col=None, top_n=10):
    df_filtrado = aplicar_blacklist(df.copy())
    if filtro_col and filtro_val and filtro_val != "Todos":
        df_filtrado = df_filtrado[df_filtrado[filtro_col]==filtro_val]
    if group_col:
        df_contagem = df_filtrado.groupby(group_col).size().reset_index(name='Quantidade')
        df_contagem = df_contagem.sort_values(by='Quantidade', ascending=False).head(top_n)
        return df_contagem
    return None

# --- Barra Lateral ---
with st.sidebar:
    st.header("Base de Conhecimento")
    data_file = st.file_uploader("1. Upload de Agendamentos (OS)", type=["csv","xlsx"])
    if data_file:
        st.session_state.df_dados = carregar_dataframe(data_file, separador_padrao=';')
        st.success("Agendamentos carregados!")

    map_file = st.file_uploader("2. Upload do Mapeamento de RT", type=["csv","xlsx"])
    if map_file:
        st.session_state.df_mapeamento = carregar_dataframe(map_file, separador_padrao=',')
        st.success("Mapeamento carregado!")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.rerun()

# --- DASHBOARD OS ---
if st.session_state.df_dados is not None:
    st.markdown("---")
    st.header("📊 Dashboard de Ordens de Serviço")
    df_dados = aplicar_blacklist(st.session_state.df_dados.copy())

    status_col = next((col for col in df_dados.columns if 'status' in col.lower()), None)
    rep_col = localizar_coluna_nome(df_dados, 'representante técnico')
    city_col = next((col for col in df_dados.columns if 'cidade' in col.lower()), None)
    fechamento_col = next((col for col in df_dados.columns if 'tipo de fechamento' in col.lower()), None)
    os_num_col = next((col for col in df_dados.columns if 'número da o.s' in col.lower() or 'numeropedido' in col.lower()), None)

    col1, col2 = st.columns(2)
    with col1:
        chart1 = grafico_ordens(df_dados, filtro_col=status_col, filtro_val='Agendada', group_col=city_col)
        if chart1 is not None: st.bar_chart(chart1.set_index(city_col)['Quantidade'])
        chart2 = grafico_ordens(df_dados, filtro_col=status_col, filtro_val='Realizada', group_col=rep_col)
        if chart2 is not None: st.bar_chart(chart2.set_index(rep_col)['Quantidade'])
    with col2:
        chart3 = grafico_ordens(df_dados, group_col=rep_col)
        if chart3 is not None: st.bar_chart(chart3.set_index(rep_col)['Quantidade'])
        chart4 = grafico_ordens(df_dados, filtro_col=fechamento_col, filtro_val='Visita Improdutiva', group_col=rep_col)
        if chart4 is not None: st.bar_chart(chart4.set_index(rep_col)['Quantidade'])

# --- FERRAMENTA DE MAPEAMENTO ---
if st.session_state.df_mapeamento is not None:
    st.markdown("---")
    st.header("🗺️ Mapeamento de RT")
    df_map = aplicar_blacklist(st.session_state.df_mapeamento.copy())
    city_col_map, rep_col_map, lat_col, lon_col = 'nm_cidade_atendimento', 'nm_representante', 'cd_latitude_atendimento', 'cd_longitude_atendimento'
    
    col1, col2 = st.columns(2)
    cidade_selecionada_map = col1.selectbox("Cidade", sorted(df_map[city_col_map].dropna().unique()))
    rep_selecionado_map = col2.selectbox("Representante", sorted(df_map[rep_col_map].dropna().unique()))
    filtered_map = df_map
    if cidade_selecionada_map: filtered_map = filtered_map[filtered_map[city_col_map]==cidade_selecionada_map]
    if rep_selecionado_map: filtered_map = filtered_map[filtered_map[rep_col_map]==rep_selecionado_map]
    st.dataframe(filtered_map)
    map_data = filtered_map.rename(columns={lat_col:'lat', lon_col:'lon'})
    st.map(map_data.dropna(subset=['lat','lon']))

# --- OTIMIZADOR DE PROXIMIDADE ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    with st.expander("🚚 Otimizador de Proximidade de RT"):
        df_agendadas = df_dados[df_dados[status_col]=='Agendada'].copy()
        if not df_agendadas.empty:
            cidade_sel = st.selectbox("Selecione cidade:", sorted(df_agendadas[city_col].dropna().unique()))
            if cidade_sel:
                ordens = df_agendadas[df_agendadas[city_col]==cidade_sel]
                st.dataframe(ordens[[os_num_col, rep_col, city_col]])
                df_map_sel = df_map[df_map[city_col_map]==cidade_sel]
                if not df_map_sel.empty:
                    ponto_atendimento = (df_map_sel.iloc[0][lat_col], df_map_sel.iloc[0][lon_col])
                    distancias = [{'Representante': r[rep_col_map], 'Distancia (km)': haversine((r['cd_latitude_representante'], r['cd_longitude_representante']), ponto_atendimento, unit=Unit.KILOMETERS)} for _,r in df_map.iterrows()]
                    df_dist = pd.DataFrame(distancias).drop_duplicates(subset=['Representante']).reset_index(drop=True)
                    rt_sugerido = df_dist.loc[df_dist['Distancia (km)'].idxmin()]
                    for _, ordem in ordens.iterrows():
                        rt_atual = ordem[rep_col]
                        dist_atual = df_dist[df_dist['Representante']==rt_atual]['Distancia (km)'].values
                        dist_atual = dist_atual[0] if len(dist_atual)>0 else float('inf')
                        st.write(f"OS {ordem[os_num_col]} | RT Atual: {rt_atual} ({dist_atual:.1f} km) | Sugestão: {rt_sugerido['Representante']} ({rt_sugerido['Distancia (km)']:.1f} km)")

# --- CHAT IA ---
st.markdown("---")
st.header("💬 Converse com a IA")
for message in st.session_state.display_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Pergunte algo sobre os dados..."):
    st.session_state.display_history.append({"role":"user","content":prompt})
    with st.chat_message("user"): st.markdown(prompt)
    df_type = 'chat'
    keywords_mapeamento = ["quem atende","representante de","contato do rt","telefone de","rt para","mapeamento"]
    if any(k in prompt.lower() for k in keywords_mapeamento) and st.session_state.df_mapeamento is not None: df_type='mapeamento'
    elif st.session_state.df_dados is not None: df_type='dados'
    with st.chat_message("assistant"):
        if df_type in ['dados','mapeamento']:
            df_hash = pd.util.hash_pandas_object(st.session_state.get(f"df_{df_type}")).sum()
            resultado_analise, erro = executar_analise_pandas(df_hash, prompt, df_type)
            if erro=="PERGUNTA_INVALIDA":
                response_text = "Desculpe, só posso responder perguntas relacionadas aos dados carregados."
            elif erro:
                response_text = "Erro: " + erro
            else:
                if isinstance(resultado_analise,(pd.Series,pd.DataFrame)):
                    st.dataframe(resultado_analise); response_text="Informação mostrada na tabela acima."
                else:
                    response_text=f"Resultado: **{resultado_analise}**"
            st.markdown(response_text)
        else:
            response = st.session_state.chat.send_message(prompt)
            st.markdown(response.text)
            response_text = response.text
    st.session_state.display_history.append({"role":"assistant","content":response_text})
