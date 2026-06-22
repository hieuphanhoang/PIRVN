# PIRVN — "The Price Is Right" Vietnam Edition

## Overview

A Vietnamese autonomous deal-hunting agent system that predicts product prices from descriptions, finds bargains on Vietnamese e-commerce sites, and sends Telegram notifications when deals are significantly below estimated value.

**Inspired by**: Weeks 6-8 capstone of the LLM Engineering course (`../week6/`, `../week7/`, `../week8/`)

---

## Decisions Summary

| Decision | Choice |
|----------|--------|
| Categories | Electronics + Home Appliances |
| Model strategy | Hybrid (Ollama local + paid APIs for Frontier) |
| Data collection | Manual seed + AI expansion |
| Notifications | Telegram bot |
| Dataset size | 100K+ items |
| Language | Bilingual — Vietnamese product data, English prompts, bilingual UI |
| Price range | 500,000 - 50,000,000 VND |
| Deal sources | websosanh.vn, priceprice.com/vn, store promotions |
| Fine-tuning | QLoRA on Google Colab (free T4) |
| Specialist deployment | HuggingFace Spaces |

---

## Source Sites

| Site | What to collect | Notes |
|------|----------------|-------|
| **thegioididong.com** | Phones, tablets, laptops, accessories | Structured pages, category URLs are clean |
| **dienmayxanh.com** | Home appliances, TVs, fridges, ACs, kitchen | Same parent company as TGDD |
| **gearvn.vn** | PC components, gaming laptops, peripherals | Tech-focused, detailed specs |
| **shopee.vn** | Broad — electronics, home, tools, accessories | Huge catalog but noisy data, needs heavy filtering |
| **cellphones.com.vn** | Phones, laptops, audio, smart home | Good product descriptions |
| **tinhocngoisao.com** | PC components, laptops, peripherals, networking | Detailed specs, competitive pricing |

---

## Project Structure

```
PIRVN/
├── PIRVN.md                    # This plan
├── REVIEW.md                   # Phase completion review
├── LESSON_LEARNED.md           # Problems & solutions log
│
├── phase1_data/                # Phase 1: Data Collection
│   ├── scrapers/
│   │   ├── tgdd_scraper.py         # thegioididong.com scraper
│   │   ├── dmx_scraper.py          # dienmayxanh.com scraper
│   │   ├── gearvn_scraper.py       # gearvn.vn scraper
│   │   ├── shopee_scraper.py       # shopee.vn scraper
│   │   ├── cellphones_scraper.py   # cellphones.com.vn scraper
│   │   ├── tinhocngoisao_scraper.py # tinhocngoisao.com scraper
│   │   └── base_scraper.py         # Shared scraping utilities
│   ├── augmentor.py            # AI-powered data augmentation
│   ├── collect.py              # Orchestrates all scrapers
│   └── raw_data/               # Raw scraped JSON files
│
├── phase2_curation/            # Phase 2: Data Curation
│   ├── items.py                # Item model (adapted from week8/agents/items.py)
│   ├── parser.py               # Parse raw data into Item objects
│   ├── curate.py               # Dedup, filter, sample, push to HF
│   ├── explore.ipynb           # EDA notebook (distributions, charts)
│   └── curated_data/           # Cleaned dataset files
│
├── phase3_baselines/           # Phase 3: Traditional ML + Baselines
│   ├── baselines.ipynb         # Constant, Linear, RF, XGBoost
│   ├── neural_net.ipynb        # PyTorch deep neural network
│   ├── llm_zeroshot.ipynb      # Ollama zero-shot pricing
│   └── models/                 # Saved model weights (.pth, .joblib)
│
├── phase4_finetune/            # Phase 4: Fine-Tuning
│   ├── prepare_data.py         # Create training JSONL for fine-tuning
│   ├── finetune_colab.ipynb    # QLoRA fine-tuning notebook (run on Colab)
│   ├── evaluate.ipynb          # Test fine-tuned model
│   └── export_gguf.py          # Convert to GGUF for local inference
│
├── phase5_rag/                 # Phase 5: RAG Pipeline
│   ├── build_vectorstore.py    # Embed products into ChromaDB
│   ├── rag_agent.py            # RAG-augmented pricing agent
│   └── products_vectorstore/   # ChromaDB persistent storage
│
├── phase6_agents/              # Phase 6: Multi-Agent System
│   ├── agent.py                # Base Agent class (from week8/agents/agent.py)
│   ├── scanner_agent.py        # Scans Vietnamese deal sites
│   ├── preprocessor.py         # Cleans deal descriptions (Ollama local)
│   ├── specialist_agent.py     # Calls fine-tuned model on HF Spaces
│   ├── frontier_agent.py       # GPT/Claude + RAG pricing
│   ├── neural_network_agent.py # Local PyTorch model
│   ├── deep_neural_network.py  # DNN architecture (from week8)
│   ├── ensemble_agent.py       # Weighted combination of all pricers
│   ├── planning_agent.py       # Orchestrates scan → price → notify
│   ├── autonomous_planning_agent.py  # LLM tool-calling loop version
│   ├── messaging_agent.py      # Telegram bot notifications
│   ├── deals.py                # Deal/Opportunity Pydantic models
│   └── items.py                # Item model for inference
│
├── phase7_deploy/              # Phase 7: Deployment & UI
│   ├── price_is_right_vn.py    # Main Gradio app
│   ├── deal_agent_framework.py # Framework orchestrator
│   ├── log_utils.py            # Log formatting
│   ├── memory.json             # Persisted deal memory
│   └── hf_spaces/              # HuggingFace Spaces deployment files
│       ├── app.py              # Specialist model API endpoint
│       ├── requirements.txt
│       └── README.md
│
└── shared/                     # Shared utilities
    ├── config.py               # All constants, API keys, model names
    ├── vn_utils.py             # Vietnamese text processing
    └── currency.py             # VND formatting, conversion helpers
```

