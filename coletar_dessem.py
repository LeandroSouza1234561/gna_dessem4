"""
GNA I & II — Coleta pdo_oper_titulacao_usinas.dat — ONS/SINTEGRE
"""
import json, logging, os, re, time, zipfile, io
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ONS_USER = os.environ.get("ONS_USER", "")
ONS_PASS = os.environ.get("ONS_PASS", "")
URL_PORTAL    = "https://pops.ons.org.br/"
URL_HISTORICO = "https://sintegre.ons.org.br/sites/9/51//paginas/servicos/historico-de-produtos.aspx?produto=Decks%20de%20entrada%20e%20sa%C3%ADda%20-%20Modelo%20DESSEM"
BASE_DOWNLOAD = "https://sintegre.ons.org.br/sites/9/51/_layouts/download.aspx?SourceUrl=/sites/9/51/Produtos/277/"
ARQUIVO_DAT   = "pdo_oper_titulacao_usinas.dat"
PLANTAS_ALVO  = ["GNA I","GNA II","GNA 1","GNA 2","GNAI","GNAII","UTE GNA"]
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
        log.info("Autenticado.")
    except PWTimeout:
        log.warning("Timeout login.")
    time.sleep(2)

def _preencher_credenciais(page):
    for sel in ["input[name='username']","input[type='email']","#i0116"]:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=8000)
            el.fill(ONS_USER)
            break
        except: continue
    for sel in ["#idSIButton9","button:has-text('Next')"]:
        try: page.locator(sel).first.click(timeout=3000); time.sleep(1); break
        except: continue
    for sel in ["input[name='password']","input[type='password']","#i0118"]:
        try:
            el = page.locator(sel).first
            el.wait_for(timeout=10000)
            el.fill(ONS_PASS)
            break
        except: continue
    for sel in ["button[type='submit']","button:has-text('Entrar')","#idSIButton9"]:
        try: page.locator(sel).first.click(timeout=5000); break
        except: continue
    time.sleep(2)

def encontrar_nome_zip(page):
    """Acessa o historico e extrai o nome do ZIP mais recente via XHR."""
    log.info("Acessando historico SINTEGRE...")
    page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
    time.sleep(4)

    # Extrai nomes de ZIP do conteúdo da página
    conteudo = page.content()
    zips = re.findall(r'DS_ONS_\d+_RV\d+D\d+\.zip', conteudo)
    if zips:
        log.info(f"ZIPs encontrados: {zips}")
        return zips[0]

    # Tenta via texto visível
    texto = page.inner_text("body")
    zips = re.findall(r'DS_ONS_\d+_RV\d+D\d+\.zip', texto)
    if zips:
        log.info(f"ZIPs no texto: {zips}")
        return zips[0]

    # Tenta via XHR (os dados vêm de chamadas getitems)
    nome = page.evaluate("""
        () => {
            const links = document.querySelectorAll('a[href*=".zip"], a[href*="download"]');
            for (const l of links) {
                const h = l.href || l.getAttribute('href') || '';
                const m = h.match(/DS_ONS_\\d+_RV\\d+D\\d+\\.zip/);
                if (m) return m[0];
            }
            // Tenta encontrar no HTML completo
            const m = document.body.innerHTML.match(/DS_ONS_\\d+_RV\\d+D\\d+\\.zip/);
            return m ? m[0] : null;
        }
    """)
    if nome:
        log.info(f"ZIP via JS: {nome}")
        return nome

    log.warning("ZIP nao encontrado na pagina.")
    return None

def baixar_zip(page, nome_zip):
    """Baixa o ZIP usando a URL de download direto."""
    url = BASE_DOWNLOAD + nome_zip
    log.info(f"Baixando: {url}")
    resultado = page.evaluate(f"""
        async () => {{
            try {{
                const resp = await fetch('{url}', {{credentials:'include', redirect:'follow'}});
                if (!resp.ok) return {{erro: 'HTTP '+resp.status}};
                const buf = await resp.arrayBuffer();
                return {{bytes: Array.from(new Uint8Array(buf))}};
            }} catch(e) {{ return {{erro: e.toString()}}; }}
        }}
    """)
    if not resultado or "erro" in resultado:
        log.error(f"Erro download: {resultado}")
        return None
    zip_bytes = bytes(resultado["bytes"])
    log.info(f"ZIP: {len(zip_bytes)} bytes")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            arquivos = zf.namelist()
            log.info(f"Conteudo ZIP: {arquivos}")
            dat = next((n for n in arquivos if ARQUIVO_DAT.lower() in n.lower()), None)
            if not dat:
                dat = next((n for n in arquivos if "pdo_oper" in n.lower()), None)
            if not dat:
                dat = next((n for n in arquivos if n.lower().endswith(".dat")), None)
            if not dat:
                log.error(f"DAT nao encontrado: {arquivos}")
                return None
            log.info(f"Extraindo: {dat}")
            return zf.read(dat).decode("latin-1", errors="replace")
    except Exception as e:
        log.error(f"Erro ZIP: {e}")
        return None

