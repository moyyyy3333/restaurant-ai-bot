#!/usr/bin/env bash
# Point Stripe at the live webhook and push both Stripe secrets to Render.
# Usage: STRIPE_SECRET_KEY=sk_live_... ./scripts/stripe_activate.sh
set -euo pipefail

url="${PUBLIC_BASE_URL:-https://restaurant-ai-bot-n844.onrender.com}/webhook/stripe"
: "${STRIPE_SECRET_KEY:?set STRIPE_SECRET_KEY}"
api() { curl -sS -u "$STRIPE_SECRET_KEY:" "$@"; }

# Stripe only reveals the signing secret at creation, so drop any prior endpoint
# for this URL instead of trying to read its secret back.
api https://api.stripe.com/v1/webhook_endpoints?limit=100 \
  | python3 -c "import sys,json;print('\n'.join(e['id'] for e in json.load(sys.stdin)['data'] if e['url']=='$url'))" \
  | while read -r id; do
      if [ -n "$id" ]; then
        api -X DELETE "https://api.stripe.com/v1/webhook_endpoints/$id" >/dev/null
      fi
    done

api https://api.stripe.com/v1/webhook_endpoints \
  -d "url=$url" \
  -d "enabled_events[]=checkout.session.completed" \
  -d "enabled_events[]=checkout.session.expired" \
  -d "enabled_events[]=invoice.paid" \
  -d "enabled_events[]=customer.subscription.deleted" \
  -o endpoint.json
python3 -c "
import json,sys
d=json.load(open('endpoint.json'))
if 'error' in d: sys.exit('stripe: '+d['error']['message'])
open('whsec.txt','w').write(d['secret'])
print('endpoint', d['id'], 'events', len(d['enabled_events']))
"

gh secret set STRIPE_SECRET_KEY --body "$STRIPE_SECRET_KEY"
gh secret set STRIPE_WEBHOOK_SECRET < whsec.txt
rm -f whsec.txt endpoint.json
gh workflow run sync-payment-env.yml
echo "Stripe wired. Watch: gh run list -w sync-payment-env.yml -L1"
