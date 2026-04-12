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

URL_HISTORICO  = "https://sintegre.ons.org.br/sites/9/51//paginas/servicos/historico-de-produtos.aspx?produto=Decks%20de%20entrada%20e%20sa%C3%ADda%20-%20Modelo%20DESSEM"
URL_PDPW_ENTRY = "https://pdpw.ons.org.br/pdp/frmCnsEnvioEmp.aspx"
URL_PDPW_OBS   = "https://pdpw.ons.org.br/pdp/frmCnsObservacoes.aspx"

ARQUIVO_DAT = "pdo_oper_term.dat"
FILTRO_GNA = {
    "GNA I":  {"usit": "137",  "numbarra": "53"},
    "GNA II": {"usit": "238",  "numbarra": "44327"},
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


def enviar_relatorio_diario(dados_dat, dados_pdpw):
    if not EMAIL_PASS:
        log.warning("EMAIL_PASS nao configurado - email nao enviado.")
        return
    ts   = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
    hoje = datetime.now().strftime("%d/%m/%Y")
    registros_dat  = dados_dat.get("registros", [])
    registros_pdpw = dados_pdpw.get("registros", [])
    data_pdpw      = dados_pdpw.get("data", "")
    empresa_pdpw   = dados_pdpw.get("empresa", "")
    colunas_dat    = dados_dat.get("colunas", [])

    linhas_dat = ""
    for reg in registros_dat:
        planta = reg.get("planta_id", "")
        cor = "#3d4d5c" if planta == "GNA I" else "#e8650a"
        cells = f"<td style='padding:6px 10px;border-bottom:1px solid #dde1e7;color:{cor};font-weight:bold'>{planta}</td>"
        for col in colunas_dat:
            val = reg.get(col, "")
            if isinstance(val, float):
                val_fmt = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                val_fmt = str(val) if val is not None else "-"
            cells += f"<td style='padding:6px 10px;border-bottom:1px solid #dde1e7;text-align:right'>{val_fmt}</td>"
        linhas_dat += f"<tr>{cells}</tr>"

    header_dat = "<th style='padding:7px 10px;background:#f7f8fa;text-align:left;color:#4a5568'>PLANTA</th>"
    for col in colunas_dat:
        header_dat += f"<th style='padding:7px 10px;background:#f7f8fa;text-align:right;color:#4a5568'>{col}</th>"

    colunas_pdpw = dados_pdpw.get("colunas", [])
    excluir = ["data_pdpw", "empresa", "data", "intervalo"]
    colunas_pdpw_exib = [c for c in colunas_pdpw if not any(ex in c.lower() for ex in excluir)]

    linhas_pdpw = ""
    for reg in registros_pdpw[:48]:
        cells = ""
        for col in colunas_pdpw_exib:
            val = reg.get(col, "")
            if isinstance(val, float):
                val_fmt = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                val_fmt = str(val) if val is not None else "-"
            cells += f"<td style='padding:5px 10px;border-bottom:1px solid #dde1e7;text-align:right;font-size:11px'>{val_fmt}</td>"
        linhas_pdpw += f"<tr>{cells}</tr>"

    header_pdpw = ""
    for col in colunas_pdpw_exib:
        header_pdpw += f"<th style='padding:6px 10px;background:#f7f8fa;text-align:right;font-size:10px;color:#4a5568'>{col}</th>"

    corpo_html = f"""
<div style="background:#f0f2f5;padding:24px;font-family:Arial,sans-serif;color:#1a2333;max-width:1000px">
  <div style="background:#fff;border-left:5px solid #2d3a4a;padding:16px 20px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,.06)">
    <div style="font-weight:900;font-size:20px;color:#2d3a4a;letter-spacing:2px;text-transform:uppercase">GNA GERACAO - RELATORIO DESSEM</div>
    <div style="font-size:11px;color:#8a94a6;margin-top:4px;font-family:monospace">Coleta: {ts} | Data PDPW: {data_pdpw} | Empresa: {empresa_pdpw}</div>
  </div>
  <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap">
    <div style="background:#fff;border:1px solid #dde1e7;padding:12px 18px;flex:1;min-width:140px">
      <div style="font-size:10px;color:#8a94a6;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px">Registros DAT</div>
      <div style="font-size:20px;color:#2d3a4a;font-family:monospace;font-weight:bold">{len(registros_dat)}</div>
    </div>
    <div style="background:#fff;border:1px solid #dde1e7;padding:12px 18px;flex:1;min-width:140px">
      <div style="font-size:10px;color:#8a94a6;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px">GNA I</div>
      <div style="font-size:20px;color:#3d4d5c;font-family:monospace;font-weight:bold">{sum(1 for r in registros_dat if r.get('planta_id')=='GNA I')}</div>
    </div>
    <div style="background:#fff;border:1px solid #dde1e7;padding:12px 18px;flex:1;min-width:140px">
      <div style="font-size:10px;color:#8a94a6;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px">GNA II</div>
      <div style="font-size:20px;color:#e8650a;font-family:monospace;font-weight:bold">{sum(1 for r in registros_dat if r.get('planta_id')=='GNA II')}</div>
    </div>
    <div style="background:#fff;border:1px solid #dde1e7;padding:12px 18px;flex:1;min-width:140px">
      <div style="font-size:10px;color:#8a94a6;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px">PDO Term</div>
      <div style="font-size:20px;color:#8b5cf6;font-family:monospace;font-weight:bold">{len(registros_pdpw)}</div>
    </div>
  </div>
  <div style="margin-bottom:20px">
    <div style="font-size:12px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;color:#2d3a4a;border-left:3px solid #2d3a4a;padding-left:10px;margin-bottom:10px">PDO OPER TERM</div>
    <table style="width:100%;border-collapse:collapse;font-family:monospace;font-size:12px;background:#fff">
      <thead><tr>{header_dat}</tr></thead>
      <tbody>{linhas_dat or "<tr><td colspan='10' style='padding:12px;color:#8a94a6;text-align:center'>Sem dados</td></tr>"}</tbody>
    </table>
  </div>
  <div style="margin-bottom:20px">
    <div style="font-size:12px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;color:#8b5cf6;border-left:3px solid #8b5cf6;padding-left:10px;margin-bottom:10px">PDO TERM ({data_pdpw})</div>
    <table style="width:100%;border-collapse:collapse;font-family:monospace;font-size:11px;background:#fff">
      <thead><tr>{header_pdpw or "<th style='padding:6px 10px;background:#f7f8fa'>-</th>"}</tr></thead>
      <tbody>{linhas_pdpw or "<tr><td colspan='10' style='padding:12px;color:#8a94a6;text-align:center'>Sem dados</td></tr>"}</tbody>
    </table>
  </div>
  <div style="border-top:1px solid #dde1e7;padding-top:14px;font-size:11px;color:#8a94a6">
    <a href="https://leandrosouza1234561.github.io/gna_dessem4/" style="color:#2d3a4a;text-decoration:none">Ver dashboard</a>
    &nbsp;|&nbsp; GNA MONITOR · GITHUB ACTIONS
  </div>
</div>"""
    enviar_email(f"GNA GERACAO - Relatorio DESSEM {hoje} | {len(registros_dat)} DAT + {len(registros_pdpw)} PDPW", corpo_html)
    log.info("Relatorio diario enviado.")


def verificar_e_alertar(registros):
    alertas = []
    for reg in registros:
        for col in COLUNAS_ALERTA:
            val = reg.get(col)
            if val is not None and isinstance(val, (int, float)) and val != 0:
                alertas.append({"planta": reg.get("planta_id",""), "iper": reg.get("IPER",""), "coluna": col, "valor": val})
    if not alertas:
        log.info("Sem alertas."); return
    ts = datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M")
    linhas = "".join(
        f"<tr><td style='padding:6px 12px;border-bottom:1px solid #dde1e7;color:{'#3d4d5c' if a['planta']=='GNA I' else '#e8650a'}'>{a['planta']}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #dde1e7'>{a['iper']}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #dde1e7;color:#e8650a'>{a['coluna']}</td>"
        f"<td style='padding:6px 12px;border-bottom:1px solid #dde1e7;text-align:right'>{a['valor']:,.2f}</td></tr>"
        for a in alertas[:100])
    corpo = f"""<div style="background:#f0f2f5;padding:24px;font-family:Arial;color:#1a2333;max-width:800px">
      <div style="background:#fff;border-left:4px solid #2d3a4a;padding:14px 20px;margin-bottom:20px">
        <h2 style="margin:0;color:#2d3a4a">GNA MONITOR - ALERTA DESSEM</h2>
        <p style="margin:4px 0 0;color:#8a94a6;font-size:12px">{ts}</p></div>
      <table style="width:100%;border-collapse:collapse;font-family:monospace;font-size:13px;background:#fff">
        <thead><tr style="background:#f7f8fa">
          <th style="padding:8px 12px;text-align:left">Planta</th><th style="padding:8px 12px;text-align:left">IPER</th>
          <th style="padding:8px 12px;text-align:left">Coluna</th><th style="padding:8px 12px;text-align:right">Valor</th>
        </tr></thead><tbody>{linhas}</tbody></table>
      <div style="margin-top:20px"><a href="https://leandrosouza1234561.github.io/gna_dessem4/" style="color:#2d3a4a">Ver dashboard</a></div>
    </div>"""
    enviar_email(f"GNA Alert - Valores detectados ({ts})", corpo)


def fazer_login_keycloak(page):
    log.info(f"Login Keycloak. URL: {page.url}")
    try:
        campo_user = page.locator("#username, input[name='username'], input[type='text']").first
        campo_user.wait_for(timeout=15000)
        campo_user.fill(ONS_USER); time.sleep(1)
        campo_pass = page.locator("#password, input[name='password'], input[type='password']").first
        campo_pass.wait_for(timeout=10000)
        campo_pass.fill(ONS_PASS); time.sleep(1)
        page.locator("#kc-login, input[type='submit'], button[type='submit']").first.click()
        page.wait_for_function("() => !window.location.href.includes('sso.ons.org.br')", timeout=60000)
        log.info(f"Autenticado! URL: {page.url}"); time.sleep(3)
        return True
    except Exception as e:
        log.error(f"Erro login: {e}"); return False


def _garantir_login(page, url_destino):
    page.goto(url_destino, wait_until="domcontentloaded", timeout=30000); time.sleep(4)
    if "sso.ons.org.br" in page.url or "login" in page.url.lower():
        if not fazer_login_keycloak(page): return False
        page.goto(url_destino, wait_until="domcontentloaded", timeout=30000); time.sleep(4)
    if "sso.ons.org.br" in page.url or "login" in page.url.lower():
        if not fazer_login_keycloak(page): return False
        page.goto(url_destino, wait_until="domcontentloaded", timeout=30000); time.sleep(4)
    return True


def _tentar_baixar(page, tmpdir):
    """Tenta encontrar botao de download por multiplos seletores."""
    # Aguarda pagina carregar completamente
    time.sleep(5)

    # Loga URL e titulo para diagnóstico
    log.info(f"URL apos login: {page.url}")
    log.info(f"Titulo pagina: {page.title()}")

    # Lista de seletores para tentar
    seletores = [
        "a:has-text('Baixar')",
        "button:has-text('Baixar')",
        "input[value*='Baixar']",
        "input[value*='baixar']",
        "a:has-text('Download')",
        "button:has-text('Download')",
        "a:has-text('download')",
        "a[href*='.zip']",
        "a[href*='download']",
        "a[href*='Download']",
        "a[href*='zip']",
        "img[title*='Baixar']",
        "img[alt*='Baixar']",
        "img[title*='baixar']",
        "a:has-text('Transferir')",
        "button:has-text('Transferir')",
        "a:has-text('Exportar')",
        "button:has-text('Exportar')",
        "[onclick*='download']",
        "[onclick*='Download']",
        "[onclick*='baixar']",
        "[onclick*='Baixar']",
        "a.download",
        "button.download",
    ]

    botao = None
    for sel in seletores:
        try:
            els = page.locator(sel).all()
            if els:
                log.info(f"Botao encontrado: seletor='{sel}' count={len(els)}")
                botao = els[0]
                break
        except Exception as ex:
            log.debug(f"Seletor '{sel}' erro: {ex}")
            continue

    if not botao:
        # Diagnóstico: loga todos os links e botões da página
        log.error("Nenhum botao de download encontrado. Diagnostico:")
        try:
            links = page.locator("a").all()
            log.info(f"Total de <a> na pagina: {len(links)}")
            for i, lnk in enumerate(links[:30]):
                try:
                    txt = lnk.inner_text(timeout=2000).strip()
                    href = lnk.get_attribute("href") or ""
                    log.info(f"  Link[{i}] texto='{txt}' href='{href[:80]}'")
                except Exception:
                    pass
            btns = page.locator("button, input[type='button'], input[type='submit']").all()
            log.info(f"Total de botoes na pagina: {len(btns)}")
            for i, btn in enumerate(btns[:20]):
                try:
                    txt = btn.inner_text(timeout=2000).strip() or btn.get_attribute("value") or ""
                    log.info(f"  Botao[{i}] texto='{txt}'")
                except Exception:
                    pass
        except Exception as ex:
            log.error(f"Erro no diagnostico: {ex}")
        return None

    # Tenta clicar e capturar download
    try:
        with page.expect_download(timeout=120000) as dl:
            botao.click()
        zip_path = Path(tmpdir) / "deck.zip"
        dl.value.save_as(zip_path)
        log.info(f"ZIP baixado: {zip_path.stat().st_size} bytes")
        return zip_path
    except Exception as e:
        log.error(f"Erro ao baixar apos clicar: {e}")
        return None


def coletar_tudo(tmpdir):
    zip_path   = None
    dados_pdpw = {"colunas": [], "registros": [], "empresa": "", "data": ""}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"]
        )
        context = browser.new_context(
            viewport={"width":1600,"height":900},
            locale="pt-BR",
            accept_downloads=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            # ── SINTEGRE ────────────────────────────────────────────
            page = context.new_page()
            log.info("Acessando SINTEGRE...")
            if not _garantir_login(page, URL_HISTORICO):
                log.error("Login SINTEGRE falhou.")
                page.close()
            else:
                if "historico-de-produtos" not in page.url:
                    page.goto(URL_HISTORICO, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(5)
                zip_path = _tentar_baixar(page, tmpdir)
                page.close()

            # ── PDPW ────────────────────────────────────────────────
            log.info("Abrindo PDPW...")
            page2 = context.new_page()
            if not _garantir_login(page2, URL_PDPW_ENTRY):
                page2.close(); return zip_path, dados_pdpw

            log.info(f"PDPW entry: {page2.url}")
            page2.goto(URL_PDPW_OBS, wait_until="domcontentloaded", timeout=30000); time.sleep(5)
            if "sso.ons.org.br" in page2.url or "login" in page2.url.lower():
                if not fazer_login_keycloak(page2):
                    page2.close(); return zip_path, dados_pdpw
                page2.goto(URL_PDPW_OBS, wait_until="domcontentloaded", timeout=30000); time.sleep(5)
            log.info(f"PDPW obs: {page2.url}")

            data_pagina = ""
            try:
                candidatos = page2.locator("span[id*='dat'], input[id*='dat'], label:has-text('Data'), td:has-text('Data')").all()
                for el in candidatos:
                    txt = el.inner_text(timeout=3000).strip()
                    if re.search(r'\d{2}/\d{2}/\d{4}', txt):
                        data_pagina = txt; break
                if not data_pagina:
                    m = re.search(r'\d{2}/\d{2}/\d{4}', page2.inner_text("body"))
                    data_pagina = m.group(0) if m else datetime.now().strftime("%d/%m/%Y")
                log.info(f"Data PDPW: {data_pagina}")
            except Exception as e:
                data_pagina = datetime.now().strftime("%d/%m/%Y")
                log.warning(f"Data nao encontrada ({e})")

            empresa_selecionada = ""
            try:
                for sel in page2.locator("select").all():
                    for opt in sel.locator("option").all():
                        txt = opt.inner_text().strip()
                        if "GNA" in txt.upper() and "GERA" in txt.upper():
                            sel.select_option(label=txt)
                            empresa_selecionada = txt
                            log.info(f"Empresa: {txt}"); time.sleep(5); break
                    if empresa_selecionada: break
                if not empresa_selecionada:
                    log.warning("Empresa GNA GERACAO nao encontrada.")
            except Exception as e:
                log.warning(f"Erro select empresa: {e}")

            tabelas = page2.locator("table").all()
            log.info(f"Tabelas PDPW: {len(tabelas)}")
            for tabela in tabelas:
                html = tabela.inner_html()
                if not ("GGNA" in html or "00:00" in html or "Intervalo" in html or "Meia" in html):
                    continue
                log.info("Tabela PDPW identificada!")
                linhas = tabela.locator("tr").all()
                if len(linhas) < 2: continue

                def _limpar(texto):
                    return [p.strip() for p in re.split(r'[\t\n]+', texto) if p.strip()]
                def _cab(linha_el):
                    cols = []
                    for cel in linha_el.locator("th,td").all():
                        p = _limpar(cel.inner_text()); cols.extend(p if p else [""])
                    return cols
                def _cel(linha_el):
                    cols = []
                    for cel in linha_el.locator("td").all():
                        p = _limpar(cel.inner_text()); cols.extend(p if p else [""])
                    return cols

                cab1, cab2 = _cab(linhas[0]), _cab(linhas[1])
                KWDS = {"dessem","sugerido","total","intervalo","programado","meia hora","ggna","ggna2"}
                eh_sub = any(c.lower() in KWDS for c in cab2)
                if eh_sub:
                    colunas_pdpw = []
                    for i in range(max(len(cab1), len(cab2))):
                        c1 = cab1[i] if i < len(cab1) else ""
                        c2 = cab2[i] if i < len(cab2) else ""
                        colunas_pdpw.append(f"{c1} {c2}".strip() if c1 and c2 and c1!=c2 else (c1 or c2))
                    inicio = 2
                else:
                    colunas_pdpw = cab1; inicio = 1

                log.info(f"Colunas PDPW ({len(colunas_pdpw)}): {colunas_pdpw}")
                regs = []
                for linha in linhas[inicio:]:
                    celulas = _cel(linha)
                    if not celulas or len(celulas) < 2: continue
                    txt = " ".join(celulas).upper()
                    if "GGNA" not in txt and not re.match(r'^\d{2}:\d{2}', celulas[0]): continue
                    reg = {"empresa": empresa_selecionada, "data_pdpw": data_pagina}
                    for j, col in enumerate(colunas_pdpw):
                        reg[col] = _parse(celulas[j]) if j < len(celulas) else None
                    regs.append(reg)
                regs = regs[:48]
                dados_pdpw = {"colunas": colunas_pdpw, "registros": regs, "empresa": empresa_selecionada, "data": data_pagina}
                log.info(f"PDPW: {len(regs)} registros | empresa={empresa_selecionada} | data={data_pagina}")
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
            encontrado = next((n for n in zf.namelist() if ARQUIVO_DAT.lower() in n.lower()), None)
            if encontrado:
                conteudo = zf.read(encontrado).decode("latin-1", errors="replace")
                log.info(f"Extraido: {encontrado}"); return conteudo
            log.warning(f"Nao encontrado: {ARQUIVO_DAT}. Arquivos: {zf.namelist()[:10]}")
    except Exception as e:
        log.error(f"Erro ZIP: {e}")
    return None


def parsear_dat(conteudo):
    linhas = conteudo.splitlines()
    cab_idx, cab_raw, colunas = None, "", []
    for i, linha in enumerate(linhas):
        if linha.strip().startswith(("-","&","%","/")):continue
        if re.search(r'[A-Z]+\s*:', linha) and ";" not in linha:continue
        if re.search(r'\bIPER\b', linha, re.I) and ";" in linha:
            partes = [c.strip() for c in linha.split(";") if c.strip()]
            if len(partes) >= 3:
                cab_idx, cab_raw, colunas = i, linha, partes
                log.info(f"Cabecalho linha {i}: {colunas}"); break
    if cab_idx is None:
        return {"colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":len(linhas),"total_registros_gna":0}

    def idx_col(nome):
        for j,c in enumerate(colunas):
            if nome.lower() in c.lower(): return j
        return -1
    idx_usit     = idx_col("USIT")
    idx_nome     = idx_col("Nome")
    idx_numbarra = idx_col("NumBarra") if idx_col("NumBarra")>=0 else idx_col("Barra")

    registros = []
    for linha in linhas[cab_idx+1:]:
        linha = linha.rstrip()
        if not linha or linha.strip().startswith(("-","&","%","/")):continue
        campos = [c.strip() for c in linha.split(";")]
        if len(campos) < 4: continue
        nome_usina = campos[idx_nome].upper() if idx_nome>=0 and idx_nome<len(campos) else ""
        usit_val   = campos[idx_usit]     if idx_usit>=0     and idx_usit<len(campos)     else ""
        barra_val  = campos[idx_numbarra] if idx_numbarra>=0 and idx_numbarra<len(campos) else ""
        planta_id = None
        if "GNA" in nome_usina:
            planta_id = "GNA II" if ("II" in nome_usina or " 2" in nome_usina) else "GNA I"
        if not planta_id: continue
        filtro = FILTRO_GNA.get(planta_id)
        if filtro and (usit_val!=filtro["usit"] or barra_val!=filtro["numbarra"]): continue
        reg = {"planta_id": planta_id}
        for j, col in enumerate(colunas):
            col_limpo = col.strip()
            if any(e.lower() in col_limpo.lower() or col_limpo.lower() in e.lower() for e in COLUNAS_EXIBIR) and j<len(campos):
                reg[col_limpo] = _parse(campos[j])
        registros.append(reg)

    colunas_exibir = [c.strip() for c in colunas if any(e.lower() in c.lower() or c.lower() in e.lower() for e in COLUNAS_EXIBIR)]
    log.info(f"Total registros GNA no DAT: {len(registros)}")
    return {"colunas":colunas_exibir,"registros":registros,"raw_header":cab_raw,"total_linhas_arquivo":len(linhas),"total_registros_gna":len(registros)}


def _parse(t):
    if not t or t in ["-","N/A","*",""]: return None
    try: return int(t)
    except: pass
    try: return float(t.replace(",","."))
    except: return t


def salvar(conteudo_raw, dados_dat, dados_pdpw):
    ts = datetime.now(timezone.utc).isoformat()
    if conteudo_raw:
        (DOCS_DIR/ARQUIVO_DAT).write_text(conteudo_raw, encoding="utf-8", errors="replace")
    hist = []
    if JSON_FILE.exists():
        try: hist = json.loads(JSON_FILE.read_text()).get("historico",[])
        except: pass
    hist.append({"timestamp":ts,"colunas":dados_dat["colunas"],"registros":dados_dat["registros"],"total":dados_dat["total_registros_gna"],"pdo_term":dados_pdpw})
    saida = {
        "ultima_coleta":ts,
        "status":"ok" if (dados_dat["registros"] or dados_pdpw.get("registros")) else "sem_dados",
        "arquivo":ARQUIVO_DAT,
        "colunas":dados_dat["colunas"],
        "raw_header":dados_dat["raw_header"],
        "total_linhas_arquivo":dados_dat["total_linhas_arquivo"],
        "registros":dados_dat["registros"],
        "total_registros_gna":dados_dat["total_registros_gna"],
        "pdo_term":dados_pdpw,
        "historico":hist[-288:],
    }
    JSON_FILE.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Salvo: {dados_dat['total_registros_gna']} DAT + {len(dados_pdpw.get('registros',[]))} PDPW")
    verificar_e_alertar(dados_dat["registros"])
    enviar_relatorio_diario(dados_dat, dados_pdpw)
    return saida


def main():
    if not ONS_PASS:
        log.error("ONS_PASS nao definido!"); return 1
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path, dados_pdpw = coletar_tudo(tmpdir)
        conteudo_dat = extrair_dat(zip_path) if zip_path else None
        dados_dat = parsear_dat(conteudo_dat) if conteudo_dat else {
            "colunas":[],"registros":[],"raw_header":"","total_linhas_arquivo":0,"total_registros_gna":0
        }
        salvar(conteudo_dat or "", dados_dat, dados_pdpw)
        log.info("Coleta concluida!")
        return 0

if __name__ == "__main__":
    exit(main())
