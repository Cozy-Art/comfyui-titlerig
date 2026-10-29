"""titlerig_ltx2_scene: the title rendered into your own image. The image is LTX-2's frame 0, the rig's edges over
the image's edges guide the Canny IC-LoRA, and the original image is restored outside the letters + shadow area."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "workflows"))
from build_workflows import DRYRUN, MODELS, SCENE_PROMPT, dryrun, ltx2_scene  # noqa: E402

G = ltx2_scene()


def ref(nid, slot=0):
    return [nid, slot]


def test_your_image_is_frame_zero_on_both_stages():
    assert G["15"]["class_type"] == "LoadImage"
    assert G["31"]["inputs"]["image"] == ref("15")
    for k in ("51", "63"):
        assert G[k]["inputs"]["image"] == ref("31") and G[k]["inputs"]["bypass"] is False


def test_title_is_absent_on_frame_zero():
    pop = G["19"]["inputs"]
    assert pop["effect"] == "pop" and pop["direction"] == "in" and pop["start"] > 0 and pop["amount"] == 0.0
    assert G["23"]["inputs"]["anim"] == ref("19")  # the audio motion layers on top of the pop-in


def test_guide_is_rig_edges_over_the_scene_edges_with_the_canny_lora():
    assert G["27"]["class_type"] == "Canny" and G["27"]["inputs"]["image"] == ref("15")
    guide = G["28"]["inputs"]
    assert guide["inside"] == ref("26", 3) and guide["outside"] == ref("27") and guide["alpha"] == ref("26", 1)
    assert G["30"]["inputs"]["image"] == ref("28")
    assert G["41"]["inputs"]["lora_name"] == MODELS["ltx2_canny_iclora"][0]
    assert G["41"]["inputs"]["strength_model"] == 1.0 and G["52"]["inputs"]["strength"] == 1.0


def test_prompt_is_yours_and_names_the_exact_text():
    assert G["46"]["inputs"]["text"] == SCENE_PROMPT
    assert '"TITLERIG"' in SCENE_PROMPT and G["1"]["inputs"]["text"] == "TITLERIG"
    assert not any(n["class_type"] == "TitleRigStylePreset" for n in G.values())


def test_plate_is_restored_outside_the_letters_and_shadow():
    cut = G["90"]["inputs"]
    assert cut["inside"] == ref("80") and cut["outside"] == ref("31")
    assert cut["mask_from"] == "silhouette + shadow" and cut["shadow"] == ref("26", 8)
    assert cut["grow"] > 0 and cut["feather"] > 0  # fur and contact shadows keep a soft edge
    saves = [n for n in G.values() if n["class_type"] == "CreateVideo"]
    assert len(saves) == 4 and all(n["inputs"]["audio"] == ref("20") for n in saves)


def test_dry_run_drops_every_model():
    d = dryrun(G, DRYRUN["titlerig_ltx2_scene"])
    names = {m[0] for m in MODELS.values()}
    assert not [n for n in d.values() if names & {str(v) for v in n["inputs"].values()}]
    assert {"15", "26", "27", "28", "80", "90"} <= set(d)
