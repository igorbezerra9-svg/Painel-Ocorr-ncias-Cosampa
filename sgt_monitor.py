"""
SGT Monitor - Cosampa
Navega até DESUL > Total, extrai incidências e atualiza painel_sgt.html.
"""

import time
import os
import re
import json
import sys
import traceback
import subprocess
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
try:
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    USE_WDM = True
except ImportError:
    USE_WDM = False

# ─── CONFIGURAÇÃO ────────────────────────────────────────────────
USUARIO           = "BR0894369203"
SENHA             = "none"
INTERVALO_MINUTOS = 1
URL_LOGIN         = "https://temporealce.enel.com/sgt/"
PASTA_SAIDA       = os.path.dirname(os.path.abspath(__file__))
# ─────────────────────────────────────────────────────────────────

AREA_MAP = {
    "C.S. MILAGRES": "MILAGRES",
    "C.S. CRATO":    "CRATO",
    "C.S. C. SALES": "C. SALES",
    "C.S. JUAZEIRO": "JUAZEIRO",
    "C.S. ICO":      "ICO",
}


# ── Driver ────────────────────────────────────────────────────────

def iniciar_driver():
    opts = Options()
    opts.add_argument("--disable-notifications")
    opts.add_argument("--password-store=basic")
    opts.add_argument("--disable-save-password-bubble")
    opts.add_argument("--log-level=3")
    opts.add_argument("--silent")
    opts.add_argument(f"--user-data-dir={os.path.join(PASTA_SAIDA, 'chrome_profile')}")
    opts.add_experimental_option("prefs", {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.password_manager_leak_detection": False,
        "profile.default_content_setting_values.notifications": 2,
    })
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    # Headless com flags de compatibilidade Windows e Linux
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--remote-debugging-port=0")
    opts.add_argument("--window-size=1920,1080")
    print("[i] Modo headless ativado")
    # Chromium no Linux (servidor) ou Chrome no Windows
    chromium = "/usr/bin/chromium-browser"
    if os.path.exists(chromium):
        opts.binary_location = chromium
    if USE_WDM:
        print("[i] Usando webdriver-manager para ChromeDriver")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    else:
        print("[i] Usando ChromeDriver do PATH")
        driver = webdriver.Chrome(options=opts)
    return driver


# ── Frames ────────────────────────────────────────────────────────

def entrar_no_frame_com(driver, condicao):
    """Percorre frames até encontrar o que satisfaz a condição."""
    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 3).until(condicao)
        return True
    except:
        pass
    frames = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")
    for i in range(len(frames)):
        try:
            driver.switch_to.default_content()
            frames = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")
            driver.switch_to.frame(frames[i])
            WebDriverWait(driver, 3).until(condicao)
            return True
        except:
            continue
    driver.switch_to.default_content()
    frames = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")
    for i in range(len(frames)):
        try:
            driver.switch_to.default_content()
            frames = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")
            driver.switch_to.frame(frames[i])
            inner = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")
            for j in range(len(inner)):
                try:
                    driver.switch_to.frame(inner[j])
                    WebDriverWait(driver, 3).until(condicao)
                    return True
                except:
                    driver.switch_to.default_content()
                    frames = driver.find_elements(By.CSS_SELECTOR, "frame, iframe")
                    driver.switch_to.frame(frames[i])
        except:
            continue
    return False


# ── Login ─────────────────────────────────────────────────────────


