import os, json, argparse, feedparser, requests, smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

# ====================== CONFIG ======================
TOPICS = {
    "Marketing": ["marketing digital","performance marketing","ads","growth","copywriting","CAC","ROI","criativo"],
    "IA": ["inteligência artificial","machine learning","IA","LLM","GPT","openai","modelo generativo"],
    "Tecnologia": ["tecnologia","startup","software","cloud","saas","github","cibersegurança","big tech"],
    "Mercado Imobiliário": ["imobiliário","mercado imobiliário","imóveis","construtora","loteamento","incorporadora","aluguel","locação"],
    "Brasil": ["Brasil","economia brasileira","política brasileira","Selic","BCB","Câmara","Senado"],
    "Mercado Financeiro": ["mercado financeiro","bolsa","renda fixa","juros","câmbio","IPCA","Ibovespa"]
}

RSS_SOURCES = [
    # Brasil / economia / tech / marketing — edite à vontade
    "https://g1.globo.com/rss/g1/economia/",
    "https://valor.globo.com/rss/",
    "https://www.infomoney.com.br/feed/",
    "https://tecnoblog.net/feed/",
    "https://canaltech.com.br/rss/",
    "https://techcrunch.com/feed/",
    "https://feeds.feedburner.com/MarketingLand"
]
# ====================================================

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()

def fetch_rss_items():
    items = []
    for url in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                items.append({
                    "title": e.get("title"),
                    "link": e.get("link"),
                    "published": e.get("published", ""),
                    "summary": e.get("summary", "")
                })
        except Exception as ex:
            print(f"[WARN] RSS erro {url}: {ex}")
    return items

def fetch_newsapi(query, api_key, from_days=7, page_size=25, lang="pt"):
    if not api_key: 
        return []
    url = "https://newsapi.org/v2/everything"
    since = (datetime.utcnow() - timedelta(days=from_days)).isoformat()
    params = {"q": query, "apiKey": api_key, "from": since, "pageSize": page_size, "language": lang, "sortBy": "publishedAt"}
    try:
        r = requests.get(url, params=params, timeout=20)
        if r.status_code == 200:
            arts = r.json().get("articles", [])
            return [{
                "title": a.get("title"),
                "link": a.get("url"),
                "published": a.get("publishedAt"),
                "summary": a.get("description") or ""
            } for a in arts]
        else:
            print("[WARN] NewsAPI status", r.status_code, r.text[:200])
    except Exception as ex:
        print("[WARN] NewsAPI erro:", ex)
    return []

def dedupe(items):
    seen, out = set(), []
    for it in items:
        key = (it.get("title") or "") + (it.get("link") or "")
        if key not in seen:
            seen.add(key); out.append(it)
    return out

def classify_by_topic(items):
    out = {k: [] for k in TOPICS}
    for it in items:
        text = (it.get("title","") + " " + it.get("summary","")).lower()
        for topic, kws in TOPICS.items():
            if any(kw.lower() in text for kw in kws):
                out[topic].append(it)
    return out

# ----- OpenAI summarize -----
import openai
def summarize_topic(topic, articles, max_articles=6):
    if not articles:
        return f"Nenhuma notícia relevante encontrada para {topic} nos últimos 7 dias."
    prompt = (
        f"Crie um resumo executivo em PT-BR sobre {topic} citando as notícias mais relevantes dos últimos 7 dias.\n"
        f"Formato:\n"
        f"1) TOP 5: TÍTULO + LINK + 1 frase de contexto.\n"
        f"2) 3 insights acionáveis.\n"
        f"3) 1 headline curta para post.\n\n"
        f"Notícias:\n"
    )
    for a in articles[:max_articles]:
        prompt += f"- {a.get('title')}\n  {a.get('link')}\n"
    prompt += "\nAgora gere o resumo, direto e claro."

    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        max_tokens=650, temperature=0.2
    )
    return resp.choices[0].message.content.strip()

def build_email_html(by_topic, summaries):
    html_sections = []
    for topic in by_topic:
        count = len(by_topic[topic])
        html_sections.append(f"<h2>{topic} — {count} notícias</h2><pre style='white-space:pre-wrap'>{summaries[topic]}</pre>")
    html = "<html><body>"
    html += "<h1>Resumo semanal — Marketing · IA · Tecnologia · Imobiliário · Brasil · Financeiro</h1>"
    html += "".join(html_sections)
    html += f"<hr><p>Gerado em {utc_now_iso()}</p>"
    html += "</body></html>"
    return html

def send_email(subject, html_body, smtp_host, smtp_port, smtp_user, smtp_pass, to_email):
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email
    s = smtplib.SMTP(smtp_host, int(smtp_port))
    s.starttls()
    s.login(smtp_user, smtp_pass)
    s.sendmail(smtp_user, [to_email], msg.as_string())
    s.quit()

def collect(from_days=7):
    rss_items = fetch_rss_items()
    news_items = []
    news_key = os.getenv("NEWSAPI_KEY")
    if news_key:
        for topic in TOPICS.keys():
            news_items += fetch_newsapi(topic, news_key, from_days=from_days)
    all_items = dedupe(rss_items + news_items)
    with open("collected.json","w",encoding="utf-8") as f:
        json.dump({"collected_at": utc_now_iso(), "items": all_items}, f, ensure_ascii=False, indent=2)
    print(f"[OK] Coletados {len(all_items)} itens em collected.json")

def summarize_and_send(collected_path="collected.json"):
    with open(collected_path,"r",encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items", [])
    by_topic = classify_by_topic(items)
    openai.api_key = os.getenv("OPENAI_KEY")
    summaries = {t: summarize_topic(t, by_topic[t]) for t in by_topic}
    html = build_email_html(by_topic, summaries)
    send_email(
        subject="Resumo semanal — Marketing/IA/Tecnologia/Imobiliário/Brasil/Financeiro",
        html_body=html,
        smtp_host=os.getenv("SMTP_HOST","smtp.gmail.com"),
        smtp_port=os.getenv("SMTP_PORT","587"),
        smtp_user=os.getenv("SMTP_USER"),
        smtp_pass=os.getenv("SMTP_PASS"),
        to_email=os.getenv("TO_EMAIL") or os.getenv("SMTP_USER")
    )
    with open("last_summary.json","w",encoding="utf-8") as f:
        json.dump({"generated_at": utc_now_iso(), "summaries": summaries}, f, ensure_ascii=False, indent=2)
    print("[OK] Email enviado e last_summary.json salvo.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect-only", action="store_true", help="Coleta e salva collected.json")
    parser.add_argument("--summarize-and-send", nargs="?", const="collected.json", help="Gera resumo e envia email a partir do arquivo")
    args = parser.parse_args()

    if args.collect_only:
        collect(from_days=7)
    elif args.summarize_and_send:
        summarize_and_send(args.summarize_and_send)
    else:
        collect(from_days=7)
        summarize_and_send("collected.json")
