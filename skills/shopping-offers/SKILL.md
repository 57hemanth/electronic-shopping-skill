---
name: shopping-offers
description: Finds and checks the current offers on a product in India (bank card discounts, no-cost EMI, exchange, coupons, sale prices) on Amazon, Flipkart and brand stores, reads their conditions, and works out the real price after the best offer the buyer can use. Use for "any offers on this phone", "is this a good deal", "which card gives the best price".
license: Not yet chosen by the author.
metadata:
  version: "0.1.0"
---

# Offers: what will this actually cost?

The headline price is rarely what people pay. A ₹1,500 card discount, an exchange or a coupon changes
which store, and sometimes which product, is the better buy. You walk out with every current offer on
the product, its conditions, and one honest number: the price after the single best offer this buyer
can actually use.

The mistakes this prevents:
- **Adding offers together** that the store won't combine, or quoting "up to ₹12,000 exchange" as if
  everyone gets it.
- **Quoting an offer the buyer can't use**: a credit-card discount for someone with only a debit card,
  or an EMI-only discount for someone paying in full.

## When to use / not
- Use on its own when someone asks about offers or deals on a specific product, and inside the
  `electronic-shopping` skill for each shortlisted product.
- Not for coupons from unofficial coupon sites or "loot deal" channels: only offers shown by the store
  or the bank on their own pages.

## Hard rules
1. **Only offers you saw today on the store's or bank's own page.** Never from memory, never from
   coupon aggregator sites. Record the store, the wording, the conditions and the link.
2. **Read only.** Don't apply coupons, clip vouchers, sign in, add to cart or check out to reveal an
   offer. If an offer only appears at checkout, write "shown at checkout, not checked".
3. **Never add offers together** unless the page says they combine. Work out the price after **one**
   instant offer at a time and report the best one.
4. **The saving is what comes off at checkout.** "Up to" amounts, exchange values and cashback paid
   later are not savings on the price; record them without a saving amount.
5. **Never change the account** (addresses, saved cards, settings).

## Step 1: Know the buyer (ask only if it isn't known)
- Which **bank cards** do they have, and are they **credit or debit**? ("HDFC credit", "SBI debit")
- Paying in **full or on EMI**?
- An **old device to exchange**? Which model and condition?
If they don't want to say, show every offer with its conditions and mark none as "you can use this".

## Step 2: Find the offers

### Amazon.in (product page)
- The **Offers** strip under the price: *Bank Offer*, *No Cost EMI*, *Cashback*, *Partner Offers*.
  Open each card to read the full terms (card type, minimum purchase, maximum discount, EMI only or
  not).
- A **coupon** checkbox near the price ("Apply ₹500 coupon"): record it as a coupon with its amount;
  don't tick it.
- **With Exchange** option: record "up to ₹X" with the condition; no saving.
- The deal badge or sale price (Limited time deal, Great Indian Festival): record the type `sale` only
  when the struck-through price is shown on the same page.

### Flipkart (product page)
- **Available offers**: *Bank Offer*, *Special Price*, *Partner Offer*, *EMI*. Open "T&C" for the terms.
- **Buy with Exchange**: record "up to ₹X" with the condition; no saving.
- **SuperCoins** or Flipkart Pay Later offers: record as `other`, no saving unless it's an instant
  discount.

### Brand stores and chains
- Brand stores (Samsung, Apple, OnePlus, Dell, HP, Lenovo…): **student, corporate and trade-in
  offers**, and bundled accessories. Some need verification (student ID); say so in the conditions.
- Croma, Reliance Digital, Vijay Sales: bank offers and exchange as on the marketplaces.
- Local shops: their offers can't be checked online. Say "ask the shop to match the online price and
  offer".

### Sales
Note when a big sale is running or announced (Big Billion Days, Great Indian Festival, Republic Day,
Independence Day, Diwali, Sankranti, Ugadi sales). If one starts within about a week, say "waiting for
the sale may be cheaper" as an option, without promising a price.

## Step 3: Record each offer

| Field | What to write |
| --- | --- |
| `site` | The store, spelled the same as in the price list |
| `type` | `bank`, `emi`, `exchange`, `coupon`, `sale` or `other` |
| `text` | The offer as the store words it, shortened: "₹1,500 instant discount on HDFC credit cards" |
| `saving` | ₹ off at checkout, only for instant `bank`, `coupon` or `sale` offers. Use the amount **this purchase** gets: for "10% up to ₹1,500" on ₹18,999, that's ₹1,500, not ₹1,900 |
| `conditions` | Card type, minimum purchase, EMI-only, valid until, "shown at checkout" |
| `applies_to_buyer` | `true` if it matches the buyer's card and payment; `false` if it clearly doesn't; leave out if unknown |
| `url` | The page the offer is on (often the product page) |

If a store shows **no offers**, that's a result: record an empty list with a note of where you looked.

## Step 4: Report

**Standalone**, in the chat:
- A table per store: offer, saving, conditions, ✓ if the buyer can use it.
- **Best price after one offer**: "₹17,499 on Amazon with ₹1,500 off on HDFC credit cards (minimum
  ₹15,000; not on EMI)".
- Exchange and EMI listed separately, with their conditions, without a saving.
- "Is it a good deal?": compare with the other stores' prices today and say whether a sale is near.
  Don't claim a "lowest ever" price unless a price history you can link shows it.
- Close with: **offers change daily; check the terms on the page before paying.**

**Inside `electronic-shopping`**: write the offers into the pick's `offers` list in `research.json`
(the format is in `../electronic-shopping/assets/research.example.json`). The report builder shows them, works
out the price after the best usable offer, and never adds offers together.
