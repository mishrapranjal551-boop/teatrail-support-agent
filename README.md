# TeaTrail Store Support Agent: Tara 🍵

Tara is a warm and cheerful customer support chat agent for **TeaTrail Store**,
a (made-up) online store for tea, coffee, snacks and gift hampers.

Built with **Google ADK** and **Gemini Flash-Lite**, with a **Streamlit** web page.

## What Tara does
- Greets customers and stays on topic: products, orders, delivery, payments, returns, refunds
- Answers only from TeaTrail's FAQ sheet (Google Sheets, read as CSV) and shows the source category
- Raises tickets (`TKT-1001`, `TKT-1002`, …) in `tickets.csv` for hand-off to a person when:
  the answer isn't in the FAQ, a refund or return is over ₹2,000, an item is damaged or wrong,
  the customer is upset, or the customer asks for a person
- Guardrails: never shares other customers' details, never promises refunds or discounts,
  ignores "ignore your rules" tricks, never asks for card numbers, OTPs or passwords
- Public web page, open to any customer with no passcode: suggested questions, 👍/👎 feedback,
  and a sidebar showing only that customer's own tickets
- Message limits protect the Gemini quota: 30 messages per visitor per day, 500 for the whole
  site per day, and a short wait between messages (change them in Secrets)

## Project files
| File | What it does |
|---|---|
| `tara/agent.py` | Tara's instructions (guardrails, tone, FAQ rules, hand-off rules) and the agent |
| `tara/faq.py` | Loads the FAQ sheet from its CSV link when Tara starts |
| `tara/tickets.py` | `create_ticket` tool: saves tickets to `tickets.csv` with IDs made by the code |
| `tara/chat.py` | Small helper to send a message to Tara and get the reply |
| `test_tricky.py` | Sends 6 tricky messages and checks the replies |
| `app.py` | The Streamlit web page |

## Run it on your laptop
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```
1. Copy `.env.example` to `.env` and add your Gemini key from https://aistudio.google.com
2. Optional: copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` to change the message limits

| Command | What it does |
|---|---|
| `adk web` | Chat with Tara in ADK's dev UI |
| `python test_tricky.py` | Run the tricky-message tests |
| `streamlit run app.py` | Open the web page |

## Deploy
On Streamlit Community Cloud, set the main file to `app.py` and add
`GOOGLE_API_KEY` under **Settings → Secrets** (plus the optional message limits).

> Secrets live only in `.env` and `.streamlit/secrets.toml`, which are git-ignored.
