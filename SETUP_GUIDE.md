# 🚀 World Market Agent - Complete Setup Guide

## ✅ What You Have Now

Your World Market shopping agent is **ready to go**! Here's what's been created:

```
world-market-agent/
├── 📂 scraper/          ✅ Web scraper (working - got 20 products!)
├── 📂 agent/            ✅ Core agent with Claude integration
├── 📂 ui/               ✅ Streamlit web interface
├── 📂 data/             ✅ products.json with 20 real products
├── 🐳 Dockerfile        ✅ Docker setup for easy sharing
├── 📝 README.md         ✅ Complete documentation
└── 🔧 All config files  ✅ Ready to run
```

## 🔑 Step 1: Get Your Claude API Key

The API key you provided doesn't match Anthropic's format. Here's how to get a valid one:

### Option A: Use Anthropic's Official API (Recommended)

1. **Go to**: https://console.anthropic.com/
2. **Sign up** or log in
3. **Click** "Get API Keys" in the left sidebar
4. **Create a new key** - it will look like: `sk-ant-api03-...` (much longer)
5. **Copy** the full key

### Option B: Use Your Company's Internal API

If you're using Salesforce's internal Claude API:
- Check your internal docs for the correct endpoint
- You may need to update `agent/world_market_agent.py` with custom base_url

## 🔧 Step 2: Update Your .env File

Replace the key in `/Users/bhagath.ganga/world-market-agent/.env`:

```bash
# Replace with your real API key
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-REAL-KEY-HERE-MUCH-LONGER
```

## 🧪 Step 3: Test the Agent

Run the test script:

```bash
cd /Users/bhagath.ganga/world-market-agent
python3 test_agent.py
```

You should see output like:

```
🌍 World Market Agent - Quick Test
============================================================
📦 Loading agent...
✅ Loaded 20 products

🧪 Testing query: 'Show me furniture under $300'
------------------------------------------------------------

✅ Agent Response:
============================================================

💭 Thought:
User wants furniture under $300. I'll search with price filter...

[Product recommendations here...]

✅ Test successful!
```

## 🎨 Step 4: Launch the Web UI

Once the test works, launch the beautiful web interface:

```bash
cd /Users/bhagath.ganga/world-market-agent
python3 -m pip install streamlit pydantic fastapi uvicorn
cd ui
streamlit run app.py
```

Then open: **http://localhost:8501**

## 🐳 Step 5: Package for Your Colleagues (Docker)

Once everything works, sharing is easy:

```bash
cd /Users/bhagath.ganga/world-market-agent

# Build and run
docker-compose up --build
```

Then share the entire folder with your team!

## 📦 Step 6: Get More Products (Optional)

Currently you have 20 products. To scrape more:

```bash
cd scraper

# Edit world_market_scraper.py, line 191:
# Change: max_products_per_category=20
# To:     max_products_per_category=100

python3 world_market_scraper.py
```

This will scrape ~100 products per category (700+ total).

## 🛠️ Troubleshooting

### "Invalid API Key" Error

**Problem**: The API key doesn't work

**Solutions**:
1. Get a real key from https://console.anthropic.com/
2. Or ask your Salesforce team for the internal Claude API endpoint
3. Check .env file is in the right place with correct format

### "Catalog not found" Error

**Problem**: Can't find products.json

**Solution**:
```bash
cd scraper
python3 world_market_scraper.py
```

### Scraper Returns 0 Products

**Problem**: World Market's website structure changed

**Solution**: Update CSS selectors in `scraper/world_market_scraper.py`:
- Line 56-61: Update `product-tile` class names
- Test with: `curl https://www.worldmarket.com/category/furniture.do`

### Import Errors

**Problem**: Missing Python packages

**Solution**:
```bash
cd /Users/bhagath.ganga/world-market-agent
python3 -m pip install -r requirements.txt
```

## 🚀 Quick Start (Once API Key Works)

```bash
cd /Users/bhagath.ganga/world-market-agent

# Test it
python3 test_agent.py

# Run web UI
cd ui && streamlit run app.py

# Or use Docker
docker-compose up
```

## 📞 Getting Help

1. **Check logs**: The agent prints detailed logs including:
   - Tool calls being made
   - Search queries being executed
   - Products found

2. **Test individual components**:
   ```bash
   # Test scraper only
   cd scraper && python3 world_market_scraper.py

   # Test catalog loading
   python3 -c "import json; print(len(json.load(open('data/products.json'))))"
   ```

3. **Verbose mode**: Edit `agent/world_market_agent.py` line 89-92 to add debug prints

## 🎯 Next Steps

Once it's working:

1. ✅ **Test with real queries** - Try the examples in README.md
2. ✅ **Scrape more products** - Expand your catalog
3. ✅ **Customize the prompt** - Edit `agent/system_prompt.py`
4. ✅ **Share with colleagues** - Just zip and send!
5. ✅ **Deploy to cloud** - Use Railway, Render, or AWS

## 💡 Pro Tips

- **Fast iteration**: Keep the web UI running, edit `system_prompt.py`, refresh
- **Better search**: The agent uses parallel queries - see `agent/system_prompt.py` for examples
- **Custom tools**: Add new tools in `agent/world_market_agent.py` line 45-70
- **Styling**: Edit `ui/app.py` CSS to match your brand

---

**Ready?** Get your API key, update .env, and run `python3 test_agent.py`! 🚀
