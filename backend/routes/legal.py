"""Legal compliance endpoints - Terms of Service and Privacy Policy."""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/legal")


@router.get("/terms")
async def terms_of_service():
    return HTMLResponse("""<!DOCTYPE html><html><head><title>Travelio - Conditions Generales</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:sans-serif;max-width:700px;margin:40px auto;padding:20px;line-height:1.6;color:#333}
h1{color:#6C63FF}h2{color:#444;margin-top:24px}p{margin:8px 0}</style></head>
<body>
<h1>Conditions Generales d'Utilisation</h1>
<p><em>Derniere mise a jour : Fevrier 2026</em></p>

<h2>1. Objet</h2>
<p>Travelio est un service de reservation de billets d'avion accessible via WhatsApp. En utilisant le service, vous acceptez les presentes conditions.</p>

<h2>2. Inscription</h2>
<p>L'utilisation de Travelio necessite un numero WhatsApp valide. Vous devez fournir des informations exactes lors de l'inscription (nom, passeport).</p>

<h2>3. Reservations</h2>
<p>Les vols proposes proviennent de nos partenaires aeriens via Duffel. Les prix incluent une commission Travelio de 15EUR par billet. Les tarifs sont affiches en EUR et XOF.</p>

<h2>4. Paiements</h2>
<p>Modes acceptes : MTN MoMo, Moov Money, Google Pay, Apple Pay. Les paiements sont securises et traites par nos partenaires certifies.</p>

<h2>5. Annulations et Remboursements</h2>
<p>Les conditions d'annulation dependent du type de billet (Budget, Standard, Flex). Les frais Travelio (15EUR) ne sont pas remboursables. Les remboursements sont traites sous 3 a 10 jours ouvres.</p>

<h2>6. Responsabilite</h2>
<p>Travelio agit en tant qu'intermediaire entre le voyageur et les compagnies aeriennes. Nous ne sommes pas responsables des annulations, retards ou modifications effectuees par les compagnies.</p>

<h2>7. Protection des Donnees</h2>
<p>Vos donnees personnelles sont chiffrees (AES-256-GCM) et stockees conformement au RGPD. Voir notre <a href="/api/legal/privacy">Politique de Confidentialite</a>.</p>

<h2>8. Contact</h2>
<p>support@travelio.app</p>
</body></html>""")


@router.get("/privacy")
async def privacy_policy():
    return HTMLResponse("""<!DOCTYPE html><html><head><title>Travelio - Politique de Confidentialite</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:sans-serif;max-width:700px;margin:40px auto;padding:20px;line-height:1.6;color:#333}
h1{color:#6C63FF}h2{color:#444;margin-top:24px}p{margin:8px 0}ul{margin:8px 0 8px 20px}</style></head>
<body>
<h1>Politique de Confidentialite</h1>
<p><em>Derniere mise a jour : Fevrier 2026</em></p>

<h2>1. Donnees Collectees</h2>
<ul>
<li>Numero WhatsApp</li>
<li>Nom et prenom (tel qu'indique sur le passeport)</li>
<li>Numero de passeport (chiffre)</li>
<li>Date de naissance (chiffree)</li>
<li>Date d'expiration du passeport (chiffree)</li>
<li>Historique des reservations</li>
</ul>

<h2>2. Utilisation des Donnees</h2>
<p>Vos donnees sont utilisees exclusivement pour :</p>
<ul>
<li>La reservation et l'emission de billets d'avion</li>
<li>Le traitement des paiements</li>
<li>Le service client et le support</li>
</ul>

<h2>3. Securite</h2>
<p>Les donnees sensibles (passeport, dates) sont chiffrees avec AES-256-GCM avant stockage. Les cles de chiffrement sont protegees et separees des donnees.</p>

<h2>4. Conservation</h2>
<p>Les sessions de conversation sont supprimees apres 30 minutes d'inactivite. Les donnees de reservation sont conservees 24 mois, puis anonymisees. Les donnees de paiement sont conservees 5 ans (obligation legale).</p>

<h2>5. Partage</h2>
<p>Vos donnees ne sont partagees qu'avec :</p>
<ul>
<li>Les compagnies aeriennes (pour l'emission du billet)</li>
<li>Les prestataires de paiement (MTN, Moov, Stripe)</li>
</ul>
<p>Aucune donnee n'est vendue a des tiers.</p>

<h2>6. Vos Droits</h2>
<p>Conformement au RGPD, vous pouvez demander l'acces, la rectification ou la suppression de vos donnees en contactant support@travelio.app.</p>

<h2>7. Retention et Suppression</h2>
<p>Les donnees de session expirent automatiquement. Sur demande, nous supprimons vos donnees sous 30 jours.</p>

<h2>8. Contact DPO</h2>
<p>dpo@travelio.app</p>
</body></html>""")