def fechar_popup_senha(driver):
    """Fecha popup do Chrome sobre senha comprometida, se aparecer."""
    from selenium.webdriver.common.keys import Keys

    for tentativa in range(3):
        # Tenta via JavaScript no shadow DOM do Chrome
        try:
            fechado = driver.execute_script("""
                const dialogs = document.querySelectorAll('password-manager-dialog, [slot="content"]');
                for(const d of dialogs){
                    const btn = d.shadowRoot && d.shadowRoot.querySelector('cr-button');
                    if(btn){ btn.click(); return true; }
                }
                return false;
            """)
            if fechado:
                print("[✓] Popup senha fechado via JS")
                time.sleep(0.5)
                return
        except:
            pass

        # Tenta via Selenium
        for xpath in [
            "//button[normalize-space()='Fechar']",
            "//button[contains(normalize-space(),'Fechar')]",
            "//button[normalize-space()='Close']",
            "//button[contains(@class,'cancel')]",
        ]:
            try:
                driver.switch_to.default_content()
                btn = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, xpath)))
                btn.click()
                print("[✓] Popup senha fechado")
                time.sleep(0.5)
                return
            except:
                continue

        # Escape
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except:
            pass

        time.sleep(1)


def fazer_login(driver):
    print("[→] Acessando SGT...")
    driver.get(URL_LOGIN)
    time.sleep(4)
    cond = EC.presence_of_element_located((By.NAME, "login"))
    entrar_no_frame_com(driver, cond)
    campo = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "login")))
    campo.clear()
    campo.send_keys(USUARIO)
    driver.find_element(By.NAME, "senha").clear()
    driver.find_element(By.NAME, "senha").send_keys(SENHA)
    try:
        driver.find_element(By.XPATH, "//input[@value='entrar']").click()
    except:
        try:
            driver.find_element(By.XPATH, "//input[@type='submit']").click()
        except:
            driver.find_element(By.XPATH, "//button").click()
    print("[✓] Login realizado")
    time.sleep(4)
    fechar_popup_senha(driver)


# ── Navegação ─────────────────────────────────────────────────────

def salvar_dump(driver, nome="dump_pagina.html"):
    try:
        with open(os.path.join(PASTA_SAIDA, nome), "w", encoding="utf-8", errors="replace") as f:
            f.write(driver.page_source)
        print(f"[i] Dump salvo: {nome}")
    except Exception as e:
        print(f"[!] Não salvou dump: {e}")


def clicar_em(driver, xpath, descricao, timeout=20):
    print(f"[→] Clicando em {descricao}...")
    cond = EC.element_to_be_clickable((By.XPATH, xpath))
    entrar_no_frame_com(driver, cond)
    try:
        el = WebDriverWait(driver, timeout).until(cond)
    except Exception:
        salvar_dump(driver, f"dump_falha_{descricao.replace(' ', '_')}.html")
        raise
    driver.execute_script("arguments[0].scrollIntoView(true);", el)
    time.sleep(0.5)
    el.click()
    time.sleep(3)


def clicar_desul(driver):
    print("[→] Clicando em DESUL...")
    for xpath in [
        "//a[normalize-space(text())='DESUL']",
        "//a[contains(normalize-space(.),'DESUL')]",
        "//td[contains(normalize-space(.),'DESUL')]//a",
        "//*[normalize-space(text())='DESUL']",
        "//*[contains(text(),'DESUL')]",
    ]:
        cond = EC.element_to_be_clickable((By.XPATH, xpath))
        entrar_no_frame_com(driver, cond)
        try:
            el = WebDriverWait(driver, 5).until(cond)
            driver.execute_script("arguments[0].scrollIntoView(true);", el)
            time.sleep(0.5)
            el.click()
            print(f"[✓] DESUL clicado")
            time.sleep(3)
            return
        except:
            continue
    raise RuntimeError("Não foi possível clicar em DESUL")


def clicar_total(driver, timeout=20):
    clicar_em(driver,
        "//tr[.//td[contains(normalize-space(.),'Total')]]//a[1] | "
        "//tr[.//b[contains(normalize-space(.),'Total')]]//a[1]",
        "Total incidências", timeout=timeout)


def clicar_voltar(driver):
    try:
        clicar_em(driver,
            "//input[@value='VOLTAR'] | //button[normalize-space()='VOLTAR'] | //a[normalize-space()='VOLTAR']",
            "VOLTAR", timeout=8)
    except:
        print("[!] VOLTAR não encontrado")


