"""Carga el catálogo de costes y los planes de partida vía la API de admin.

Idempotente: no duplica tarifas (misma clave + precio + fecha) ni planes
(mismo código). Para cambiar un precio más adelante, se añade una tarifa
nueva con otra `valid_from` desde la PWA (Planes -> Costes), no aquí.

Uso:
    ADMIN_API_KEY=... python scripts/billing/seed_pricing.py [--base-url http://localhost:8000] [--dry-run]

Fuentes (septiembre 2026):
- OpenAI, precios estándar por 1M tokens: https://developers.openai.com/api/docs/pricing
- Twilio España: recibir llamada 0,0178 USD/min + ConversationRelay 0,07 USD/min:
  https://www.twilio.com/en-us/voice/pricing/es
- Cambio 1 EUR = 1,1447 USD (22-sep-2026): https://tradingeconomics.com/euro-area/currency
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

USD_TO_EUR = 1 / 1.1447
MILLION = 1_000_000
VALID_FROM = "2026-01-01T00:00:00Z"
FX_NOTE = "USD->EUR a 1,1447 (22-sep-2026)"


def usd(amount: float) -> int:
    """USD -> micro-euros."""
    return round(amount * USD_TO_EUR * MILLION)


# (sku, input, cached input, output) en USD por 1M tokens - OpenAI, tier estándar.
OPENAI_MODELS = [
    ("gpt-4.1-mini*", 0.40, 0.10, 1.60),
    ("gpt-4.1-nano*", 0.10, 0.025, 0.40),
    ("gpt-4.1*", 2.00, 0.50, 8.00),
    ("gpt-4o-mini*", 0.15, 0.075, 0.60),
    ("gpt-5-mini*", 0.25, 0.025, 2.00),
    ("gpt-5-nano*", 0.05, 0.005, 0.40),
    ("gpt-5*", 1.25, 0.125, 10.00),
]

RATES = []
for sku, inp, cached, out in OPENAI_MODELS:
    for unit, price in (("input_token", inp), ("cached_input_token", cached), ("output_token", out)):
        RATES.append(dict(kind="llm", provider="openai", sku=sku, unit=unit, price_micros=usd(price),
                          per_quantity=MILLION, note=f"OpenAI lista {price} USD/1M · {FX_NOTE}"))

# Canales: Evolution (WhatsApp no oficial), Telegram y Messenger/Instagram no
# cobran por mensaje. Voz: se mide por turno (aún no por minuto); se estima un
# turno ~20 s de llamada = (0,0178 + 0,07) USD/min x 20/60.
for channel in ("whatsapp_evolution", "telegram", "facebook", "instagram"):
    RATES.append(dict(kind="channel", provider=channel, sku="*", unit="message", price_micros=0, per_quantity=1,
                      note="Sin coste por mensaje"))
RATES.append(dict(kind="channel", provider="voice", sku="message.inbound", unit="message",
                  price_micros=usd((0.0178 + 0.07) * 20 / 60), per_quantity=1,
                  note=f"Twilio ES: recibir 0,0178 + ConversationRelay 0,07 USD/min, ~20 s por turno · {FX_NOTE}"))
RATES.append(dict(kind="channel", provider="voice", sku="message.outbound", unit="message", price_micros=0,
                  per_quantity=1, note="Incluido en el coste por minuto del turno entrante"))
# Infraestructura propia (VPS, almacenamiento) repartida por mensaje atendido.
# ESTIMACIÓN: ajustar a coste mensual del VPS / mensajes al mes.
RATES.append(dict(kind="platform", provider="flowsdone", sku="ai_message", unit="message", price_micros=1_000,
                  per_quantity=1, note="Estimación de infraestructura (0,001 €/mensaje): ajustar a la factura real"))

MINI_MODELS = ["gpt-4.1-mini*", "gpt-4.1-nano*", "gpt-4o-mini*", "gpt-5-mini*", "gpt-5-nano*"]

PLANS = [
    dict(code="starter", name="Starter", description="Un asistente para empezar: texto, sin voz, sin sorpresas en la factura.",
         monthly_fee_micros=29 * MILLION, included_messages={"*": 1000, "voice": 0},
         overage_price_micros={"*": 30_000}, margin_pct="400", allowed_models=MINI_MODELS,
         monthly_token_allowance=5_000_000, default_overage_mode="hard_stop"),
    dict(code="pro", name="Pro", description="Varios canales y voz, con excedente por mensaje.",
         monthly_fee_micros=99 * MILLION, included_messages={"*": 5000, "voice": 300},
         overage_price_micros={"*": 20_000, "voice": 80_000}, margin_pct="300", allowed_models=MINI_MODELS,
         monthly_token_allowance=25_000_000, default_overage_mode="overage"),
    dict(code="business", name="Business", description="Volumen alto, cualquier modelo y más voz.",
         monthly_fee_micros=299 * MILLION, included_messages={"*": 20000, "voice": 1500},
         overage_price_micros={"*": 15_000, "voice": 70_000}, margin_pct="250", allowed_models=[],
         monthly_token_allowance=120_000_000, default_overage_mode="overage"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=os.getenv("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    key = os.getenv("ADMIN_API_KEY")
    if not key:
        print("Falta ADMIN_API_KEY", file=sys.stderr)
        return 2

    client = httpx.Client(base_url=f"{args.base_url.rstrip('/')}/internal/admin", headers={"X-Admin-Api-Key": key}, timeout=15)
    existing = {(r["kind"], r["provider"], r["sku"], r["unit"], r["price_micros"], r["valid_from"][:10])
                for r in client.get("/cost-rates").raise_for_status().json()}
    created = 0
    for rate in RATES:
        key_ = (rate["kind"], rate["provider"], rate["sku"], rate["unit"], rate["price_micros"], VALID_FROM[:10])
        if key_ in existing:
            continue
        print(f"tarifa  {rate['kind']:8} {rate['provider']:18} {rate['sku']:16} {rate['unit']:18} {rate['price_micros']:>10} µ€ / {rate['per_quantity']}")
        if not args.dry_run:
            client.post("/cost-rates", json={**rate, "valid_from": VALID_FROM}).raise_for_status()
        created += 1

    codes = {p["code"] for p in client.get("/plans").raise_for_status().json()}
    for plan in PLANS:
        if plan["code"] in codes:
            print(f"plan    {plan['code']}: ya existe, no se toca")
            continue
        print(f"plan    {plan['code']}: {plan['monthly_fee_micros'] / MILLION:.0f} €/mes")
        if not args.dry_run:
            client.post("/plans", json=plan).raise_for_status()
    print(f"{created} tarifas nuevas{' (dry-run)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
