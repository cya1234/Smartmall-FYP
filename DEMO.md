# Demo script — showing the virtual try-on to your professor

Everything below uses only what is already in the repository.

---

## 1. Which photos to use

Four sample person photos ship with the vendored CatVTON source. They are
front-facing, waist-up and evenly lit, which is exactly what the model expects.

```
ai-service/vendor/CatVTON/resource/demo/example/condition/person/
├── baumu30483223c3_1719437121402_2-0._QL90_UX564_V12524t6_.jpg   ← verified good
├── jbeeq301271a569_1719429971246_2-0._QL90_UX564_V12524t6_.jpg
├── mison407622250d_1719258948458_2-0._QL90_UX564_V12524t6_.jpg
└── mothr22044226e8_1718142523286_2-0._QL90_UX564_V12524t6_.jpg
```

Only the first one has been tested end to end in this project. Open the others
once beforehand and pick whichever looks most natural after a try-on — you want
the ones where the shoulders and hem land cleanly.

**Licence:** these are CatVTON demo assets, released under CC BY-NC-SA 4.0.
Fine for a class demonstration; say so if asked, and do not use them in anything
commercial.

### Where to get more, legally

| Source | Licence | Notes |
|---|---|---|
| Pexels / Unsplash | free for most uses | search "fashion model full body white background" |
| VITON-HD dataset | research only | it is what CatVTON was trained on, so results are best |
| Your own photo | yours | best option for a live demo — it is obviously *you* being dressed |

What matters more than the source is the **input**: front-facing, waist-up or
three-quarter, plain background, arms not crossing the torso, even lighting. A
photo of someone sitting, back-turned, or in a busy street will look worse and
make the model look worse than it is.

---

## 2. Five-minute demo, in order

> Do **one throwaway try-on before the meeting starts**. The first generation
> loads the pipeline and takes ~15 s longer; after that each run is ~20–30 s.

### Step 1 — the problem (30 s)

Open the product page for the linen shirt:

```
http://localhost:3000/#/product/p004
```

Point at the 門市現貨 block: 8 stores, live stock, one-tap directions. Then at
the price block: "suggest waiting, 11.6% drop, Double 11 in 14 days."

> The point to land: this is a shop that answers questions, not a catalogue.

### Step 2 — the closet (60 s)

```
http://localhost:3000/#/closet
```

* Upload the model photo once. It is downscaled to 720 px and kept **in the
  browser only** — nothing is sent to the server.
* Seven purchased pieces appear, each with size, months since purchase, wear
  count and condition.

> The point to land: customers can try on anything they own, any time — a closet,
> not a checkout.

### Step 3 — the try-on (40 s)

Click **立即試穿** on the linen shirt. A timer counts up while CatVTON runs.

While it runs, say what is happening: "the model concatenates my photo and the
garment photo into one canvas and re-generates the masked region; 768×1024, 20
steps, 3.57 GB of VRAM on the local 4070."

The result appears at the same size as the input, face intact.

### Step 4 — the honesty beat (60 s) — this is the part that impresses

Show the numbers, then the caveats.

```
http://localhost:3000/#/forecast     price forecasting: MAPE 0.34%, wins 38/40
```

Say plainly:

* The price data is synthetic and the sale dates are known to the model, so the
  margin over baseline is an upper bound.
* The try-on lower body is re-generated and can drift, because CatVTON is trained
  on upper-body data. That is why the flow asks for a waist-up photo.
* The assistant's router is rule-based; unfamiliar phrasing will miss.

> Delivering the limitations yourself is worth more than any extra feature. It is
> what separates a demo from an argument.

### Step 5 — the differentiator (60 s)

```
http://localhost:3000/#/dashboard
```

Search volume, retention rate, conversion, and the embeddable widget demo at
`/demo-store.html`.

> The point to land: the customer here is the shop, not the shopper. Taobao
> entering Hong Kong makes this *more* necessary, not less.

---

## 3. If something breaks mid-demo

| Symptom | What it means | What to say / do |
|---|---|---|
| Try-on says "服務離線" | the CatVTON window closed | start `start-with-ai.bat` again; the site falls back to the colour overlay |
| Try-on fails with a channel error | wrong base model | run `tools/prepare_catvton_base.py` again |
| Visual search returns odd results | CLIP service down | fallback is the colour heuristic; say so |
| Everything is slow | GPU busy with another app | close Chrome tabs / Discord and retry |
| A page looks wrong after a CSS change | you edited `styles.css` | hard-refresh with Ctrl+F5 |

---

## 4. Answers to the questions you will actually get

**"Did you train the model?"**
No. CatVTON is an ICLR 2025 model used as-is; the contribution is the system
around it, plus the measurement work.

**"Is this real AI or a mock?"**
Four services: visual search (Marqo-FashionSigLIP + FAISS), price forecasting
(Meta Prophet), try-on (CatVTON), and the assistant (tool calling). Three of the
four load real weights; the assistant's router is rule-based on purpose, so the
tool layer can be measured independently.

**"Why not just use Taobao's API?"**
Because the customer is the shop Taobao is competing with.

**"What is the actual research contribution?"**
A negative result with a correction: the vendor's claimed +57% retrieval gain
does not transfer to Chinese queries, because the encoder is English-aligned.
Adding a 120-term query normalisation lifts Chinese Recall@5 from 17% to 100% on
the 94-query set. Measured, reproducible, and it contradicts the vendor.

**"How do you know the numbers are right?"**
Every table comes from a script in `tools/` (`eval_retrieval.py`,
`eval_forecast.py`, `eval_assistant.py`), and the raw results are committed in
`data/eval/`. You can re-run them in front of them.
