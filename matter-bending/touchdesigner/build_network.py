"""Matter Bending -- TouchDesigner network builder.

Run this ONCE inside TouchDesigner to generate the full starter network:
OSC input, a particle/water system, gesture-driven forces, a glow/bloom +
trail render chain, and an avatar-assembly placeholder channel. See
touchdesigner/README.md for the exact steps to run this.

This script was written and syntax-checked without TouchDesigner installed
(see the repo's development notes) -- every TD operator TYPE it creates
(oscinCHOP, particleSOP, forceSOP, geoCOMP, renderTOP, ...) is a long-stable
part of TD's Python API and should exist across TD versions. A handful of
individual PARAMETER names are less certain (exact internal names for
things like Force SOP's position/type, or Particle SOP's reset pulse, can
vary by version) -- every parameter set below is wrapped so a bad guess is
recorded as a warning and skipped rather than crashing the build. Read the
summary this script prints at the end: anything under "MANUAL FIXUPS
NEEDED" is a short, precise list of exactly what to set by hand in the UI
(TD's own parameter dialog will show you the right name once you're
looking at the node).

Safe to re-run: it destroys and rebuilds /matterbending1 from scratch each
time, so any manual edits inside that COMP will be lost -- duplicate it
first if you want to keep changes.
"""

# Edit these two if you move the repo somewhere other than where this
# script itself lives (TD's exec-from-Textport has no reliable way to
# infer its own file path, so this is a plain constant instead).
REPO_MATTER_BENDING_DIR = "/Users/user/Desktop/cool-projects/matter-bending"
CALLBACK_SOURCE_PATH = REPO_MATTER_BENDING_DIR + "/touchdesigner/matterbending_callbacks.py"
GLSL_SOURCE_PATH = REPO_MATTER_BENDING_DIR + "/touchdesigner/glow_bloom.frag"
PROJECT_SAVE_PATH = REPO_MATTER_BENDING_DIR + "/touchdesigner/matterbending.toe"

WORLD_HALF_WIDTH = 3.0
WORLD_HALF_HEIGHT = 3.0

REPORT = {"created": [], "warnings": []}


def log(msg):
    print("[matterbending] {}".format(msg))


def warn(msg):
    REPORT["warnings"].append(msg)
    log("WARNING: {}".format(msg))


def create_op(container, optype, name, label):
    """Create `name` in `container`, replacing it if it already exists."""
    existing = container.op(name)
    if existing is not None:
        existing.destroy()
    try:
        new_op = container.create(optype, name)
        REPORT["created"].append(name)
        log("created {} ({})".format(name, label))
        return new_op
    except Exception as exc:
        warn("could not create '{}' ({}): {}".format(name, label, exc))
        return None


def set_par(op_ref, par_name, value, context=""):
    if op_ref is None:
        return False
    try:
        setattr(op_ref.par, par_name, value)
        return True
    except Exception as exc:
        warn("{}.par.{} = {!r} failed ({}): {}".format(
            getattr(op_ref, "name", "?"), par_name, value, context, exc
        ))
        return False


def set_par_any(op_ref, candidates, value, context=""):
    if op_ref is None:
        return None
    for name in candidates:
        try:
            setattr(op_ref.par, name, value)
            return name
        except Exception:
            continue
    warn("{}: none of {} accepted {!r} ({}) -- set this manually".format(
        getattr(op_ref, "name", "?"), candidates, value, context
    ))
    return None


def connect(dest_op, src_op, input_index=0, context=""):
    if dest_op is None or src_op is None:
        return False
    try:
        dest_op.inputConnectors[input_index].connect(src_op)
        return True
    except Exception as exc:
        warn("could not connect {} -> {}[{}] ({}): {}".format(
            getattr(src_op, "name", "?"), getattr(dest_op, "name", "?"),
            input_index, context, exc
        ))
        return False


def read_text_file(path, description):
    try:
        with open(path, "r") as handle:
            return handle.read()
    except Exception as exc:
        warn("could not read {} from {}: {}".format(description, path, exc))
        return ""


