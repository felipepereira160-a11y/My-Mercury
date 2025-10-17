# Gerar nova versão com pesquisa por número de O.S.
v3_code = r'''
import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from haversine import haversine, Unit

# --- Configuração da Página ---
st.set_page_config(page_title="Assistente de Dados com IA", page_icon="🧠", layout="wide")
st.title("🧠 Assistente de Dados com IA")
st.write("Converse comigo ou faça o upload de seus arquivos para começar!")

# --- Configuração da API ---
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

# --- Estado ---
if "chat" not in st.session_state and model:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções Auxiliares ---
def carregar_dataframe(arquivo, separador_padrao=','):
    if arquivo.name.endswith('.xlsx') or arquivo.name.endswith('.xls'):
        return pd.read_excel(arquivo)
    elif arquivo.name.endswith('.csv'):
        try:
            arquivo.seek(0)
            df = pd.read_csv(arquivo, encoding='latin-1', sep=separador_padrao, on_bad_lines='skip')
            if len(df.columns) > 1:
                return df
        except Exception:
            pass
        arquivo.seek(0)
        outro_sep = ',' if separador_padrao == ';' else ';'
        return pd.read_csv(arquivo, encoding='latin-1', sep=outro_sep, on_bad_lines='skip')
    return None

def aplicar_filtro_exclusao(df, termos_excluidos, campos_verificados=None):
    if df is None:
        return None
    df_f = df.copy()
    if campos_verificados is None:
        campos_verificados = [col for col in df_f.columns if any(x in col.lower() for x in ['cliente', 'representante', 'rep', 'nm_representante'])]
    if not campos_verificados:
        campos_verificados = [col for col in df_f.columns if df_f[col].dtype == object]
    pattern = '|'.join([p.lower() for p in termos_excluidos if p.strip()])
    mask_total = pd.Series(False, index=df_f.index)
    for col in campos_verificados:
        try:
            mask = df_f[col].astype(str).str.lower().str.contains(pattern, na=False)
            mask_total = mask_total | mask
        except Exception:
            continue
    return df_f[~mask_total].copy()

# --- Barra Lateral ---
with st.sidebar:
    st.header("📂 Base de Conhecimento")
    data_file = st.file_uploader("Upload de Agendamentos (OS)", type=["csv", "xlsx"])
    map_file = st.file_uploader("Upload de Mapeamento (RT)", type=["csv", "xlsx"])

    termos_padrao = ['stellantis', 'ceabs', 'ceabvs', 'fca', 'fca chrysler', 'serviços ceabs', 'locadora', 'montadora']
    termos_input = st.text_area("Termos para ignorar:", ', '.join(termos_padrao))
    termos_excluidos = [t.strip() for t in termos_input.split(',') if t.strip()]

    if st.button("Aplicar Filtro"):
        if data_file:
            df = carregar_dataframe(data_file, separador_padrao=';')
            st.session_state.df_dados = aplicar_filtro_exclusao(df, termos_excluidos)
        if map_file:
            dfm = carregar_dataframe(map_file, separador_padrao=',')
            st.session_state.df_mapeamento = aplicar_filtro_exclusao(dfm, termos_excluidos)
        st.success("Filtro aplicado e bases carregadas!")

    if st.button("Limpar Tudo"):
        st.session_state.clear()
        st.experimental_rerun()

# --- OTIMIZADOR ---
if st.session_state.df_dados is not None and st.session_state.df_mapeamento is not None:
    st.markdown("---")
    with st.expander("🚚 Otimizador de Proximidade de RT"):
        try:
            df_dados_otim = st.session_state.df_dados.copy()
            df_map_otim = st.session_state.df_mapeamento.copy()

            # Colunas principais
            os_id_col = next((c for c in df_dados_otim.columns if 'número' in c.lower() or 'os' in c.lower()), None)
            os_cliente_col = next((c for c in df_dados_otim.columns if 'cliente' in c.lower()), None)
            os_city_col = next((c for c in df_dados_otim.columns if 'cidade' in c.lower()), None)
            os_rep_col = next((c for c in df_dados_otim.columns if 'representante' in c.lower()), None)
            os_status_col = next((c for c in df_dados_otim.columns if 'status' in c.lower()), None)

            map_city_col = 'nm_cidade_atendimento'
            map_rep_col = 'nm_representante'
            map_rep_lat_col = 'cd_latitude_representante'
            map_rep_lon_col = 'cd_longitude_representante'
            map_lat_atendimento_col = 'cd_latitude_atendimento'
            map_lon_atendimento_col = 'cd_longitude_atendimento'

            # Reforço de filtro de exclusão
            df_map_otim = df_map_otim[~df_map_otim[map_rep_col].astype(str).str.lower().str.contains('|'.join([t.lower() for t in termos_excluidos]), na=False)]

            df_agendadas = df_dados_otim[df_dados_otim[os_status_col].astype(str).str.lower() == 'agendada'].copy()
            if df_agendadas.empty:
                st.info("Nenhuma ordem 'Agendada' encontrada.")
                st.stop()

            # Campo de busca por número da OS
            st.subheader("🔍 Buscar por Número da O.S.")
            os_search = st.text_input("Digite o número da O.S. (ex: 123456 ou 123456.7):", "")

            ordem_encontrada = None
            if os_search.strip():
                df_filtrado_os = df_agendadas[df_agendadas[os_id_col].astype(str).str.contains(os_search.strip(), case=False, na=False)]
                if not df_filtrado_os.empty:
                    ordem_encontrada = df_filtrado_os.iloc[0]
                    st.success(f"O.S. encontrada: {ordem_encontrada[os_id_col]} - Cliente: {ordem_encontrada[os_cliente_col]}")
                else:
                    st.warning("Nenhuma O.S. correspondente encontrada.")

            # Caso não busque O.S., filtra por cidade
            if ordem_encontrada is None:
                lista_cidades = sorted(df_agendadas[os_city_col].dropna().unique())
                cidade = st.selectbox("Selecione a cidade:", lista_cidades, index=None, placeholder="Escolha uma cidade")
                if not cidade:
                    st.stop()
                ordens = df_agendadas[df_agendadas[os_city_col] == cidade]
            else:
                cidade = ordem_encontrada[os_city_col]
                ordens = df_agendadas[df_agendadas[os_id_col].astype(str).str.contains(os_search.strip(), na=False)]

            st.subheader(f"Ordens 'Agendadas' em {cidade}:")
            st.dataframe(ordens[[os_id_col, os_cliente_col, os_rep_col]])

            cidade_info = df_map_otim[df_map_otim[map_city_col] == cidade]
            if cidade_info.empty:
                st.warning("Cidade não encontrada no mapeamento.")
            else:
                ponto = (cidade_info.iloc[0][map_lat_atendimento_col], cidade_info.iloc[0][map_lon_atendimento_col])
                df_map_filtrado_final = df_map_otim[~df_map_otim[map_rep_col].astype(str).str.lower().str.contains('|'.join([t.lower() for t in termos_excluidos]), na=False)].copy()
                distancias = [
                    {'Representante': r[map_rep_col], 'Distancia (km)': haversine((r[map_rep_lat_col], r[map_rep_lon_col]), ponto, unit=Unit.KILOMETERS)}
                    for _, r in df_map_filtrado_final.dropna(subset=[map_rep_lat_col, map_rep_lon_col]).iterrows()
                ]
                df_dist = pd.DataFrame(distancias)
                if not df_dist.empty:
                    rt_sugerido = df_dist.loc[df_dist['Distancia (km)'].idxmin()]
                    for _, ordem in ordens.iterrows():
                        rt_atual = ordem[os_rep_col]
                        with st.expander(f"OS: {ordem[os_id_col]} | Cliente: {ordem[os_cliente_col]}"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.info(f"RT Agendado: {rt_atual}")
                                atual_df = df_dist[df_dist['Representante'] == rt_atual]
                                if not atual_df.empty:
                                    dist_atual = atual_df['Distancia (km)'].values[0]
                                    st.metric("Distância do RT Agendado", f"{dist_atual:.1f} km")
                                else:
                                    st.warning("RT não encontrado no mapeamento.")
                                    dist_atual = float('inf')
                            with col2:
                                st.success(f"Sugestão (Mais Próximo): {rt_sugerido['Representante']}")
                                economia = dist_atual - rt_sugerido['Distancia (km)']
                                st.metric("Distância do RT Sugerido", f"{rt_sugerido['Distancia (km)']:.1f} km",
                                          delta=f"{economia:.1f} km de economia" if economia > 0 and economia != float('inf') else None)
        except Exception as e:
            st.error(f"Erro no Otimizador: {e}")
'''

v3_path = "/mnt/data/app_corrigido_v3.py"
with open(v3_path, "w", encoding="utf-8") as f:
    f.write(v3_code)

v3_path
