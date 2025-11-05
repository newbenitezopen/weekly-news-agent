# Weekly News Agent

Agente semanal que coleta notícias relevantes dos últimos 7 dias (domingo 22:00 BRT) e envia um resumo por e-mail na segunda às 13:00 BRT.

## Horários
- Coleta: **Domingo 22:00 BRT** (equivalente a **Segunda 01:00 UTC**).
- Resumo+Envio: **Segunda 13:00 BRT** (equivalente a **16:00 UTC**).

## Secrets necessários
- `OPENAI_KEY`
- `SMTP_HOST` = smtp.gmail.com
- `SMTP_PORT` = 587
- `SMTP_USER` = seuemail@gmail.com
- `SMTP_PASS` = senha de app do Gmail
- `TO_EMAIL`  = destinatário
- (opcional) `NEWSAPI_KEY`

## Rodar manualmente
- Em Actions → Run workflow, ou local:
```
pip install -r requirements.txt
python agent_weekly.py --collect-only
python agent_weekly.py --summarize-and-send collected.json
```
