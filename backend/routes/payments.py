"""Payment callback and payment page routes."""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
import stripe as stripe_lib
from config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY, APP_BASE_URL
from database import db
from conversation.booking import complete_card_payment

router = APIRouter()
logger = logging.getLogger("PaymentRoutes")
stripe_lib.api_key = STRIPE_SECRET_KEY


@router.post("/momo/callback")
async def momo_callback(request: Request):
    try:
        data = await request.json()
        logger.info(f"MoMo callback: {data}")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"MoMo callback error: {e}")
        return {"status": "error"}


@router.post("/moov/callback")
async def moov_callback(request: Request):
    try:
        data = await request.json()
        logger.info(f"Moov callback: {data}")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Moov callback error: {e}")
        return {"status": "error"}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        if STRIPE_WEBHOOK_SECRET and STRIPE_WEBHOOK_SECRET != 'your_webhook_secret_here':
            event = stripe_lib.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            import json
            event = json.loads(payload)
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return {"error": str(e)}

    event_type = event.get("type", "")
    if event_type == "payment_intent.succeeded":
        intent = event.get("data", {}).get("object", {})
        intent_id = intent.get("id")
        if intent_id:
            await complete_card_payment(None, intent_id)
    return {"status": "ok"}


@router.get("/pay/{booking_id}")
async def payment_page(booking_id: str):
    booking = await db.bookings.find_one({"booking_ref": booking_id}, {"_id": 0})
    if not booking:
        booking = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not booking:
        return HTMLResponse("<h1>Booking not found</h1>", status_code=404)

    payment_intent = await db.payment_intents.find_one({"booking_id": booking.get("booking_ref") or booking.get("id")}, {"_id": 0})
    client_secret = payment_intent.get("client_secret", "") if payment_intent else ""

    if not STRIPE_PUBLISHABLE_KEY or STRIPE_PUBLISHABLE_KEY == 'your_stripe_publishable_key_here':
        return HTMLResponse(f"""<!DOCTYPE html><html><body style='font-family:sans-serif;max-width:600px;margin:50px auto;text-align:center'>
<h2>Travelio Payment</h2><p>Booking: {booking.get("booking_ref")}</p><p>Amount: {booking.get("price_eur")}EUR</p>
<p style='color:orange'>Stripe not configured -- simulated mode</p>
<button onclick='window.close()' style='padding:12px 24px;background:#6C63FF;color:white;border:none;border-radius:8px;cursor:pointer'>Simulate Payment</button>
</body></html>""")

    return HTMLResponse(f"""<!DOCTYPE html><html><head>
<title>Travelio - Paiement</title><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://js.stripe.com/v3/"></script>
<style>body{{font-family:sans-serif;max-width:500px;margin:50px auto;padding:20px}}
.pay-btn{{width:100%;padding:14px;border:none;border-radius:8px;font-size:16px;cursor:pointer;margin:8px 0}}
#card-element{{border:1px solid #ccc;border-radius:8px;padding:14px;margin:16px 0}}
.gpay{{background:#000;color:#fff}}.apay{{background:#000;color:#fff}}
.card-pay{{background:#6C63FF;color:#fff}}</style></head>
<body><h2>Travelio</h2>
<p>Reservation: <strong>{booking.get("booking_ref")}</strong></p>
<p>Montant: <strong>{booking.get("price_eur")}EUR</strong></p>
<div id="card-element"></div><div id="error" style="color:red;margin:8px 0"></div>
<button class="pay-btn gpay" id="gpay">Google Pay</button>
<button class="pay-btn apay" id="apay">Apple Pay</button>
<button class="pay-btn card-pay" id="card-btn">Payer par carte</button>
<div id="success" style="display:none;text-align:center;color:green;font-size:18px;margin-top:20px">
<p>Paiement confirme ! Retournez sur WhatsApp.</p></div>
<script>
const stripe=Stripe('{STRIPE_PUBLISHABLE_KEY}');
const elements=stripe.elements({{clientSecret:'{client_secret}'}});
if('{client_secret}'){{
  const card=elements.create('payment');card.mount('#card-element');
  document.getElementById('card-btn').onclick=async()=>{{
    const{{error}}=await stripe.confirmPayment({{elements,confirmParams:{{return_url:'{APP_BASE_URL}/api/pay/{booking_id}?success=1'}}}});
    if(error)document.getElementById('error').textContent=error.message;
  }};
}}
</script></body></html>""")


@router.get("/tickets/{filename}")
async def serve_ticket(filename: str):
    from fastapi.responses import FileResponse
    from config import TICKETS_DIR
    filepath = TICKETS_DIR / filename
    if filepath.exists():
        return FileResponse(str(filepath), media_type="application/pdf", filename=filename)
    return {"error": "Ticket not found"}


@router.get("/verify_qr/{booking_ref}")
async def verify_qr(booking_ref: str):
    booking = await db.bookings.find_one({"booking_ref": booking_ref}, {"_id": 0})
    if not booking:
        return {"valid": False, "error": "Booking not found"}
    return {"valid": booking.get("status") == "confirmed", "booking_ref": booking_ref, "status": booking.get("status"), "passenger": booking.get("passenger_name"), "route": f"{booking.get('origin')} -> {booking.get('destination')}", "date": booking.get("departure_date")}
