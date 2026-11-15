#!/usr/bin/env python3
"""Validate a shopping research file and build the report.

  python3 build_report.py shopping/<folder>/research.json [--png] [--out DIR]

Reads research.json (format: ../assets/research.example.json), refuses it if any price lacks a site,
a number, a URL or a date, or any pick lacks a source, then writes next to it (or into --out):
  report.html   one self-contained page, phone friendly, light and dark, with "Share on WhatsApp"
                and "Copy message" buttons (left out of report.png)
  whatsapp.txt  a short message to paste into WhatsApp
  report.png    with --png, a full-page image made with local Chrome (shares well on WhatsApp)
Exit 0 on success, 1 on invalid research or a missing file.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

CATEGORIES = {"mobile", "laptop", "tv", "ac", "watch"}
DELIVERY = {"yes", "no", "not_checked"}
SERVICE = {"found", "not_found", "not_checked"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OFFER_TYPES = {"bank", "emi", "exchange", "coupon", "sale", "other"}
INSTANT = {"bank", "coupon", "sale"}  # offers that lower what you pay at checkout

LABELS = {
    "en": {
        "title": "Buying advice", "category": {"mobile": "Mobile", "laptop": "Laptop", "tv": "TV", "ac": "AC", "watch": "Watch"},
        "budget": "Budget", "use": "Use", "for": "For", "pincode": "Pincode", "place": "Place", "checked": "Prices checked on",
        "del_to": "to {pin}", "del_other": "not the buyer's pincode",
        "advice": "My advice", "best_price": "Best price", "why": "Why it fits", "drawbacks": "Drawbacks", "specs": "Key specs",
        "prices": "Prices", "site": "Site", "price": "Price", "delivery": "Delivery", "link": "Link", "open": "Open",
        "offers": "Offers", "service": "Service centre", "sources": "Sources", "also": "Also considered",
        "assumed": "Assumptions", "unconfirmed": "Not confirmed", "brand": {"trusted": "Trusted brands", "value": "Value / power brands", "specific": "", "none": "Any brand"},
        "del": {"yes": "✓ Delivers", "no": "✗ No delivery", "not_checked": "Not checked"},
        "svc": {"found": "✓", "not_found": "✗ None nearby", "not_checked": "Not checked"},
        "footer": "Prices change daily. Check the link again before buying. At a local shop, show this online price and ask them to match it.",
        "wa_head": "{cat} advice", "wa_best": "My pick", "wa_tail": "Prices checked on {date}. Check the link again before buying.",
        "on": "", "variant": "Variant",
        "cards": "Cards", "with_offer": "with offer", "you_can_use": "You can use this",
        "offer_type": {"bank": "Bank offer", "emi": "EMI", "exchange": "Exchange", "coupon": "Coupon", "sale": "Sale price", "other": "Offer"},
        "saving": "Saving", "conditions": "Conditions", "no_offers": "No offers found on the sites checked.",
        "offers_note": "Offers aren't added together unless the store says they stack. Exchange value depends on your old device.",
        "reviews": "Ratings and reviews", "ratings": "ratings", "experts": "Expert reviews", "like": "Buyers like", "complain": "Buyers complain about",
        "wa_offer": "Offer", "wa_rating": "ratings",
        "share_wa": "Share on WhatsApp", "copy": "Copy message", "copied": "Copied ✓", "copy_fail": "Select and copy the message below",
    },
}


def inr(n: float | int) -> str:
    """Indian digit grouping: 123456 -> ₹1,23,456."""
    n = int(round(float(n)))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", head)
        s = f"{head},{tail}"
    return ("-" if n < 0 else "") + "₹" + s


def validate(d: dict) -> list[str]:
    errs: list[str] = []
    if "_schema" in d:
        errs.append("remove the _schema field (it marks the example file)")
    req = d.get("request") or {}
    if req.get("category") not in CATEGORIES:
        errs.append(f"request.category must be one of {sorted(CATEGORIES)}")
    if req.get("pincode") not in (None, "") and not re.fullmatch(r"\d{6}", str(req["pincode"])):
        errs.append("request.pincode must be 6 digits, or empty when the buyer didn't give one")
    if not DATE_RE.match(str(d.get("checked_on", ""))):
        errs.append("checked_on must be YYYY-MM-DD")
    if not str(d.get("advice", "")).strip():
        errs.append("advice is empty")
    picks = d.get("picks") or []
    if not 1 <= len(picks) <= 5:
        errs.append("picks must have 1 to 5 entries")
    for i, p in enumerate(picks, 1):
        tag = f"pick {i} ({p.get('name', '?')})"
        for k in ("name", "best_for"):
            if not str(p.get(k, "")).strip():
                errs.append(f"{tag}: {k} is empty")
        for k in ("why", "drawbacks"):
            if not isinstance(p.get(k), list) or not p.get(k):
                errs.append(f"{tag}: {k} must be a non-empty list (every product has a drawback)")
        prices = p.get("prices") or []
        if not prices:
            errs.append(f"{tag}: no prices")
        for j, pr in enumerate(prices, 1):
            ptag = f"{tag} price {j}"
            if not str(pr.get("site", "")).strip():
                errs.append(f"{ptag}: site missing")
            if not isinstance(pr.get("price"), (int, float)) or pr["price"] <= 0:
                errs.append(f"{ptag}: price must be a positive number in rupees")
            if not str(pr.get("url", "")).startswith(("http://", "https://")):
                errs.append(f"{ptag}: url missing (the exact product page)")
            if not DATE_RE.match(str(pr.get("checked_on", ""))):
                errs.append(f"{ptag}: checked_on must be YYYY-MM-DD")
            if pr.get("delivery", "not_checked") not in DELIVERY:
                errs.append(f"{ptag}: delivery must be one of {sorted(DELIVERY)}")
            dp = pr.get("delivery_pincode")
            if dp not in (None, "") and not re.fullmatch(r"\d{6}", str(dp)):
                errs.append(f"{ptag}: delivery_pincode must be the 6-digit pincode the store showed")
            if pr.get("delivery") in ("yes", "no") and not dp and not req.get("pincode"):
                errs.append(f"{ptag}: a delivery result needs delivery_pincode (the pincode the store checked)")
        sites = {str(pr.get("site", "")).strip().lower() for pr in prices}
        for j, o in enumerate(p.get("offers") or [], 1):
            otag = f"{tag} offer {j}"
            if isinstance(o, str):
                continue  # older research files: plain text, shown as is
            if not str(o.get("text", "")).strip():
                errs.append(f"{otag}: text missing (the offer as the store words it)")
            if o.get("type", "other") not in OFFER_TYPES:
                errs.append(f"{otag}: type must be one of {sorted(OFFER_TYPES)}")
            if not str(o.get("site", "")).strip():
                errs.append(f"{otag}: site missing")
            elif o.get("saving") is not None and str(o["site"]).strip().lower() not in sites:
                errs.append(f"{otag}: site {o['site']!r} has no price in this pick, so the saving can't be applied")
            if o.get("saving") is not None and (not isinstance(o["saving"], (int, float)) or o["saving"] <= 0):
                errs.append(f"{otag}: saving must be a positive number in rupees, or left out")
            if o.get("url") and not str(o["url"]).startswith(("http://", "https://")):
                errs.append(f"{otag}: url must start with http")
        rv = p.get("reviews") or {}
        for j, r in enumerate(rv.get("ratings") or [], 1):
            rtag = f"{tag} rating {j}"
            if not str(r.get("site", "")).strip():
                errs.append(f"{rtag}: site missing")
            if not isinstance(r.get("rating"), (int, float)) or not 0 < r["rating"] <= 5:
                errs.append(f"{rtag}: rating must be a number from 0 to 5 as shown on the site")
            if not isinstance(r.get("count"), int) or r["count"] < 0:
                errs.append(f"{rtag}: count must be the number of ratings (a whole number)")
            if not str(r.get("url", "")).startswith(("http://", "https://")):
                errs.append(f"{rtag}: url missing")
        for j, x in enumerate(rv.get("expert") or [], 1):
            xtag = f"{tag} expert review {j}"
            for k in ("source", "verdict"):
                if not str(x.get(k, "")).strip():
                    errs.append(f"{xtag}: {k} missing")
            if not str(x.get("url", "")).startswith(("http://", "https://")):
                errs.append(f"{xtag}: url missing")
        srcs = p.get("sources") or []
        if not srcs or not all(str(s.get("url", "")).startswith(("http://", "https://")) for s in srcs):
            errs.append(f"{tag}: needs at least one source, each with a url")
        svc = p.get("service") or {"status": "not_checked"}
        if svc.get("status", "not_checked") not in SERVICE:
            errs.append(f"{tag}: service.status must be one of {sorted(SERVICE)}")
    return errs


def warnings(d: dict) -> list[str]:
    out = []
    req = d.get("request") or {}
    lo, hi = req.get("budget_min"), req.get("budget_max")
    for p in d.get("picks") or []:
        prices = [x["price"] for x in p.get("prices") or [] if isinstance(x.get("price"), (int, float))]
        if prices and isinstance(hi, (int, float)) and min(prices) > hi:
            out.append(f"{p.get('name')}: best price {inr(min(prices))} is above the budget {inr(hi)}; say so in the advice")
        if prices and isinstance(lo, (int, float)) and max(prices) < lo * 0.7:
            out.append(f"{p.get('name')}: priced well below the budget; check it isn't a different variant")
        if len(p.get("prices") or []) < 2:
            out.append(f"{p.get('name')}: only one site checked (the skill asks for two)")
        if "offers" not in p:
            out.append(f"{p.get('name')}: offers not recorded (use an empty list if none were found)")
        rv = p.get("reviews") or {}
        if not rv.get("ratings"):
            out.append(f"{p.get('name')}: no store ratings recorded")
        if not rv.get("expert"):
            out.append(f"{p.get('name')}: no expert review recorded")
    return out


def e(x: object) -> str:
    return html.escape(str(x), quote=True)


def delivery_note(pr: dict, req: dict, L: dict) -> str:
    """Say which pincode a delivery result is for, and flag it when it isn't the buyer's."""
    if pr.get("delivery", "not_checked") == "not_checked":
        return ""
    dp = pr.get("delivery_pincode") or req.get("pincode") or ""
    if not dp:
        return ""
    other = req.get("pincode") and dp != req.get("pincode")
    text = L["del_to"].format(pin=dp) + (f" · {L['del_other']}" if other else "")
    return f'<br><span style="color:var(--muted);font-size:12px">{e(text)}</span>'


def offers_of(p: dict) -> list[dict]:
    return [{"text": o, "type": "other"} if isinstance(o, str) else o for o in p.get("offers") or []]


def best_offer(p: dict) -> tuple[float, dict, dict] | None:
    """Lowest price after one instant offer (bank, coupon, sale) the buyer isn't known to be unable to use.

    Returns (price after offer, the offer, the price entry it applies to). Offers are never stacked:
    stores word stacking rules differently, so one offer at a time is the honest number.
    """
    by_site = {str(pr["site"]).strip().lower(): pr for pr in p.get("prices") or []}
    found = None
    for o in offers_of(p):
        if o.get("type") not in INSTANT or not o.get("saving") or o.get("applies_to_buyer") is False:
            continue
        pr = by_site.get(str(o.get("site", "")).strip().lower())
        if not pr:
            continue
        after = pr["price"] - o["saving"]
        if after > 0 and (found is None or after < found[0]):
            found = (after, o, pr)
    return found


def count(n: int) -> str:
    """Indian grouping for counts: 123456 -> 1,23,456."""
    return inr(n)[1:]


def stars(r: float) -> str:
    return f"★ {r:.1f}"


def best(p: dict) -> dict:
    return min(p["prices"], key=lambda x: x["price"])


def budget_text(req: dict) -> str:
    lo, hi = req.get("budget_min"), req.get("budget_max")
    if lo and hi:
        return f"{inr(lo)} – {inr(hi)}"
    if hi:
        return f"≤ {inr(hi)}"
    return "—"


CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#16181d;--muted:#5d6470;--line:#e3e4e8;--accent:#2457d6;--accent-soft:#eaf0fd;--good:#1f7a4d;--bad:#b3261e;--warn:#8a5a00}
@media (prefers-color-scheme:dark){:root{--bg:#111317;--card:#1a1d23;--ink:#eceef2;--muted:#a3a9b5;--line:#2c3039;--accent:#7aa2ff;--accent-soft:#1d2740;--good:#5fd39a;--bad:#ff8a80;--warn:#f2c46b}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Noto Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 48px}
header h1{font-size:26px;line-height:1.2;margin:0 0 4px}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 0;padding:0;list-style:none}
.meta li{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:14px;color:var(--muted)}
.meta b{color:var(--ink);font-weight:600}
.advice{margin:20px 0;padding:16px 18px;background:var(--accent-soft);border-left:4px solid var(--accent);border-radius:10px}
.advice h2{margin:0 0 6px;font-size:15px;color:var(--accent);letter-spacing:.02em}
.advice p{margin:0;font-size:17px}
.summary{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:15px}
.summary th,.summary td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.summary th{font-size:13px;color:var(--muted);font-weight:600}
.summary tr:last-child td{border-bottom:0}
.summary .num{white-space:nowrap;font-weight:700}
.pick{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin:18px 0}
.pick-head{display:flex;gap:12px;align-items:flex-start}
.rank{flex:0 0 32px;height:32px;border-radius:50%;background:var(--accent);color:#fff;display:grid;place-items:center;font-weight:700}
.pick h3{margin:0;font-size:19px;line-height:1.3}
.bestfor{margin:2px 0 0;color:var(--muted)}
.price{margin:14px 0 4px;font-size:28px;font-weight:800;letter-spacing:-.01em}
.price small{font-size:14px;font-weight:500;color:var(--muted);margin-left:6px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:4px 20px}
@media (max-width:560px){.cols{grid-template-columns:1fr}}
.pick h4{margin:16px 0 6px;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.pick ul{margin:0;padding-left:20px}
.pick li{margin:2px 0}
.why li::marker{color:var(--good)}.cons li::marker{color:var(--bad)}
.tbl{width:100%;border-collapse:collapse;font-size:14px}
.tbl td,.tbl th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
.tbl th{color:var(--muted);font-weight:600;font-size:12px}
.specs td:first-child{color:var(--muted);width:40%}
a{color:var(--accent)}
.svc-found{color:var(--good)}.svc-not_found{color:var(--bad)}.svc-not_checked,.del-not_checked{color:var(--warn)}
.del-yes{color:var(--good)}.del-no{color:var(--bad)}
.note{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin:18px 0}
.note h2{font-size:15px;margin:0 0 6px}
.note ul{margin:0;padding-left:20px}
.after{margin:0 0 4px;font-size:15px;color:var(--good);font-weight:600}
.after span{color:var(--muted);font-weight:400}
.offer-type{display:inline-block;font-size:12px;font-weight:700;padding:1px 8px;border-radius:999px;background:var(--accent-soft);color:var(--accent);margin-right:6px;white-space:nowrap}
.can-use{display:inline-block;font-size:12px;font-weight:700;color:var(--good);margin-left:6px}
.fine{color:var(--muted);font-size:13px}
.ratings{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 6px}
.chip{border:1px solid var(--line);border-radius:10px;padding:6px 10px;font-size:14px;text-decoration:none;color:var(--ink);background:var(--bg)}
.chip b{color:#b26b00}
.expert{margin:0;padding-left:20px}.expert li{margin:4px 0}
.like li::marker{color:var(--good)}.complain li::marker{color:var(--bad)}
main{padding-bottom:104px}
.share{position:fixed;left:0;right:0;bottom:0;z-index:10;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-top:1px solid var(--line);padding:12px 16px calc(12px + env(safe-area-inset-bottom))}
.share-in{max-width:760px;margin:0 auto;display:flex;gap:10px}
.btn{flex:1;display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:0 16px;border-radius:12px;font:inherit;font-weight:700;font-size:16px;text-decoration:none;cursor:pointer;border:1px solid transparent}
.btn-wa{background:#1a7f4b;color:#fff}.btn-wa:hover{background:#156b3f}
.btn-copy{flex:0 0 auto;background:var(--card);color:var(--ink);border-color:var(--line)}.btn-copy:hover{border-color:var(--muted)}
.btn:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.btn svg{width:20px;height:20px;flex:0 0 auto}
#wa-fallback{display:none;width:100%;margin-top:10px;min-height:140px;font:14px/1.4 ui-monospace,monospace;border:1px solid var(--line);border-radius:8px;padding:8px;background:var(--card);color:var(--ink)}
html.capture .share{display:none}html.capture main{padding-bottom:48px}
footer{margin-top:28px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:14px}
"""


