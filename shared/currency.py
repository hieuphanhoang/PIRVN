def format_vnd(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", ".") + " VND"


def format_vnd_short(amount: float) -> str:
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"{amount / 1_000:.0f}K"
    return str(int(amount))


def parse_vnd(text: str) -> float:
    text = text.replace(".", "").replace(",", "").replace(" ", "")
    text = text.replace("₫", "").replace("đ", "").replace("VND", "")
    try:
        return float(text)
    except ValueError:
        return 0.0
