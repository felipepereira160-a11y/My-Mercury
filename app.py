import subprocess
import os
import sys
import logging
import tkinter as tk
from tkinter import messagebox

# --- Configuração do Logging ---
# Define o caminho do arquivo de log. Funciona tanto para o script .py quanto para o .exe
def get_log_path():
    """Retorna o diretório base para o arquivo de log."""
    if getattr(sys, 'frozen', False):
        # Estamos rodando em um .exe, o log fica ao lado dele
        return os.path.dirname(sys.executable)
    else:
        # Estamos rodando como script .py
        return os.path.dirname(os.path.abspath(__file__))

# Configura o logger para escrever em um arquivo
log_file_path = os.path.join(get_log_path(), 'app_log.txt')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file_path,
    filemode='w' # 'w' para sobrescrever o log a cada execução
)

def show_error(title, message):
    """Exibe uma caixa de diálogo de erro gráfica."""
    try:
        root = tk.Tk()
        root.withdraw()  # Esconde a janela principal do tkinter
        messagebox.showerror(title, message)
        root.destroy()
    except Exception as e:
        logging.error(f"Falha ao exibir a caixa de erro do tkinter: {e}")

def get_script_path():
    """Retorna o caminho do script, funcionando tanto para .py quanto para o executável."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def main():
    """Função principal que localiza e executa o app Streamlit."""
    logging.info("="*30)
    logging.info("Aplicação iniciada.")
    
    script_dir = get_script_path()
    app_path = os.path.join(script_dir, "app.py")
    logging.info(f"Procurando por app.py em: {app_path}")

    if not os.path.exists(app_path):
        error_message = f"Erro Crítico: O arquivo 'app.py' não foi encontrado no diretório: {script_dir}"
        logging.error(error_message)
        show_error("Erro de Arquivo", error_message)
        return

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_path,
        "--server.headless", "true",
        "--server.port", "8501"
    ]
    logging.info(f"Comando de execução: {' '.join(command)}")
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    logging.info("Iniciando o processo do Streamlit...")
    subprocess.run(command, check=True, startupinfo=startupinfo)
    logging.info("Processo do Streamlit finalizado normalmente.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Pega qualquer erro que não foi tratado dentro de main()
        logging.error(f"Erro fatal não tratado na aplicação: {e}", exc_info=True)
        show_error("Erro Fatal", f"Ocorreu um erro fatal. Por favor, verifique o arquivo 'app_log.txt' para mais detalhes.\n\nErro: {e}")