def render_html(d: dict, L: dict) -> str:
    req = d["request"]
    cat = L["category"][req["category"]]
    brand = L["brand"].get(req.get("brand_preference", ""), "") or ", ".join(req.get("brands") or [])
    meta = [(L["budget"], budget_text(req))]
    if req.get("use"):
        meta.append((L["use"], req["use"]))
    if brand:
        meta.append(("Brand", brand))
    if req.get("for_whom"):
        meta.append((L["for"], req["for_whom"]))
    if req.get("pincode") or req.get("place"):
        meta.append((L["pincode"] if req.get("pincode") else L["place"],
                     " · ".join(x for x in (req.get("pincode"), req.get("place")) if x)))
    if req.get("cards"):
        meta.append((L["cards"], ", ".join(req["cards"])))
    meta.append((L["checked"], d["checked_on"]))
    out = [f'<header><h1>{e(cat)} · {e(L["title"])}</h1><ul class="meta">']
    out += [f"<li>{e(k)}: <b>{e(v)}</b></li>" for k, v in meta]
    out.append("</ul></header>")
    out.append(f'<section class="advice"><h2>{e(L["advice"])}</h2><p>{e(d["advice"])}</p></section>')

    out.append(f'<table class="summary"><thead><tr><th>#</th><th>Model</th><th>{e(L["best_price"])}</th></tr></thead><tbody>')
    for i, p in enumerate(d["picks"], 1):
        b = best(p)
        bo = best_offer(p)
        rts = (p.get("reviews") or {}).get("ratings") or []
        top = max(rts, key=lambda r: r["count"]) if rts else None
        rating = f' · <span style="color:#b26b00">{e(stars(top["rating"]))}</span>' if top else ""
        after = (f'<br><span style="font-weight:600;color:var(--good)">{e(inr(bo[0]))} {e(L["with_offer"])}</span>' if bo else "")
        out.append(f'<tr><td>{i}</td><td><b>{e(p["name"])}</b>{rating}<br><span style="color:var(--muted)">{e(p["best_for"])}</span></td>'
                   f'<td class="num">{e(inr(b["price"]))}<br><span style="font-weight:400;color:var(--muted)">{e(b["site"])}</span>{after}</td></tr>')
    out.append("</tbody></table>")

    for i, p in enumerate(d["picks"], 1):
        b = best(p)
        out.append(f'<article class="pick"><div class="pick-head"><div class="rank">{i}</div><div>'
                   f'<h3>{e(p["name"])}</h3><p class="bestfor">{e(p["best_for"])}</p></div></div>')
        out.append(f'<div class="price">{e(inr(b["price"]))}<small>{e(b["site"])} · {e(b["checked_on"])}</small></div>')
        bo = best_offer(p)
        if bo:
            out.append(f'<p class="after">{e(inr(bo[0]))} {e(L["with_offer"])} <span>· {e(bo[1]["text"])} ({e(bo[2]["site"])})</span></p>')
        out.append('<div class="cols"><div>')
        out.append(f'<h4>{e(L["why"])}</h4><ul class="why">' + "".join(f"<li>{e(x)}</li>" for x in p["why"]) + "</ul></div><div>")
        out.append(f'<h4>{e(L["drawbacks"])}</h4><ul class="cons">' + "".join(f"<li>{e(x)}</li>" for x in p["drawbacks"]) + "</ul></div></div>")
        out.append(f'<h4>{e(L["prices"])}</h4><table class="tbl"><thead><tr><th>{e(L["site"])}</th><th>{e(L["price"])}</th>'
                   f'<th>{e(L["delivery"])}</th><th>{e(L["link"])}</th></tr></thead><tbody>')
        for pr in sorted(p["prices"], key=lambda x: x["price"]):
            dv = pr.get("delivery", "not_checked")
            var = f'<br><span style="color:var(--muted)">{e(pr["variant"])}</span>' if pr.get("variant") else ""
            out.append(f'<tr><td>{e(pr["site"])}{var}</td><td><b>{e(inr(pr["price"]))}</b></td>'
                       f'<td class="del-{e(dv)}">{e(L["del"][dv])}{delivery_note(pr, req, L)}</td><td><a href="{e(pr["url"])}" target="_blank" rel="noopener">{e(L["open"])}</a></td></tr>')
        out.append("</tbody></table>")
        if "offers" in p:
            out.append(f'<h4>{e(L["offers"])}</h4>')
            offs = offers_of(p)
            if not offs:
                out.append(f'<p class="fine" style="margin:0">{e(p.get("offers_note") or L["no_offers"])}</p>')
            else:
                rows = []
                for o in sorted(offs, key=lambda o: -(o.get("saving") or 0)):
                    t = o.get("type", "other")
                    use = f'<span class="can-use">✓ {e(L["you_can_use"])}</span>' if o.get("applies_to_buyer") else ""
                    cond = f'<br><span class="fine">{e(o["conditions"])}</span>' if o.get("conditions") else ""
                    link = f' · <a href="{e(o["url"])}" target="_blank" rel="noopener">{e(L["open"])}</a>' if o.get("url") else ""
                    saving = e(inr(o["saving"])) if o.get("saving") else "—"
                    rows.append(f'<tr><td><span class="offer-type">{e(L["offer_type"].get(t, t))}</span>{e(o["text"])}{use}{cond}</td>'
                                f'<td>{e(o.get("site", ""))}{link}</td><td><b>{saving}</b></td></tr>')
                out.append(f'<table class="tbl"><thead><tr><th>{e(L["offers"])}</th><th>{e(L["site"])}</th><th>{e(L["saving"])}</th></tr></thead>'
                           f'<tbody>{"".join(rows)}</tbody></table><p class="fine" style="margin:6px 0 0">{e(L["offers_note"])}</p>')
        rv = p.get("reviews") or {}
        if any(rv.get(k) for k in ("ratings", "expert", "praise", "complaints")):
            out.append(f'<h4>{e(L["reviews"])}</h4>')
            if rv.get("ratings"):
                out.append('<div class="ratings">' + "".join(
                    f'<a class="chip" href="{e(r["url"])}" target="_blank" rel="noopener"><b>{e(stars(r["rating"]))}</b> · '
                    f'{e(count(r["count"]))} {e(L["ratings"])} · {e(r["site"])}</a>'
                    for r in sorted(rv["ratings"], key=lambda r: -r["count"])) + "</div>")
            if rv.get("expert"):
                out.append(f'<p class="fine" style="margin:8px 0 2px">{e(L["experts"])}</p><ul class="expert">' + "".join(
                    f'<li><a href="{e(x["url"])}" target="_blank" rel="noopener">{e(x["source"])}</a>'
                    + (f' · <b>{e(x["score"])}</b>' if x.get("score") else "") + f': {e(x["verdict"])}</li>'
                    for x in rv["expert"]) + "</ul>")
            if rv.get("praise") or rv.get("complaints"):
                out.append('<div class="cols"><div>')
                if rv.get("praise"):
                    out.append(f'<p class="fine" style="margin:8px 0 2px">{e(L["like"])}</p><ul class="like">'
                               + "".join(f"<li>{e(x)}</li>" for x in rv["praise"]) + "</ul>")
                out.append("</div><div>")
                if rv.get("complaints"):
                    out.append(f'<p class="fine" style="margin:8px 0 2px">{e(L["complain"])}</p><ul class="complain">'
                               + "".join(f"<li>{e(x)}</li>" for x in rv["complaints"]) + "</ul>")
                out.append("</div></div>")
        if p.get("key_specs"):
            out.append(f'<h4>{e(L["specs"])}</h4><table class="tbl specs"><tbody>'
                       + "".join(f"<tr><td>{e(k)}</td><td>{e(v)}</td></tr>" for k, v in p["key_specs"].items()) + "</tbody></table>")
        svc = p.get("service") or {"status": "not_checked"}
        st = svc.get("status", "not_checked")
        detail = e(svc.get("detail", ""))
        if svc.get("url"):
            detail += f' · <a href="{e(svc["url"])}" target="_blank" rel="noopener">{e(L["open"])}</a>'
        out.append(f'<h4>{e(L["service"])}</h4><p class="svc-{e(st)}" style="margin:0">{e(L["svc"][st])} {detail}</p>')
        out.append(f'<h4>{e(L["sources"])}</h4><ul>' + "".join(
            f'<li><a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s.get("title") or s["url"])}</a></li>' for s in p["sources"]) + "</ul>")
        out.append("</article>")

    if d.get("also_considered"):
        out.append(f'<section class="note"><h2>{e(L["also"])}</h2><ul>' + "".join(
            f'<li><b>{e(a.get("name", ""))}</b>: {e(a.get("why_not", ""))}</li>' for a in d["also_considered"]) + "</ul></section>")
    for key, label in (("assumptions", L["assumed"]), ("not_confirmed", L["unconfirmed"])):
        if d.get(key):
            out.append(f'<section class="note"><h2>{e(label)}</h2><ul>' + "".join(f"<li>{e(x)}</li>" for x in d[key]) + "</ul></section>")
    out.append(f'<footer>{e(L["footer"])}</footer>')

    msg = render_whatsapp(d, L)
    wa_url = "https://wa.me/?text=" + urllib.parse.quote(msg, safe="")
    bubble = ('<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.4 8.4 0 0 1-12.4 7.4L3 20.5l1.6-5.4'
              'A8.4 8.4 0 1 1 21 11.5z"/></svg>')
    copy_icon = ('<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" '
                 'stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/>'
                 '<path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>')
    share = (f'<div class="share" role="region" aria-label="Share"><div class="share-in">'
             f'<a class="btn btn-wa" href="{e(wa_url)}" target="_blank" rel="noopener">{bubble}{e(L["share_wa"])}</a>'
             f'<button type="button" class="btn btn-copy" id="copy-btn" data-label="{e(L["copy"])}" '
             f'data-done="{e(L["copied"])}" data-fail="{e(L["copy_fail"])}">{copy_icon}<span>{e(L["copy"])}</span></button>'
             f'</div><div class="share-in"><textarea id="wa-fallback" readonly aria-label="WhatsApp message">{e(msg)}</textarea></div></div>')
    msg_json = json.dumps(msg, ensure_ascii=False).replace("</", "<\\/")

    title = f"{cat} · {L['title']}" + (f" · {req['pincode']}" if req.get("pincode") else "")
    return ("<!doctype html>\n"
            f'<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{e(title)}</title>"
            "<script>if(/[?&]capture=1/.test(location.search))document.documentElement.className+=' capture'</script>"
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
            f"<style>{CSS}</style></head><body><main>" + "\n".join(out) + "</main>" + share +
            f'<script type="application/json" id="wa-msg">{msg_json}</script>'
            + COPY_JS +
            "<script>addEventListener('load',function(){(document.fonts?document.fonts.ready:Promise.resolve()).then(function(){"
            "document.documentElement.setAttribute('data-h',document.documentElement.scrollHeight)})})</script>"
            "</body></html>\n")


