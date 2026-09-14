@echo off
chcp 65001 >nul
echo ============================================================
echo  RavenStack - Gerador de Relatorio de Churn (Excel + Markdown)
echo ============================================================
echo.
echo Este arquivo gera uma planilha Excel e um relatorio Markdown
echo com o diagnostico de churn atualizado, a partir dos dados em
echo data/*.csv.
echo Nao precisa saber programar - so precisa ter Python instalado.
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado nesta maquina.
    echo Baixe em https://www.python.org/downloads/ e tente de novo.
    pause
    exit /b 1
)

echo Verificando dependencia (openpyxl)...
python -c "import openpyxl" >nul 2>nul
if errorlevel 1 (
    echo Instalando openpyxl pela primeira vez, aguarde...
    python -m pip install --quiet openpyxl
)

echo.
echo Gerando planilha e relatorio Markdown...
cd /d "%~dp0solution"
python gerar_excel.py

echo.
echo ============================================================
echo Pronto! Na pasta desta submissao voce vai encontrar:
echo  - RavenStack_Diagnostico_Churn.xlsx  (planilha navegavel)
echo  - RavenStack_Diagnostico_Churn.md    (relatorio em texto)
echo ============================================================
pause
