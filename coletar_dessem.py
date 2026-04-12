import json, logging, os, re, time, zipfile, io, tempfile
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ONS_USER = os.environ.get("ONS_USER", "")
ONS_PASS = os.environ.get("ONS_PASS", "")
URL_HISTORICO = "https://sintegre.ons.org.br/sites/9/51//paginas/servicos/historico-de-produtos.aspx?produto=Decks%20de%20entrada%20e%20sa%C3%ADda%20-%20Modelo%20DESSEM"
ARQUIVO_DAT  = "pdo_oper_titulacao_usinas.dat"
PLANTAS_ALVO = ["GNA I","GNA II","GNA 1","GNA 2","GNAI","GNAII","UTE GNA"]
DOCS_DIR  = Path(__file__).parent / "docs"
JSON_FILE = DOCS_DIR / "dados_gna.json"
RAW_FILE  = DOCS_DIR / "pdo_oper_titulacao_usinas.dat"
DOCS_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GNA-DAT")

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
            # Vai direto para o historico — o SSO vai interceptar e pedir login
            log.info("Acessando historico SINTEGRE...")
            page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            log.info(f"URL apos goto: {page.url}")

            # Se redirecionou para SSO, faz login
            if "sso.ons.org.br" in page.url or "login" in page.url.lower():
                log.info("Fazendo login SSO...")
                # Usuario
                for sel in ["input[name='username']","input[type='email']","#i0116"]:
                    try:
                        el = page.locator(sel).first
                        el.wait_for(timeout=8000)
                        el.fill(ONS_USER)
                        log.info(f"Usuario via {sel}")
                        break
                    except: continue
                # Botao next se existir
                for sel in ["#idSIButton9","button:has-text('Next')"]:
                    try: page.locator(sel).first.click(timeout=3000); time.sleep(1); break
                    except: continue
                # Senha
                for sel in ["input[name='password']","input[type='password']","#i0118"]:
                    try:
                        el = page.locator(sel).first
                        el.wait_for(timeout=10000)
                        el.fill(ONS_PASS)
                        log.info("Senha preenchida.")
                        break
                    except: continue
                # Submit
                for sel in ["button[type='submit']","button:has-text('Entrar')","#idSIButton9","input[type='submit']"]:
                    try: page.locator(sel).first.click(timeout=5000); log.info("Login clicado."); break
                    except: continue
                # Aguarda voltar para SINTEGRE
                log.info("Aguardando autenticacao...")
                try:
                    page.wait_for_url("**/sintegre.ons.org.br/**", timeout=60000)
                    log.info("Autenticado no SINTEGRE!")
                except PWTimeout:
                    log.warning(f"Timeout SSO. URL atual: {page.url}")
                time.sleep(3)

            log.info(f"URL final: {page.url}")

            # Navega para o historico se ainda nao estiver la
            if "historico-de-produtos" not in page.url:
                log.info("Navegando para historico...")
                page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
                time.sleep(4)

            log.info(f"URL historico: {page.url}")
            log.info(f"Titulo: {page.title()}")

            # Clica no primeiro botao Baixar
            log.info("Procurando botao Baixar...")
            botoes = page.locator("a:has-text('Baixar'), button:has-text('Baixar')").all()
            log.info(f"Botoes encontrados: {len(botoes)}")

            if not botoes:
                # Loga HTML para debug
                html = page.content()
                log.info(f"HTML preview: {html[:500]}")
                return None

            with page.expect_download(timeout=120000) as dl:
                botoes[0].click()
                log.info("Clicou em Baixar!")

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
    saida = {"ultima_coleta": ts, "status": "ok" if dados["registros"] else "sem_dados",
             "arquivo": ARQUIVO_DAT, "colunas": dados["colunas"], "raw_header": dados["raw_header"],
             "total_linhas_arquivo": dados["total_linhas_arquivo"],
             "registros": dados["registros"], "total_registros_gna": dados["total_registros_gna"],
             "historico": hist[-288:]}
    JSON_FILE.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Salvo: {dados['total_registros_gna']} registros")

def main():
    if not ONS_PASS:
        log.error("ONS_PASS nao definido!"); return 1
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = login_e_baixar(tmpdir)
        if not zip_path:
            salvar("", {"colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":0,"total_registros_gna":0})
            return 1
        raw = extrair_dat(zip_path)
        if not raw:
            salvar("", {"colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":0,"total_registros_gna":0})
            return 1
        dados = parsear_dat(raw)
        salvar(raw, dados)
        log.info(f"Concluido: {dados['total_registros_gna']} registros.")
        return 0

if __name__ == "__main__":
    exit(main())
