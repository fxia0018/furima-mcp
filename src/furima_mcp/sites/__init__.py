from . import mercari, paypay, rakuma, yahoo

SITES = {m.NAME: m for m in (mercari, yahoo, paypay, rakuma)}
# Sites with a searchable sold history.
SOLD_SITES = ("mercari", "yahoo", "rakuma")
