import json, logging, os, re, time, zipfile, io, tempfile
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ONS_USER = os.environ.get("ONS_USER", "")
ONS_PASS = os.environ.get("ONS_PASS", "")
URL_HISTORICO = "https://sintegre.ons.org.br/sites/9/51//paginas/servicos/historico-de-produtos.aspx?produto=Decks%20de%20entrada%20e%20sa%C3%ADda%20-%20Modelo%20DESSEM"
ARQUIVO_DAT  = "pdo_oper_titulacao_usinas.dat"
DOCS_DIR  = Path(__file__).parent / "docs"
JSON_FILE = DOCS_DIR / "dados_gna.json"
RAW_FILE  = DOCS_DIR / "pdo_oper_titulacao_usinas.dat"
DOCS_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GNA-DAT")

def fazer_login_keycloak(page):
    """Login no SSO Keycloak da ONS."""
    log.info(f"Login Keycloak. URL: {page.url}")
    try:
        # Keycloak usa id="username" e id="password"
        campo_user = page.locator("#username, input[name='username'], input[type='text']").first
        campo_user.wait_for(timeout=15000)
        campo_user.fill(ONS_USER)
        log.info("Usuario preenchido.")
        time.sleep(1)

        campo_pass = page.locator("#password, input[name='password'], input[type='password']").first
        campo_pass.wait_for(timeout=10000)
        campo_pass.fill(ONS_PASS)
        log.info("Senha preenchida.")
        time.sleep(1)

        # Botao login do Keycloak
        botao = page.locator("#kc-login, input[type='submit'], button[type='submit']").first
        botao.click()
        log.info("Login submetido.")

        # Aguarda sair do SSO
        page.wait_for_function(
            "() => !window.location.href.includes('sso.ons.org.br')",
            timeout=60000
        )
        log.info(f"Autenticado! URL: {page.url}")
        time.sleep(3)
        return True

    except Exception as e:
        log.error(f"Erro login Keycloak: {e}")
        log.info(f"URL atual: {page.url}")
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
            log.info(f"URL inicial: {page.url}")

            # Se redirecionou para SSO/Keycloak
            if "sso.ons.org.br" in page.url:
                ok = fazer_login_keycloak(page)
                if not ok:
                    return None
                # Navega de volta para o historico
                if "historico-de-produtos" not in page.url:
                    log.info("Voltando ao historico...")
                    page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(4)

            log.info(f"Pagina final: {page.title()} | {page.url}")

            # Procura botao Baixar
            botoes = page.locator("a:has-text('Baixar'), button:has-text('Baixar')").all()
            log.info(f"Botoes Baixar: {len(botoes)}")

            if not botoes:
                log.error("Botao nao encontrado.")
                log.info(f"HTML preview: {page.content()[:800]}")
                return None

            with page.expect_download(timeout=120000) as dl:
                botoes[0].click()
                log.info("Clicou Baixar!")

            download = dl.value
            zip_path = Path(tmpdir) / "deck.zip"
            download.save_as(zip_path)
            log.info(f"ZIP salvo: {zip_path.stat().st_size} bytes")
            return zip_path

        except Exception as e:
            log.error(f"Erro: {e}", exc_info=True)
            return None
        finally:
            browser.close()

def extrair_dat(zip_path):
    try:
        with zipfile.ZipFile(zip_path) as zf:
            arquivos = zf.namelist()
            log.info(f"ZIP conteudo: {arquivos}")
            dat = next((n for n in arquivos if ARQUIVO_DAT.lower() in n.lower()), None)
            if not dat: dat = next((n for n in arquivos if "pdo_oper" in n.lower()), None)
            if not dat: dat = next((n for n in arquivos if n.lower().endswith(".dat")), None)
            if not dat: return None
            log.info(f"Extraindo: {dat}")
            return zf.read(dat).decode("latin-1", errors="replace")
    except Exception as e:
        log.error(f"Erro ZIP: {e}"); return None

def parsear_dat(conteudo):
    linhas = conteudo.splitlines()
    log.info(f"Total linhas: {len(linhas)}")
    cab_idx, cab_raw, colunas = None, "", []
    for i, linha in enumerate(linhas):
        if re.search(r'\bIPER\b', linha, re.I) and re.search(r'\bUsit\b|\bNome\b', linha, re.I):
            cab_idx = i
            cab_raw = linha
            colunas = [c.strip() for c in linha.split(";") if c.strip()]
            log.info(f"Cabecalho linha {i}: {colunas}")
            break
    if cab_idx is None:
        log.warning("Cabecalho nao encontrado!")
        return {"colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":len(linhas),"total_registros_gna":0}
    registros = []
    for linha in linhas[cab_idx+1:]:
        linha = linha.rstrip()
        if not linha or linha.strip().startswith(("-","&","%","/")):
            continue
        campos = [c.strip() for c in linha.split(";")]
        if len(campos) < 3: continue
        nome_usina = campos[2].upper() if len(campos) > 2 else ""
        planta_id = None
        if "GNA" in nome_usina:
            planta_id = "GNA II" if ("II" in nome_usina or " 2" in nome_usina) else "GNA I"
        if not planta_id: continue
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

def salvar(raw, dados):
    ts = datetime.now(timezone.utc).isoformat()
    if raw: RAW_FILE.write_text(raw, encoding="utf-8", errors="replace")
    hist = []
    if JSON_FILE.exists():
        try: hist = json.loads(JSON_FILE.read_text()).get("historico", [])
        except: pass
    hist.append({"timestamp":ts,"colunas":dados["colunas"],"registros":dados["registros"],"total":dados["total_registros_gna"]})
    saida = {"ultima_coleta":ts,"status":"ok" if dados["registros"] else "sem_dados",
             "arquivo":ARQUIVO_DAT,"colunas":dados["colunas"],"raw_header":dados["raw_header"],
             "total_linhas_arquivo":dados["total_linhas_arquivo"],"registros":dados["registros"],
             "total_registros_gna":dados["total_registros_gna"],"historico":hist[-288:]}
    JSON_FILE.write_text(json.dumps(saida,ensure_ascii=False,indent=2),encoding="utf-8")
    log.info(f"Salvo: {dados['total_registros_gna']} registros")

def main():
    if not ONS_PASS:
        log.error("ONS_PASS nao definido!"); return 1
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = login_e_baixar(tmpdir)
        if not zip_path:
            salvar("",{"colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":0,"total_registros_gna":0})
            return 1
        raw = extrair_dat(zip_path)
        if not raw:
            salvar("",{"colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":0,"total_registros_gna":0})
            return 1
        dados = parsear_dat(raw)
        salvar(raw, dados)
        log.info(f"Concluido: {dados['total_registros_gna']} registros.")
        return 0

if __name__ == "__main__":
    exit(main())