def build_osc_chain(base):
    osc_hand = create_op(base, oscinCHOP, "osc_hand", "OSC In CHOP")
    set_par(osc_hand, "port", 9000, "OSC network port")

    hand_data = create_op(base, nullCHOP, "hand_data", "Null CHOP")
    connect(hand_data, osc_hand, context="osc_hand -> hand_data")

    return hand_data


def build_particle_system(base):
    geo = create_op(base, geoCOMP, "geo1", "Geometry COMP")
    if geo is None:
        return None, None

    # Everything below lives inside geo1's own SOP network.
    source1 = create_op(geo, sphereSOP, "source1", "Sphere SOP (particle birth source)")
    set_par(source1, "rad1", 1.5, "source radius")

    particle1 = create_op(geo, particleSOP, "particle1", "Particle SOP")
    set_par(particle1, "life", 4.0, "particle life expectancy (seconds)")

    attract1 = create_op(geo, forceSOP, "attract1", "Force SOP (attract/repel)")
    set_par_any(attract1, ("type",), "attract", "force type")
    set_par(attract1, "strength", 0.0, "initial strength")

    turbulence1 = create_op(geo, forceSOP, "turbulence1", "Force SOP (grab deformation)")
    set_par_any(turbulence1, ("type",), "turbulence", "force type")
    set_par(turbulence1, "strength", 0.0, "initial strength")

    merge1 = create_op(geo, mergeSOP, "merge1", "Merge SOP (combine forces)")
    connect(merge1, attract1, input_index=0, context="attract1 -> merge1")
    connect(merge1, turbulence1, input_index=1, context="turbulence1 -> merge1")

    connect(particle1, source1, input_index=0, context="source1 -> particle1 (birth source)")
    connect(particle1, merge1, input_index=1, context="merge1 -> particle1 (forces)")

    avatar_placeholder1 = create_op(
        geo, sphereSOP, "avatar_placeholder1", "avatar-assembly placeholder geometry"
    )
    avatar_placeholder1.bypass = True

    mat1 = create_op(base, constMAT, "glow_mat1", "Constant MAT (particle color)")
    set_par(mat1, "colorr", 0.4, "glow color R")
    set_par(mat1, "colorg", 0.8, "glow color G")
    set_par(mat1, "colorb", 1.0, "glow color B")

    set_par(geo, "material", "../glow_mat1", "assign particle material")

    try:
        particle1.render = True
    except Exception as exc:
        warn("could not set particle1.render = True: {}".format(exc))

    return geo, particle1


def build_render_chain(base, geo):
    cam1 = create_op(base, cameraCOMP, "cam1", "Camera COMP")
    set_par(cam1, "tz", 8.0, "camera pull-back distance")

    light1 = create_op(base, lightCOMP, "light1", "Light COMP")

    render1 = create_op(base, renderTOP, "render1", "Render TOP")
    set_par(render1, "camera", "../cam1", "render camera")
    set_par(render1, "lights", "../light1", "render light")

    blur1 = create_op(base, blurTOP, "blur1", "Blur TOP (bloom source)")
    set_par_any(blur1, ("size", "blursize"), 12.0, "blur radius")
    connect(blur1, render1, context="render1 -> blur1")

    glow_comp1 = create_op(base, compositeTOP, "glow_comp1", "Composite TOP (additive glow)")
    set_par_any(glow_comp1, ("operand",), "add", "composite blend mode")
    connect(glow_comp1, render1, input_index=0, context="render1 -> glow_comp1")
    connect(glow_comp1, blur1, input_index=1, context="blur1 -> glow_comp1")

    level1 = create_op(base, levelTOP, "level1", "Level TOP (trail fade)")
    set_par_any(level1, ("brightness1", "opacity"), 0.9, "trail fade amount")

    feedback1 = create_op(base, feedbackTOP, "feedback1", "Feedback TOP (trails)")
    set_par_any(feedback1, ("top",), "../level1", "feedback source")

    trail_comp1 = create_op(base, compositeTOP, "trail_comp1", "Composite TOP (trails + glow)")
    set_par_any(trail_comp1, ("operand",), "add", "composite blend mode")
    connect(trail_comp1, glow_comp1, input_index=0, context="glow_comp1 -> trail_comp1")
    connect(trail_comp1, feedback1, input_index=1, context="feedback1 -> trail_comp1")

    connect(level1, trail_comp1, context="trail_comp1 -> level1 (close feedback loop)")

    final_out = create_op(base, nullTOP, "final_out", "Null TOP (final output)")
    connect(final_out, trail_comp1, context="trail_comp1 -> final_out")

    # Bonus/optional: the custom GLSL bloom pass from glow_bloom.frag, left
    # unwired -- its uniform parameters need one manual "Setup Parameters"
    # click inside TD before they can be scripted, see touchdesigner/README.md.
    glsl_text = read_text_file(GLSL_SOURCE_PATH, "glow_bloom.frag")
    if glsl_text:
        shader_dat = create_op(base, textDAT, "glow_bloom_shader", "GLSL source (Text DAT)")
        if shader_dat is not None:
            shader_dat.text = glsl_text
        glow_glsl1 = create_op(base, glslTOP, "glow_glsl1", "GLSL TOP (optional bonus bloom)")
        set_par(glow_glsl1, "pixeldat", "../glow_bloom_shader", "pixel shader source")
        connect(glow_glsl1, render1, context="render1 -> glow_glsl1 (optional)")
        warn(
            "glow_glsl1 was created but left unwired -- open it, click "
            "'Setup Parameters' on the Text DAT-referencing page to expose "
            "uThreshold/uIntensity/uRadiusPx, then it's an optional drop-in "
            "replacement for blur1+glow_comp1"
        )

    return final_out


