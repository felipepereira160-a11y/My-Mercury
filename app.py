import streamlit as st
import google.generativeai as genai
import pandas as pd
import pydeck as pdk
import openrouteservice
from urllib.parse import quote

# --- Configuração da Página ---
st.set_page_config(page_title="Seu Assistente de Dados com IA", page_icon="🧠", layout="wide")

# --- Título ---
st.title("🧠 Your IA Assist")
st.write("Converse comigo ou faça o upload de seus arquivos na barra lateral para começar a analisar!")

# --- Configuração das APIs e Modelos ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-pro-latest')
    # Configura o cliente do OpenRouteService com a chave dos secrets
    ors_client = openrouteservice.Client(key=st.secrets["ORS_API_KEY"])
except Exception as e:
    st.error(f"Erro de configuração: Verifique suas chaves de API nos Secrets. Detalhe: {e}")
    st.stop()

# --- Inicialização do Estado da Sessão ---
# (O código de inicialização do session_state permanece o mesmo)
if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
if "display_history" not in st.session_state:
    st.session_state.display_history = []
if 'df_dados' not in st.session_state:
    st.session_state.df_dados = None
if 'df_mapeamento' not in st.session_state:
    st.session_state.df_mapeamento = None

# --- Funções de Análise (sem alterações) ---
# (A função 'executar_analise_pandas' permanece a mesma)

# --- Barra Lateral (sem alterações) ---
with st.sidebar:
    st.header("Base de Conhecimento")
    # (O código da barra lateral permanece o mesmo)

# --- Corpo Principal ---
if st.session_state.df_dados is not None or st.session_state.df_mapeamento is not None:
    st.markdown("---")
    # --- NOVA SEÇÃO: FERRAMENTAS DE ANÁLISE ---
    st.header("Ferramentas de Análise Rápida")
    
    os_id_input = st.text_input("Buscar Ordem de Serviço por ID:", placeholder="Digite o ID da OS aqui...")

    if os_id_input:
        df_dados = st.session_state.df_dados
        df_map = st.session_state.df_mapeamento
        
        if df_dados is not None:
            try:
                # Busca a ordem de serviço nos dados
                os_data = df_dados[df_dados['NumeroPedido'] == int(os_id_input)].iloc[0]
                st.subheader(f"Detalhes da OS: {os_id_input}")
                st.dataframe(os_data)

                # --- Lógica do QR Code ---
                if st.button("Gerar QR Code para esta OS"):
                    qr_text = f"OS: {os_data.get('NumeroPedido', 'N/A')}\\nCliente: {os_data.get('ClienteNome', 'N/A')}\\nEndereço: {os_data.get('Endereco', 'N/A')}, {os_data.get('Cidade', 'N/A')}"
                    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={quote(qr_text)}"
                    st.image(qr_url, caption="QR Code gerado com as informações da OS")

                # --- Lógica do OpenRouteService ---
                if df_map is not None and st.button("Calcular Rota e Distância"):
                    with st.spinner("Calculando a melhor rota..."):
                        rep_nome = os_data.get('RepresentanteTecnicoNome')
                        if rep_nome:
                            rep_data = df_map[df_map['nm_representante'] == rep_nome].iloc[0]
                            
                            start_coords = (rep_data['cd_longitude_representante'], rep_data['cd_latitude_representante'])
                            end_coords = (os_data['Longitude'], os_data['Latitude']) # Supondo que essas colunas existam nos seus dados
                            
                            coords = (start_coords, end_coords)
                            route = ors_client.directions(coordinates=coords, profile='driving-car', format='geojson')
                            
                            distance_km = route['features'][0]['properties']['summary']['distance'] / 1000
                            duration_min = route['features'][0]['properties']['summary']['duration'] / 60
                            
                            st.success("Rota calculada!")
                            col_a, col_b = st.columns(2)
                            col_a.metric("Distância da Rota", f"{distance_km:.2f} km")
                            col_b.metric("Tempo Estimado", f"{duration_min:.0f} min")

                            # Exibe o mapa com a rota
                            route_points = route['features'][0]['geometry']['coordinates']
                            st.map([{'latitude': p[1], 'longitude': p[0]} for p in route_points])
                        else:
                            st.warning("Não foi possível encontrar o representante desta OS no arquivo de mapeamento.")

            except (IndexError, KeyError) as e:
                st.error(f"Não foi possível encontrar a OS com o ID '{os_id_input}' ou faltam colunas essenciais (como 'Longitude'/'Latitude'). Detalhe: {e}")
        else:
            st.warning("Por favor, carregue o arquivo de 'Dados do Dia' para buscar uma OS.")
    st.markdown("---")


st.header("Converse com a IA")
# (O resto do código, com o histórico do chat e a lógica de entrada, permanece o mesmo)
# ...
