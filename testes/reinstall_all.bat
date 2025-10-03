@echo off
echo ======================================================================
echo AIcentralv2 - Reinstalacao Completa
echo ======================================================================

:: Ativar venv
call venv\Scripts\activate.bat

:: Desinstalar tudo
echo.
echo Desinstalando pacotes antigos...
pip uninstall -y Flask Werkzeug psycopg psycopg-binary python-dotenv

:: Limpar cache do pip
echo.
echo Limpando cache...
pip cache purge

:: Atualizar pip
echo.
echo Atualizando pip...
python -m pip install --upgrade pip

:: Instalar um por um
echo.
echo ======================================================================
echo Instalando dependencias...
echo ======================================================================

echo.
echo [1/4] Flask...
pip install Flask==3.0.0

echo.
echo [2/4] Werkzeug...
pip install Werkzeug==3.0.1

echo.
echo [3/4] python-dotenv...
pip install python-dotenv==1.0.0

echo.
echo [4/4] psycopg...
pip install "psycopg[binary]==3.1.18"

:: Verificar
echo.
echo ======================================================================
echo Pacotes instalados:
echo ======================================================================
pip list

echo.
echo ======================================================================
echo Testando imports...
echo ======================================================================
python -c "import flask; print('✅ Flask:', flask.__version__)"
python -c "from dotenv import load_dotenv; print('✅ python-dotenv: OK')"
python -c "import psycopg; print('✅ psycopg:', psycopg.__version__)"

echo.
echo ======================================================================
echo Instalacao concluida!
echo ======================================================================
pause