def build_avatar_placeholder_channel(base):
    assemble1 = create_op(base, constantCHOP, "assemble1", "Constant CHOP (avatar-assembly placeholder)")
    set_par_any(assemble1, ("name0",), "assemble", "channel name")
    set_par_any(assemble1, ("value0",), 0.0, "initial value")
    return assemble1


def build_callback_dat(base):
    code = read_text_file(CALLBACK_SOURCE_PATH, "matterbending_callbacks.py")
    hand_logic1 = create_op(base, textDAT, "hand_logic1", "Execute DAT source (Text DAT)")
    if hand_logic1 is None:
        return None

    exec_dat = create_op(base, executeDAT, "hand_logic1_exec", "Execute DAT")
    if code:
        hand_logic1.text = code
    set_par(exec_dat, "framestart", 1, "run on Frame Start")

    # Point the Execute DAT at the callback source so it actually calls
    # onFrameStart() from matterbending_callbacks.py.
    try:
        exec_dat.text = (
            "# Delegates to hand_logic1 (matterbending_callbacks.py contents).\n"
            "def onFrameStart(frame):\n"
            "    op('hand_logic1').module.onFrameStart(frame)\n"
        )
    except Exception as exc:
        warn("could not wire hand_logic1_exec to hand_logic1: {}".format(exc))

    return exec_dat


def build():
    root_container = op("/")
    existing = root_container.op("matterbending1")
    if existing is not None:
        log("removing existing /matterbending1 and rebuilding from scratch")
        existing.destroy()

    base = root_container.create(baseCOMP, "matterbending1")
    REPORT["created"].append("matterbending1")
    log("created container /matterbending1")

    build_osc_chain(base)
    geo, _particle1 = build_particle_system(base)
    build_render_chain(base, geo)
    build_avatar_placeholder_channel(base)
    build_callback_dat(base)

    log("saving project to {}".format(PROJECT_SAVE_PATH))
    try:
        project.save(PROJECT_SAVE_PATH)
        log("saved.")
    except Exception as exc:
        warn("project.save() failed: {} -- save manually with Cmd+S to {}".format(
            exc, PROJECT_SAVE_PATH
        ))

    log("")
    log("=== BUILD SUMMARY ===")
    log("{} operators created".format(len(REPORT["created"])))
    if REPORT["warnings"]:
        log("")
        log("=== MANUAL FIXUPS NEEDED ({}) ===".format(len(REPORT["warnings"])))
        for warning in REPORT["warnings"]:
            log(" - " + warning)
    else:
        log("no warnings -- network built cleanly.")
    log("")
    log("Next: run `python3 hand_tracker.py` from matter-bending/ and confirm")
    log("hand_data's `present` channel goes to 1 with a hand in frame.")


build()
