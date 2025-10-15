import subprocess
import os
import sys

def get_script_path():
    """Retorna o caminho do script, funcionando tanto para .py quanto para o executável."""
    if getattr(sys, 'frozen', False):
        # O aplicativo está "congelado" (executável)
        return os.path.dirname(sys.executable)
    else:
        # O aplicativo está rodando como um script normal
        return os.path.dirname(os.path.abspath(__file__))

def main():
    """
    Função principal que localiza o script app.py e o executa com o Streamlit.
    """
    # Define o caminho para o script principal do Streamlit
    script_dir = get_script_path()
    app_path = os.path.join(script_dir, "app.py")

    # Verifica se o arquivo app.py existe
    if not os.path.exists(app_path):
        # Esta parte é mais para debug, não deve acontecer no .exe final
        print(f"Erro: O arquivo 'app.py' não foi encontrado no diretório: {script_dir}")
        input("Pressione Enter para sair.")
        return

    # Comando para rodar o Streamlit
    # Usamos sys.executable para garantir que estamos usando o python embutido no .exe
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_path,
        "--server.headless", "true", # Evita abrir uma nova aba automaticamente, pode ser mais estável
        "--server.port", "8501" # Define uma porta padrão
    ]

    print(f"Iniciando o servidor Streamlit... Acesse http://localhost:8501 no seu navegador.")
    
    try:
        # Executa o comando
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Ocorreu um erro ao tentar iniciar o Streamlit: {e}")
        input("Pressione Enter para sair.")
    except FileNotFoundError:
        print("Erro: 'streamlit' não foi encontrado. Verifique se está instalado no ambiente.")
        input("Pressione Enter para sair.")


if __name__ == "__main__":
    main()