COPY_JS = """<script>(function(){var b=document.getElementById('copy-btn');if(!b)return;
var t=JSON.parse(document.getElementById('wa-msg').textContent),s=b.querySelector('span');
function done(ok){if(ok){s.textContent=b.dataset.done;setTimeout(function(){s.textContent=b.dataset.label},2000)}
else{var f=document.getElementById('wa-fallback');f.style.display='block';f.focus();f.select();s.textContent=b.dataset.fail}}
function legacy(){var a=document.createElement('textarea');a.value=t;a.setAttribute('readonly','');a.style.position='fixed';a.style.opacity='0';
document.body.appendChild(a);a.select();var ok=false;try{ok=document.execCommand('copy')}catch(e){}document.body.removeChild(a);return ok}
b.addEventListener('click',function(){if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t).then(function(){done(true)},function(){done(legacy())})}else{done(legacy())}})})()</script>"""


def render_whatsapp(d: dict, L: dict) -> str:
    req = d["request"]
    cat = L["category"][req["category"]]
    head = L["wa_head"].format(cat=cat)
    where = f", {L['pincode']} {req['pincode']}" if req.get("pincode") else ""
    lines = [f"*{head}* ({budget_text(req)}{where})", ""]
    for i, p in enumerate(d["picks"], 1):
        b = best(p)
        lines.append(f"*{i}. {p['name']}*: {inr(b['price'])} ({b['site']})")
        lines.append(f"   {p['best_for']}")
        bo = best_offer(p)
        if bo:
            lines.append(f"   💳 {inr(bo[0])} with {bo[1]['text']} ({bo[2]['site']})")
        rts = (p.get("reviews") or {}).get("ratings") or []
        if rts:
            top = max(rts, key=lambda r: r["count"])
            lines.append(f"   ⭐ {top['rating']:.1f} ({count(top['count'])} {L['wa_rating']}, {top['site']})")
        lines.append(f"   {b['url']}")
    lines += ["", f"*{L['wa_best']}:* {d['advice']}", "", L["wa_tail"].format(date=d["checked_on"])]
    return "\n".join(lines) + "\n"


