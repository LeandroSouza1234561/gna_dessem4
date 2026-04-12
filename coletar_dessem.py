import json, logging, os, re, time, zipfile, io, tempfile, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ONS_USER   = os.environ.get("ONS_USER", "")
ONS_PASS   = os.environ.get("ONS_PASS", "")
EMAIL_PASS = os.environ.get("EMAIL_PASS", "")
EMAIL_FROM = "leandro.souza@gna.com.br"
EMAIL_TO   = "leandro.souza@gna.com.br"
SMTP_HOST  = "smtp.office365.com"
SMTP_PORT  = 587

URL_HISTORICO = "https://sintegre.ons.org.br/sites/9/51//paginas/servicos/historico-de-produtos.aspx?produto=Decks%20de%20entrada%20e%20sa%C3%ADda%20-%20Modelo%20DESSEM"
URL_PDPW      = "https://pdpw.ons.org.br/pdp/frmCnsObservacoes.aspx"

ARQUIVO_DAT = "pdo_oper_term.dat"

FILTRO_GNA = {
    "GNA I":  {"usit": "137", "numbarra": "53"},
    "GNA II": {"usit": "238", "numbarra": "44327"},
}

COLUNAS_EXIBIR = ["USIT", "Nome Usit", "NomeSist", "NumBarra", "GTER", "ClinGter", "CMO", "CMB"]
COLUNAS_ALERTA = ["GTER", "ClinGter", "CMO", "CMB"]

DOCS_DIR  = Path(__file__).parent / "docs"
JSON_FILE = DOCS_DIR / "dados_gna.json"
DOCS_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GNA-DAT")


def enviar_email(assunto, corpo_html):
    if not EMAIL_PASS:
        log.warning("EMAIL_PASS nao configurado.")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo(); smtp.starttls()
            smtp.login(EMAIL_FROM, EMAIL_PASS)
            smtp.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        log.info(f"Email enviado: {assunto}")
    except Exception as e:
        log.error(f"Erro email: {e}")


def verificar_e_alertar(registros):
    alertas = []
    for reg in registros:
        for col in COLUNAS_ALERTA:
            val = reg.get(col)
            if val is not None and isinstance(val, (int, float)) and val != 0:
                alertas.append({"planta": reg.get("planta_id",""), "iper": reg.get("IPER",""), "coluna": col, "valor": val})
    if not alertas:
        log.info("Sem alertas.")
        return
    ts = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
    linhas = "".join(f"<tr><td style='padding:6px 12px;border-bottom:1px solid #1e3a5f;color:{'#00c8ff' if a['planta']=='GNA I' else '#ffaa00'}'>{a['planta']}</td><td style='padding:6px 12px;border-bottom:1px solid #1e3a5f'>{a['iper']}</td><td style='padding:6px 12px;border-bottom:1px solid #1e3a5f;color:#ffaa00'>{a['coluna']}</td><td style='padding:6px 12px;border-bottom:1px solid #1e3a5f;color:#00e57a;text-align:right'>{a['valor']:,.2f}</td></tr>" for a in alertas[:100])
    corpo_html = f"""<div style="background:#090d12;padding:24px;font-family:Arial;color:#c8dff5;max-width:800px">
      <div style="background:#0d2040;border-left:4px solid #00c8ff;padding:14px 20px;margin-bottom:20px">
        <h2 style="margin:0;color:#fff">⚡ GNA MONITOR — ALERTA DESSEM</h2>
        <p style="margin:4px 0 0;color:#6a8faf;font-size:12px">{ts}</p>
      </div>
      <table style="width:100%;border-collapse:collapse;font-family:monospace;font-size:13px;background:#0d1520">
        <thead><tr style="background:#111d2e"><th style="padding:8px 12px;text-align:left">Planta</th><th style="padding:8px 12px;text-align:left">IPER</th><th style="padding:8px 12px;text-align:left">Coluna</th><th style="padding:8px 12px;text-align:right">Valor</th></tr></thead>
        <tbody>{linhas}</tbody>
      </table>
      <div style="margin-top:20px"><a href="https://leandrosouza1234561.github.io/gna_dessem4/" style="color:#00c8ff">→ Ver dashboard</a></div>
    </div>"""
    enviar_email(f"⚡ GNA Alert — Valores detectados ({ts})", corpo_html)


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
        page.locator("#kc-login, input[type='submit'], button[type='submit']").first.click()
        page.wait_for_function("() => !window.location.href.includes('sso.ons.org.br')", timeout=60000)
        log.info(f"Autenticado! URL: {page.url}")
        time.sleep(3)
        return True
    except Exception as e:
        log.error(f"Erro login: {e}"); return False


