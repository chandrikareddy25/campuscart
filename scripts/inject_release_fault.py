"""Edit local source only. Apply solely during a scheduled demo without users."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('fault',choices=['checkout-500','wrong-total']);a=p.parse_args()
path=Path('backend/app/main.py');text=path.read_text()
if '# RELEASE EXPERIMENT FAULT' in text:raise SystemExit('A fault is already present; restore source first')
if a.fault=='checkout-500':
    anchor='def create_order(body:OrderInput,user=Depends(current_user)):\n'
    replacement=anchor+"    # RELEASE EXPERIMENT FAULT\n    raise HTTPException(500, 'Controlled release experiment')\n"
else:
    anchor='    ORDERS.inc();return result'
    replacement="    # RELEASE EXPERIMENT FAULT\n    result['total'] += Decimal('1.00')\n"+anchor
if text.count(anchor)!=1:raise SystemExit('Source differs: refusing to edit')
path.write_text(text.replace(anchor,replacement))
print('Local source changed. No release was deployed. Review git diff before committing.')
