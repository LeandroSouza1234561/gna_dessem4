"""
╔══════════════════════════════════════════════════════════════════════╗
║   GNA I & II — Coleta pdo_oper_titulacao_usinas.dat — ONS/SINTEGRE  ║
║   Roda via GitHub Actions a cada 5 minutos                           ║
║   Publica resultado em docs/dados_gna.json (GitHub Pages)            ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Configurações ───────────────────────────────────────────────────────────
ONS_USER = os.environ.get("ONS_USER", "leandro.souza@gna.com.br")
ONS_PASS = os.environ.get("ONS_PASS", "")

URL_PORTAL   = "https://pops.ons.org.br/"
URL_SINTEGRE = "https://sintegre.ons.org.br/"

# Nome do arquivo que queremos baixar
ARQUIVO_DAT = "pdo_oper_titulacao_usinas.dat"

# Filtro de plantas
PLANTAS_ALVO = ["GNA I", "GNA II", "GNA 1", "GNA 2", "GNAI", "GNAII", "UTE GNA"]

# Pasta de saída para GitHub Pages
DOCS_DIR  = Path(__file__).parent / "docs"
JSON_FILE = DOCS_DIR / "dados_gna.json"
RAW_FILE  = DOCS_DIR / "pdo_oper_titulacao_usinas.dat"

DOCS_DIR.mkdir(exist_ok=True)

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("GNA-DAT")


# ═══════════════════════════════════════════════════════════════════════════
#  LOGIN SSO
# ═══════════════════════════════════════════════════════════════════════════

def fazer_login(page):
    """Realiza login no SSO da ONS."""
    log.info("Acessando portal ONS...")
    page.goto(URL_PORTAL, wait_until="domcontentloaded")
    time.sleep(3)

    current = page.url
    log.info(f"URL atual: {current}")

    # Se já redirecionou para SSO
    if "sso.ons.org.br" in current or "login" in current.lower():
        _preencher_credenciais(page)
    elif "pops.ons.org.br" in current:
        log.info("Sessão já ativa.")
        return

    # Aguarda retorno ao portal
    try:
        page.wait_for_url("**/pops.ons.org.br/**", timeout=40000)
        log.info("✓ Autenticado no portal.")
    except PWTimeout:
        log.warning("Timeout aguardando redirecionamento pós-login. Continuando...")

    time.sleep(2)


def _preencher_credenciais(page):
    """Preenche usuário e senha no formulário SSO."""
    # Campo usuário / email
    for sel in ["input[name='username']", "input[id='username']",
                "input[type='email']", "#i0116"]:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=8000)
            el.fill(ONS_USER)
            log.info(f"Usuário preenchido via '{sel}'")
            break
        except Exception:
            continue

    # Botão "Próximo" (fluxo Microsoft)
    for sel in ["#idSIButton9", "button:has-text('Next')", "button:has-text('Próximo')"]:
        try:
            page.locator(sel).first.click(timeout=3000)
            time.sleep(1)
            break
        except Exception:
            continue

    # Campo senha
    for sel in ["input[name='password']", "input[id='password']",
                "input[type='password']", "#i0118"]:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=10000)
            el.fill(ONS_PASS)
            log.info(f"Senha preenchida via '{sel}'")
            break
        except Exception:
            continue

    # Submeter
    for sel in ["button[type='submit']", "input[type='submit']",
                "button:has-text('Entrar')", "button:has-text('Sign in')",
                "#idSIButton9", "button:has-text('Login')"]:
        try:
            page.locator(sel).first.click(timeout=5000)
            log.info("Botão de login clicado.")
            break
        except Exception:
            continue

    time.sleep(2)


# ═══════════════════════════════════════════════════════════════════════════
#  NAVEGAR ATÉ O ARQUIVO .DAT
# ═══════════════════════════════════════════════════════════════════════════

def encontrar_e_baixar_dat(page) -> str | None:
    """
    Navega até o arquivo pdo_oper_titulacao_usinas.dat no SINTEGRE/POPS.
    Retorna o conteúdo do arquivo como string, ou None se não encontrado.
    """
    conteudo = None

    # ── Estratégia 1: SINTEGRE diretamente ───────────────────────────────
    urls_tentativa = [
        # SINTEGRE - caminhos comuns para arquivos DESSEM
        "https://sintegre.ons.org.br/ons.sintegre.web/Planejamento/DESSEM",
        "https://sintegre.ons.org.br/ons.sintegre.web/ProgramacaoOperacao/DESSEM",
        "https://sintegre.ons.org.br/sintetizador/DESSEM",
        # POPS - seção de decks
        "https://pops.ons.org.br/ons.pop.operacao/ProgramacaoOperacao/DeckEntradaSaida",
        "https://pops.ons.org.br/ons.pop.operacao/Dessem",
    ]

    for url in urls_tentativa:
        try:
            log.info(f"Tentando: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

            # Verifica se há link para o arquivo .dat
            links = page.locator(f"a[href*='{ARQUIVO_DAT}'], a[href*='pdo_oper']").all()
            if links:
                log.info(f"Encontrado link para .dat em {url}")
                # Tenta fazer download via interceptação de rede
                conteudo = _baixar_via_link(page, links[0])
                if conteudo:
                    break

            # Busca por qualquer lista de arquivos
            links_dat = page.locator("a[href$='.dat']").all()
            for link in links_dat:
                href = link.get_attribute("href") or ""
                texto = link.inner_text().strip()
                if "pdo_oper" in href.lower() or "titulac" in href.lower() or "titulac" in texto.lower():
                    log.info(f"Link .dat relevante: {href}")
                    conteudo = _baixar_via_link(page, link)
                    if conteudo:
                        break

            if conteudo:
                break

        except Exception as e:
            log.warning(f"Erro em {url}: {e}")
            continue

    # ── Estratégia 2: Navegar pelo menu ──────────────────────────────────
    if not conteudo:
        conteudo = _navegar_menu_e_buscar(page)

    return conteudo


def _baixar_via_link(page, link_element) -> str | None:
    """Baixa conteúdo do arquivo via link Playwright com interceptação."""
    try:
        href = link_element.get_attribute("href") or ""

        # URL absoluta ou relativa
        if href.startswith("http"):
            url_arquivo = href
        else:
            base = "/".join(page.url.split("/")[:3])
            url_arquivo = base + ("/" if not href.startswith("/") else "") + href

        log.info(f"Baixando: {url_arquivo}")

        # Usa fetch via JavaScript para obter conteúdo de texto
        conteudo = page.evaluate(f"""
            async () => {{
                const resp = await fetch('{url_arquivo}', {{credentials: 'include'}});
                if (!resp.ok) return null;
                return await resp.text();
            }}
        """)

        if conteudo and len(conteudo) > 100:
            log.info(f"✓ Arquivo baixado: {len(conteudo)} chars")
            return conteudo

    except Exception as e:
        log.warning(f"Erro ao baixar via link: {e}")

    return None


def _navegar_menu_e_buscar(page) -> str | None:
    """Tenta navegar pelo menu do POPS até encontrar o arquivo."""
    log.info("Tentando navegação por menu...")

    menus = [
        ("text=Programação da Operação", "text=Decks", "text=DESSEM"),
        ("text=Programação", "text=Deck", "text=DESSEM"),
        ("a:has-text('Programação')", "a:has-text('DESSEM')", None),
    ]

    for caminho in menus:
        try:
            for seletor in caminho:
                if seletor is None:
                    continue
                el = page.locator(seletor).first
                el.wait_for(timeout=8000)
                el.click()
                time.sleep(1)

            # Procura link .dat na página resultante
            time.sleep(3)
            links = page.locator(f"a[href*='pdo_oper'], a[href$='.dat']").all()
            for link in links:
                href = link.get_attribute("href") or ""
                if "titulac" in href.lower() or "pdo_oper" in href.lower():
                    conteudo = _baixar_via_link(page, link)
                    if conteudo:
                        return conteudo
        except Exception as e:
            log.warning(f"Erro no menu: {e}")
            continue

    return None


# ═══════════════════════════════════════════════════════════════════════════
#  PARSEAR O ARQUIVO .DAT
# ═══════════════════════════════════════════════════════════════════════════

def parsear_dat(conteudo: str) -> dict:
    """
    Parseia o arquivo pdo_oper_titulacao_usinas.dat.

    Formato típico DESSEM:
    - Linhas de comentário começam com '&' ou '%'
    - Seções identificadas por palavras-chave em maiúsculas
    - Colunas separadas por espaço (largura fixa)

    Retorna dict com:
      - colunas: lista de nomes de colunas detectados
      - registros: lista de dicts {coluna: valor} para GNA I e GNA II
      - raw_header: cabeçalho original
    """
    linhas = conteudo.splitlines()
    log.info(f"Arquivo tem {len(linhas)} linhas")

    # Detecta cabeçalho (linha que contém nomes de colunas)
    cabecalho_idx = None
    cabecalho_raw = ""
    colunas = []

    for i, linha in enumerate(linhas):
        # Pula comentários
        if linha.strip().startswith(("&", "%", "/")):
            continue
        # Cabeçalho geralmente contém NOME, USINA, ou os identificadores de coluna
        if re.search(r'\b(NOME|USINA|USINAMED|NOMEUSINA|IUSI|NUM)\b', linha, re.I):
            cabecalho_idx = i
            cabecalho_raw = linha
            # Extrai colunas pelo espaço (arquivos DESSEM têm formato fixo)
            colunas = linha.split()
            log.info(f"Cabeçalho encontrado na linha {i}: {colunas}")
            break

    # Fallback: detecta pelo maior número de campos
    if not colunas:
        max_campos = 0
        for i, linha in enumerate(linhas[:50]):
            if linha.strip().startswith(("&", "%", "/")):
                continue
            campos = linha.split()
            if len(campos) > max_campos and not all(c.isdigit() or c in '.-+' for c in campos):
                max_campos = len(campos)
                cabecalho_idx = i
                cabecalho_raw = linha
                colunas = campos
        log.info(f"Cabeçalho por heurística na linha {cabecalho_idx}: {colunas}")

    # Extrai registros após o cabeçalho
    registros_brutos = []
    if cabecalho_idx is not None:
        for linha in linhas[cabecalho_idx + 1:]:
            linha = linha.rstrip()
            if not linha or linha.strip().startswith(("&", "%", "/")):
                continue
            # Linha de dado: split por espaço respeitando campos contíguos
            campos = linha.split()
            if campos:
                registros_brutos.append(campos)

    log.info(f"Total de registros brutos: {len(registros_brutos)}")

    # Filtra GNA I e GNA II
    registros_gna = []
    for campos in registros_brutos:
        linha_str = " ".join(campos).upper()
        eh_gna = False
        planta_id = None

        for planta in PLANTAS_ALVO:
            if planta.upper() in linha_str:
                eh_gna = True
                if "II" in planta or "2" in planta:
                    planta_id = "GNA II"
                else:
                    planta_id = "GNA I"
                break

        if not eh_gna:
            continue

        # Mapeia colunas detectadas
        registro = {"planta_id": planta_id, "_raw": " ".join(campos)}
        for j, col in enumerate(colunas):
            if j < len(campos):
                registro[col] = _parse_valor(campos[j])
            else:
                registro[col] = None

        # Se há mais campos que colunas, adiciona como extras
        for j in range(len(colunas), len(campos)):
            registro[f"col_{j}"] = _parse_valor(campos[j])

        registros_gna.append(registro)
        log.info(f"  → {planta_id}: {registro}")

    return {
        "colunas": colunas,
        "registros": registros_gna,
        "raw_header": cabecalho_raw,
        "total_linhas_arquivo": len(linhas),
        "total_registros_gna": len(registros_gna),
    }


def _parse_valor(texto: str):
    """Converte texto para número se possível."""
    if not texto or texto in ["-", "—", "N/A", "*", ""]:
        return None
    try:
        return int(texto)
    except ValueError:
        pass
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return texto


# ═══════════════════════════════════════════════════════════════════════════
#  SALVAR RESULTADO
# ═══════════════════════════════════════════════════════════════════════════

def salvar_resultado(conteudo_raw: str, dados_parseados: dict):
    """Salva .dat raw e JSON processado na pasta docs/."""
    ts = datetime.now(timezone.utc).isoformat()

    # Salva arquivo raw
    if conteudo_raw:
        RAW_FILE.write_text(conteudo_raw, encoding="utf-8", errors="replace")
        log.info(f"✓ Arquivo raw salvo: {RAW_FILE}")

    # Carrega histórico anterior
    historico = []
    if JSON_FILE.exists():
        try:
            anterior = json.loads(JSON_FILE.read_text(encoding="utf-8"))
            historico = anterior.get("historico", [])
        except Exception:
            historico = []

    snapshot = {
        "timestamp": ts,
        "colunas": dados_parseados["colunas"],
        "registros": dados_parseados["registros"],
        "total_registros_gna": dados_parseados["total_registros_gna"],
    }

    historico.append(snapshot)
    historico = historico[-288:]  # ~24h a cada 5min

    saida = {
        "ultima_coleta": ts,
        "status": "ok" if dados_parseados["registros"] else "sem_dados",
        "arquivo": ARQUIVO_DAT,
        "colunas": dados_parseados["colunas"],
        "raw_header": dados_parseados["raw_header"],
        "total_linhas_arquivo": dados_parseados["total_linhas_arquivo"],
        "registros": dados_parseados["registros"],
        "total_registros_gna": dados_parseados["total_registros_gna"],
        "historico": historico,
    }

    JSON_FILE.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"✓ JSON salvo: {JSON_FILE} ({dados_parseados['total_registros_gna']} registros GNA)")

    return saida


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    if not ONS_PASS:
        log.error("Variável ONS_PASS não definida! Configure o secret no GitHub.")
        # Cria JSON de erro para o dashboard não quebrar
        erro_json = {
            "ultima_coleta": datetime.now(timezone.utc).isoformat(),
            "status": "erro_credencial",
            "erro": "ONS_PASS não configurado",
            "colunas": [],
            "registros": [],
            "historico": [],
        }
        DOCS_DIR.mkdir(exist_ok=True)
        JSON_FILE.write_text(json.dumps(erro_json, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            fazer_login(page)
            conteudo_raw = encontrar_e_baixar_dat(page)

            if not conteudo_raw:
                log.error("Não foi possível obter o arquivo .dat")
                dados = {"colunas": [], "registros": [], "raw_header": "",
                         "total_linhas_arquivo": 0, "total_registros_gna": 0}
                saida = salvar_resultado("", dados)
                saida["status"] = "arquivo_nao_encontrado"
                JSON_FILE.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
                return 1

            dados = parsear_dat(conteudo_raw)
            salvar_resultado(conteudo_raw, dados)
            log.info(f"✓ Concluído: {dados['total_registros_gna']} registros GNA extraídos.")
            return 0

        except Exception as e:
            log.error(f"Erro fatal: {e}", exc_info=True)
            return 1

        finally:
            browser.close()


if __name__ == "__main__":
    exit(main())