def coletar_tudo(tmpdir):
    """Abre UMA sessão do browser e faz tudo: baixa ZIP + coleta PDPW."""
    zip_path    = None
    dados_pdpw  = {"colunas": [], "registros": []}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"])
        context = browser.new_context(
            viewport={"width":1600,"height":900}, locale="pt-BR", accept_downloads=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")

        try:
            # ── 1. Baixa ZIP do SINTEGRE ──────────────────────────────
            page = context.new_page()
            log.info("Acessando historico SINTEGRE...")
            page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            if "sso.ons.org.br" in page.url:
                if not fazer_login_keycloak(page):
                    page.close(); return zip_path, dados_pdpw
                time.sleep(3)
            if "historico-de-produtos" not in page.url:
                page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)
            if "sso.ons.org.br" in page.url:
                if not fazer_login_keycloak(page):
                    page.close(); return zip_path, dados_pdpw
                page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
                time.sleep(5)
            botoes = page.locator("a:has-text('Baixar'), button:has-text('Baixar')").all()
            log.info(f"Botoes Baixar: {len(botoes)}")
            if botoes:
                with page.expect_download(timeout=120000) as dl:
                    botoes[0].click()
                zip_path = Path(tmpdir) / "deck.zip"
                dl.value.save_as(zip_path)
                log.info(f"ZIP: {zip_path.stat().st_size} bytes")
            else:
                log.error("Botao nao encontrado.")
            page.close()

            # ── 2. Coleta PDPW ────────────────────────────────────────
            log.info("Acessando PDPW...")
            page2 = context.new_page()
            page2.goto(URL_PDPW, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)
            if "sso.ons.org.br" in page2.url or "login" in page2.url.lower():
                if not fazer_login_keycloak(page2):
                    page2.close()
                    return zip_path, dados_pdpw
                page2.goto(URL_PDPW, wait_until="domcontentloaded", timeout=30000)
                time.sleep(4)
            log.info(f"PDPW URL: {page2.url}")

            # Seleciona empresa GNA GERAÇÃO
            try:
                selects = page2.locator("select").all()
                for sel in selects:
                    opts = sel.locator("option").all()
                    for opt in opts:
                        txt = opt.inner_text().strip()
                        if "GNA" in txt.upper() and "GERA" in txt.upper():
                            sel.select_option(label=txt)
                            log.info(f"Empresa selecionada: {txt}")
                            time.sleep(4)
                            break
            except Exception as e:
                log.warning(f"Erro select empresa: {e}")

            # Extrai tabela
            tabelas = page2.locator("table").all()
            log.info(f"Tabelas PDPW: {len(tabelas)}")
            for tabela in tabelas:
                html = tabela.inner_html()
                if "GGNA" in html or "00:00" in html or "Intervalo" in html:
                    log.info("Tabela PDPW encontrada!")
                    linhas = tabela.locator("tr").all()
                    if len(linhas) < 2:
                        continue

                    # Cabeçalho (pode ter 2 linhas de header)
                    cab1 = [c.inner_text().strip() for c in linhas[0].locator("th,td").all()]
                    cab2 = [c.inner_text().strip() for c in linhas[1].locator("th,td").all()]

                    # Decide se cab2 é subheader ou dado
                    eh_subheader = any(c in ["DESSEM","Sugerido","Total","Intervalo"] for c in cab2)
                    if eh_subheader:
                        # Monta colunas combinando cab1 + cab2
                        colunas_pdpw = []
                        for i in range(max(len(cab1), len(cab2))):
                            c1 = cab1[i] if i < len(cab1) else ""
                            c2 = cab2[i] if i < len(cab2) else ""
                            if c1 and c2 and c1 != c2:
                                colunas_pdpw.append(f"{c1} {c2}".strip())
                            elif c1:
                                colunas_pdpw.append(c1)
                            else:
                                colunas_pdpw.append(c2)
                        inicio = 2
                    else:
                        colunas_pdpw = cab1
                        inicio = 1

                    log.info(f"Colunas PDPW: {colunas_pdpw}")

                    regs = []
                    for linha in linhas[inicio:]:
                        celulas = [c.inner_text().strip() for c in linha.locator("td").all()]
                        if not celulas or len(celulas) < 2: continue
                        reg = {}
                        for j, col in enumerate(colunas_pdpw):
                            reg[col] = _parse(celulas[j]) if j < len(celulas) else None
                        regs.append(reg)

                    dados_pdpw = {"colunas": colunas_pdpw, "registros": regs}
                    log.info(f"PDPW: {len(regs)} registros extraidos")
                    break

            page2.close()

        except Exception as e:
            log.error(f"Erro geral: {e}", exc_info=True)
        finally:
            browser.close()

    return zip_path, dados_pdpw


def extrair_dat(zip_path):
    try:
        with zipfile.ZipFile(zip_path) as zf:
            arquivos = zf.namelist()
            encontrado = next((n for n in arquivos if ARQUIVO_DAT.lower() in n.lower()), None)
            if encontrado:
                conteudo = zf.read(encontrado).decode("latin-1", errors="replace")
                log.info(f"Extraido: {encontrado}")
                return conteudo
            log.warning(f"Nao encontrado: {ARQUIVO_DAT}. Arquivos: {arquivos[:10]}")
    except Exception as e:
        log.error(f"Erro ZIP: {e}")
    return None


