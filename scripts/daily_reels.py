"""Daily batch: render N science reels and upload them to YouTube (The Science Drop).

Pulls from a curated, sourced topic pool (deliberately NOT auto-LLM-generated —
fabricated medical citations are a misinformation/strike risk). Each run picks
the N least-recently-used unseen topics, renders a ScienceNewsReel, and uploads
it unlisted (staged for review → you bulk-publish what you like).

Run (needs Node 18+ on PATH for Remotion):
    PATH="$HOME/.nvm/versions/node/v22.22.1/bin:$PATH" \
      .venv/bin/python scripts/daily_reels.py --count 6

Flags:
    --count N        how many reels this run (default 6 — YouTube free quota ceiling)
    --voice NAME     ElevenLabs preset (default male_deep)
    --privacy P      private|unlisted|public (default unlisted)
    --no-upload      render only (skip YouTube)
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from aeco.tools.video.composer import render_reel  # noqa: E402
from aeco.tools.content.smm_team import hero_director, review_and_optimize  # noqa: E402
from aeco.tools.content.image_gen import generate_image  # noqa: E402
from scripts.make_content_reel import build_segments  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("daily_reels")

OUTPUT_DIR = REPO_ROOT / "workspace" / "content" / "output"
STATE_DIR = REPO_ROOT / "workspace" / "content" / "state"
SEEN_FILE = STATE_DIR / "seen_topics.json"
BRAND = "sciencedropdaily"
HEADER = "SCIENCE DROP"
DISCLAIMER = "Educational — not medical advice"

# A fitting emoji per topic — floats faintly behind the captions for visual interest.
ICONS = {
    "creatine-brain": "🧠", "urolithin-a": "🔋", "omega3-brain": "🐟",
    "vitamin-d-immune": "☀️", "magnesium-sleep": "😴", "spermidine-autophagy": "♻️",
    "berberine-glucose": "🩸", "glynac-aging": "⏳", "fisetin-senolytic": "🧫",
    "trf-metabolic": "⏰", "l-theanine-focus": "🍵", "taurine-aging": "⏳",
    "ashwagandha-stress": "🌿", "nmn-nad": "🔋", "collagen-skin": "✨",
    "sauna-heart": "🔥", "zinc-cold": "🤧", "fiber-longevity": "🌾", "exercise-bdnf": "🏃",
    "lions-mane-nerve": "🍄", "saffron-mood": "🌷", "beetroot-bp": "🫀", "cocoa-flavanols": "🍫",
    "vitamin-k2-arteries": "🦴", "coq10-heart": "❤️", "melatonin-jetlag": "✈️",
    "curcumin-inflammation": "🟡", "green-tea-egcg": "🍵", "rhodiola-fatigue": "🏔️",
    "fish-oil-heart": "🐟", "iron-fatigue": "🔩", "b12-energy": "⚡", "sleep-glymphatic": "🛏️",
    "cold-plunge-dopamine": "🧊", "fasting-autophagy": "🍽️", "mediterranean-diet": "🫒",
    "evoo-polyphenols": "🟢", "protein-aging-muscle": "💪", "caffeine-endurance": "☕",
}

# Which body region the luminous wireframe figure flares as the "superhuman
# upgrade" hero, per topic. head=brain/sleep/mood/focus, heart=cardio/bp/arteries,
# core=gut/metabolism/glucose, muscle=strength/endurance/energy, whole=immune/aging/skin.
BODY_FOCUS: dict[str, str] = {
    "magnesium-sleep": "head", "sleep-glymphatic": "head", "ashwagandha-stress": "head",
    "l-theanine-focus": "head", "creatine-brain": "head", "saffron-mood": "head",
    "melatonin-jetlag": "head", "omega3-brain": "head", "lions-mane-nerve": "head",
    "exercise-bdnf": "head", "cold-plunge-dopamine": "head",
    "sauna-heart": "heart", "fish-oil-heart": "heart", "beetroot-bp": "heart",
    "cocoa-flavanols": "heart", "coq10-heart": "heart", "vitamin-k2-arteries": "heart",
    "green-tea-egcg": "core", "fiber-longevity": "core", "mediterranean-diet": "core",
    "berberine-glucose": "core", "curcumin-inflammation": "core", "fasting-autophagy": "core",
    "trf-metabolic": "core", "evoo-polyphenols": "core",
    "iron-fatigue": "muscle", "b12-energy": "muscle", "rhodiola-fatigue": "muscle",
    "caffeine-endurance": "muscle", "protein-aging-muscle": "muscle",
    "vitamin-d-immune": "whole", "zinc-cold": "whole", "collagen-skin": "whole",
    # demoted topics (out of rotation, mapped for restore-readiness)
    "urolithin-a": "muscle", "spermidine-autophagy": "core", "glynac-aging": "whole",
    "fisetin-senolytic": "whole", "taurine-aging": "whole", "nmn-nad": "whole",
}

# Curated, sourced topics on a 5-beat HOOK formula (retuned 2026-05-30):
#   HOOK (pattern interrupt / stake — never a soft "Can/Could…?") →
#   TURN (the surprising mechanism) → EVIDENCE (cited) →
#   honest caveat folded MID-script → PAYOFF (a concrete, memorable closer —
#   never end on "the catch", it reads as "never mind").
# Claims modest/hedged; no dosage or cure language. **bold** = accent word.
# NOTE: the first line doubles as the video title, so make beat 1 carry.
TOPIC_POOL: list[dict] = [
    {"id": "magnesium-sleep", "segments": [
        {"text": "Your racing brain at 2am isn't **random**."},
        {"text": "It's often low on **magnesium** — the mineral behind your calm switch."},
        {"text": "It feeds GABA, the brain's brake; trials tie it to **deeper sleep**.", "source": "early trials"},
        {"text": "Food first: **pumpkin seeds, spinach, dark chocolate**."},
        {"text": "Tired and wired? Start **there**."}]},
    {"id": "sleep-glymphatic", "segments": [
        {"text": "Your brain takes out the **trash** — but only at night."},
        {"text": "In deep sleep, fluid flushes waste from between your **neurons**."},
        {"text": "Scientists filmed this **glymphatic** system in action.", "source": "Science, 2013"},
        {"text": "Skip deep sleep and the **garbage** stays."},
        {"text": "Sleep isn't lazy. It's **maintenance**."}]},
    {"id": "ashwagandha-stress", "segments": [
        {"text": "One herb keeps beating **stress** in the lab."},
        {"text": "**Ashwagandha** — used in India for thousands of years."},
        {"text": "In trials, it measurably **lowered cortisol**.", "source": "RCTs, 2019"},
        {"text": "People slept better and felt **calmer**."},
        {"text": "Ancient remedy, modern data finally **catching up**."}]},
    {"id": "iron-fatigue", "segments": [
        {"text": "You're not lazy. You might be running on **empty**."},
        {"text": "Your blood test says iron is \"normal\" — but your tank can be near-empty and still **pass**."},
        {"text": "It's called low **ferritin** — and it drains energy for years before anemia ever shows.", "source": "clinical reviews"},
        {"text": "Correct it and the fog often **lifts**; fatigue dropped fast in trials.", "source": "RCTs"},
        {"text": "One number most checkups skip. Ask for **ferritin**."}]},
    {"id": "b12-energy", "segments": [
        {"text": "Bone-tired with **tingling** hands? Don't brush it off."},
        {"text": "Your nerves run on **B12** — and it quietly runs low."},
        {"text": "Vegans and over-50s are most at risk of **deficiency**.", "source": "clinical reviews"},
        {"text": "Left too long, the nerve damage can be **permanent**."},
        {"text": "A cheap blood test settles it. Get **B12** checked."}]},
    {"id": "l-theanine-focus", "segments": [
        {"text": "Love coffee, hate the **jitters**? There's a pairing for that."},
        {"text": "**L-theanine** — the calm amino acid in green tea."},
        {"text": "With caffeine, it gives focus **without** the edge.", "source": "Nutritional Neuroscience"},
        {"text": "Same energy, none of the **shakes**."},
        {"text": "Coffee plus L-theanine. Try it **once**."}]},
    {"id": "creatine-brain", "segments": [
        {"text": "Creatine isn't just for the **gym**."},
        {"text": "Your brain burns the **same fuel** as your muscles — sleep loss drains it."},
        {"text": "In 2024, one big dose snapped tired minds back to **sharp**.", "source": "Scientific Reports, 2024"},
        {"text": "It took a **huge** dose — everyday amounts may do less."},
        {"text": "The most studied supplement on Earth, hiding in **plain sight**."}]},
    {"id": "rhodiola-fatigue", "segments": [
        {"text": "Burned out by **3pm**? An arctic herb has a track record."},
        {"text": "**Rhodiola** grows on freezing cliffs — and handles stress for a living."},
        {"text": "Trials link it to **less fatigue** under pressure.", "source": "RCTs"},
        {"text": "Early research, but the **pattern** keeps showing up."},
        {"text": "When stress drains you, it's worth a **look**."}]},
    {"id": "caffeine-endurance", "segments": [
        {"text": "The world's best **legal** performance drug is in your kitchen."},
        {"text": "Plain **caffeine** — and the science is overwhelming."},
        {"text": "It reliably boosts **endurance** across sports.", "source": "meta-analyses"},
        {"text": "Skip it for a week and it hits **harder** again."},
        {"text": "Your pre-workout's real secret? Just **coffee**."}]},
    {"id": "green-tea-egcg", "segments": [
        {"text": "Green tea's quiet power has a **name**."},
        {"text": "**EGCG** — a compound your morning cup is full of."},
        {"text": "It's tied to a small but real **metabolism** bump.", "source": "meta-analyses"},
        {"text": "No fat-burner — but a free, easy **upgrade**."},
        {"text": "Swap one coffee for **green tea** and see."}]},
    {"id": "saffron-mood", "segments": [
        {"text": "The world's priciest spice may also lift your **mood**."},
        {"text": "**Saffron** has gone head-to-head with antidepressants in trials."},
        {"text": "Several found it **surprisingly** close on mild cases.", "source": "meta-analyses"},
        {"text": "Small studies — not a treatment, but a real **signal**."},
        {"text": "Sometimes the kitchen surprises the **lab**."}]},
    {"id": "melatonin-jetlag", "segments": [
        {"text": "The real fix for **jet lag** isn't more coffee."},
        {"text": "**Melatonin** is your body's clock-setting signal."},
        {"text": "Reviews show it genuinely **eases** jet lag.", "source": "Cochrane review"},
        {"text": "But timing beats dose — take it at the **right** hour."},
        {"text": "Tiny dose, correct timing. That's the **trick**."}]},
    {"id": "sauna-heart", "segments": [
        {"text": "Finland may have a **heart-health** secret hiding in plain sight."},
        {"text": "Scientists tracked **2,000 men** for decades."},
        {"text": "Frequent **sauna** users had far fewer heart deaths.", "source": "JAMA Intern. Med., 2015"},
        {"text": "Heat may train your vessels like **light exercise**."},
        {"text": "A link, not proof — but a **striking** one."}]},
    {"id": "fish-oil-heart", "segments": [
        {"text": "Most fish oil does **nothing** for your heart."},
        {"text": "The difference comes down to **dose**."},
        {"text": "High-dose **EPA** cut cardiac events in a major trial.", "source": "REDUCE-IT, 2019"},
        {"text": "Drugstore softgels? Often **too little** to matter."},
        {"text": "If you take it, the **dose** is the whole game."}]},
    {"id": "beetroot-bp", "segments": [
        {"text": "Athletes drink **beet juice** for a reason."},
        {"text": "Beets are loaded with natural **nitrates**."},
        {"text": "Your body turns them into **nitric oxide**, widening vessels.", "source": "meta-analyses"},
        {"text": "The blood-pressure dip is real but **short-lived**."},
        {"text": "A pre-workout shot of **beets** — backed by data."}]},
    {"id": "cocoa-flavanols", "segments": [
        {"text": "Good news for **chocolate** lovers — with a catch."},
        {"text": "Cocoa's heart perk comes from compounds called **flavanols**."},
        {"text": "A huge trial tied them to a **healthier heart**.", "source": "COSMOS, 2022"},
        {"text": "But the **sugary bar** isn't the source — dark and pure is."},
        {"text": "Real cocoa, not candy. That's the **difference**."}]},
    {"id": "coq10-heart", "segments": [
        {"text": "Your heart never rests — and it runs on **one** molecule."},
        {"text": "It's **CoQ10**, and your levels fall with age."},
        {"text": "In heart-failure patients, it **improved outcomes**.", "source": "Q-SYMBIO trial"},
        {"text": "Healthy hearts may notice **little** — context matters."},
        {"text": "An energy spark plug worth **knowing** about."}]},
    {"id": "fiber-longevity", "segments": [
        {"text": "The most **underrated** longevity nutrient is dirt cheap."},
        {"text": "It's **fiber** — fuel for the good bacteria in your gut."},
        {"text": "Big studies tie more fiber to **lower mortality**.", "source": "The Lancet, 2019"},
        {"text": "Most people get barely **half** the target."},
        {"text": "Ramp up slowly — then let your **gut** thank you."}]},
    {"id": "exercise-bdnf", "segments": [
        {"text": "There's a drug that **grows** your brain — and it's free."},
        {"text": "It's **exercise**."},
        {"text": "Movement floods the brain with **BDNF** — fertilizer for neurons.", "source": "neuroscience research"},
        {"text": "No pill has **matched** it yet."},
        {"text": "Your best nootropic is a **walk**."}]},
    {"id": "mediterranean-diet", "segments": [
        {"text": "The most studied diet on Earth isn't really a **diet**."},
        {"text": "The **Mediterranean** pattern — olive oil, fish, plants, real food."},
        {"text": "A landmark trial cut **heart events**.", "source": "PREDIMED, 2018"},
        {"text": "No single magic food — it's the whole **pattern**."},
        {"text": "Eat like the **coast**. The data agrees."}]},
    {"id": "protein-aging-muscle", "segments": [
        {"text": "After 50, your muscle **quietly** walks out the door."},
        {"text": "Doctors call the slow loss **sarcopenia**."},
        {"text": "More **protein** plus lifting fights back.", "source": "clinical reviews"},
        {"text": "Older bodies need **more** protein, not less — most get less."},
        {"text": "Lift something. Eat the **protein**. Keep the muscle."}]},
    {"id": "vitamin-d-immune", "segments": [
        {"text": "**Vitamin D** and colds — the truth is in the details."},
        {"text": "Scientists pooled **25 trials** to settle it."},
        {"text": "It modestly cut **respiratory infections**.", "source": "BMJ, 2017"},
        {"text": "The win was biggest in people already **deficient**."},
        {"text": "More isn't better. Get **tested**, then top up."}]},
    {"id": "zinc-cold", "segments": [
        {"text": "Caught a cold? The **first 24 hours** decide a lot."},
        {"text": "**Zinc** can block the virus from copying itself."},
        {"text": "Taken early, lozenges **shortened** colds in reviews.", "source": "meta-analyses"},
        {"text": "Wait too long and it barely **works**."},
        {"text": "Keep zinc lozenges ready for **day one**."}]},
    {"id": "collagen-skin", "segments": [
        {"text": "Collagen drinks sound like **hype** — until you read the trials."},
        {"text": "**Collagen** is the scaffolding your skin is built on."},
        {"text": "Reviews saw **firmer, more elastic** skin.", "source": "Int. J. Dermatology, 2021"},
        {"text": "Many studies were **industry-funded** — eyes open."},
        {"text": "Promising, not proven — but the **signal** is there."}]},
    {"id": "omega3-brain", "segments": [
        {"text": "Your brain is **60% fat** — and picky about which kind."},
        {"text": "A fish-oil fat called **omega-3** may slow how it ages."},
        {"text": "Scans of thousands of brains: more omega-3, **healthier** brains.", "source": "Neurology, 2022"},
        {"text": "A link, not proof — but a **consistent** one."},
        {"text": "The fats that matter most: **DHA and EPA**."}]},
    {"id": "berberine-glucose", "segments": [
        {"text": "There's a plant compound people call **nature's metformin**."},
        {"text": "It's **berberine**, from barberry and goldenseal."},
        {"text": "Reviews show it can **lower blood sugar**.", "source": "meta-analyses"},
        {"text": "It is **not** a swap for real medicine — talk to a doctor."},
        {"text": "Powerful enough to **respect**, not self-prescribe."}]},
    {"id": "curcumin-inflammation", "segments": [
        {"text": "Turmeric's golden compound has a **problem**."},
        {"text": "**Curcumin** calms inflammation in study after study."},
        {"text": "But on its own, it's **barely absorbed**.", "source": "reviews"},
        {"text": "**Black pepper** boosts uptake many times over."},
        {"text": "Turmeric without pepper? Mostly **wasted**."}]},
    {"id": "lions-mane-nerve", "segments": [
        {"text": "A shaggy mushroom might **feed** your brain."},
        {"text": "**Lion's mane** triggers nerve growth factor in the lab."},
        {"text": "A small trial hinted at **sharper** thinking in older adults.", "source": "Mori, 2009"},
        {"text": "Human evidence is still **thin** — early days."},
        {"text": "Strange-looking, but worth **watching**."}]},
    {"id": "cold-plunge-dopamine", "segments": [
        {"text": "Ice baths aren't just for **influencers**."},
        {"text": "Cold shock triggers a long, slow **dopamine** surge."},
        {"text": "One study saw dopamine stay up **for hours**.", "source": "2000 study"},
        {"text": "Start slow — cold is a **stressor**, respect it."},
        {"text": "A natural high you can **train** for."}]},
    {"id": "fasting-autophagy", "segments": [
        {"text": "Your cells can eat their own **garbage**."},
        {"text": "The process is **autophagy** — and fasting may switch it on."},
        {"text": "Discovering how it works won a **Nobel Prize**.", "source": "Ohsumi, 2016"},
        {"text": "Most human proof is still **early**."},
        {"text": "Skipping a meal might be quiet **spring cleaning**."}]},
    {"id": "trf-metabolic", "segments": [
        {"text": "**When** you eat may matter as much as what."},
        {"text": "Researchers squeezed eating into a **10-hour** window."},
        {"text": "Metabolic health **improved**.", "source": "Cell Metabolism, 2020"},
        {"text": "An **earlier** window worked best — not for everyone, though."},
        {"text": "Same food, tighter window. Worth a **test**."}]},
    {"id": "evoo-polyphenols", "segments": [
        {"text": "Not all **olive oil** is doing you any favors."},
        {"text": "**Extra-virgin** is packed with protective polyphenols."},
        {"text": "Those are the part linked to a **healthier heart**.", "source": "PREDIMED"},
        {"text": "**Refined** oils lose most of them."},
        {"text": "Buy extra-virgin. The rest is mostly **fat**."}]},
    {"id": "vitamin-k2-arteries", "segments": [
        {"text": "Calcium in your bones is good. In your **arteries**? Not so much."},
        {"text": "**Vitamin K2** helps steer calcium to the **right** place."},
        {"text": "More of it tracks with **less** arterial calcium.", "source": "Rotterdam Study"},
        {"text": "Mostly observational so far — but **intriguing**."},
        {"text": "The traffic cop your calcium **needs**."}]},
    # Added 2026-05-31: demand-driven everyday topics mined from YouTube's Research
    # tab ("benefits of" search demand). Each backed by a real citation; chosen for
    # broad search appeal over niche novelty.
    {"id": "walking-glucose", "segments": [
        {"text": "A 2-minute walk after dinner beats a **workout** for one thing."},
        {"text": "It flattens the **blood-sugar spike** that follows every meal."},
        {"text": "Even 2–5 minutes of strolling after eating **lowered glucose**.", "source": "Sports Medicine, 2022"},
        {"text": "It won't replace exercise — but the **timing** is the trick."},
        {"text": "Don't sit after meals. **Walk** them off."}]},
    {"id": "hydration-brain", "segments": [
        {"text": "Foggy and tired by noon? You might just be **dehydrated**."},
        {"text": "Losing barely **1–2%** of your water hits the brain first."},
        {"text": "Mild dehydration measurably **worsened focus and mood**.", "source": "J. Nutrition, 2012"},
        {"text": "More isn't better — you only need to cover the **deficit**."},
        {"text": "Before the next coffee, try a glass of **water**."}]},
    {"id": "coffee-longevity", "segments": [
        {"text": "The habit you feel guilty about may help you **live longer**."},
        {"text": "**Coffee** — and the data is bigger than you'd think."},
        {"text": "In huge studies, 2–3 cups a day tracked with **lower mortality**.", "source": "Annals of Internal Medicine, 2022"},
        {"text": "It's a link, not proof — and **sugar** undoes the upside."},
        {"text": "Black coffee, in reason — the science is **on your side**."}]},
    {"id": "morning-light-sleep", "segments": [
        {"text": "The best **sleep** trick happens the moment you wake up."},
        {"text": "**Morning sunlight** sets the clock that runs your whole day."},
        {"text": "Early outdoor light **anchored circadian rhythm** and sleep.", "source": "Current Biology, 2013"},
        {"text": "Through a window is weaker — **outdoors** beats glass."},
        {"text": "Ten minutes of morning light. **Free**, and it works."}]},
    {"id": "strength-longevity", "segments": [
        {"text": "Lifting weights isn't about looking good — it's about **living longer**."},
        {"text": "Muscle is an organ that **defends** your whole body."},
        {"text": "Regular strength training tracked with **lower death rates**.", "source": "Br. J. Sports Medicine, 2022"},
        {"text": "You don't need a gym — **bodyweight** counts too."},
        {"text": "Two short sessions a week. Your future self **wins**."}]},
    {"id": "garlic-bp", "segments": [
        {"text": "One kitchen staple nudges **blood pressure** down."},
        {"text": "**Garlic** — and the effect isn't just folklore."},
        {"text": "Concentrated garlic modestly **lowered blood pressure** in trials.", "source": "meta-analyses"},
        {"text": "It's a small dip — not a replacement for **medication**."},
        {"text": "A real, food-first **edge** for your heart."}]},
    {"id": "ginger-nausea", "segments": [
        {"text": "Before you reach for a pill, the **spice rack** has an answer."},
        {"text": "**Ginger** has calmed queasy stomachs for centuries."},
        {"text": "Reviews found it genuinely **eased nausea** — even in pregnancy.", "source": "Cochrane reviews"},
        {"text": "Great for mild queasiness — not for **serious** illness."},
        {"text": "Fresh ginger or tea. A remedy that actually **holds up**."}]},
    {"id": "breathing-stress", "segments": [
        {"text": "You can flip your body out of **stress** in 90 seconds."},
        {"text": "The tool is your **breath** — slow it, and the alarm quiets."},
        {"text": "Five minutes of slow breathing **cut stress and anxiety**.", "source": "Cell Reports Medicine, 2023"},
        {"text": "One catch: the **long exhale** is what does the work."},
        {"text": "Inhale, then exhale **longer**. That's the whole hack."}]},
]


# Demoted 2026-05-30: niche "longevity-molecule" topics that drew ~0 views at
# day-1 (spermidine, GlyNAC, fisetin, taurine, NMN, urolithin-A). Broad
# problem-driven topics (sleep, energy, focus, stress, heart) dominate at this
# scale. Kept here — out of rotation but preserved — so they're easy to restore.
DEMOTED_TOPICS: list[dict] = [
    {"id": "urolithin-a", "segments": [
        {"text": "Inside every cell are tiny **power plants**."},
        {"text": "With age, the **broken ones** pile up."},
        {"text": "A molecule from **pomegranates** tells your body to recycle them.", "source": "Cell Reports Medicine, 2022"},
        {"text": "In older adults, it **boosted muscle endurance**."},
        {"text": "The catch: your gut may **not** make enough alone."},
        {"text": "Follow @sciencedropdaily."}]},
    {"id": "spermidine-autophagy", "segments": [
        {"text": "Your cells have a **self-cleaning** mode."},
        {"text": "It's called **autophagy** — and it slows with age."},
        {"text": "**Spermidine**, in wheat germ and aged cheese, may switch it on.", "source": "Nature Medicine, 2016"},
        {"text": "In animals, it **extended lifespan**."},
        {"text": "The catch: human data is still **observational**."},
        {"text": "Follow @sciencedropdaily."}]},
    {"id": "glynac-aging", "segments": [
        {"text": "Two **cheap** amino acids, one bold claim."},
        {"text": "Together they're called **GlyNAC**."},
        {"text": "They may restore a key antioxidant, **glutathione**."},
        {"text": "Small trials saw **better aging markers**.", "source": "Baylor, 2022"},
        {"text": "The catch: the trials are **tiny** — early days."},
        {"text": "Follow @sciencedropdaily."}]},
    {"id": "fisetin-senolytic", "segments": [
        {"text": "Some old cells **refuse to die**."},
        {"text": "They're called **zombie cells** — and they age you."},
        {"text": "**Fisetin**, found in strawberries, may help clear them.", "source": "EBioMedicine, 2018"},
        {"text": "It worked in **mice**; humans are being tested now."},
        {"text": "The catch: no proven anti-aging pill exists **yet**."},
        {"text": "Follow for tomorrow's drop."}]},
    {"id": "taurine-aging", "segments": [
        {"text": "Could **one amino acid** slow aging?"},
        {"text": "Scientists noticed taurine **drops** as we age.", "source": "Science, 2023"},
        {"text": "So they topped it back up in **mice and monkeys**."},
        {"text": "Their **healthspan improved**."},
        {"text": "The catch: whether it helps **humans** is unproven."},
        {"text": "Follow @sciencedropdaily."}]},
    {"id": "nmn-nad", "segments": [
        {"text": "There's a molecule that **fades** as you age."},
        {"text": "It's **NAD+**, the fuel cells use to repair themselves."},
        {"text": "A precursor called **NMN** can raise it back up.", "source": "human pilot trials"},
        {"text": "In mice, it improved **energy and metabolism**."},
        {"text": "The catch: human anti-aging proof is **missing**."},
        {"text": "Follow for tomorrow's drop."}]},
]


def _load_seen() -> list[str]:
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text())
        except json.JSONDecodeError:
            return []
    return []


def _save_seen(seen: list[str]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def _pick(count: int) -> list[dict]:
    """Pick `count` least-recently-used topics (recycle oldest when pool exhausted)."""
    seen = _load_seen()
    unseen = [t for t in TOPIC_POOL if t["id"] not in seen]
    chosen = unseen[:count]
    if len(chosen) < count:  # pool exhausted → recycle the oldest-seen first
        order = {tid: i for i, tid in enumerate(seen)}
        recycled = sorted(
            (t for t in TOPIC_POOL if t["id"] in seen),
            key=lambda t: order.get(t["id"], 0),
        )
        chosen += recycled[: count - len(chosen)]
    return chosen


def _frame_uris(mp4: str, times=(1.5, 8.0)) -> list[str]:
    """Grab a couple of frames as base64 data URIs for the visual-QA agent."""
    uris = []
    for t in times:
        p = tempfile.mktemp(suffix=".png")
        try:
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t),
                            "-i", mp4, "-vframes", "1", p], check=True)
            uris.append("data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode())
        except Exception:  # noqa: BLE001 — vision is best-effort
            pass
        finally:
            Path(p).unlink(missing_ok=True)
    return uris


def _img_data_uri(path: str) -> str:
    """Base64 data URI with the correct MIME (Imagen returns PNG, Pollinations JPEG)."""
    data = Path(path).read_bytes()
    mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(data).decode()


async def _make_one(topic: dict, *, voice: str, privacy: str, upload: bool,
                    use_agent: bool = True, use_images: bool = False, slot_index: int = 0) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = OUTPUT_DIR / f"{topic['id']}-{ts}.mp4"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    segments = await build_segments(topic["segments"], voice=voice, use_vo=True)

    # Premium scene imagery: ONE cinematic hero image per reel (not one per beat) →
    # the composition renders it as a continuous full-reel backdrop with a slow Ken
    # Burns under the captions. Best-effort: falls back to motion graphics on failure,
    # so a flaky image provider can never produce a broken/blank frame.
    hero_uri = None
    if use_images:
        try:
            prompt = await hero_director(topic["id"], topic["segments"])
            seed = int(__import__("hashlib").md5(topic["id"].encode()).hexdigest()[:6], 16)
            img = await generate_image(prompt, seed=seed)
            if img:
                hero_uri = _img_data_uri(img)
                logger.info("hero image: ok")
            else:
                logger.info("hero image: none — motion graphics only")
        except Exception as e:  # noqa: BLE001 — imagery is best-effort
            logger.warning("hero imagery failed (%s) — motion-graphics only", e)

    props = {"segments": segments, "brand": BRAND, "headerLabel": HEADER,
             "disclaimer": DISCLAIMER, "icon": ICONS.get(topic["id"], "🔬"),
             "bodyFocus": BODY_FOCUS.get(topic["id"], "whole")}
    if hero_uri:
        props["heroImage"] = hero_uri
    rendered = await render_reel(composition="ScienceNewsReel", props=props, output_path=str(out))
    result = {"id": topic["id"], "file": rendered.path, "uploaded": False}
    if not upload:
        result["status"] = "rendered"
        return result

    from aeco.tools.content.youtube_publisher import YouTubeError, upload_short

    # Basic metadata (fallback if the agent is off or errors).
    title = topic["segments"][0]["text"].replace("**", "") + " #Shorts"
    src = next((s.get("source") for s in topic["segments"] if s.get("source")), None)
    desc = ("A daily science drop on supplements & medical discoveries.\n"
            "Educational only — not medical advice." + (f"\nSource: {src}" if src else ""))
    tags = ["science", "health", "longevity", "supplements", "shorts"]

    # ── Social-media team: review + optimize before publishing ──
    if use_agent:
        script = " ".join(s["text"].replace("**", "") for s in topic["segments"])
        opt = await review_and_optimize(topic["id"], script, _frame_uris(rendered.path),
                                        slot_index=slot_index)
        result["agent"] = {k: opt[k] for k in
                           ("approved", "quality_score", "decision", "visual_ok", "issues", "posting_time")}
        if not opt["approved"]:
            result["status"] = "held_by_agent"
            return result  # gate: don't publish what the team flagged
        # Keep the first-line hook as the title — the agent's rewrites read as
        # generic "Discover…" clickbait and underperform the punchy hook.
        if opt["description"]:
            desc = opt["description"]
        if opt["tags"]:
            tags = opt["tags"]
        if opt["hashtags"]:
            desc = (desc + "\n\n" + " ".join(opt["hashtags"])).strip()

    try:
        res = await upload_short(rendered.path, title=title, description=desc,
                                 tags=tags, privacy=privacy)
        result.update(uploaded=True, status="uploaded", video_id=res["id"],
                      url=res["watch_url"], title=title)
    except YouTubeError as e:
        result.update(status="upload_failed", error=str(e)[:200])
    return result


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--voice", default="male_deep")
    ap.add_argument("--privacy", default="unlisted", choices=["private", "unlisted", "public"])
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--no-agent", action="store_true", help="skip the social-media review/optimize team")
    ap.add_argument("--images", action="store_true", help="enable AI scene imagery (default OFF — clean kinetic-typography only)")
    ap.add_argument("--topic", help="render only this topic id (testing; skips the LRU picker and seen-state)")
    args = ap.parse_args()

    if args.topic:
        pool = {t["id"]: t for t in TOPIC_POOL + DEMOTED_TOPICS}
        if args.topic not in pool:
            sys.exit(f"unknown topic {args.topic!r}. Known: {', '.join(sorted(pool))}")
        topics = [pool[args.topic]]
    else:
        topics = _pick(args.count)
    logger.info("Batch of %d: %s", len(topics), ", ".join(t["id"] for t in topics))
    seen = _load_seen()
    results = []
    for i, t in enumerate(topics):
        logger.info("── %s ──", t["id"])
        try:
            r = await _make_one(t, voice=args.voice, privacy=args.privacy,
                                upload=not args.no_upload, use_agent=not args.no_agent,
                                use_images=args.images, slot_index=i)
        except Exception as e:  # noqa: BLE001 — one failure shouldn't sink the batch
            logger.exception("failed %s", t["id"])
            r = {"id": t["id"], "status": "error", "error": str(e)[:200], "uploaded": False}
        results.append(r)
        # Consume a topic once it's uploaded OR the team held it (same script would just
        # be held again). Quota failures/errors stay unseen so they retry next run.
        if r.get("status") in ("uploaded", "held_by_agent") and t["id"] not in seen:
            seen.append(t["id"])
            _save_seen(seen)

    print("\n" + "=" * 64)
    print(f"DAILY REELS — {sum(1 for r in results if r.get('uploaded'))}/{len(results)} published")
    print("=" * 64)
    for r in results:
        line = f"  [{r.get('status','?'):14}] {r['id']}"
        ag = r.get("agent")
        if ag:
            line += f"  (score {ag['quality_score']:.2f}, {ag['posting_time']})"
        if r.get("url"):
            line += f"  → {r['url']}"
        if r.get("status") == "held_by_agent" and ag:
            line += f"  ⚠ {'; '.join(ag['issues'][:2])}"
        elif r.get("error"):
            line += f"  ✗ {r['error']}"
        print(line)
    print("=" * 64)


if __name__ == "__main__":
    asyncio.run(main())
