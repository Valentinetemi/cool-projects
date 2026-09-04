# TouchDesigner: build the starter project

TouchDesigner isn't installed in the environment this repo was developed
in, so the network below was written and syntax-checked but never run or
opened in TouchDesigner itself. `build_network.py` is written defensively
(every parameter it sets is wrapped so a version-specific naming mismatch
becomes a one-line warning, not a crash) — see its own docstring for
details. Treat this as a strong starting point to open and verify, not a
guaranteed-perfect project.

## What you need

- TouchDesigner (the free non-commercial build is enough) — download from
  the official site, touchdesigner.com, if it isn't already installed.
- This repo checked out at `/Users/user/Desktop/cool-projects/matter-bending`
  (the path `build_network.py` is hardcoded to — see below if yours
  differs).

## Steps

1. **Open TouchDesigner** and start a new, empty project.
2. **Open the Textport**: menu *Dialogs → Textport and DATs* (or `Alt+T`).
3. **Run the build script** by pasting this into the Textport and pressing
   Enter:
   ```python
   exec(open('/Users/user/Desktop/cool-projects/matter-bending/touchdesigner/build_network.py').read())
   ```
4. **Read the printed summary.** It ends with either "no warnings -- network
   built cleanly" or a short `MANUAL FIXUPS NEEDED` list naming the exact
   node and parameter to check — open that node's parameter dialog in TD,
   find the correctly-named field (autocomplete/hover-help will show it),
   and set it there. This is expected to be a handful of items at most, not
   a rebuild.
5. **Start the hand tracker** from a terminal:
   ```bash
   cd /Users/user/Desktop/cool-projects/matter-bending
   source .venv/bin/activate
   python3 hand_tracker.py
   ```
6. **Verify inside TD**: open `/matterbending1/hand_data`'s viewer — with a
   hand in frame, `present` should read `1` and `palm:x`/`palm:y` should
   move as your hand does. Open `/matterbending1/final_out` to see the
   particle render; pinch should pull it toward your hand, grab should
   pull harder and turn rough/turbulent, open palm should push it away.
7. The build script already saves the project to
   `matter-bending/touchdesigner/matterbending.toe` as its last step (you
   don't need to save manually). Commit it:
   ```bash
   cd /Users/user/Desktop/cool-projects
   git add matter-bending/touchdesigner/matterbending.toe
   git commit -m "feat: add generated TouchDesigner starter project"
   git push origin main
   ```

## If your repo path is different

`build_network.py` and `matterbending_callbacks.py` don't try to detect
their own file location (TD's Textport `exec()` doesn't reliably expose
that) — instead `build_network.py` has the repo path as a constant at the
top:

```python
REPO_MATTER_BENDING_DIR = "/Users/user/Desktop/cool-projects/matter-bending"
```

Edit that one line if you've checked the repo out somewhere else, then
re-run step 3.

## What the script builds

See [../docs/TOUCHDESIGNER_GUIDE.md](../docs/TOUCHDESIGNER_GUIDE.md) for
the full walkthrough of the network and the reasoning behind it. Briefly:

```
osc_hand (OSC In CHOP, port 9000) -> hand_data (Null CHOP)
                                          |
                         hand_logic1_exec (Execute DAT, Frame Start)
                         reads hand_data every frame and drives:
                                          |
        +---------------------+----------+-----------------------+
        |                     |                                  |
   attract1 (Force SOP)  turbulence1 (Force SOP)          geo1 visibility
   position = palm       strength = grab only              + particle1
   strength = pinch/                                       reset pulse
   grab/-openness                                           (presence)
        |                     |
        +--------> merge1 ----+
                     |
                  particle1 (source1 = birth geometry)
                     |
                   geo1 (material = glow_mat1)
                     |
             cam1 + light1 -> render1
                     |
        blur1 --> glow_comp1 (add) --> trail_comp1 (add) --> final_out
                                              ^
                          feedback1 <-- level1 (dim) <--------+

assemble1 (Constant CHOP) -- avatar-assembly placeholder, ramped by
sustained pinch/grab (up) and open_palm (down), not yet consumed by
anything -- see the guide's "Later: transform particles into an avatar".

glow_glsl1 (GLSL TOP, glow_bloom.frag) -- optional bonus bloom, created
but left unwired; needs one manual "Setup Parameters" click (see the
warning the build script prints) before it can replace blur1+glow_comp1.
```
