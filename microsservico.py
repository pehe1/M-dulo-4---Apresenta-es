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


from typing import Optional  # Adicione isso lá nas importações do topo!


# ==========================================
# 1. FRONT-END: INGESTÃO UNIFICADA
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def get_form():
    return """
    <html>
        <head>
            <title>Gerador de Apresentações com IA</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 40px; background-color: #f4f4f9; }
                .container { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }
                input[type=url], textarea { width: 100%; padding: 10px; margin-top: 5px; margin-bottom: 20px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
                button { padding: 12px 20px; background: #6200ea; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; width: 100%; }
                button:hover { background: #3700b3; }
                .tag-ia { display: inline-block; background: #e0f7fa; color: #00838f; padding: 4px 8px; border-radius: 12px; font-size: 12px; margin-bottom: 15px; font-weight: bold; }
                hr { border: 0; border-top: 1px solid #eee; margin: 20px 0; }
                label { font-weight: bold; color: #333; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Gerador de Sprint Review 🚀</h2>
                <span class="tag-ia">✨ Powered by Gemini AI</span>
                <p>Escolha a origem dos dados para gerar a sua apresentação:</p>

                <form action="/gerar-pptx" method="post">
                    <label>Opção 1: Extrair direto do Código</label>
                    <input type="url" name="url_github" placeholder="Ex: https://github.com/usuario/repositorio">

                    <hr>

                    <label>Opção 2: Colar anotações manualmente</label>
                    <textarea name="texto_bruto" rows="5" placeholder="Cole aqui o resumo da reunião, notas da Sprint, etc..."></textarea>

                    <button type="submit">Processar com IA e Gerar PPTX</button>
                </form>
            </div>
        </body>
    </html>
    """


# ==========================================
# 2. BACK-END: ROTEAMENTO INTELIGENTE
# ==========================================
# Note que agora usamos Optional[str] e Form(None) para não obrigar o usuário a preencher os dois
@app.post("/gerar-pptx")
async def gerar_pptx(url_github: Optional[str] = Form(None), texto_bruto: Optional[str] = Form(None)):
    # LÓGICA DE DECISÃO: De onde vem a informação?
    if url_github:
        try:
            dados_entrada = extrair_commits_do_github(url_github)
            subtitulo_slide = f"Análise automatizada do repositório\n{url_github}"
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    elif texto_bruto and texto_bruto.strip():
        dados_entrada = f"Anotações da equipe:\n{texto_bruto}"
        subtitulo_slide = "Resumo gerado a partir de anotações manuais"

    else:
        raise HTTPException(status_code=400, detail="Você precisa preencher a URL do GitHub OU colar um texto.")

    # INGESTÃO CONCLUÍDA! Agora passa a bola para o Gemini (Membro 2)
    chave = os.environ.get("GEMINI_API_KEY")
    cliente = genai.Client(api_key=chave)

    prompt = f"""
    Você é um Tech Lead analisando informações de uma equipe de desenvolvimento.
    Traduza as seguintes informações em 3 a 5 tópicos profissionais e curtos para serem apresentados em um slide de Sprint Review para stakeholders.
    Regras estritas: 
    - Retorne APENAS os tópicos, um por linha.
    - NÃO use asteriscos, números, hífens ou marcadores no início da frase.
    - Vá direto ao ponto.

    Informações:
    {dados_entrada}
    """

    resposta_ia = cliente.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )

    topicos_processados = resposta_ia.text.strip().split('\n')

    # GERAÇÃO DO ARQUIVO PPTX (Membro 3)
    prs = Presentation()

    slide_capa = prs.slides.add_slide(prs.slide_layouts[0])
    slide_capa.shapes.title.text = "Sprint Review"
    slide_capa.placeholders[1].text = subtitulo_slide

    slide_conteudo = prs.slides.add_slide(prs.slide_layouts[1])
    slide_conteudo.shapes.title.text = "Principais Entregas"
    corpo_texto = slide_conteudo.placeholders[1].text_frame

    p0 = corpo_texto.paragraphs[0]
    p0.text = "Destaques da iteração:"

    for topico in topicos_processados:
        texto_limpo = topico.strip()
        if texto_limpo:
            p = corpo_texto.add_paragraph()
            p.text = texto_limpo
            p.level = 1

    file_path = "Sprint_Review_Inteligente.pptx"
    prs.save(file_path)

    return FileResponse(
        path=file_path,
        media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        filename="Sprint_Review_Inteligente.pptx"
    )