def parsear_dat(conteudo):
    linhas = conteudo.splitlines()
    log.info(f"Linhas: {len(linhas)}")
    cab_idx, cab_raw, colunas = None, "", []
    for i, linha in enumerate(linhas):
        if linha.strip().startswith(("&","%","/")):
            continue
        if re.search(r'\b(NOME|USINA|USINAMED|IUSI|NUM|CODNOME)\b', linha, re.I):
            cab_idx, cab_raw, colunas = i, linha, linha.split()
            log.info(f"Cabecalho linha {i}: {colunas}")
            break
    if not colunas:
        max_c = 0
        for i, linha in enumerate(linhas[:80]):
            if linha.strip().startswith(("&","%","/")):
                continue
            c = linha.split()
            if len(c) > max_c:
                max_c, cab_idx, cab_raw, colunas = len(c), i, linha, c
    registros = []
    if cab_idx is not None:
        for linha in linhas[cab_idx+1:]:
            linha = linha.rstrip()
            if not linha or linha.strip().startswith(("&","%","/")):
                continue
            campos = linha.split()
            if not campos: continue
            s = " ".join(campos).upper()
            planta_id = None
            for p in PLANTAS_ALVO:
                if p.upper() in s:
                    planta_id = "GNA II" if ("II" in p or "2" in p) else "GNA I"
                    break
            if not planta_id: continue
            reg = {"planta_id": planta_id}
            for j, col in enumerate(colunas):
                reg[col] = _parse(campos[j]) if j < len(campos) else None
            for j in range(len(colunas), len(campos)):
                reg[f"col_{j}"] = _parse(campos[j])
            registros.append(reg)
            log.info(f"  -> {planta_id}: {reg}")
    return {"colunas": colunas, "registros": registros, "raw_header": cab_raw,
            "total_linhas_arquivo": len(linhas), "total_registros_gna": len(registros)}

def _parse(t):
    if not t or t in ["-","N/A","*",""]: return None
    try: return int(t)
    except: pass
    try: return float(t.replace(",","."))
    except: return t

def salvar(raw, dados):
    ts = datetime.now(timezone.utc).isoformat()
    if raw: RAW_FILE.write_text(raw, encoding="utf-8", errors="replace")
    hist = []
    if JSON_FILE.exists():
        try: hist = json.loads(JSON_FILE.read_text()).get("historico", [])
        except: pass
    hist.append({"timestamp": ts, "colunas": dados["colunas"],
                 "registros": dados["registros"], "total": dados["total_registros_gna"]})
    hist = hist[-288:]
    saida = {"ultima_coleta": ts, "status": "ok" if dados["registros"] else "sem_dados",
             "arquivo": ARQUIVO_DAT, "colunas": dados["colunas"], "raw_header": dados["raw_header"],
             "total_linhas_arquivo": dados["total_linhas_arquivo"],
             "registros": dados["registros"], "total_registros_gna": dados["total_registros_gna"],
             "historico": hist}
    JSON_FILE.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Salvo: {dados['total_registros_gna']} registros")
    return saida

def main():
    if not ONS_PASS:
        log.error("ONS_PASS nao definido!")
        JSON_FILE.write_text(json.dumps({"ultima_coleta": datetime.now(timezone.utc).isoformat(),
            "status":"erro_credencial","colunas":[],"registros":[],"historico":[]}), encoding="utf-8")
        return 1
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"])
        page = browser.new_context(
            viewport={"width":1600,"height":900}, locale="pt-BR",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ).new_page()
        try:
            fazer_login(page)
            nome_zip = encontrar_nome_zip(page)
            if not nome_zip:
                log.error("ZIP nao encontrado.")
                salvar("", {"colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":0,"total_registros_gna":0})
                return 1
            raw = baixar_zip(page, nome_zip)
            if not raw:
                log.error("Falha ao extrair DAT.")
                salvar("", {"colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":0,"total_registros_gna":0})
                return 1
            dados = parsear_dat(raw)
            salvar(raw, dados)
            log.info(f"Concluido: {dados['total_registros_gna']} registros.")
            return 0
        except Exception as e:
            log.error(f"Erro: {e}", exc_info=True)
            return 1
        finally:
            browser.close()

if __name__ == "__main__":
    exit(main())
