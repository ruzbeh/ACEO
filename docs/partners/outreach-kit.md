# Partner outreach kit

**Status: ready to use today. No further code is needed to run the first partners.**

The attribution rail shipped in PR #42 already tracks a partner end to end, verified on production 2026-09-22:

| Hop | How it works | Verified |
|---|---|---|
| Link | `https://www.headshot-generators.com/?partner=<code>` | Sets `hs_partner`, 60 days, first-touch, HttpOnly |
| Job | Cookie is copied to `job.acquisition.partner` at upload | Unit-tested |
| Stripe | Spread as `acquisition_partner` on the session and the payment intent | The sibling `acquisition_*` fields confirmed present on a live session |
| Readout | `/stats` → "Acquisition (30d, real money only)" → **By partner** table | Live, reading real data |

So a partner can be signed up and paid without waiting for the Phase 2a build. The first real partner order will confirm the one hop that cannot be tested without a purchase.

---

## Why not build the partner infrastructure first

The Phase 2a spec calls for a `partners` table, a `/partners` page, a server-applied client discount and a payout report. None of that is needed to learn whether partners will send traffic, and this codebase has a history of shipping infrastructure that then sits idle. The $19/month subscription is fully built, fully live, and has zero subscribers, because nothing ever drove traffic to the offer.

The binding constraint is not software. It is whether a career coach will actually put our link in front of her clients. That is answered by sending ten emails, not by writing a migration.

**Build the infrastructure when at least 3 partners are driving real orders.** Until then the manual version costs nothing: issue a code, read the partner table on `/stats`, pay by PayPal once a month.

---

## Terms to offer

Match the category. HeadshotPro, Aragon and Magic Studio all pay 30%, and HeadshotPro's affiliates generate over 15% of its revenue, so 30% is table stakes rather than generous.

- **30% of what the client actually pays**, first purchase only.
- **60-day first-touch attribution.** This is what the `hs_partner` cookie implements, and it is deliberately longer than the 30-day last-touch window so a client who returns through one of our ads still credits the partner.
- **Paid monthly by PayPal**, 30-day hold, $25 minimum payout.
- **Disclosure required** where the platform requires it, which on LinkedIn means saying it is an affiliate link.
- **No self-referral.** Commission is on new customers, not the partner's own purchase.

At the $29 tier that is $8.70 per sale. Against a Facebook cost per purchase somewhere between $29 and $64, a partner sale is three to seven times cheaper.

---

## Who to approach, in order

Ordered by how cheaply they can be reached, not by audience size.

1. **Reviewers and bloggers already ranking for "AI headshot generator".** They monetise by affiliate link and will add a new one without being persuaded. Aragon's early revenue was more than half from a single affiliate blog.
2. **Career coaches and resume writers.** Their clients are mid-career professionals being told to fix their LinkedIn profile. Category affiliate rates run 10-30%, so 30% is competitive.
3. **Midlife-career creators and "over 50" job-seeker group admins.** Closest match to who actually buys from us.
4. **Real-estate team leads and direct-sales uplines, as individuals.** The median REALTOR is a woman of 57 and 63% of REALTORS are women, which is our winning ad set almost exactly. They are 1099 contractors, so sell to the person, never to the brokerage.

---

## The email

Short, names the specific benefit to their audience, and does not ask for a call.

> Subject: 30% affiliate on AI headshots for your clients
>
> Hi <name>,
>
> I run AI Headshot Studio. People upload a few selfies and get studio-quality headshots back in about two minutes, and they see a free preview of their own face before paying anything.
>
> I thought of you because <specific reason: the LinkedIn-refresh work you do with clients / your review of AI headshot tools / the group you run>. The free preview tends to matter here: your audience can see their own result before they spend, so recommending it costs you no credibility.
>
> The offer is 30% of the first purchase, 60-day cookie, paid monthly. Most orders are $29, so that is $8.70 a sale.
>
> If you want to try it, here is your link: https://www.headshot-generators.com/?partner=<code>
>
> Happy to send a free set so you can judge the quality yourself before recommending it.
>
> <name>

---

## Running it

**Issue a code:** lowercase letters, digits, hyphen or underscore, 40 characters maximum. Anything else is rejected by the rail and the visit falls back to normal attribution. Use something recognisable, like `coachjane` or `careerpivot`.

**Give a free set** to any partner who asks, using the `SELFTEST-*` promotion code at checkout. A partner who has seen the output recommends it far better, and it costs only generation.

**Read results** on `/stats` under "By partner". Only real-money orders count there, since coupon and feedback unlocks are `$0` rows and are excluded.

**Pay** by PayPal monthly, 30 days after the order to clear the refund window.

---

## When to stop or escalate

- **Stop a segment** after 10 non-responses. Move to the next one rather than pushing harder.
- **Build Phase 2a** once 3 or more partners have produced a real order. At that point the manual payout arithmetic is the bottleneck and the table earns its keep.
- **Kill the channel** if 20 approaches across at least two segments produce no partner willing to post. That is a cheaper answer than a migration.

The honest expectation from the strategy review is 0.3 to 1.2 partner-attributed orders a month by day 90, base case. This is a channel that compounds slowly through relationships, not a growth loop.
