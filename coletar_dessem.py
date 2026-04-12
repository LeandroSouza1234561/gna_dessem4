import json, logging, os, re, time, zipfile, io, tempfile
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ONS_USER = os.environ.get("ONS_USER", "")
ONS_PASS = os.environ.get("ONS_PASS", "")
URL_HISTORICO = "https://sintegre.ons.org.br/sites/9/51//paginas/servicos/historico-de-produtos.aspx?produto=Decks%20de%20entrada%20e%20sa%C3%ADda%20-%20Modelo%20DESSEM"

ARQUIVOS_DAT = {
    "pdo_oper_titulacao_usinas.dat": {"col_nome": 2},
    "pdo_term.dat":                  {"col_nome": 3},
}
PLANTAS_ALVO = ["GNA I","GNA II","GNA 1","GNA 2","GNAI","GNAII","UTE GNA"]
DOCS_DIR  = Path(__file__).parent / "docs"
JSON_FILE = DOCS_DIR / "dados_gna.json"
DOCS_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GNA-DAT")

def fazer_login_keycloak(page):
    log.info(f"Login Keycloak. URL: {page.url}")
    try:
        campo_user = page.locator("#username, input[name='username'], input[type='text']").first
        campo_user.wait_for(timeout=15000)
        campo_user.fill(ONS_USER)
        time.sleep(1)
        campo_pass = page.locator("#password, input[name='password'], input[type='password']").first
        campo_pass.wait_for(timeout=10000)
        campo_pass.fill(ONS_PASS)
        time.sleep(1)
        botao = page.locator("#kc-login, input[type='submit'], button[type='submit']").first
        botao.click()
        page.wait_for_function(
            "() => !window.location.href.includes('sso.ons.org.br')",
            timeout=60000
        )
        log.info(f"Autenticado! URL: {page.url}")
        time.sleep(3)
        return True
    except Exception as e:
        log.error(f"Erro login: {e}")
        return False

