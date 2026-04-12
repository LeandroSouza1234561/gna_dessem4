# GNA Monitor — DESSEM / ONS

Coleta automática do arquivo `pdo_oper_titulacao_usinas.dat` do portal SINTEGRE/ONS,
filtrado para **GNA I** e **GNA II**, com dashboard publicado via **GitHub Pages**.

---

## 📁 Estrutura

```
.
├── coletar_dessem.py              ← Script de coleta (roda no GitHub Actions)
├── requirements.txt               ← Dependências Python
├── .github/
│   └── workflows/
│       └── coletar.yml            ← Workflow do GitHub Actions (a cada 5min)
└── docs/
    ├── index.html                 ← Dashboard (GitHub Pages)
    ├── dados_gna.json             ← Dados coletados (atualizado automaticamente)
    └── pdo_oper_titulacao_usinas.dat ← Arquivo raw (atualizado automaticamente)
```

---

## 🚀 Como configurar

### 1. Criar o repositório no GitHub

```bash
git init
git add .
git commit -m "feat: GNA Monitor DESSEM"
git remote add origin https://github.com/SEU_USUARIO/gna-dessem.git
git push -u origin main
```

### 2. Configurar Secrets (credenciais ONS)

No GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Secret     | Valor                          |
|------------|-------------------------------|
| `ONS_USER` | `leandro.souza@gna.com.br`    |
| `ONS_PASS` | `sua_senha_do_portal_ONS`     |

> ⚠️ **Nunca** coloque a senha diretamente no código ou no `coletar_dessem.py`.

### 3. Ativar GitHub Pages

**Settings → Pages → Source → Deploy from a branch**
- Branch: `main`
- Folder: `/docs`

O dashboard ficará disponível em:
`https://SEU_USUARIO.github.io/gna-dessem/`

### 4. Ativar o workflow

O workflow roda automaticamente a cada 5 minutos.
Para rodar manualmente: **Actions → Coleta GNA — DESSEM / ONS → Run workflow**

---

## 📊 Dashboard

O dashboard em `docs/index.html`:
- Mostra **todas as colunas** do arquivo `.dat`
- Filtra automaticamente por **GNA I** e **GNA II**
- Tabs separadas para GNA I / GNA II / Todos
- Busca/filtro em tempo real
- Ordenação por coluna (clique no cabeçalho)
- Auto-refresh a cada 5 minutos
- Mostra cabeçalho raw do arquivo

---

## 🔧 Ajuste fino

Se o portal ONS mudar a estrutura da navegação, edite as funções
`fazer_login()` e `encontrar_e_baixar_dat()` em `coletar_dessem.py`.

Com o Actions, o browser roda em modo **headless** (sem janela).
Para depurar localmente, troque `headless=True` por `headless=False`.

---

## ⚠️ Observações

- GitHub Actions tem granularidade mínima de **5 minutos** no `cron`.
- O portal pode solicitar MFA. Nesse caso, o script não conseguirá
  autenticar automaticamente — será necessário ajustar para usar
  uma conta de serviço sem MFA ou implementar TOTP.
- O histórico mantém as últimas **288 coletas** (~24h).