def find_chrome() -> str | None:
    for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "google-chrome-stable",
              "chromium", "chromium-browser", "chrome"):
        if Path(c).exists() or shutil.which(c):
            return shutil.which(c) or c
    return None


def make_png(html_path: Path, png_path: Path, width: int = 540) -> bool:
    """Full-page phone-width image in light mode, using local Chrome only (no extra packages).

    Pass 1 loads the page and dumps the DOM after fonts load; the page records its own height in
    <html data-h>. Pass 2 screenshots at exactly that height. Chrome's headless window can't be
    narrower than about 500 px, so the width stays at 540.
    """
    chrome = find_chrome()
    if not chrome:
        print("  --png: Chrome not found; skipped report.png", file=sys.stderr)
        return False
    url = html_path.resolve().as_uri() + "?capture=1"  # hides the share bar in the image
    base = [chrome, "--headless=new", "--hide-scrollbars", "--blink-settings=preferredColorScheme=1",
            "--virtual-time-budget=4000"]
    height = 2400
    r = subprocess.run(base + [f"--window-size={width},800", "--dump-dom", url], capture_output=True, text=True, timeout=60)
    m = re.search(r'data-h="(\d+)"', r.stdout or "")
    if m:
        height = min(20000, int(m.group(1)) + 8)
    r = subprocess.run(base + ["--force-device-scale-factor=2", f"--window-size={width},{height}",
                               f"--screenshot={png_path}", url], capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or not png_path.exists():
        print(f"  --png: Chrome failed: {r.stderr.strip()[:300]}", file=sys.stderr)
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("research", help="path to research.json")
    ap.add_argument("--png", action="store_true", help="also save report.png using local Chrome")
    ap.add_argument("--out", help="output folder (default: next to research.json)")
    a = ap.parse_args()

    src = Path(a.research)
    if not src.is_file():
        print(f"error: {src} not found", file=sys.stderr)
        return 1
    try:
        d = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        print(f"error: {src} is not valid JSON: {ex}", file=sys.stderr)
        return 1
    errs = validate(d)
    if errs:
        print(f"Research is incomplete ({len(errs)} problem{'s' if len(errs) != 1 else ''}). Fix the research; never fill in a value to pass:", file=sys.stderr)
        for x in errs:
            print(f"  - {x}", file=sys.stderr)
        return 1
    L = LABELS["en"]
    out = Path(a.out) if a.out else src.parent
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.html").write_text(render_html(d, L), encoding="utf-8")
    (out / "whatsapp.txt").write_text(render_whatsapp(d, L), encoding="utf-8")
    print(f"wrote {out / 'report.html'}")
    print(f"wrote {out / 'whatsapp.txt'}")
    if a.png and make_png(out / "report.html", out / "report.png"):
        print(f"wrote {out / 'report.png'}")
    for w in warnings(d):
        print(f"  warning: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
