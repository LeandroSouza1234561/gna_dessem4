"""
GNA I & II — Coleta pdo_oper_titulacao_usinas.dat — ONS/SINTEGRE
Roda via GitHub Actions a cada 5 minutos
"""

import json
import logging
import os
import re
import time
import zipfile
import io
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ONS_USER = os.environ.get("ONS_USER", "")
ONS_PASS = os.environ.get("ONS_PASS", "")

URL_PORTAL    = "https://pops.ons.org.br/"
URL_HISTORICO = "https://sintegre.ons.org.br/sites/9/51//paginas/servicos/historico-de-produtos.aspx?produto=Decks%20de%20entrada%20e%20sa%C3%ADda%20-%20Modelo%20DESSEM"

ARQUIVO_DAT  = "pdo_oper_titulacao_usinas.dat"
PLANTAS_ALVO = ["GNA I", "GNA II", "GNA 1", "GNA 2", "GNAI", "GNAII", "UTE GNA"]

DOCS_DIR  = Path(__file__).parent / "docs"
JSON_FILE = DOCS_DIR / "dados_gna.json"
RAW_FILE  = DOCS_DIR / "pdo_oper_titulacao_usinas.dat"
DOCS_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GNA-DAT")


def fazer_login(page):
    log.info("Acessando portal ONS...")
    page.goto(URL_PORTAL, wait_until="domcontentloaded")
    time.sleep(3)
    if "sso.ons.org.br" in page.url or "login" in page.url.lower():
        _preencher_credenciais(page)
    try:
        page.wait_for_url("**/pops.ons.org.br/**", timeout=40000)
        log.info("Autenticado no portal.")
    except PWTimeout:
        log.warning("Timeout redirecionamento.")
    time.sleep(2)


def _preencher_credenciais(page):
    for sel in ["input[name='username']", "input[id='username']", "input[type='email']", "#i0116"]:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=8000)
            el.fill(ONS_USER)
            log.info(f"Usuario preenchido via {sel}")
            break
        except Exception:
            continue
    for sel in ["#idSIButton9", "button:has-text('Next')", "button:has-text('Proximo')"]:
        try:
            page.locator(sel).first.click(timeout=3000)
            time.sleep(1)
            break
        except Exception:
            continue
    for sel in ["input[name='password']", "input[id='password']", "input[type='password']", "#i0118"]:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=10000)
            el.fill(ONS_PASS)
            log.info(f"Senha preenchida via {sel}")
            break
        except Exception:
            continue
    for sel in ["button[type='submit']", "input[type='submit']", "button:has-text('Entrar')", "#idSIButton9"]:
        try:
            page.locator(sel).first.click(timeout=5000)
            log.info("Botao login clicado.")
            break
        except Exception:
            continue
    time.sleep(2)


def encontrar_zip_mais_recente(page):
    log.info(f"Acessando historico: {URL_HISTORICO}")
    page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
    time.sleep(4)

    links_zip = page.locator("a[href*='.zip'], a[href*='download.aspx']").all()
    log.info(f"Encontrados {len(links_zip)} links de download.")

    urls_zip = []
    for link in links_zip:
        href = link.get_attribute("href") or ""
        if ".zip" in href.lower() or "download.aspx" in href.lower():
            if not href.startswith("http"):
                href = "https://sintegre.ons.org.br" + href
            urls_zip.append(href)
            log.info(f"  ZIP: {href}")

    return urls_zip[0] if urls_zip else None


def baixar_zip_e_extrair_dat(page, url_zip):
    log.info(f"Baixando ZIP: {url_zip}")

    resultado = page.evaluate(f"""
        async () => {{
            try {{
                const resp = await fetch('{url_zip}', {{
                    credentials: 'include',
                    headers: {{ 'Accept': '*/*' }}
                }});
                if (!resp.ok) return {{ erro: 'HTTP ' + resp.status }};
                const buffer = await resp.arrayBuffer();
                const bytes = Array.from(new Uint8Array(buffer));
                return {{ bytes: bytes }};
            }} catch(e) {{
                return {{ erro: e.toString() }};
            }}
        }}
    """)

    if not resultado or "erro" in resultado:
        log.error(f"Erro ao baixar ZIP: {resultado}")
        return None

    zip_bytes = bytes(resultado["bytes"])
    log.info(f"ZIP baixado: {len(zip_bytes)} bytes")

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            arquivos = zf.namelist()
            log.info(f"Arquivos no ZIP: {arquivos}")

            dat_encontrado = None
            for nome in arquivos:
                if ARQUIVO_DAT.lower() in nome.lower() or "pdo_oper" in nome.lower():
                    dat_encontrado = nome
                    break
            if not dat_encontrado:
                for nome in arquivos:
                    if nome.lower().endswith(".dat"):
                        dat_encontrado = nome
                        break

            if not dat_encontrado:
                log.error(f"DAT nao encontrado no ZIP: {arquivos}")
                return None

            log.info(f"Extraindo: {dat_encontrado}")
            conteudo = zf.read(dat_encontrado).decode("latin-1", errors="replace")
            log.info(f"Arquivo extraido: {len(conteudo)} chars")
            return conteudo
    except Exception as e:
        log.error(f"Erro descompactar: {e}")
        return None


