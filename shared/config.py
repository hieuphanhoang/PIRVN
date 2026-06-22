import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "phase1_data" / "raw_data"
CURATED_DATA_DIR = PROJECT_ROOT / "phase2_curation" / "curated_data"
MODELS_DIR = PROJECT_ROOT / "phase3_baselines" / "models"
VECTORSTORE_DIR = PROJECT_ROOT / "phase5_rag" / "products_vectorstore"

# Price range (VND)
MIN_PRICE = 500_000
MAX_PRICE = 50_000_000

# Text constraints
MIN_DESCRIPTION_LENGTH = 50
MAX_TEXT_LENGTH = 4000

# Categories (standardized across all sources)
CATEGORIES = [
    "Dien_thoai",
    "Laptop",
    "May_tinh_bang",
    "TV",
    "Tu_lanh",
    "May_giat",
    "May_lanh",
    "Am_thanh",
    "Nha_bep",
    "VGA",
    "CPU",
    "Mainboard",
    "RAM",
    "Luu_tru",
    "Nguon_Case",
    "Tan_nhiet",
    "Man_hinh",
    "Ban_phim",
    "Chuot",
    "Phu_kien",
]

CATEGORY_DISPLAY = {
    "Dien_thoai": "Dien thoai",
    "Laptop": "Laptop",
    "May_tinh_bang": "May tinh bang",
    "TV": "TV",
    "Tu_lanh": "Tu lanh",
    "May_giat": "May giat",
    "May_lanh": "May lanh",
    "Am_thanh": "Am thanh",
    "Nha_bep": "Nha bep",
    "VGA": "VGA / Card man hinh",
    "CPU": "CPU",
    "Mainboard": "Mainboard",
    "RAM": "RAM",
    "Luu_tru": "SSD / HDD",
    "Nguon_Case": "Nguon / Case",
    "Tan_nhiet": "Tan nhiet",
    "Man_hinh": "Man hinh",
    "Ban_phim": "Ban phim",
    "Chuot": "Chuot",
    "Phu_kien": "Phu kien khac",
}

CATEGORY_COLORS = [
    "red", "blue", "brown", "orange", "yellow",
    "green", "purple", "cyan", "pink", "lime",
    "darkred", "darkblue", "teal", "gold", "coral",
    "navy", "olive", "magenta", "gray", "salmon",
]

# Models
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
FRONTIER_MODEL = os.getenv("FRONTIER_MODEL", "gpt-4.1-mini")
SPECIALIST_HF_SPACE = os.getenv("SPECIALIST_HF_SPACE", "")

# Embedding model (Qwen3 via Ollama — strong on Vietnamese)
EMBEDDING_MODEL = "qwen3-embedding"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# HuggingFace
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_DATASET_NAME = os.getenv("HF_DATASET_NAME", "your-username/pirvn-products")

# Agent thresholds
DEAL_THRESHOLD = 1_000_000  # 1M VND discount to trigger notification
SCANNER_TOP_K = 5
RAG_SIMILAR_K = 5

# Scraping
SCRAPE_DELAY = 0.5  # seconds between requests
SCRAPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}