def extrair_html(driver):
    cond = lambda d: len(d.find_elements(By.XPATH,
        "//*[contains(text(),'Incidência') or contains(text(),'INCIDÊNCIA')]")) > 0
    entrar_no_frame_com(driver, cond)
    try:
        WebDriverWait(driver, 15).until(
            lambda d: len(d.find_elements(By.XPATH, "//table//tr")) > 2)
    except:
        print("[!] Tabela demorou a carregar")
    html = driver.page_source
    print("[✓] HTML capturado")
    return html


def navegar_e_extrair(driver, primeira_vez=False):
    """
    1ª vez : DESUL → Total → extrai → VOLTAR
    Demais : Total → extrai → VOLTAR  (já na tela do DESUL)
    """
    driver.switch_to.default_content()
    fechar_popup_senha(driver)  # fecha popup se aparecer entre ciclos
    if primeira_vez:
        clicar_desul(driver)
        clicar_total(driver)
    else:
        try:
            clicar_total(driver, timeout=8)
        except:
            print("[!] Total não encontrado — refazendo via DESUL")
            driver.switch_to.default_content()
            clicar_desul(driver)
            clicar_total(driver)
    time.sleep(2)
    html = extrair_html(driver)
    clicar_voltar(driver)
    return html


# ── Parser ────────────────────────────────────────────────────────

def parsear_incidencias(html):
    soup = BeautifulSoup(html, "html.parser")
    todas = soup.find_all("tr")
    idx_cab, col = None, {}

    for idx, row in enumerate(todas):
        cel = row.find_all(["th", "td"], recursive=False)
        txt = [c.get_text(strip=True) for c in cel]
        if (len(txt) >= 6
                and any("Incidência" in t for t in txt)
                and all(len(t) < 200 for t in txt)):
            col = {h: i for i, h in enumerate(txt) if h}
            idx_cab = idx
            print(f"[i] Cabeçalho em linha {idx} → {txt[:6]}...")
            break

    if idx_cab is None:
        print("[!] Cabeçalho não encontrado")
        return []

    def get(row, nome):
        cells = row.find_all(["td", "th"], recursive=False)
        for h, i in col.items():
            if nome.lower() in h.lower() and i < len(cells):
                return cells[i].get_text(strip=True)
        return ""

    incidencias = []
    for row in todas[idx_cab + 1:]:
        cel = row.find_all(["td", "th"], recursive=False)
        if len(cel) < 4:
            continue
        if any("Nº Incidência" in c.get_text(strip=True) for c in cel):
            continue
        # Extrai coordenada cliente
        coord_raw = get(row, "Coordenada Cliente")
        gps = ""
        if coord_raw and "," in coord_raw:
            partes = coord_raw.strip().split(",")
            if len(partes) >= 2:
                try:
                    lat = float(partes[0].strip())
                    lng = float(partes[1].strip())
                    gps = f"{lat},{lng}"
                except:
                    pass

        # Observação cliente — extrai texto após "TL: LIGAÇÃO XX "
        obs_raw = get(row, "Observação Cliente")
        obs = ""
        if obs_raw:
            import re as _re
            # Extrai texto após "TL: LIGAÇÃO MONOFASICA " ou "TL: LIGAÇÃO TRIFASICA "
            # Extrai texto apos TL: LIGACAO
            for prefix in ['TL: LIGAÇÃO TRIFASICA ', 'TL: LIGAÇÃO MONOFASICA ', 'TL: LIGACAO ']:
                if prefix in obs_raw:
                    obs = obs_raw.split(prefix, 1)[1].strip()
                    # Remove linha de contato se houver
                    if chr(10)+'Contato' in obs:
                        obs = obs[:obs.find(chr(10)+'Contato')].strip()
                    obs = obs[:250]
                    break

        inc = {
            "id":      get(row, "Incidência"),
            "viatura": get(row, "Viatura"),
            "clientes":get(row, "Clientes"),
            "duracao": get(row, "Duração"),
            "estado":  get(row, "Estado"),
            "area":    get(row, "Área Despacho") or get(row, "Área"),
            "tipo":    get(row, "Tipo Reclamação") or get(row, "Tipo"),
            "avisos":  get(row, "Total Avisos") or "1",
            "gps":     gps,
            "obs":     obs,
        }
        if inc["id"]:
            incidencias.append(inc)

    print(f"[✓] {len(incidencias)} incidências extraídas")
    return incidencias


