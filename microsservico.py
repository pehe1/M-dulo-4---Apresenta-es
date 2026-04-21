from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pptx import Presentation
from google import genai
import requests
import os
import re
from dotenv import load_dotenv

# Carrega as variáveis de ambiente escondidas no arquivo .env
load_dotenv()

app = FastAPI()


# ==========================================
# FUNÇÃO DO MEMBRO 1: INGESTÃO DO GITHUB
# ==========================================
def extrair_commits_do_github(url: str) -> str:
    """
    Recebe uma URL do GitHub, acessa a API pública e retorna os últimos 10 commits em formato de texto.
    """
    # Usa Expressão Regular (Regex) para extrair o 'owner' e o 'repo' da URL
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if not match:
        raise ValueError("URL do GitHub em formato inválido. Use: https://github.com/usuario/repositorio")

    owner, repo = match.groups()

    # Monta a URL da API do GitHub
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits"

    # Limpa o .git se o usuário colar o link de clone
    if repo.endswith('.git'):
        repo = repo[:-4]  # Remove as últimas 4 letras (".git")

    # Monta a URL da API do GitHub
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits"

    # Faz a requisição na internet
    resposta = requests.get(api_url)

    # Valida se o repositório existe e é público
    if resposta.status_code == 404:
        raise ValueError("Repositório não encontrado. Verifique se a URL está correta e se o repositório é público.")
    elif resposta.status_code != 200:
        raise ValueError(f"Erro ao acessar o GitHub: {resposta.status_code}")

    # Extrai as mensagens dos últimos 10 commits
    dados_commits = resposta.json()
    historico_texto = "Histórico recente de atualizações do código:\n"

    for item in dados_commits[:10]:  # Limita aos 10 mais recentes
        mensagem = item.get("commit", {}).get("message", "Sem mensagem")
        autor = item.get("commit", {}).get("author", {}).get("name", "Desconhecido")
        # Remove quebras de linha das mensagens de commit para não confundir a IA
        mensagem_limpa = mensagem.replace('\n', ' | ')
        historico_texto += f"- {mensagem_limpa} (Autor: {autor})\n"

    return historico_texto


# ==========================================
# 1. FRONT-END DO MVP (Atualizado)
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def get_form():
    return """
    <html>
        <head>
            <title>Gerador de Apresentações com IA</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 50px; background-color: #f4f4f9; }
                .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }
                input[type=url] { width: 100%; padding: 10px; margin-bottom: 20px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
                button { padding: 10px 20px; background: #6200ea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; width: 100%; }
                button:hover { background: #3700b3; }
                .tag-ia { display: inline-block; background: #e0f7fa; color: #00838f; padding: 4px 8px; border-radius: 12px; font-size: 12px; margin-bottom: 15px; font-weight: bold; }
                .tag-git { display: inline-block; background: #eeeeee; color: #333; padding: 4px 8px; border-radius: 12px; font-size: 12px; margin-bottom: 15px; font-weight: bold; margin-right: 5px;}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Gerador de Sprint Review 🚀</h2>
                <span class="tag-git">🐙 Integração GitHub</span><span class="tag-ia">✨ Powered by Gemini AI</span>
                <p>Insira a URL de um repositório público. O sistema irá extrair os commits automaticamente, interpretar o código e gerar a apresentação.</p>
                <form action="/gerar-pptx" method="post">
                    <input type="url" name="url_github" placeholder="Ex: https://github.com/ProfJuliani/EngSoft" required><br>
                    <button type="submit">Extrair do GitHub e Gerar PPTX</button>
                </form>
            </div>
        </body>
    </html>
    """


# ==========================================
# 2. BACK-END: INTEGRAÇÃO COMPLETA
# ==========================================
@app.post("/gerar-pptx")
async def gerar_pptx(url_github: str = Form(...)):
    try:
        # CHAMA A FUNÇÃO DO MEMBRO 1
        texto_bruto = extrair_commits_do_github(url_github)
    except ValueError as e:
        # Se a URL for inválida ou o repo não existir, mostra erro na tela
        raise HTTPException(status_code=400, detail=str(e))

    # Busca a chave de forma segura e instancia a IA (Papel do Membro 2)
    chave = os.environ.get("GEMINI_API_KEY")
    cliente = genai.Client(api_key=chave)

    prompt = f"""
    Você é um Tech Lead analisando o log de commits extraídos diretamente do repositório GitHub da equipe de desenvolvimento.
    Traduza as seguintes atualizações de código em 3 a 5 tópicos profissionais, focados em valor de negócio ou melhorias arquiteturais, para serem apresentados em um slide de Sprint Review para stakeholders.
    Regras estritas: 
    - Retorne APENAS os tópicos, um por linha.
    - NÃO use asteriscos, números, hífens ou marcadores no início da frase.
    - Vá direto ao ponto e ignore commits inúteis como "correção de typo" ou "update readme".

    Logs do GitHub:
    {texto_bruto}
    """

    resposta_ia = cliente.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )

    topicos_processados = resposta_ia.text.strip().split('\n')

    # GERAÇÃO DO ARQUIVO PPTX (Papel do Membro 3)
    prs = Presentation()

    slide_capa = prs.slides.add_slide(prs.slide_layouts[0])
    slide_capa.shapes.title.text = "Sprint Review"
    slide_capa.placeholders[1].text = f"Análise automatizada do repositório\n{url_github}"

    slide_conteudo = prs.slides.add_slide(prs.slide_layouts[1])
    slide_conteudo.shapes.title.text = "Principais Entregas (Baseadas no Código)"
    corpo_texto = slide_conteudo.placeholders[1].text_frame

    p0 = corpo_texto.paragraphs[0]
    p0.text = "Destaques da iteração validados no repositório:"

    for topico in topicos_processados:
        texto_limpo = topico.strip()
        if texto_limpo:
            p = corpo_texto.add_paragraph()
            p.text = texto_limpo
            p.level = 1

    file_path = "Sprint_Review_GitHub.pptx"
    prs.save(file_path)

    return FileResponse(
        path=file_path,
        media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        filename="Sprint_Review_GitHub.pptx"
    )