---

## Phase 1: Data Collection (Manual + AI Expansion)

**Goal**: Collect 100K+ Vietnamese product listings with title, description, price, category, source.

**Reference**: `../week6/day1.ipynb` (Amazon data loading & initial exploration)

### Step 1.1 — Build Site-Specific Scrapers

Each scraper outputs a standardized JSON format:
```json
{
  "title": "Laptop ASUS VivoBook 15 OLED A1505ZA",
  "description": "Laptop van phong, man hinh 15.6 inch OLED...",
  "price": 16990000,
  "category": "Laptop",
  "source": "thegioididong.com",
  "url": "https://www.thegioididong.com/laptop/...",
  "brand": "ASUS",
  "specs": {"ram": "16GB", "storage": "512GB SSD", ...},
  "scraped_at": "2026-06-17"
}
```

**Scraping approach per site**:

| Site | Method | Notes |
|------|--------|-------|
| thegioididong.com | `requests` + `BeautifulSoup` | Category pages are server-rendered, paginated |
| dienmayxanh.com | `requests` + `BeautifulSoup` | Same structure as TGDD |
| gearvn.vn | `requests` + `BeautifulSoup` | Product list pages, detail pages for specs |
| shopee.vn | `playwright` or Shopee API | JS-rendered, needs browser automation or API |
| cellphones.com.vn | `requests` + `BeautifulSoup` | Clean HTML structure |
| tinhocngoisao.com | `requests` + `BeautifulSoup` | Server-rendered product pages |

**Target per site**: ~15K-20K items each to reach 100K+ total (6 sites).

**Categories to scrape**:
- `Dien_thoai` (Phones)
- `Laptop`
- `May_tinh_bang` (Tablets)
- `TV`
- `Tu_lanh` (Refrigerators)
- `May_giat` (Washing machines)
- `May_lanh` (Air conditioners)
- `Phu_kien` (Accessories)
- `Am_thanh` (Audio)
- `Nha_bep` (Kitchen appliances)

### Step 1.2 — AI-Powered Data Augmentation

For products with short/missing descriptions, use Ollama (Qwen3-4B) to:
1. Generate richer product descriptions from title + specs
2. Standardize category names across sources
3. Translate spec tables into readable paragraphs

