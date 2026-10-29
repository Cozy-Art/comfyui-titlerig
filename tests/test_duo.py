"""titlerig_ltx2_duo: two rig layers, each guiding its own LTX-2 pass with its own prompt, cut back together."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "workflows"))
sys.path.insert(0, os.path.join(ROOT, "examples"))
from build_workflows import DRYRUN, LINE_Y, MODELS, dryrun, ltx2_animated, ltx2_duo  # noqa: E402

G = ltx2_duo()


def ref(nid, slot=0):
    return [nid, slot]


def test_each_layer_has_its_own_prompt_and_material():
    assert G["5"]["inputs"]["preset"] == "Shaggy Fur" and G["5"]["inputs"]["glyphs"] == ref("1")
    assert G["105"]["inputs"]["preset"] == "Cloud Puff" and G["105"]["inputs"]["glyphs"] == ref("101")
    assert G["46"]["inputs"]["text"] == ref("5") and G["146"]["inputs"]["text"] == ref("105")
    assert G["26"]["inputs"]["look"] == ref("5", 2) and G["126"]["inputs"]["look"] == ref("105", 2)


def test_each_pass_is_guided_by_its_own_layer_and_shares_the_models():
    assert G["30"]["inputs"]["image"] == ref("26", 2) and G["130"]["inputs"]["image"] == ref("126", 2)
    assert G["152"]["inputs"]["image"] == ref("130") and G["152"]["inputs"]["latent"] == ref("151")
    loaders = [k for k, n in G.items() if "Loader" in n["class_type"]]
    assert sorted(loaders, key=int) == ["40", "41", "42", "43", "44", "45"]  # loaded once, used by both passes
    assert G["157"]["inputs"]["model"] == ref("41") and G["165"]["inputs"]["model"] == ref("42")
    hero = ltx2_animated()  # pass 2 is the hero's chain, renumbered
    for k in [k for k in hero if 46 <= int(k) <= 71]:
        assert G[str(int(k) + 100)]["class_type"] == hero[k]["class_type"]


def test_both_layers_match_frame_for_frame():
    a, b = G["26"]["inputs"], G["126"]["inputs"]
    assert (a["width"], a["height"], a["pad_ltx"]) == (b["width"], b["height"], b["pad_ltx"]) == (1280, 720, True)
    from duo_preview import evaluate, pack  # noqa: E402

    nodes, memo = pack(), {}
    n = []
    for rid in ("26", "126"):
        r = G[rid]["inputs"]
        anim = evaluate(G, r["anim"][0], nodes, memo)[0]
        glyphs = evaluate(G, r["glyphs"][0], nodes, memo)[0]
        n.append(anim.n_frames(sum(1 for c in glyphs.text if c.strip())))
    assert n[0] == n[1] == 120  # 5 s of track at 24 fps -> 121 with pad_ltx, LTX's 8n+1


def test_motion_title_flies_in_then_dances_line_streams_and_is_magnetised():
    chain, k = [], "25"
    while k:
        chain.append(G[k]["inputs"].get("effect"))
        k = (G[k]["inputs"].get("anim") or [None])[0]
    assert chain[::-1] == ["pop", "slide", "roll_z", "pop", "drop", "shadow_length"]
    mg = G["112"]["inputs"]
    assert mg["polarity"] == "repel" and mg["drive"] == ref("21") and mg["y"] == round(LINE_Y, 4)
    assert G["110"]["inputs"]["effect"] == "slide" and G["110"]["inputs"]["start"] > 0
    assert G["126"]["inputs"]["anim"] == ref("112")


def test_fur_title_is_cut_in_over_the_spell_locked_clouds():
    assert G["80"]["inputs"]["images"] == ref("171") and G["80"]["inputs"]["alpha"] == ref("126", 1)
    cut = G["90"]["inputs"]
    assert cut["inside"] == ref("71") and cut["alpha"] == ref("26", 1) and cut["outside"] == ref("80")
    saves = [n for n in G.values() if n["class_type"] == "CreateVideo"]
    assert len(saves) == 6 and all(n["inputs"]["audio"] == ref("20") for n in saves)


def test_dry_run_keeps_the_rig_half_and_drops_every_model():
    d = dryrun(G, DRYRUN["titlerig_ltx2_duo"])
    names = {m[0] for m in MODELS.values()}
    assert not [n for n in d.values() if names & {str(v) for v in n["inputs"].values()}]
    assert {"26", "126", "80", "90", "91"} <= set(d)
    assert d["90"]["inputs"]["inside"] == ref("26") and d["80"]["inputs"]["images"] == ref("126")