def parsear_dat(conteudo):
    linhas = conteudo.splitlines()
    log.info(f"Arquivo tem {len(linhas)} linhas")

    cabecalho_idx = None
    cabecalho_raw = ""
    colunas = []

    for i, linha in enumerate(linhas):
        if linha.strip().startswith(("&", "%", "/")):
            continue
        if re.search(r'\b(NOME|USINA|USINAMED|NOMEUSINA|IUSI|NUM|CODNOME)\b', linha, re.I):
            cabecalho_idx = i
            cabecalho_raw = linha
            colunas = linha.split()
            log.info(f"Cabecalho linha {i}: {colunas}")
            break

    if not colunas:
        max_campos = 0
        for i, linha in enumerate(linhas[:80]):
            if linha.strip().startswith(("&", "%", "/")):
                continue
            campos = linha.split()
            if len(campos) > max_campos:
                max_campos = len(campos)
                cabecalho_idx = i
                cabecalho_raw = linha
                colunas = campos

    registros_gna = []
    if cabecalho_idx is not None:
        for linha in linhas[cabecalho_idx + 1:]:
            linha = linha.rstrip()
            if not linha or linha.strip().startswith(("&", "%", "/")):
                continue
            campos = linha.split()
            if not campos:
                continue

            linha_str = " ".join(campos).upper()
            planta_id = None
            for planta in PLANTAS_ALVO:
                if planta.upper() in linha_str:
                    planta_id = "GNA II" if ("II" in planta or "2" in planta) else "GNA I"
                    break

            if not planta_id:
                continue

            registro = {"planta_id": planta_id}
            for j, col in enumerate(colunas):
                registro[col] = _parse_valor(campos[j]) if j < len(campos) else None
            for j in range(len(colunas), len(campos)):
                registro[f"col_{j}"] = _parse_valor(campos[j])

            registros_gna.append(registro)
            log.info(f"  -> {planta_id}: {registro}")

    return {
        "colunas": colunas,
        "registros": registros_gna,
        "raw_header": cabecalho_raw,
        "total_linhas_arquivo": len(linhas),
        "total_registros_gna": len(registros_gna),
    }


def _parse_valor(texto):
    if not texto or texto in ["-", "N/A", "*", ""]:
        return None
    try:
        return int(texto)
    except ValueError:
        pass
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return texto


def salvar_resultado(conteudo_raw, dados):
    ts = datetime.now(timezone.utc).isoformat()
    if conteudo_raw:
        RAW_FILE.write_text(conteudo_raw, encoding="utf-8", errors="replace")
    historico = []
    if JSON_FILE.exists():
        try:
            historico = json.loads(JSON_FILE.read_text(encoding="utf-8")).get("historico", [])
        except Exception:
            pass
    historico.append({"timestamp": ts, "colunas": dados["colunas"],
                      "registros": dados["registros"], "total": dados["total_registros_gna"]})
    historico = historico[-288:]
    saida = {
        "ultima_coleta": ts,
        "status": "ok" if dados["registros"] else "sem_dados",
        "arquivo": ARQUIVO_DAT,
        "colunas": dados["colunas"],
        "raw_header": dados["raw_header"],
        "total_linhas_arquivo": dados["total_linhas_arquivo"],
        "registros": dados["registros"],
        "total_registros_gna": dados["total_registros_gna"],
        "historico": historico,
    }
    JSON_FILE.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"JSON salvo: {dados['total_registros_gna']} registros GNA")
    return saida


def main():
    if not ONS_PASS:
        log.error("ONS_PASS nao definido!")
        erro = {"ultima_coleta": datetime.now(timezone.utc).isoformat(),
                "status": "erro_credencial", "colunas": [], "registros": [], "historico": []}
        JSON_FILE.write_text(json.dumps(erro, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            locale="pt-BR",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        try:
            fazer_login(page)
            url_zip = encontrar_zip_mais_recente(page)
            if not url_zip:
                log.error("ZIP nao encontrado.")
                salvar_resultado("", {"colunas": [], "registros": [], "raw_header": "",
                                      "total_linhas_arquivo": 0, "total_registros_gna": 0})
                return 1
            conteudo_raw = baixar_zip_e_extrair_dat(page, url_zip)
            if not conteudo_raw:
                log.error("Nao foi possivel extrair o .dat.")
                salvar_resultado("", {"colunas": [], "registros": [], "raw_header": "",
                                      "total_linhas_arquivo": 0, "total_registros_gna": 0})
                return 1
            dados = parsear_dat(conteudo_raw)
            salvar_resultado(conteudo_raw, dados)
            log.info(f"Concluido: {dados['total_registros_gna']} registros GNA.")
            return 0
        except Exception as e:
            log.error(f"Erro fatal: {e}", exc_info=True)
            return 1
        finally:
            browser.close()


if __name__ == "__main__":
    exit(main())