```python
# augmentor.py — expand thin listings using local LLM
prompt = f"""Given this product info, write a detailed Vietnamese product description (3-5 sentences):
Title: {item['title']}
Brand: {item['brand']}
Specs: {item['specs']}
Price: {item['price']:,} VND
"""
```

### Step 1.3 — Manual Quality Check

- Sample 500 items randomly, verify price/description accuracy
- Fix systematic scraping errors found in the sample
- Remove obvious junk (placeholder listings, out-of-stock items with price=0)

**Deliverable**: `raw_data/` folder with JSON files per source, 100K+ items total.

---

## Phase 2: Data Curation

**Goal**: Clean, deduplicate, and prepare the dataset for training/evaluation.

**Reference**: `../week6/day1.ipynb` (dedup, filtering, distribution analysis), `../week8/agents/items.py` (Item model)

### Step 2.1 — Define the Item Model

Adapt from `../week8/agents/items.py`:
```python
class Item(BaseModel):
    title: str           # Product name (Vietnamese)
    title_en: str = ""   # English translation (optional, for prompts)
    category: str        # Standardized category
    price: float         # Price in VND
    source: str          # Which site it came from
    brand: str = ""
    full: str = ""       # Full description text
    weight: float = 0    # Weight in grams (if available)
    specs: dict = {}     # Structured specs
    prompt: str = ""     # Training prompt (filled in Phase 4)
```

### Step 2.2 — Filter & Clean

- Price range: 500,000 - 50,000,000 VND
- Minimum description length: 50 characters
- Remove duplicates by title similarity (fuzzy matching for Vietnamese)
- Normalize Vietnamese text (unicode NFC, strip HTML entities)
- Standardize category names across all sources

### Step 2.3 — Exploratory Data Analysis

Create `explore.ipynb` with:
- Price distribution histograms (overall + per category)
- Description length distribution
- Category balance chart
- Price vs. description length scatter plot
- Source distribution pie chart

### Step 2.4 — Train/Val/Test Split & Push to HuggingFace

```python
# 80% train, 5% val, 15% test
train = items[:80_000]
val = items[80_000:85_000]
test = items[85_000:]
Item.push_to_hub("your-username/pirvn-products", train, val, test)
```

**Deliverable**: Clean HuggingFace dataset with 100K+ items, EDA notebook with insights.

---

## Phase 3: Baselines & Traditional ML

**Goal**: Establish baseline performance. Measure MAE in VND.

**Reference**: `../week6/day3.ipynb` (baselines), `../week6/day4.ipynb` (deep learning)

### Step 3.1 — Constant Baseline

Predict the mean price for everything. This is the "floor" to beat.

### Step 3.2 — Traditional ML

Train and evaluate:
1. **Linear Regression** on text features (TF-IDF or hashing vectorizer)
2. **Random Forest** on text + category + brand features
3. **XGBoost** on the same features — this should be the strongest traditional model

### Step 3.3 — Deep Neural Network

Adapt from `../week8/agents/deep_neural_network.py`:
- Same architecture (10-layer residual network, 4096 hidden, skip connections)
- Input: HashingVectorizer(n_features=5000) on Vietnamese text
- Output: log-price regression
- Train on local CPU (slow but works) or Colab

### Step 3.4 — LLM Zero-Shot

Test Ollama (Qwen3-4B) zero-shot pricing:
```
Estimate the price of this product in VND. Respond with just the number.

{product_description}
```

### Expected Leaderboard (Phase 3)

| Model | MAE (VND) | Notes |
|-------|-----------|-------|
| Constant (mean) | ~5,000,000 | Floor |
| Linear Regression | ~3,500,000 | Text features only |
| Random Forest | ~2,800,000 | + category/brand |
| XGBoost | ~2,200,000 | Best traditional |
| Deep Neural Net | ~2,000,000 | Needs more training time |
| Qwen3-4B zero-shot | ~2,500,000 | No training, just prompting |

