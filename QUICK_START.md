# ⚡ Quick Start - World Market Agent

## 🚦 Status Check

✅ Project created  
✅ 20 products scraped  
⚠️ **Need valid Anthropic API key**

## 🔑 Step 1: Get API Key (5 minutes)

Go to https://console.anthropic.com/ → Get API Keys → Copy the key

It should look like: `sk-ant-api03-...` (very long)

## 🔧 Step 2: Update .env

```bash
cd /Users/bhagath.ganga/world-market-agent
nano .env
```

Replace with your real key:
```
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-REAL-KEY-HERE
```

Save (Ctrl+O, Enter, Ctrl+X)

## 🧪 Step 3: Test It

```bash
python3 test_agent.py
```

Should see:
```
✅ Loaded 20 products
✅ Agent Response:
[Product recommendations]
✅ Test successful!
```

## 🎨 Step 4: Launch Web UI

```bash
python3 -m pip install streamlit
cd ui
streamlit run app.py
```

Open: http://localhost:8501

## 🎉 Done!

Try asking:
- "Show me furniture under $300"
- "What food items do you have?"
- "I need a chair for my living room"

## 🐳 Docker Alternative

```bash
docker-compose up --build
```

Then open: http://localhost:8501

## 📦 Share with Team

```bash
cd /Users/bhagath.ganga
zip -r world-market-agent.zip world-market-agent/
```

Send to colleagues → They run: `docker-compose up`

## 🆘 Issues?

See: `SETUP_GUIDE.md` for detailed troubleshooting

---

**Current Location**: `/Users/bhagath.ganga/world-market-agent/`
