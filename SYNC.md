# Working across two machines

Measured on 2026-11-18 on the Windows machine, so the numbers are real rather than
copied from an earlier note.

| Part | Size | In git? | What to do on the Mac |
|---|---|---|---|
| Tracked files (744) | **28.5 MB** | yes | `git clone` |
| `.git` history | 21.7 MB | yes | comes with the clone |
| `.cache/hf` (SigLIP, instruct-pix2pix) | **6.72 GB** | no — `.cache/` ignored | re-download |
| `data/models` (CatVTON weights) | **4.07 GB** | no — `data/models/` ignored | re-download |
| `.venv` | 0.56 GB | no | rebuild (never copy) |
| **whole folder** | **12.57 GB** | | |
| Ollama models (3B + 7B) | 6.16 GB | outside the project | re-pull if wanted |

So the code is about **50 MB** and the models are **10.8 GB**. That ratio is the whole
point of this document: sync the small part, regenerate the large part.

---

## The short version

```bash
# Mac, first time
git clone https://github.com/cya1234/Smartmall-FYP.git SmartMall
cd SmartMall
bash setup-mac.sh          # venv, dependencies, models, MPS check
bash start-all.sh
```

```powershell
# Windows, first time only — make sure everything is pushed
cd C:\Users\wpuil\Downloads\SmartMall
git status                 # expect "nothing to commit"
git push
```

After that, the loop is `git pull` before you start and `git push` when you stop.

---

## What must not be copied

| Never copy | Why |
|---|---|
| `.venv` | Windows binaries; a Mac venv is arm64. `setup-mac.sh` builds it in ~2 min. |
| `.cache/hf`, `data/models` | 10.8 GB of weights that can be re-downloaded, and a bad fit for git |
| `.git` through iCloud/Dropbox | two machines editing under a syncing folder corrupts history |
| `node_modules` | not used here, but the same rule |

If you skip this and copy the folder wholesale, you get a repo that is 12 GB, sorts
badly, and has a venv the Mac cannot run.

---

## Moving the models by hand (only if downloading again is painful)

The models are the only slow part. If your connection makes a 10.8 GB re-download
unreasonable, copy these two folders to the same relative paths on the Mac:

```
SmartMall/.cache/hf       <- 6.72 GB
SmartMall/data/models     <- 4.07 GB
```

`setup-mac.sh` then finds them and skips the downloads. An external SSD or Syncthing
over the local network both work; iCloud does not (it chokes on tens of thousands of
small files and will re-upload them).

---

## Rules that keep the two machines sane

1. **Edit on one machine at a time.** Git merges text well and conflicts badly; a
   second machine that has not pulled will fight you.
2. **`git pull` before starting work, `git push` before you stop.** Treating the push
   as part of finishing is what makes "it works on the other one" true.
3. **The database is local.** `data/analytics.db` (the merchant dashboard) and
   `data/preferences.json` (the survey's learned preferences) are ignored on purpose —
   each machine learns from its own clicks. That is correct, not a bug.
4. **Model files are not source.** If you need a different model, change the code that
   points at it, not the blobs.

---

## Checking a fresh clone is complete

```bash
node --check server.js
python -c "import torch; print(torch.cuda.is_available())"   # Windows: True
python -c "import torch; print(torch.backends.mps.is_available())"  # Mac: True
curl -s localhost:3000/api/visual-search/status
curl -s localhost:3000/api/forecast/status
```

If `visual-search/status` says `online:false`, the CLIP service is not up — the site
still runs, it just falls back to the colour heuristic. That is the designed
behaviour, not a broken install.