**Deliverable**: Saved model weights in `models/`, baseline comparison notebook.

---

## Phase 4: Fine-Tuning (QLoRA on Colab)

**Goal**: Fine-tune a small LLM to predict Vietnamese product prices, beating all baselines.

**Reference**: `../week7/day1.ipynb` through `../week7/day5.ipynb`

### Step 4.1 — Prepare Training Data

Format each item as a prompt-completion pair:
```
### Instruction:
San pham nay gia bao nhieu (VND)?

### Input:
Laptop ASUS VivoBook 15 OLED, man hinh 15.6 inch, RAM 16GB, SSD 512GB...

### Response:
16990000
```

Generate JSONL file with `messages` format for chat fine-tuning:
```json
{"messages": [
  {"role": "system", "content": "You are a Vietnamese product price estimator. Given a product description, predict its price in VND. Respond with only the number."},
  {"role": "user", "content": "San pham nay gia bao nhieu?\n\nLaptop ASUS VivoBook 15..."},
  {"role": "assistant", "content": "16990000"}
]}
```

### Step 4.2 — Fine-Tune on Colab

- **Base model**: Qwen3-1.7B (or Qwen2.5-3B if memory allows)
- **Method**: QLoRA (4-bit quantization + LoRA adapters)
- **Framework**: Unsloth (fast, memory-efficient)
- **Training**: ~3-5 epochs on 80K training items
- **Evaluation**: MAE on validation set after each epoch

### Step 4.3 — Export & Test

1. Merge LoRA adapters back into base model
2. Export to GGUF format for Ollama local testing
3. Also keep HuggingFace format for Spaces deployment
4. Evaluate on test set, compare to Phase 3 baselines

### Step 4.4 — Deploy to HuggingFace Spaces

Create a simple API endpoint on HF Spaces:
```python
# hf_spaces/app.py
import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer

model = AutoModelForCausalLM.from_pretrained("your-username/pirvn-pricer")
tokenizer = AutoTokenizer.from_pretrained("your-username/pirvn-pricer")

def price(description: str) -> float:
    prompt = f"San pham nay gia bao nhieu?\n\n{description}"
    # ... generate and parse price
    return predicted_price

iface = gr.Interface(fn=price, inputs="text", outputs="number")
iface.launch()
```

**Deliverable**: Fine-tuned model on HF Hub, deployed API on HF Spaces, evaluation results.

---

## Phase 5: RAG Pipeline

**Goal**: Build a vector database of 100K+ products for similarity-based pricing context.

**Reference**: `../week8/agents/frontier_agent.py` (RAG search), `../week8/deal_agent_framework.py` (ChromaDB setup)

### Step 5.1 — Build ChromaDB Vector Store

```python
# build_vectorstore.py
from sentence_transformers import SentenceTransformer
import chromadb

# Use multilingual model for Vietnamese text
model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

client = chromadb.PersistentClient(path="products_vectorstore")
collection = client.get_or_create_collection("vn_products")

for batch in batched(items, 500):
    embeddings = model.encode([item.full for item in batch])
    collection.add(
        ids=[str(item.id) for item in batch],
        embeddings=embeddings.tolist(),
        documents=[item.full for item in batch],
        metadatas=[{"price": item.price, "category": item.category, "source": item.source} for item in batch]
    )
```

**Key difference from original**: Use `paraphrase-multilingual-MiniLM-L12-v2` instead of `all-MiniLM-L6-v2` because the data is Vietnamese.

### Step 5.2 — RAG-Augmented Pricing Agent

When pricing a product:
1. Encode the description with the same multilingual model
2. Query ChromaDB for 5 most similar products
3. Include those 5 products + their prices as context in the LLM prompt
4. Ask GPT/Claude to estimate price given the context

### Step 5.3 — Evaluate RAG Impact

Compare:
- Frontier model (GPT/Claude) without RAG
- Frontier model + RAG (5 similar products)
- Frontier model + RAG (10 similar products)

**Deliverable**: ChromaDB vectorstore, RAG agent, evaluation showing improvement.

---

## Phase 6: Multi-Agent System

