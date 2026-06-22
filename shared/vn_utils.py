import re
import unicodedata
from html import unescape


def normalize_vietnamese(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_price_vnd(text: str) -> int | None:
    if not text:
        return None
    text = text.replace(".", "").replace(",", "").replace(" ", "")
    text = text.replace("₫", "").replace("đ", "").replace("VND", "").replace("vnđ", "")
    match = re.search(r"(\d+)", text)
    if match:
        price = int(match.group(1))
        if price < 1000:
            price *= 1000
        return price
    return None


def clean_title(title: str) -> str:
    title = normalize_vietnamese(title)
    title = re.sub(r"\s*\([^)]*chính hãng[^)]*\)", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*-\s*Hàng chính hãng", "", title, flags=re.IGNORECASE)
    # Strip promotional badges that get mixed into product-title elements
    for tag in ["Mẫu mới", "Hàng sắp về", "HOTSALE", "Giá rẻ quá", "Online giá rẻ quá",
                 "Giảm giá", "Trả chậm 0%", "Trả trước 0đ", "Độc quyền"]:
        title = title.replace(tag, "")
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def extract_brand(title: str) -> str:
    known_brands = [
        "Apple", "Samsung", "Xiaomi", "OPPO", "Vivo", "Realme", "Nokia",
        "ASUS", "Acer", "Dell", "HP", "Lenovo", "MSI", "Gigabyte",
        "LG", "Sony", "Panasonic", "Sharp", "Toshiba", "Electrolux",
        "Daikin", "Midea", "Aqua", "Casper", "TCL", "Hisense",
        "JBL", "Harman Kardon", "Marshall", "Bose", "Logitech",
        "TP-Link", "Corsair", "Razer", "SteelSeries", "HyperX",
        "Intel", "AMD", "Nvidia", "WD", "Seagate", "Kingston",
        "Philips", "Bosch", "Sunhouse", "Kangaroo", "Karofi",
        # New brands from expanded sources
        "Huawei", "Honor", "Google", "OnePlus", "Nothing", "ZTE",
        "NZXT", "Cooler Master", "Thermaltake", "DeepCool", "Xigmatek",
        "ASRock", "EVGA", "Zotac", "Galax", "Colorful", "Inno3D",
        "Crucial", "Lexar", "ADATA", "Transcend", "KIOXIA", "Hikvision",
        "ViewSonic", "BenQ", "AOC", "Dahua",
        "Whirlpool", "Hitachi", "Mitsubishi", "Carrier", "Gree",
        "Hafele", "Malloca", "Teka", "Bluestone", "Lock&Lock",
    ]
    title_upper = title.upper()
    for brand in known_brands:
        if brand.upper() in title_upper:
            return brand
    return ""


VALID_CATEGORIES = {
    "Dien_thoai", "Laptop", "May_tinh_bang", "TV", "Tu_lanh", "May_giat",
    "May_lanh", "Am_thanh", "Nha_bep", "VGA", "CPU", "Mainboard", "RAM",
    "Luu_tru", "Nguon_Case", "Tan_nhiet", "Man_hinh", "Ban_phim", "Chuot",
    "Phu_kien",
}

# keyword → category, checked in order (first match wins)
_CATEGORY_MAPPING = [
    ("dien thoai", "Dien_thoai"), ("điện thoại", "Dien_thoai"),
    ("smartphone", "Dien_thoai"), ("phone", "Dien_thoai"), ("mobile", "Dien_thoai"),
    ("laptop", "Laptop"), ("may tinh xach tay", "Laptop"), ("máy tính xách tay", "Laptop"),
    ("tablet", "May_tinh_bang"), ("may tinh bang", "May_tinh_bang"),
    ("máy tính bảng", "May_tinh_bang"), ("ipad", "May_tinh_bang"),
    ("tivi", "TV"), ("tv", "TV"), ("television", "TV"),
    ("tu lanh", "Tu_lanh"), ("tủ lạnh", "Tu_lanh"), ("refrigerator", "Tu_lanh"),
    ("may giat", "May_giat"), ("máy giặt", "May_giat"), ("washing", "May_giat"),
    ("may lanh", "May_lanh"), ("máy lạnh", "May_lanh"),
    ("dieu hoa", "May_lanh"), ("điều hòa", "May_lanh"),
    ("tai nghe", "Am_thanh"), ("loa", "Am_thanh"), ("am thanh", "Am_thanh"),
    ("âm thanh", "Am_thanh"), ("audio", "Am_thanh"), ("speaker", "Am_thanh"),
    ("headphone", "Am_thanh"), ("earphone", "Am_thanh"),
    ("nha bep", "Nha_bep"), ("nhà bếp", "Nha_bep"), ("kitchen", "Nha_bep"),
    ("noi com", "Nha_bep"), ("nồi cơm", "Nha_bep"), ("lo vi song", "Nha_bep"),
    ("lò vi sóng", "Nha_bep"), ("bep tu", "Nha_bep"), ("bếp từ", "Nha_bep"),
]


def standardize_category(raw_category: str, source: str = "", title: str = "") -> str:
    # If the raw category is already a valid standardized name, keep it
    # But refine generic "Phu_kien" by title if possible
    if raw_category in VALID_CATEGORIES and raw_category != "Phu_kien":
        return raw_category

    if raw_category != "Phu_kien":
        raw = raw_category.lower().replace("_", " ").strip()
        for key, value in _CATEGORY_MAPPING:
            if key in raw:
                return value

    # Classify by title keywords (PC hardware, peripherals, etc.)
    if title:
        return classify_by_title(title)

    return "Phu_kien"


def classify_by_title(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["vga", "card màn hình", "card man hinh", "geforce", "radeon", "rtx ", "gtx "]):
        return "VGA"
    if any(k in t for k in ["màn hình", "man hinh", "monitor"]):
        return "Man_hinh"
    if any(k in t for k in ["cpu ", "core i", "ryzen", "vi xử lý", "xeon"]):
        return "CPU"
    if any(k in t for k in ["mainboard", "bo mạch chủ", "bo mach chu"]):
        return "Mainboard"
    if any(k in t for k in ["ram ", "ram\t", "bộ nhớ"]) and "laptop" not in t:
        return "RAM"
    if any(k in t for k in ["ssd ", "ssd\t", "ổ cứng thể rắn", "o cung the ran"]):
        return "Luu_tru"
    if any(k in t for k in ["hdd ", "hdd\t", "ổ cứng", "o cung"]):
        return "Luu_tru"
    if any(k in t for k in ["nguồn", "nguon", "psu"]):
        return "Nguon_Case"
    if any(k in t for k in ["case ", "vỏ case", "vo case", "thùng máy", "thung may"]):
        return "Nguon_Case"
    if any(k in t for k in ["tản nhiệt", "tan nhiet", "cooling", "quạt", "quat", "aio "]):
        return "Tan_nhiet"
    if any(k in t for k in ["bàn phím", "ban phim", "keyboard"]):
        return "Ban_phim"
    if any(k in t for k in ["chuột", "chuot", "mouse", "lót chuột", "lot chuot"]):
        return "Chuot"
    if any(k in t for k in ["tai nghe", "headphone", "earphone", "earbuds"]):
        return "Am_thanh"
    if any(k in t for k in ["loa ", "speaker"]):
        return "Am_thanh"
    return "Phu_kien"


def fuzzy_title_key(title: str) -> str:
    key = title.lower()
    key = re.sub(r"[^a-z0-9\s]", "", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key