# ── Painel ────────────────────────────────────────────────────────

def publicar_github():
    """Faz git add/commit/push do painel_sgt.html para o GitHub Pages."""
    try:
        subprocess.run(["git", "add", "painel_sgt.html", "dados.json"], cwd=PASTA_SAIDA, check=True, capture_output=True)
        # Força commit mesmo sem mudança via --allow-empty
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", f"SGT {datetime.now().strftime('%d/%m %H:%M')}"],
            cwd=PASTA_SAIDA, check=True, capture_output=True
        )
        subprocess.run(["git", "push"], cwd=PASTA_SAIDA, check=True, capture_output=True)
        print("[✓] Publicado no GitHub Pages")
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or b"").decode("utf-8", errors="replace")
        print(f"[!] Erro ao publicar: {msg.strip()}")


def salvar_painel(incidencias):
    """
    Atualiza const dados=[...] no painel_sgt.html via regex.
    Não mexe em nada mais do arquivo — layout intacto.
    """
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    dados = []
    for inc in incidencias:
        area_raw = inc.get("area", "") or ""
        area = AREA_MAP.get(area_raw, area_raw.replace("C.S. ", "").strip() or "OUTROS")
        dados.append({
            "id":   inc["id"],
            "est":  inc["estado"] or "",
            "area": area,
            "dur":  inc["duracao"] or "0:00",
            "cli":  re.sub(r"\D", "", inc["clientes"] or "") or "0",
            "av":   inc.get("avisos") or "1",
            "tipo": inc["tipo"] or "",
            "vtr":  inc["viatura"] or "",
            "gps":  inc.get("gps") or "",
            "obs":  (inc.get("obs") or "").replace("\n", " ").replace("\r", " ").replace('"', "'").strip(),
        })

    painel_path = os.path.join(PASTA_SAIDA, "painel_sgt.html")
    try:
        with open(painel_path, "r", encoding="utf-8") as f:
            html = f.read()

        dados_json = json.dumps(dados, ensure_ascii=True)

        # Substitui const dados=[...];
        novo_html = re.sub(
            r"const dados\s*=\s*\[.*?\]\s*;",
            lambda m: "const dados=" + dados_json + ";",
            html, flags=re.DOTALL
        )
        if novo_html == html:
            print("[!] AVISO: regex de dados nao encontrou padrao no painel")
        html = novo_html

        # Recalcula métricas
        total      = len(dados)
        total_cli  = sum(int(d.get("cli") or 0) for d in dados)
        sem_vtr    = sum(1 for d in dados if not d.get("vtr"))
        URGENTES   = ["PERIGO IMINENTE","INCÊNDIO","CONDUTOR (FIO) PARTIDO","FALTA EM CLIENTE VITAL"]
        urgentes   = sum(1 for d in dados if (d.get("tipo") or "").upper() in [u.upper() for u in URGENTES])
        rec        = sum(1 for d in dados if d.get("est") == "RECEBIDA")
        nova       = sum(1 for d in dados if d.get("est") == "NOVA")
        pct_sv     = round(sem_vtr * 100 / total) if total else 0

        areas_count = {}
        areas_cli   = {}
        for d in dados:
            a = d.get("area","OUTROS")
            areas_count[a] = areas_count.get(a,0) + 1
            areas_cli[a]   = areas_cli.get(a,0) + int(d.get("cli") or 0)

        urgentes_lista = [d for d in dados if (d.get("tipo") or "").upper() in [u.upper() for u in URGENTES]]

        def subst_card(h, classe, num, sub):
            pat = f'class="{classe}">\\s*<div class="met-num">[^<]*</div>\\s*<div class="met-label">[^<]*</div>\\s*<div class="met-sub">[^<]*</div>'
            rep = f'class="{classe}">\n      <div class="met-num">{num}</div>\n      <div class="met-label">{{}}</div>\n      <div class="met-sub">{sub}</div>'
            m = re.search(f'class="{classe}">(.*?)</div>\\s*</div>', h, flags=re.DOTALL)
            return h

        # Substitui número total de incidências
        html = re.sub(
            r'(class="met met-blue">\s*<div class="met-num">)[^<]*(</div>\s*<div class="met-label">Incidências ativas</div>\s*<div class="met-sub">)[^<]*(</div>)',
            f'\\g<1>{total}\\g<2>{rec} recebidas · {nova} novas\\g<3>',
            html, flags=re.DOTALL
        )
        # Substitui clientes afetados
        html = re.sub(
            r'(class="met met-muted">\s*<div class="met-num">)[^<]*(</div>\s*<div class="met-label">Clientes afetados</div>\s*<div class="met-sub">)[^<]*(</div>)',
            f'\\g<1>{total_cli:,}\\g<2>0,02% da base sul\\g<3>',
            html, flags=re.DOTALL
        )
        # Substitui sem viatura
        html = re.sub(
            r'(class="met met-orange">\s*<div class="met-num">)[^<]*(</div>\s*<div class="met-label">Aguardando viatura</div>\s*<div class="met-sub">)[^<]*(</div>)',
            f'\\g<1>{sem_vtr}\\g<2>{pct_sv}% ainda sem equipe\\g<3>',
            html, flags=re.DOTALL
        )
        # Substitui urgentes
        html = re.sub(
            r'(class="met met-red">\s*<div class="met-num">)[^<]*(</div>)',
            f'\\g<1>{urgentes}\\g<2>',
            html, flags=re.DOTALL, count=1
        )

        # Substitui pills de urgentes
        pills_html = "".join(
            f'<span class="urg-pill">{d["tipo"]} · {d["area"]}</span>'
            for d in urgentes_lista[:4]
        )
        html = re.sub(
            r'(<div class="urg-pills">).*?(</div>)',
            f'\\g<1>{pills_html}\\g<2>',
            html, flags=re.DOTALL, count=1
        )

        # Substitui cards de área
        AREA_ORDER = ["C. SALES","MILAGRES","JUAZEIRO","CRATO","ICO"]
        AREA_NAMES = {"C. SALES":"Campos Sales","MILAGRES":"Milagres","JUAZEIRO":"Juazeiro do Norte","CRATO":"Crato","ICO":"Icó"}
        for area in AREA_ORDER:
            nome = AREA_NAMES.get(area, area)
            cnt  = areas_count.get(area, 0)
            cli  = areas_cli.get(area, 0)
            # Localiza o card pelo nome da área e substitui número e clientes
            pat = (
                rf'(<div class="area"[^>]*>\s*<div class="area-num"[^>]*>)[^<]*'
                rf'(</div>\s*<div class="area-name">{re.escape(nome)}</div>\s*'
                rf'<div class="area-row"><span>Incidências</span><span class="area-val"[^>]*>)[^<]*'
                rf'(</span></div>\s*<div class="area-row"[^>]*><span>Clientes</span><span class="area-val">)[^<]*'
                rf'(</span>)'
            )
            html = re.sub(pat, rf'\g<1>{cnt}\g<2>{cnt}\g<3>{cli}\g<4>', html, flags=re.DOTALL, count=1)

        # ── Atualiza seção de equipes em campo ──
        COSAMPA_PROC_MAP = {
            'CPS-TR-11B':'em','CPR-RD-12B':'em','CPN-RD-13B':'em','CPF-RD-14B':'em',
            'CPB-RD-15B':'em','CPE-RD-16B':'em','CPE-RD-12C':'em','CPN-RD-13C':'em',
            'CPS-TR-11C':'em','CPR-RD-14D':'em','CPN-RD-12D':'em','CPA-RD-13D':'em',
            'CPS-LB-11B':'co','CPR-LB-12B':'co','CPE-LB-13B':'co','CPB-LB-14B':'co',
            'CPS-MM-11B':'co','CPP-MM-13B':'co','CPE-MM-14B':'co','CPB-MM-15B':'co',
            'CPS-MP-11B':'ml','CPS-COS-02B':'ml','CPS-COS-03B':'ml','CPS-COS-01B':'ml',
            'CPS-COS-04B':'ml','CPS-COS-05B':'ml','CPS-LV-11B':'ml',
            'JZN-RD-19C':'em','JZB-RD-16C':'em','JZN-SK-11C':'em','JZN-RD-17C':'em',
            'JZN-RD-16C':'em','JZN-RD-13D':'em','JZN-RD-15D':'em','JZN-RD-10C':'em',
            'JZC-RD-14D':'em','JZC-RD-12C':'em','JZN-RD-10B':'em','JZN-RD-11B':'em',
            'JZN-RD-22B':'em','JZN-RD-15B':'em','JZB-RD-16B':'em','JZN-SK-11B':'em',
            'JZN-RD-28B':'em','JZU-RD-14B':'em','JZC-RD-17B':'em','JZC-RD-18B':'em',
            'JZN-MP-11B':'em','JZN-RD-27B':'em',
            'JZN-LB-12B':'co','JZN-LB-13B':'co','JZN-LB-14B':'co','JZN-LB-15B':'co',
            'JZN-LB-17B':'co','JZC-LB-20B':'co','JZC-LB-21B':'co','JZC-LB-22B':'co',
            'CPN-LB-28B':'co','JZN-LB-11B':'co','JZN-LB-18B':'co','JZN-LB-19B':'co',
            'JZB-LB-23B':'co','JZB-LB-24B':'co','JZB-LB-25B':'co','MLJ-LB-16B':'co',
            'JZU-LB-26B':'co','JZN-GA-11B':'co',
            'JZN-COS-01B':'ml','JZN-COS-02B':'ml','JZN-COS-03B':'ml','JZN-COS-05B':'ml',
            'JZN-COS-06B':'ml','JZN-COS-07B':'ml','JZN-COS-04B':'ml','JZD-COS-09B':'ml',
            'JZN-COS-10B':'ml','JZN-COS-11B':'ml','JZN-COS-12B':'ml',
            'JZN-MM-13B':'co','JZN-MM-14B':'co','JZN-MM-15B':'co','JZN-MM-21B':'co',
            'JZN-MM-23B':'co','JZC-MM-11B':'co','JZC-MM-17B':'co','JZB-MM-16B':'co',
            'JZB-MM-22B':'co','MLJ-MM-12B':'co','JZU-MM-19B':'co','CPN-MM-18B':'co',
            'CPF-MM-24B':'co','JZN-MM-12B':'co',
            'JZN-ML-11B':'ml','JZN-LV-11B':'ml','JZN-LV-12B':'ml',
            'JZN-LV-11R':'ml','JZN-LV-12R':'ml',
            'MLG-TR-11B':'em','MLV-RD-12B':'em','MLS-RD-15B':'em','MLM-RD-16B':'em',
            'MLJ-RD-17B':'em','MLP-RD-18B':'em','MLB-RD-13B':'em','MLG-TR-11C':'em',
            'MLS-RD-12C':'em','MLB-RD-13C':'em','MLM-RD-14C':'em','MLV-RD-16C':'em',
            'MLG-RD-14B':'em','MLB-RD-15D':'em',
            'MLG-LB-11B':'co','MLV-LB-12B':'co','MLV-LB-13B':'co','MLS-LB-14B':'co',
            'MLM-LB-18B':'co','MLA-LB-16B':'co','MLP-LB-19B':'co',
            'MLG-MM-11B':'co','MLV-MM-12B':'co','MLS-MM-13B':'co','MLM-MM-14B':'co',
            'MLA-MM-15B':'co','MLP-MM-16B':'co',
            'MLG-ML-11B':'ml','MLG-MP-11B':'ml','MLG-COS-01B':'ml','MLG-COS-03B':'ml',
            'MLG-COS-04B':'ml','MLG-COS-06B':'ml','MLG-COS-02B':'ml','MLG-COS-05B':'ml',
            'MLG-COS-08B':'ml','MLG-COS-09B':'ml','MLG-LV-11B':'ml',
        }
        VTR_TITLE = {'em':'Cosampa Emergencial','co':'Cosampa Comercial','ml':'Cosampa Manutenção'}

        vtrs_ativas = list(dict.fromkeys(d['vtr'] for d in dados if d.get('vtr')))
        total_vtr = len(vtrs_ativas)
        n_em  = sum(1 for v in vtrs_ativas if COSAMPA_PROC_MAP.get(v) == 'em')
        n_co  = sum(1 for v in vtrs_ativas if COSAMPA_PROC_MAP.get(v) == 'co')
        n_ml  = sum(1 for v in vtrs_ativas if COSAMPA_PROC_MAP.get(v) == 'ml')
        n_cos = n_em + n_co + n_ml
        n_el  = total_vtr - n_cos
        pct_em = round(n_em * 100 / total_vtr) if total_vtr else 0
        pct_co_ml = round((n_co + n_ml) * 100 / total_vtr) if total_vtr else 0
        pct_el = 100 - pct_em - pct_co_ml

        vtrs_el = [v for v in vtrs_ativas if v not in COSAMPA_PROC_MAP]

        # Atualiza total de viaturas
        html = re.sub(
            r'(<span class="eq-total">)[^<]*(</span>)',
            f'\g<1>{total_vtr} viaturas em atendimento\g<2>',
            html, count=1
        )
        # Atualiza barras
        html = re.sub(
            r'(<div class="eq-barra">).*?(</div>)',
            f'\g<1>'
            f'<div class="eq-seg" style="width:{pct_em}%;background:var(--red);opacity:.85"></div>'
            f'<div class="eq-seg" style="width:{pct_co_ml}%;background:var(--green)"></div>'
            f'<div class="eq-seg" style="width:{pct_el}%;background:var(--muted)"></div>'
            f'\g<2>',
            html, flags=re.DOTALL, count=1
        )
        # Atualiza legenda
        enel_ids = ' · '.join(vtrs_el) if vtrs_el else ''
        html = re.sub(
            r'(<div class="eq-legend">).*?(</div>\s*<div class="divider">)',
            f'\g<1>'
            f'<div class="eq-item"><div class="eq-dot" style="background:var(--red)"></div>'
            f'<span class="eq-num" style="color:#fca5a5">{n_em}</span>'
            f'<span class="eq-lbl">Cosampa Emergencial</span><span class="eq-pct">{pct_em}%</span></div>'
            f'<div class="eq-item"><div class="eq-dot" style="background:var(--green)"></div>'
            f'<span class="eq-num" style="color:#6ee7b7">{n_co + n_ml}</span>'
            f'<span class="eq-lbl">Cosampa Comercial/Outros</span><span class="eq-pct">{pct_co_ml}%</span></div>'
            f'<div class="eq-item"><div class="eq-dot" style="background:var(--muted)"></div>'
            f'<span class="eq-num" style="color:#9ca3af">{n_el}</span>'
            f'<span class="eq-lbl">Enel / não identificada</span><span class="eq-pct">{pct_el}%</span>'
            f'<span class="eq-enel-ids">{enel_ids}</span></div>'
            f'\g<2>',
            html, flags=re.DOTALL, count=1
        )
        # Atualiza tags de viaturas
        def vtr_tag(v):
            p = COSAMPA_PROC_MAP.get(v)
            cls = 'vtr-em' if p == 'em' else 'vtr-co' if p == 'co' else 'vtr-ml' if p == 'ml' else 'vtr-el'
            title = VTR_TITLE.get(p, 'Enel / não identificada')
            return f'<span class="vtr {cls}" title="{title}">{v}</span>'
        vtrs_html = '\n      '.join(vtr_tag(v) for v in vtrs_ativas)
        html = re.sub(
            r'(<div class="vtr-row">).*?(</div>)',
            f'\\g<1>\n      {vtrs_html}\n    \\g<2>',
            html, flags=re.DOTALL, count=1
        )

        # Atualiza horario no header
        TAG = 'id="hdr-time"'
        if TAG in html:
            ini = html.find('>', html.find(TAG)) + 1
            fim = html.find('</span>', ini)
            html = html[:ini] + agora + html[fim:]

        with open(painel_path, "w", encoding="utf-8") as f:
            f.write(html)
        # Salva também dados.json para atualização em tempo real
        json_path = os.path.join(PASTA_SAIDA, "dados.json")
        payload = {
            "atualizado": agora,
            "total": len(dados),
            "dados": dados,
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True)

        print(f"[✓] Painel atualizado — {len(dados)} incidências  ({agora})")
    except Exception as e:
        print(f"[ERRO ao atualizar painel] {e}")
        traceback.print_exc()