**Goal**: Build the full agent system adapted for Vietnam.

**Reference**: All files in `../week8/agents/`

### Agent Architecture

```
Vietnamese Deal Sites (websosanh.vn, priceprice.com)
    |
Scanner Agent (Ollama local) --> selects 5 best deals
    |
Preprocessor (Ollama local) --> clean product descriptions
    |
+------------------------------------------+
| Ensemble Agent                           |
|  +-- Frontier Agent (GPT/Claude + RAG)   |  <-- ChromaDB with 100K+ products
|  +-- Specialist Agent (HF Spaces)        |  <-- Fine-tuned Qwen on HF Spaces
|  +-- Neural Network Agent (local PyTorch)|  <-- Trained DNN
|  --> weighted combination = estimate     |
+------------------------------------------+
    |
Planning Agent: if (estimate - deal_price) > threshold
    |
Messaging Agent --> Telegram bot notification
```

### Step 6.1 — Adapt Scanner Agent

Replace DealNews RSS with Vietnamese deal sources:

```python
# scanner_agent.py
DEAL_SOURCES = [
    "https://websosanh.vn/rss/...",       # websosanh price comparison
    "https://www.priceprice.com/vn/...",   # priceprice deals
]
```

The Scanner will:
1. Scrape/fetch current deals from Vietnamese deal sites
2. Use Ollama (Qwen3-4B) locally to select the 5 best deals with clear prices
3. Return structured `DealSelection` using Pydantic

### Step 6.2 — Adapt Preprocessor

Same as original but with Vietnamese-aware prompt:
```python
SYSTEM_PROMPT = """Tao mo ta ngan gon ve san pham. Chi tra loi theo dinh dang sau:
Title: Tieu de ngan gon
Category: Vi du Dien tu
Brand: Ten thuong hieu
Description: 1 cau mo ta
Details: 1 cau ve tinh nang"""
```

Uses Ollama locally (Qwen3-4B). No API cost.

### Step 6.3 — Adapt Specialist Agent

Instead of Modal.com, call HuggingFace Spaces API:
```python
class SpecialistAgent(Agent):
    HF_SPACE_URL = "https://your-username-pirvn-pricer.hf.space/api/predict"

    def price(self, description: str) -> float:
        response = requests.post(self.HF_SPACE_URL, json={"data": [description]})
        return response.json()["data"][0]
```

### Step 6.4 — Adapt Frontier Agent

Use GPT or Claude with RAG context (paid API — this is the "hybrid" part):
```python
class FrontierAgent(Agent):
    MODEL = "gpt-4.1-mini"  # or claude-sonnet for cost control

    def price(self, description: str) -> float:
        documents, prices = self.find_similars(description)  # ChromaDB RAG
        # Include 5 similar Vietnamese products as context
        # Ask model to estimate price in VND
```

### Step 6.5 — Adapt Messaging Agent

Replace Pushover with Telegram Bot API:
```python
class MessagingAgent(Agent):
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def push(self, text):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        requests.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"})
```

### Step 6.6 — Adapt Ensemble Agent

Same weighted combination approach:
```python
combined = frontier * 0.8 + specialist * 0.1 + neural_network * 0.1
```

Tune these weights based on Phase 3/4 evaluation results.

### Step 6.7 — Deal Threshold

Original used $50 discount threshold. For VND:
```python
DEAL_THRESHOLD = 1_000_000  # 1M VND discount to trigger notification
```

**Deliverable**: All 7 agents working together, end-to-end pipeline tested.

---

## Phase 7: Deployment & Gradio UI

**Goal**: Build the final Gradio dashboard with Vietnamese deal hunting.

**Reference**: `../week8/price_is_right.py`, `../week8/deal_agent_framework.py`

### Step 7.1 — Deal Agent Framework

Adapt `deal_agent_framework.py`:
- Same ChromaDB setup but with Vietnamese products
- Same memory.json persistence
- Same t-SNE 3D visualization

### Step 7.2 — Gradio Dashboard

