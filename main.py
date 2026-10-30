import os, csv, io, hmac, logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field, HttpUrl
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("keyword-master")

APP_NAME = "Keyword Master | Odonto Master"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
GOOGLE_CUSTOMER_ID = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "").replace("-", "")
GOOGLE_LOGIN_CUSTOMER_ID = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "")
GOOGLE_DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_ADS_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

app = FastAPI(title=APP_NAME, version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET or "local-dev-secret-change-me",
                   same_site="lax", https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true")
app.add_middleware(CORSMiddleware, allow_origins=[], allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

class LoginBody(BaseModel):
    password: str

class KeywordRequest(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=20)
    url: Optional[str] = None
    location_id: str = "2076"
    language_id: str = "1014"
    limit: int = Field(default=100, ge=1, le=500)
    include_average_cpc: bool = True

class AnalyzeBody(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=1000)

def require_auth(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Sessão expirada. Entre novamente.")
    return True

def google_configured():
    return all([GOOGLE_CUSTOMER_ID, GOOGLE_DEVELOPER_TOKEN, GOOGLE_CLIENT_ID,
                GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN])

def google_client():
    if not google_configured():
        raise HTTPException(status_code=503, detail="Integração Google Ads ainda não configurada. Preencha as variáveis GOOGLE_ADS_* no Render.")
    config = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": GOOGLE_REFRESH_TOKEN,
        "use_proto_plus": True,
    }
    if GOOGLE_LOGIN_CUSTOMER_ID:
        config["login_customer_id"] = GOOGLE_LOGIN_CUSTOMER_ID
    try:
        return GoogleAdsClient.load_from_dict(config)
    except Exception as exc:
        log.exception("Falha ao inicializar Google Ads")
        raise HTTPException(status_code=500, detail=f"Não foi possível iniciar o cliente Google Ads: {str(exc)[:240]}")

@app.get("/api/health")
def health():
    return {"status": "ok", "google_ads_configured": google_configured(),
            "openai_configured": bool(OPENAI_API_KEY)}

@app.post("/api/login")
def login(body: LoginBody, request: Request):
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="Defina ADMIN_PASSWORD nas variáveis de ambiente.")
    if not hmac.compare_digest(body.password.encode(), ADMIN_PASSWORD.encode()):
        raise HTTPException(status_code=401, detail="Senha incorreta.")
    request.session.clear()
    request.session["authenticated"] = True
    request.session["created_at"] = datetime.now(timezone.utc).isoformat()
    return {"ok": True}

@app.post("/api/logout")
def logout(request: Request, _: bool = Depends(require_auth)):
    request.session.clear()
    return {"ok": True}

@app.get("/api/me")
def me(request: Request):
    return {"authenticated": bool(request.session.get("authenticated"))}

@app.post("/api/keywords")
def generate_keywords(body: KeywordRequest, _: bool = Depends(require_auth)):
    seeds = [s.strip() for s in body.keywords if s.strip()]
    if not seeds and not body.url:
        raise HTTPException(status_code=400, detail="Informe pelo menos uma palavra-chave ou uma URL.")
    if len(seeds) > 20:
        raise HTTPException(status_code=400, detail="Informe no máximo 20 palavras-chave iniciais.")
    if body.url and not body.url.startswith(("https://", "http://")):
        raise HTTPException(status_code=400, detail="A URL precisa começar com http:// ou https://.")
    client = google_client()
    service = client.get_service("KeywordPlanIdeaService")
    request_obj = client.get_type("GenerateKeywordIdeasRequest")
    request_obj.customer_id = GOOGLE_CUSTOMER_ID
    request_obj.language = client.get_service("GoogleAdsService").language_constant_path(body.language_id)
    request_obj.geo_target_constants.append(
        client.get_service("GoogleAdsService").geo_target_constant_path(body.location_id)
    )
    request_obj.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    request_obj.include_adult_keywords = False
    request_obj.page_size = min(body.limit, 500)
    request_obj.historical_metrics_options.include_average_cpc = body.include_average_cpc

    if seeds and body.url:
        request_obj.keyword_and_url_seed.url = body.url
        request_obj.keyword_and_url_seed.keywords.extend(seeds)
    elif seeds:
        request_obj.keyword_seed.keywords.extend(seeds)
    else:
        request_obj.url_seed.url = body.url

    try:
        response = service.generate_keyword_ideas(request=request_obj)
        rows = []
        for item in response.results:
            m = item.keyword_idea_metrics
            low = int(m.low_top_of_page_bid_micros or 0) / 1_000_000
            high = int(m.high_top_of_page_bid_micros or 0) / 1_000_000
            avg = int(m.average_cpc_micros or 0) / 1_000_000
            rows.append({
                "keyword": item.text,
                "close_variants": list(item.close_variants),
                "avg_monthly_searches": int(m.avg_monthly_searches or 0),
                "competition": str(m.competition).replace("KeywordPlanCompetitionLevelEnum.", ""),
                "competition_index": int(m.competition_index or 0),
                "low_top_of_page_bid": round(low, 2),
                "high_top_of_page_bid": round(high, 2),
                "average_cpc": round(avg, 2),
                "monthly_search_volumes": [
                    {"year": int(v.year), "month": str(v.month).replace("MonthOfYearEnum.", ""),
                     "searches": int(v.monthly_searches or 0)} for v in m.monthly_search_volumes
                ],
            })
        rows.sort(key=lambda x: x["avg_monthly_searches"], reverse=True)
        return {"count": len(rows), "keywords": rows, "generated_at": datetime.now(timezone.utc).isoformat(),
                "target": {"location_id": body.location_id, "language_id": body.language_id}}
    except GoogleAdsException as exc:
        details = []
        for error in exc.failure.errors:
            details.append(getattr(error, "message", "Erro Google Ads"))
        log.exception("Google Ads API retornou erro")
        raise HTTPException(status_code=502, detail="Google Ads: " + " | ".join(details)[:900])
    except Exception as exc:
        log.exception("Erro ao gerar ideias")
        raise HTTPException(status_code=502, detail=f"Falha ao consultar Google Ads: {str(exc)[:500]}")

def classify_keyword(keyword: str):
    k = keyword.lower()
    groups = [
        ("Compra / contratação", ["comprar", "preço", "preco", "valor", "orçamento", "orcamento", "fornecedor", "loja", "onde comprar"]),
        ("Cursos / capacitação", ["curso", "especialização", "especializacao", "pós-graduação", "pos graduacao", "aperfeiçoamento", "aperfeicoamento", "aula"]),
        ("Produtos / equipamentos", ["equipamento", "instrumento", "material", "broca", "autoclave", "resina", "scanner", " cadeira", "consultório", "consultorio"]),
        ("Informacional", ["como", "o que é", "o que e", "para que", "benefícios", "beneficios", "tipos", "diferença", "diferenca"]),
    ]
    for label, terms in groups:
        if any(t in k for t in terms):
            return label
    return "Pesquisa / consideração"

@app.post("/api/analyze")
def analyze(body: AnalyzeBody, _: bool = Depends(require_auth)):
    cleaned = list(dict.fromkeys(k.strip() for k in body.keywords if k.strip()))
    groups = {}
    for k in cleaned:
        groups.setdefault(classify_keyword(k), []).append(k)
    negatives = ["grátis", "gratis", "gratuito", "download", "pdf", "apostila grátis", "emprego", "salário", "salario", "concurso", "sus"]
    suggested_negatives = [n for n in negatives if any(token in " ".join(cleaned).lower() for token in [n])]
    return {"total": len(cleaned), "groups": groups, "negative_keyword_ideas": suggested_negatives,
            "note": "Agrupamento heurístico inicial. Revise as negativas antes de aplicar: alguns termos podem ser relevantes para campanhas específicas."}

@app.post("/api/export.csv")
def export_csv(body: AnalyzeBody, _: bool = Depends(require_auth)):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Palavra-chave"])
    for keyword in body.keywords:
        writer.writerow([keyword])
    data = io.BytesIO(("\ufeff" + output.getvalue()).encode("utf-8"))
    return StreamingResponse(data, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=keyword-master-odonto-master.csv"})

@app.get("/", response_class=HTMLResponse)
def home():
    path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
