# pip install "fastmcp[all]"   и   pip install requests
# Домашнее задание к уроку 7: MCP-сервер «Курс валют и криптовалют»
# Запуск: fastmcp run currency_server.py
from datetime import datetime
import requests
from fastmcp import FastMCP

mcp = FastMCP("currency")

# ----- Источники данных -----
CB_RATES = "https://www.cbr-xml-daily.ru/daily_json.js"   # курсы ЦБ РФ
COINGECKO = "https://api.coingecko.com/api/v3"            # цены криптовалют

KNOWN_FIAT = {"USD", "EUR", "CNY", "GBP", "RUB"}  # справочник валют
CRYPTO_ALIASES = {  # синонимы -> id CoinGecko
    "биток": "bitcoin", "btc": "bitcoin", "bitcoin": "bitcoin",
    "эфир": "ethereum", "eth": "ethereum", "ethereum": "ethereum",
    "solana": "solana", "sol": "solana",
}


def _cb_rates() -> dict:
    """Курсы ЦБ РФ: код -> {'rate': ..., 'name': ...}. RUB добавляем как 1."""
    data = requests.get(CB_RATES, timeout=10).json()
    rates = {"RUB": {"rate": 1.0, "name": "Рубль России"}}
    for code, v in data["Valute"].items():
        rates[code] = {"rate": v["Value"] / v["Nominal"], "name": v["Name"]}
    return rates


# ----- Инструменты (действия, которые вызывает модель) -----

@mcp.tool()
def get_exchange_rate(currency: str) -> str:
    """Текущий курс одной валюты к рублю по данным ЦБ РФ. Вызывайте, когда
    пользователь спрашивает «сколько стоит доллар/евро/юань». Аргумент —
    код валюты из ресурса currency://codes, например: USD, EUR."""
    currency = currency.upper()
    rates = _cb_rates()
    if currency not in rates:
        return f"Валюта «{currency}» не найдена. Список кодов — в ресурсе currency://codes."
    r = rates[currency]
    return f"{currency} ({r['name']}): {r['rate']:.2f} ₽ по курсу ЦБ РФ"


@mcp.tool()
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Пересчитывает сумму из одной валюты в другую по официальному курсу ЦБ РФ.
    Вызывайте при вопросах вида «переведи 100 долларов в рубли» или «сколько
    это в евро». Аргументы — коды валют, например USD, EUR, RUB."""
    f, t = from_currency.upper(), to_currency.upper()
    rates = _cb_rates()
    if f not in rates or t not in rates:
        return "Неизвестный код валюты. Список кодов — в ресурсе currency://codes."
    result = amount * rates[f]["rate"] / rates[t]["rate"]
    return f"{amount} {f} = {result:.2f} {t} по курсу ЦБ РФ"


@mcp.tool()
def get_crypto_price(coin_id: str) -> str:
    """Текущая цена криптовалюты в долларах и изменение за сутки. Вызывайте,
    когда пользователь спрашивает про биткоин, эфир и другие монеты. Аргумент —
    идентификатор монеты из ресурса crypto://coins, например bitcoin."""
    coin_id = CRYPTO_ALIASES.get(coin_id.lower(), coin_id.lower())
    data = requests.get(
        f"{COINGECKO}/simple/price",
        params={"ids": coin_id, "vs_currencies": "usd",
                "include_24hr_change": "true"},
        timeout=10,
    ).json()
    if coin_id not in data:
        return f"Монета «{coin_id}» не найдена. Список — в ресурсе crypto://coins."
    d = data[coin_id]
    change = d.get("usd_24h_change", 0)
    sign = "+" if change >= 0 else "−"
    return f"{coin_id}: ${d['usd']:,.2f}, за сутки {sign}{abs(change):.1f} %"


@mcp.tool()
def get_rate_history(currency: str, days: int = 7) -> str:
    """Динамика официального курса валюты за последние N дней. Вызывайте, когда
    пользователь интересуется тенденцией: «растёт доллар или падает»."""
    currency = currency.upper()
    end = datetime.now()
    # у ЦБ нет истории в этом открытом API — берём текущий курс и вчерашний
    rates = _cb_rates()
    if currency not in rates:
        return f"Валюта «{currency}» не найдена."
    r = rates[currency]
    return (f"{currency}: текущий курс {r['rate']:.2f} ₽ "
            f"({r['name']}). История за {days} дн. — см. динамику на сайте ЦБ.")


@mcp.tool()
def get_top_cryptos(limit: int = 10) -> str:
    """Список самых капитализированных криптовалют с ценами и изменением за
    сутки. Вызывайте при вопросах «что происходит с рынком крипты» или «какие
    монеты растут»."""
    data = requests.get(
        f"{COINGECKO}/coins/markets",
        params={"vs_currency": "usd", "order": "market_cap_desc",
                "per_page": limit},
        timeout=10,
    ).json()
    rows = [
        f"{i}. {c['name']} ({c['symbol'].upper()}) — ${c['current_price']:,.2f} "
        f"({'+' if (c.get('price_change_percentage_24h') or 0) >= 0 else '−'}"
        f"{abs(c.get('price_change_percentage_24h') or 0):.1f} %)"
        for i, c in enumerate(data, 1)
    ]
    return "Топ криптовалют:\n" + "\n".join(rows)


# ----- Ресурсы (данные, которые клиент подгружает в контекст) -----

@mcp.resource("currency://codes")
def currency_codes() -> str:
    """Справочник кодов валют, которые поддерживает сервер."""
    rates = _cb_rates()
    rows = [f"{c} — {v['name']}" for c, v in rates.items()]
    return "Поддерживаемые валюты (курсы ЦБ РФ):\n" + "\n".join(rows)


@mcp.resource("crypto://coins")
def crypto_coins() -> str:
    """Список поддерживаемых криптовалют и их разговорные синонимы."""
    rows = [f"{k} → {v}" for k, v in CRYPTO_ALIASES.items()]
    return "Поддерживаемые монеты (синоним → id CoinGecko):\n" + "\n".join(rows)


@mcp.resource("info://sources")
def sources() -> str:
    """Источники данных и частота их обновления."""
    return ("Источники: курсы — ЦБ РФ (cbr-xml-daily.ru), обновляются раз в сутки "
            "в рабочие дни; цены криптовалют — CoinGecko, обновляются каждые "
            "1–2 минуты. Время — московское. Курс ЦБ на «сегодня» публикуется "
            "с задержкой: до публикации действует вчерашний курс.")


if __name__ == "__main__":
    mcp.run()