def parsear_dat(conteudo):
    linhas = conteudo.splitlines()
    cab_idx, cab_raw, colunas = None, "", []
    for i, linha in enumerate(linhas):
        if linha.strip().startswith(("-","&","%","/")):
            continue
        if re.search(r'[A-Z]+\s*:', linha) and ";" not in linha:
            continue
        if re.search(r'\bIPER\b', linha, re.I) and ";" in linha:
            partes = [c.strip() for c in linha.split(";") if c.strip()]
            if len(partes) >= 3:
                cab_idx, cab_raw, colunas = i, linha, partes
                log.info(f"Cabecalho linha {i}: {colunas}")
                break
    if cab_idx is None:
        return {"colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":len(linhas),"total_registros_gna":0}

    def idx_col(nome):
        for j, c in enumerate(colunas):
            if nome.lower() in c.lower(): return j
        return -1

    idx_usit     = idx_col("USIT")
    idx_nome     = idx_col("Nome")
    idx_numbarra = idx_col("NumBarra") if idx_col("NumBarra") >= 0 else idx_col("Barra")

    registros = []
    for linha in linhas[cab_idx+1:]:
        linha = linha.rstrip()
        if not linha or linha.strip().startswith(("-","&","%","/")):
            continue
        campos = [c.strip() for c in linha.split(";")]
        if len(campos) < 4: continue
        nome_usina = campos[idx_nome].upper() if idx_nome >= 0 and idx_nome < len(campos) else ""
        usit_val   = campos[idx_usit] if idx_usit >= 0 and idx_usit < len(campos) else ""
        barra_val  = campos[idx_numbarra] if idx_numbarra >= 0 and idx_numbarra < len(campos) else ""
        planta_id = None
        if "GNA" in nome_usina:
            planta_id = "GNA II" if ("II" in nome_usina or " 2" in nome_usina) else "GNA I"
        if not planta_id: continue
        filtro = FILTRO_GNA.get(planta_id)
        if filtro and (usit_val != filtro["usit"] or barra_val != filtro["numbarra"]):
            continue
        reg = {"planta_id": planta_id}
        for j, col in enumerate(colunas):
            col_limpo = col.strip()
            exibir = any(e.lower() in col_limpo.lower() or col_limpo.lower() in e.lower() for e in COLUNAS_EXIBIR)
            if exibir and j < len(campos):
                reg[col_limpo] = _parse(campos[j])
        registros.append(reg)

    colunas_exibir = [c.strip() for c in colunas if any(e.lower() in c.lower() or c.lower() in e.lower() for e in COLUNAS_EXIBIR)]
    log.info(f"Total GNA: {len(registros)}")
    return {"colunas": colunas_exibir, "registros": registros, "raw_header": cab_raw,
            "total_linhas_arquivo": len(linhas), "total_registros_gna": len(registros)}


def _parse(t):
    if not t or t in ["-","N/A","*",""]: return None
    try: return int(t)
    except: pass
    try: return float(t.replace(",","."))
    except: return t


def salvar(conteudo_raw, dados_dat, dados_pdpw):
    ts = datetime.now(timezone.utc).isoformat()
    if conteudo_raw:
        (DOCS_DIR / ARQUIVO_DAT).write_text(conteudo_raw, encoding="utf-8", errors="replace")
    hist = []
    if JSON_FILE.exists():
        try: hist = json.loads(JSON_FILE.read_text()).get("historico", [])
        except: pass
    snapshot = {"timestamp": ts, "colunas": dados_dat["colunas"],
                "registros": dados_dat["registros"], "total": dados_dat["total_registros_gna"],
                "pdpw": dados_pdpw}
    hist.append(snapshot)
    saida = {
        "ultima_coleta": ts,
        "status": "ok" if dados_dat["registros"] or dados_pdpw.get("registros") else "sem_dados",
        "arquivo": ARQUIVO_DAT,
        "colunas": dados_dat["colunas"],
        "raw_header": dados_dat["raw_header"],
        "total_linhas_arquivo": dados_dat["total_linhas_arquivo"],
        "registros": dados_dat["registros"],
        "total_registros_gna": dados_dat["total_registros_gna"],
        "pdpw": dados_pdpw,
        "historico": hist[-288:],
    }
    JSON_FILE.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Salvo: {dados_dat['total_registros_gna']} dat + {len(dados_pdpw.get('registros',[]))} pdpw")
    verificar_e_alertar(dados_dat["registros"])
    return saida


def main():
    if not ONS_PASS:
        log.error("ONS_PASS nao definido!"); return 1
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path, dados_pdpw = coletar_tudo(tmpdir)
        conteudo_dat = extrair_dat(zip_path) if zip_path else None
        dados_dat = parsear_dat(conteudo_dat) if conteudo_dat else {
            "colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":0,"total_registros_gna":0}
        salvar(conteudo_dat or "", dados_dat, dados_pdpw)
        log.info("Concluido!")
        return 0

if __name__ == "__main__":
    exit(main())