`price_is_right_vn.py` — bilingual UI:
- Title: "Gia Dung Roi — Vietnamese Deal Hunter"
- Table columns: Description | Price (VND) | Estimate (VND) | Discount (VND) | URL
- VND formatting with thousands separator (e.g., "16.990.000 VND")
- Live agent log panel
- 3D product vector visualization
- Auto-refresh every 5 minutes

### Step 7.3 — Telegram Bot Setup

1. Create bot via @BotFather on Telegram
2. Get bot token and your chat ID
3. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```

**Deliverable**: Working Gradio app, Telegram notifications, full pipeline running.

---

## Execution Plan

All code is written (57 files). See **[EX_PLAN.md](EX_PLAN.md)** for the step-by-step execution guide with detailed explanations of what to do, why it matters, and what to learn at each step.

**Quick summary**: 4 days total — Day 1 data collection, Day 2 curation + baselines, Day 3 fine-tuning, Day 4 integration + launch.

---

## Key Differences from Original

| Aspect | Original | PIRVN |
|--------|----------|-------|
| Data source | Amazon Reviews HF dataset (820K) | Manual scraping VN sites (100K+) |
| Currency | USD ($1-$1000) | VND (500K-50M) |
| Language | English | Vietnamese data, bilingual prompts |
| Embedding model | all-MiniLM-L6-v2 | paraphrase-multilingual-MiniLM-L12-v2 |
| Fine-tune base | Llama 3.2 3B | Qwen3-1.7B (or Qwen2.5-3B) |
| Specialist deploy | Modal.com (serverless GPU) | HuggingFace Spaces (free) |
| Deal source | DealNews RSS | websosanh.vn, priceprice.com/vn |
| Notifications | Pushover | Telegram bot |
| Scanner model | GPT-5-mini (paid) | Ollama/Qwen3-4B (local, free) |
| Preprocessor | Ollama/Llama 3.2 | Ollama/Qwen3-4B |
| Frontier model | GPT-5.1 (paid) | GPT-4.1-mini or Claude Sonnet (paid, cheaper) |

---

## Environment & Dependencies

Reuse the existing project venv where possible. Additional packages needed:

```bash
uv add playwright beautifulsoup4 feedparser chromadb sentence-transformers
uv add python-telegram-bot gradio plotly scikit-learn xgboost
uv add unidecode underthesea   # Vietnamese NLP
```

For Colab fine-tuning:
```bash
pip install unsloth transformers datasets peft bitsandbytes
```

---

## Files Reused from Original Project

These files from `../week8/` can be directly adapted:

| Original File | PIRVN Adaptation | Changes Needed |
|--------------|------------------|----------------|
| `agents/agent.py` | `phase6_agents/agent.py` | None — copy as-is |
| `agents/deep_neural_network.py` | `phase6_agents/deep_neural_network.py` | Adjust Y_MEAN/Y_STD for VND log-prices |
| `agents/items.py` | `phase2_curation/items.py` | Add Vietnamese fields, VND price |
| `agents/deals.py` | `phase6_agents/deals.py` | Change RSS feeds to VN deal sites |
| `agents/ensemble_agent.py` | `phase6_agents/ensemble_agent.py` | Minimal — adjust weights |
| `agents/planning_agent.py` | `phase6_agents/planning_agent.py` | Change threshold to VND |
| `agents/preprocessor.py` | `phase6_agents/preprocessor.py` | Vietnamese system prompt |
| `deal_agent_framework.py` | `phase7_deploy/deal_agent_framework.py` | VN categories/colors |
| `price_is_right.py` | `phase7_deploy/price_is_right_vn.py` | VND formatting, bilingual UI |
| `log_utils.py` | `phase7_deploy/log_utils.py` | Copy as-is |

---

## Status Tracker

- [ ] Phase 1: Data Collection
- [ ] Phase 2: Data Curation
- [ ] Phase 3: Baselines & Traditional ML
- [ ] Phase 4: Fine-Tuning
- [ ] Phase 5: RAG Pipeline
- [ ] Phase 6: Multi-Agent System
- [ ] Phase 7: Deployment & UI
