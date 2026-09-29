import os
import time
import requests

BASE = "https://api.gateio.ws/api/v4/futures/usdt"

GROWTH_MIN = 50.0
ATH_RATIO_MAX = 3.0


def get_json(url, params=None):
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def get_ath(contract):
    highs = []
    to_ts = int(time.time())

    while True:
        candles = get_json(
            f"{BASE}/candlesticks",
            {
                "contract": contract,
                "interval": "1d",
                "to": to_ts,
                "limit": 1000,
            },
        )

        if not candles:
            break

        valid = [c for c in candles if "h" in c and "t" in c]

        highs.extend(float(c["h"]) for c in valid)

        if len(candles) < 1000 or not valid:
            break

        oldest = min(int(c["t"]) for c in valid)

        if oldest >= to_ts:
            break

        to_ts = oldest - 1
        time.sleep(0.15)

    return max(highs) if highs else None


def send_ntfy(message):
    topic = os.environ.get("NTFY_TOPIC")

    if not topic:
        print("NTFY_TOPIC не задан")
        return

    r = requests.post(
        f"https://ntfy.sh/{topic}",
        data=message.encode("utf-8"),
        headers={
            "Title": "Gate Futures",
            "Priority": "high",
            "Tags": "chart_with_upwards_trend",
        },
        timeout=30,
    )

    r.raise_for_status()
    print("Push-уведомление отправлено")


def main():
    tickers = get_json(f"{BASE}/tickers")

    candidates = []

    for x in tickers:
        try:
            growth = float(x["change_percentage"])
            price = float(x["last"])

            if growth > GROWTH_MIN and price > 0:
                candidates.append(
                    (x["contract"], growth, price)
                )

        except (KeyError, TypeError, ValueError):
            pass

    print(
        f"Фьючерсов с ростом > {GROWTH_MIN}%: "
        f"{len(candidates)}"
    )

    signals = []

    for contract, growth, price in candidates:
        try:
            ath = get_ath(contract)

            if not ath:
                continue

            ratio = ath / price
            below_ath = (1 - price / ath) * 100

            print(
                contract,
                "24h:", growth,
                "price:", price,
                "ATH:", ath,
                "ATH/price:", ratio,
            )

            if ratio <= ATH_RATIO_MAX:
                signals.append(
                    {
                        "contract": contract,
                        "growth": growth,
                        "price": price,
                        "ath": ath,
                        "below_ath": below_ath,
                    }
                )

        except Exception as e:
            print(f"{contract}: ошибка {e}")

    print("\nНАШИ СИГНАЛЫ")

    if not signals:
        print("Подходящих фьючерсов сейчас нет.")
        return

    signals.sort(
        key=lambda x: x["growth"],
        reverse=True,
    )

    for s in signals:
        print()
        print(s["contract"])
        print(f'Рост 24ч: +{s["growth"]:.2f}%')
        print(f'Цена: {s["price"]}')
        print(f'ATH: {s["ath"]}')
        print(f'Ниже ATH: {s["below_ath"]:.2f}%')

        message = (
            f'🔥 {s["contract"]}\n'
            f'Рост за 24ч: +{s["growth"]:.2f}%\n'
            f'Цена: {s["price"]}\n'
            f'ATH: {s["ath"]}\n'
            f'Ниже ATH: {s["below_ath"]:.2f}%'
        )

        send_ntfy(message)


if __name__ == "__main__":
    main()
