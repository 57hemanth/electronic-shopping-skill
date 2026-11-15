---
name: shopping-reviews
description: Summarises what buyers and expert reviewers say about a product sold in India: Amazon and Flipkart star ratings with rating counts, expert review verdicts with links, and the recurring praise and complaints in recent buyer reviews. Use for "reviews of this phone/laptop/TV/AC/watch", "is it reliable", "what are the problems with".
license: Not yet chosen by the author.
metadata:
  version: "0.1.0"
---

# Reviews: what do people who own it say?

Specs say what a product should do; reviews say what it does after a month in someone's hand. You walk
out with the store ratings (with how many people rated), one or two expert verdicts with links, and the
handful of things buyers keep praising or complaining about, so the buyer knows the real trade-off
before paying.

The mistakes this prevents:
- **Trusting the star number alone.** 4.6 from 80 ratings means less than 4.2 from 30,000, and stores
  often merge ratings across colours, storage variants or even older models.
- **Missing the problem that shows up later**: heating, a software update that broke something, poor
  after-sales service. These live in recent low-star reviews, not in the average.

## When to use / not
- Use on its own when someone asks about a specific product's reviews or reliability, and inside the
  `electronic-shopping` skill for each shortlisted product.
- Not for judging a seller's or shop's reliability, and not for medical claims a watch's reviews make
  (heart rate, SpO2): say a watch isn't a medical device.

## Hard rules
1. **Only what you read today, with links.** Never invent a rating, a count, a score or a quote.
2. **Paraphrase; don't paste.** Summarise themes in your own words. Quote at most a few words of a
   review, and never more than one quote per source.
3. **Say how strong a pattern is.** "Several recent 1–2 star reviews mention heating while gaming" is
   honest; "the phone overheats" from one review is not.
4. **Read only.** Don't sign in, vote, report or write reviews.

## Step 1: Store ratings
On **Amazon.in** and **Flipkart**, on the exact product page:
- the **star rating** and the **number of ratings** (Amazon: "X global ratings"; Flipkart: "X Ratings
  & Y Reviews");
- **check the rating is for this product**: if the page merges colours, storage variants or an older
  model, say so in the summary;
- the link to the ratings page.

## Step 2: Expert reviews (one or two)
Pick reviewers who actually test the product, recently and for India:
- phones and watches: GSMArena, Gadgets 360, 91mobiles, Smartprix, Beebom, Digit;
- laptops: NotebookCheck, Gadgets 360, Digit;
- TVs: RTINGS (often the global model; check it's the same panel), Gadgets 360, Digit;
- ACs: few expert reviews exist; rely more on buyer reviews and the brand's service reputation.
Record the source, its score if it gives one ("8/10"), a one-line verdict in your words, and the URL.
Skip pages that are only affiliate lists ("10 best phones under 20k") with no testing.

## Step 3: What buyers keep saying
- On each store, **sort reviews by most recent** and read the **critical (1–3 star)** ones first, then
  some 5-star ones. Twenty or so in total is enough to see patterns.
- Look for problems that matter after purchase: heating, battery drain after updates, display or
  speaker faults, missing software updates, **service-centre experience** (repair time, parts),
  installation quality (AC, TV), delivery damage.
- Ignore complaints about the courier, the seller's packing, or a wrong colour delivered, unless many
  reviews mention the same thing.
- Note anything that looks like fake reviews (many short 5-star reviews posted the same week) and say
  so.

Write **2–4 praise points** and **2–4 complaint points**, each a short phrase ("battery lasts a day and a
half", "warms up during long video calls").

## Step 4: Report

**Standalone**, in the chat:
- The store ratings: "★ 4.3 from 12,840 ratings on Amazon · ★ 4.4 from 35,112 on Flipkart".
- Expert verdicts with links.
- "Buyers like" and "Buyers complain about".
- A one-line conclusion: who will be happy with it, and who should look elsewhere.

**Inside `electronic-shopping`**: write it into the pick's `reviews` object in `research.json` (format in
`../electronic-shopping/assets/research.example.json`): `ratings` (site, rating, count, url), `expert` (source,
score, verdict, url), `praise` and `complaints`. Use the complaints to fill the pick's `drawbacks` too.