def login_e_baixar(tmpdir):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"])
        context = browser.new_context(
            viewport={"width":1600,"height":900}, locale="pt-BR",
            accept_downloads=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            log.info("Acessando historico SINTEGRE...")
            page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            if "sso.ons.org.br" in page.url:
                ok = fazer_login_keycloak(page)
                if not ok: return None
                if "historico-de-produtos" not in page.url:
                    page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(4)
            log.info(f"Pagina: {page.title()}")
            botoes = page.locator("a:has-text('Baixar'), button:has-text('Baixar')").all()
            log.info(f"Botoes Baixar: {len(botoes)}")
            if not botoes:
                log.error("Botao nao encontrado.")
                return None
            with page.expect_download(timeout=120000) as dl:
                botoes[0].click()
            download = dl.value
            zip_path = Path(tmpdir) / "deck.zip"
            download.save_as(zip_path)
            log.info(f"ZIP: {zip_path.stat().st_size} bytes")
            return zip_path
        except Exception as e:
            log.error(f"Erro: {e}", exc_info=True)
            return None
        finally:
            browser.close()

def extrair_arquivos(zip_path):
    resultados = {}
    try:
        with zipfile.ZipFile(zip_path) as zf:
            arquivos_zip = zf.namelist()
            log.info(f"ZIP: {len(arquivos_zip)} arquivos")
            for nome_alvo in ARQUIVOS_DAT:
                encontrado = next((n for n in arquivos_zip if nome_alvo.lower() in n.lower()), None)
                if encontrado:
                    conteudo = zf.read(encontrado).decode("latin-1", errors="replace")
                    resultados[nome_alvo] = conteudo
                    log.info(f"Extraido: {encontrado} ({len(conteudo)} chars)")
                else:
                    log.warning(f"Nao encontrado: {nome_alvo}")
    except Exception as e:
        log.error(f"Erro ZIP: {e}")
    return resultados

def parsear_dat(conteudo, col_nome=2):
    linhas = conteudo.splitlines()
    log.info(f"Total linhas: {len(linhas)}")
    cab_idx, cab_raw, colunas = None, "", []

    for i, linha in enumerate(linhas):
        # Pula separadores e comentarios
        if linha.strip().startswith(("-","&","%","/")):
            continue
        # Pula linhas de descricao tipo "IPER: Indice do periodo."
        if re.search(r'IPER\s*:', linha, re.I):
            continue
        # Cabecalho real: tem IPER + ; + pelo menos 3 campos
        if re.search(r'\bIPER\b', linha, re.I) and ";" in linha:
            partes = [c.strip() for c in linha.split(";") if c.strip()]
            if len(partes) >= 3:
                cab_idx = i
                cab_raw = linha
                colunas = partes
                log.info(f"Cabecalho linha {i}: {colunas}")
                break

    if cab_idx is None:
        log.warning("Cabecalho nao encontrado!")
        return {"colunas":[],"registros":[],"raw_header":"",
                "total_linhas_arquivo":len(linhas),"total_registros_gna":0}

    registros = []
    for linha in linhas[cab_idx+1:]:
        linha = linha.rstrip()
        if not linha or linha.strip().startswith(("-","&","%","/")):
            continue
        campos = [c.strip() for c in linha.split(";")]
        if len(campos) <= col_nome:
            continue
        nome_usina = campos[col_nome].upper()
        planta_id = None
        if "GNA" in nome_usina:
            planta_id = "GNA II" if ("II" in nome_usina or " 2" in nome_usina) else "GNA I"
        if not planta_id:
            continue
        reg = {"planta_id": planta_id}
        for j, col in enumerate(colunas):
            reg[col] = _parse(campos[j]) if j < len(campos) else None
        registros.append(reg)
        log.info(f"  -> {planta_id}: {reg}")

    log.info(f"Total GNA: {len(registros)}")
    return {"colunas":colunas,"registros":registros,"raw_header":cab_raw,
            "total_linhas_arquivo":len(linhas),"total_registros_gna":len(registros)}

def _parse(t):
    if not t or t in ["-","N/A","*",""]: return None
    try: return int(t)
    except: pass
    try: return float(t.replace(",","."))
    except: return t

def salvar(dados_por_arquivo):
    ts = datetime.now(timezone.utc).isoformat()

    for nome, conteudo in dados_por_arquivo.items():
        if conteudo:
            raw_path = DOCS_DIR / nome
            raw_path.write_text(conteudo, encoding="utf-8", errors="replace")

    hist = []
    if JSON_FILE.exists():
        try: hist = json.loads(JSON_FILE.read_text()).get("historico", [])
        except: pass

    dados_parseados = {}
    for nome_arquivo, cfg in ARQUIVOS_DAT.items():
        conteudo = dados_por_arquivo.get(nome_arquivo, "")
        if conteudo:
            dados_parseados[nome_arquivo] = parsear_dat(conteudo, cfg["col_nome"])
        else:
            dados_parseados[nome_arquivo] = {"colunas":[],"registros":[],"raw_header":"",
                                              "total_linhas_arquivo":0,"total_registros_gna":0}

    principal = dados_parseados.get("pdo_oper_titulacao_usinas.dat", {})
    pdo_term  = dados_parseados.get("pdo_term.dat", {})

    snapshot = {
        "timestamp": ts,
        "colunas": principal.get("colunas", []),
        "registros": principal.get("registros", []),
        "total": principal.get("total_registros_gna", 0),
        "pdo_term": {
            "colunas": pdo_term.get("colunas", []),
            "registros": pdo_term.get("registros", []),
            "total": pdo_term.get("total_registros_gna", 0),
        }
    }
    hist.append(snapshot)
    hist = hist[-288:]

    saida = {
        "ultima_coleta": ts,
        "status": "ok" if principal.get("registros") or pdo_term.get("registros") else "sem_dados",
        "colunas": principal.get("colunas", []),
        "raw_header": principal.get("raw_header", ""),
        "total_linhas_arquivo": principal.get("total_linhas_arquivo", 0),
        "registros": principal.get("registros", []),
        "total_registros_gna": principal.get("total_registros_gna", 0),
        "pdo_term": {
            "colunas": pdo_term.get("colunas", []),
            "raw_header": pdo_term.get("raw_header", ""),
            "total_linhas_arquivo": pdo_term.get("total_linhas_arquivo", 0),
            "registros": pdo_term.get("registros", []),
            "total_registros_gna": pdo_term.get("total_registros_gna", 0),
        },
        "historico": hist,
    }
    JSON_FILE.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Salvo: {principal.get('total_registros_gna',0)} titulacao + {pdo_term.get('total_registros_gna',0)} term")
    return saida

def main():
    if not ONS_PASS:
        log.error("ONS_PASS nao definido!"); return 1
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = login_e_baixar(tmpdir)
        if not zip_path:
            salvar({})
            return 1
        dados_raw = extrair_arquivos(zip_path)
        if not dados_raw:
            log.error("Nenhum arquivo extraido.")
            salvar({})
            return 1
        salvar(dados_raw)
        log.info("Concluido!")
        return 0

if __name__ == "__main__":
    exit(main())