# ── Main ──────────────────────────────────────────────────────────

def main():
    run_once = "--once" in sys.argv

    driver = iniciar_driver()
    try:
        fazer_login(driver)
    except Exception as e:
        print(f"[ERRO FATAL no login] {e}")
        traceback.print_exc()
        driver.quit()
        sys.exit(1)

    iteracao = 0
    while True:
        iteracao += 1
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iteração #{iteracao}")
        try:
            html_pagina = navegar_e_extrair(driver, primeira_vez=(iteracao == 1))
            # Valida se capturou a tela certa pelo cabeçalho
            tela_certa = "Nº Incidência" in html_pagina or "N° Incidência" in html_pagina or "INCIDÊNCIA" in html_pagina.upper()
            tela_errada = any(x in html_pagina for x in ["Distribuição", "Comarca", "GER DIST."])

            if tela_certa and not tela_errada:
                incidencias = parsear_incidencias(html_pagina)
                if incidencias:
                    salvar_painel(incidencias)
                    publicar_github()
                else:
                    print("[!] Nenhuma incidência extraída — mantendo dados anteriores")
            else:
                print("[!] Tela errada capturada — reiniciando Chrome do zero...")
                salvar_dump(driver, "dump_tela_errada.html")
                try:
                    driver.quit()
                except:
                    pass
                time.sleep(3)
                driver = iniciar_driver()
                fazer_login(driver)
                iteracao = 0
                print("[✓] Chrome reiniciado — próximo ciclo vai navegar do zero")
        except Exception as e:
            msg = str(e)
            print(f"[ERRO] {msg[:200]}")

            # Se sessão morreu (Chrome fechou), reinicia tudo do zero
            sessao_morta = any(x in msg for x in [
                "invalid session id", "session deleted", "NewConnectionError",
                "Max retries exceeded", "ConnectionRefusedError", "Failed to establish"
            ])

            if sessao_morta:
                print("[!] Sessão do Chrome morreu — reiniciando do zero...")
                try:
                    driver.quit()
                except:
                    pass
                time.sleep(3)
                try:
                    driver = iniciar_driver()
                    fazer_login(driver)
                    iteracao = 0
                    print("[✓] Chrome reiniciado com sucesso")
                except Exception as e2:
                    print(f"[ERRO ao reiniciar] {e2}")
                    time.sleep(10)
            else:
                # Erro leve — tenta só refazer login
                iteracao = 0
                try:
                    driver.get(URL_LOGIN)
                    time.sleep(3)
                    fazer_login(driver)
                except Exception as e2:
                    print(f"[ERRO login] {e2}")

        if run_once:
            print("[i] --once: encerrando")
            driver.quit()
            break

        print(f"[⏱] Aguardando {INTERVALO_MINUTOS} min...")
        time.sleep(INTERVALO_MINUTOS * 60)


if __name__ == "__main__":
    main()