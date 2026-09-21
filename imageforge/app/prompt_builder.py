from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


LEGACY_PROMPT_VERSION = "legacy"
NATURAL_EXPRESSION_PROMPT_VERSION = "natural-expression-v1"
REFERENCE_FAITHFUL_PROMPT_VERSION = "reference-faithful-v2"
SUPPORTED_PROMPT_VERSIONS = frozenset(
    {
        LEGACY_PROMPT_VERSION,
        NATURAL_EXPRESSION_PROMPT_VERSION,
        REFERENCE_FAITHFUL_PROMPT_VERSION,
    }
)


@dataclass(frozen=True, slots=True)
class ExpressionPlan:
    strategy_id: str
    head_and_gaze: str
    expression: str


_POSE_PLANS: dict[str, ExpressionPlan] = {
    "FRONT": ExpressionPlan(
        strategy_id="gentle_camera_smile",
        head_and_gaze=(
            "Keep the torso and face directed toward the camera, with level, relaxed shoulders and "
            "both eyes naturally visible. The person's attention rests on the camera. Do not turn "
            "the head toward the animal or force the chin into a posed angle."
        ),
        expression=(
            "The person looks toward the camera with a small, easy smile. The lips meet lightly, "
            "the jaw is relaxed, and the eyes remain naturally attentive. The smile is warm and "
            "understated, like a comfortable moment during a zoo visit."
        ),
    ),
    "SIDE": ExpressionPlan(
        strategy_id="spontaneous_warmth",
        head_and_gaze=(
            "Rotate the torso, hips, and feet together approximately 45–60 degrees to the camera. "
            "Turn the face back gently toward the lens without twisting the neck; keep one full eye "
            "and most or all of the far eye naturally visible. The gaze follows the lens."
        ),
        expression=(
            "The person shows a brief, genuine moment of enjoyment, with gently lifted cheeks and "
            "relaxed eyes. Keep the smile modest and characteristic of this person. The lips may "
            "part slightly when it fits the expression, but a broad toothy grin is not required."
        ),
    ),
    "BACK": ExpressionPlan(
        strategy_id="attentive_interest",
        head_and_gaze=(
            "Keep the back and shoulder line facing the camera while the body remains oriented toward "
            "the animal or habitat. Turn the head back only 20–35 degrees over one shoulder toward a "
            "nearby animal positioned in that look-back direction, leaving a recognizable three-quarter "
            "portion of the face visible. The eyes follow that animal; do not turn the torso front-on."
        ),
        expression=(
            "The person's attention rests naturally on the nearby animal. Their expression conveys "
            "quiet interest with a relaxed mouth and an easy, neutral-to-warm expression. The eyes "
            "follow the selected target in a way that matches the head angle, without turning the "
            "moment into exaggerated surprise."
        ),
    ),
}


_REFERENCE_FAITHFUL_POSE_PLANS: dict[str, ExpressionPlan] = {
    "FRONT": ExpressionPlan(
        strategy_id="reference_consistent_neutral",
        head_and_gaze=(
            "Keep the torso and face directed toward the camera, with level relaxed shoulders and "
            "both eyes naturally visible. Keep the person's attention on the camera without changing "
            "the characteristic eye opening, brow position, or chin shape from the subject references."
        ),
        expression=(
            "Retain the primary subject reference's neutral or lightly relaxed expression. Keep the "
            "mouth comfortable and the eyes naturally attentive. Do not introduce a broader smile, "
            "larger-looking eyes, lifted mouth corners, or a redesigned jaw."
        ),
    ),
    "SIDE": ExpressionPlan(
        strategy_id="reference_consistent_neutral",
        head_and_gaze=(
            "Rotate the torso, hips, and feet together approximately 45–60 degrees to the camera. "
            "Turn the face back gently toward the lens without twisting the neck. Preserve the visible "
            "face contour and eye shape from the subject references at this viewing angle."
        ),
        expression=(
            "Keep a restrained neutral-to-warm expression consistent with the primary subject "
            "reference. The mouth, cheeks, and eyelids may relax naturally for the side angle, but a "
            "smile is not required and facial features must not be beautified or redesigned."
        ),
    ),
    "BACK": ExpressionPlan(
        strategy_id="reference_consistent_neutral",
        head_and_gaze=(
            "Keep the back and shoulder line facing the camera while the body remains oriented toward "
            "the animal or habitat. Turn the head back only 20–35 degrees over the left shoulder toward "
            "the nearby animal, leaving a natural three-quarter portion of the face visible. Keep the "
            "eyes aligned with that target and do not rotate the torso front-on."
        ),
        expression=(
            "Keep a relaxed neutral expression consistent with the primary subject reference, with a "
            "comfortable mouth and naturally attentive eyes. Do not introduce a smile solely because "
            "the body pose is active."
        ),
    ),
}


# These descriptions preserve the existing scene IDs and intent while leaving person orientation,
# gaze, and expression decisions to the selected pose plan above.
_NATURAL_SCENES: dict[str, str] = {
    "PANDA_CASUAL_01": (
        "One adult giant panda with species-accurate black-and-white fur calmly eats bamboo or "
        "briefly looks outward inside a real modern Chinese zoo panda habitat. Place the visitor on "
        "the public side of a slightly used dark viewing railing, with the panda a short believable "
        "distance inside its protected habitat. Use a casual waist-up, friend-held smartphone "
        "composition with the visitor slightly off center. Include bamboo, habitat rocks, subtle "
        "safety-glass reflection, worn visitor surfaces, and a softly blurred educational sign."
    ),
    "RED_PANDA_VIEW_01": (
        "A real red panda with an accurate reddish coat, dark limbs, ringed tail, and natural "
        "proportions moves on a wooden climbing structure inside a leafy zoo habitat. Place the "
        "visitor at the public viewing rail and keep the red panda inside its protected habitat. "
        "Use an imperfect friend-held waist-up smartphone snapshot with ordinary daylight filtered "
        "through leaves, worn timber, mesh or glass protection, and blurred signage."
    ),
    "ELEPHANT_WALK_01": (
        "One anatomically accurate Asian elephant walks calmly inside a spacious zoo habitat behind "
        "a clearly visible safety boundary. Place the visitor on the public path in the foreground, "
        "with believable scale and distance. Use a slightly wide, eye-level smartphone frame with "
        "realistic perspective and a little background motion softness. Include habitat trees, earth, "
        "rocks, a worn railing, and an unreadable blurred information board."
    ),
    "GIRAFFE_WINDOW_01": (
        "One real giraffe with correct coat pattern, ossicones, long neck, muzzle, and scale leans "
        "curiously toward a zoo viewing window or protected feeding overlook. Keep the visitor safely "
        "on the public side. Use a casual waist-up smartphone photo where the giraffe enters from one "
        "side of frame, preserving wide-angle perspective without distorting the face. Include habitat "
        "trees, rail hardware, and softly blurred visitor infrastructure."
    ),
    "FLAMINGO_LAGOON_01": (
        "Several anatomically correct flamingos stand and forage naturally in a shallow zoo lagoon "
        "behind a subtle habitat boundary. Place the visitor on the public lakeside path. Use an "
        "ordinary friend-held smartphone composition with a slightly imperfect horizon and realistic "
        "depth. Include reeds, worn path edging, softly rippled water, and blurred zoo signage."
    ),
    "DOLPHIN_WINDOW_01": (
        "One anatomically accurate dolphin swims naturally behind a large underwater viewing window "
        "in a real zoo aquarium. Keep the visitor on the dry public side of the glass and the dolphin "
        "at a believable depth. Use a casual waist-up smartphone snapshot with plausible blue-green "
        "tank light, subtle glass smudges, water caustics, structural window edges, and an unreadable "
        "blurred information panel."
    ),
    "LEMUR_HABITAT_01": (
        "One ring-tailed lemur with accurate facial markings, hands, feet, and striped tail sits or "
        "climbs on a natural branch inside a glass-fronted zoo habitat. Keep the visitor on the public "
        "side and make the glass and safe separation physically clear. Use a slightly off-center, "
        "waist-up smartphone composition with mild reflection, branches, leaves, enclosure hardware, "
        "and a blurred sign."
    ),
    "WHITE_TIGER_GLASS_01": (
        "One anatomically accurate adult white tiger walks or rests inside a real zoo habitat behind "
        "thick safety glass. Keep the visitor on the public viewing side and the tiger on a separate "
        "depth plane. Use an eye-level friend-held smartphone frame with the visitor slightly off "
        "center. Include rocks, vegetation, glass seams, restrained reflections, and blurred signage."
    ),
    "CAPYBARA_LAWN_01": (
        "One calm, anatomically accurate capybara stands or sits in a staff-managed zoo encounter "
        "lawn. Place the visitor beside a low boundary at a believable supervised distance, with a "
        "railing or clear spatial cue. Use a casual friend-held smartphone snapshot with believable "
        "ground contact, slight depth of field, ordinary lawn wear, low fencing, scattered vegetation, "
        "and blurred signage."
    ),
}


_STYLE_AND_COMPOSITION = """
Create an ordinary, photorealistic friend-held smartphone photograph at eye level, approximately a
26 mm full-frame-equivalent perspective, with plausible perspective, slightly imperfect off-center
framing, realistic dynamic range, restrained grain, tiny natural motion softness, and believable
depth of field. Use the existing scene's ordinary daylight or mixed exhibit light rather than studio
or advertising lighting.

Keep the person, animals, barriers, and environment coherent in scale, perspective, lighting,
shadows, ground contact, and occlusion. Respect safety glass, railings, habitat edges, and realistic
zoo distances. Preserve species-accurate animal anatomy and the defining details of the selected
scene and selected body pose.
""".strip()


_PHOTO_FACE_RENDERING = """
Render believable skin texture and soft, coherent facial lighting. The face should feel naturally
present in the scene, without heavy beauty retouching or a waxy finish. Preserve pores, ordinary
facial volume, normal asymmetry, and the person's natural skin tone. Do not apply face slimming,
eye enlargement, a V-shaped jaw, or an influencer-style beauty filter.
""".strip()


_OUTPUT_REQUIREMENTS = """
Return one portrait-oriented 2:3 photorealistic image only. Depict exactly the requested number of
visitors, each once. Keep hands and limbs anatomically plausible. Do not add readable text, captions,
logos, borders, watermarks, collages, split screens, or extra reflected faces.
""".strip()


EXPRESSION_REPAIR_TEMPLATE = """
Edit the supplied generated image to make the person's facial expression more relaxed and natural.

Use the original subject references to preserve the same person's identity. Adjust only the facial
expression as needed: {specific_observed_expression_problem}
Target expression: {resolved_expression_description}

Keep the existing head direction, body pose, hairstyle, clothing, animals, background, framing, and
lighting unchanged as far as possible. Preserve the person's distinctive facial proportions. Do not
replace the person with a different face.
""".strip()


def _reference_role_description(reference_roles: Iterable[str]) -> str:
    roles = [role.strip() for role in reference_roles if role and role.strip()]
    if not roles:
        raise ValueError("natural-expression-v1 requires at least one labeled subject reference")
    lines = [
        "The supplied images are subject identity references. Their labels and order are:",
        *(f"- {role}" for role in roles),
        "No scene or pose image is supplied; the selected scene and pose are defined by the text below.",
        "If a future scene or pose reference contains another model, that model must not define the "
        "visitor's face, age, or identity.",
    ]
    return "\n".join(lines)


def _faithful_reference_role_description(reference_roles: Iterable[str]) -> str:
    roles = [role.strip() for role in reference_roles if role and role.strip()]
    if not roles:
        raise ValueError("reference-faithful-v2 requires at least one labeled subject reference")
    primary_count = sum("SUBJECT_PRIMARY" in role for role in roles)
    if primary_count < 1:
        raise ValueError("reference-faithful-v2 requires a SUBJECT_PRIMARY reference")
    return "\n".join(
        [
            "The supplied images and their actual request order are:",
            *(f"- {role}" for role in roles),
            "SUBJECT_PRIMARY defines current facial appearance, hairstyle, fringe, eyewear, and other "
            "visible accessories for that person.",
            "SUBJECT_ADDITIONAL images are other views of the same person and only supplement identity, "
            "outfit, and target-angle information.",
            "No SCENE_REFERENCE or POSE_REFERENCE image is supplied in this request. The scene and pose "
            "are defined by the selected server-side text below.",
        ]
    )


def _group_layout(participant_count: int) -> str:
    if participant_count < 1 or participant_count > 4:
        raise ValueError("参与者数量必须为 1 至 4 人")
    layout = {
        1: "one visitor in a relaxed off-center composition",
        2: "two visitors side by side with a slight natural depth offset and no overlapping faces",
        3: "three visitors in a shallow triangular arrangement with all faces readable",
        4: "four visitors in a balanced two-front/two-back or gentle arc arrangement without hidden faces",
    }[participant_count]
    plural = "s" if participant_count != 1 else ""
    return (
        f"Depict exactly {participant_count} human visitor{plural}: {layout}. Keep each participant's "
        "identity, hairstyle, glasses, outfit, body shape, age appearance, and skin tone distinct. "
        "Never merge, average, duplicate, omit, or exchange people or clothing between groups."
    )


def _faithful_group_layout(participant_count: int) -> str:
    if participant_count < 1 or participant_count > 4:
        raise ValueError("参与者数量必须为 1 至 4 人")
    layout = {
        1: "one visitor in a relaxed off-center composition",
        2: "two visitors side by side with a slight natural depth offset and no overlapping faces",
        3: "three visitors in a shallow triangular arrangement with all faces readable",
        4: "four visitors in a balanced two-front/two-back or gentle arc arrangement without hidden faces",
    }[participant_count]
    plural = "s" if participant_count != 1 else ""
    return (
        f"Depict exactly {participant_count} human visitor{plural}: {layout}. Keep each participant's "
        "identity, hairstyle, eyewear state, visible accessories, outfit, body shape, age appearance, "
        "and skin tone distinct. Never merge, average, duplicate, omit, or exchange people or "
        "clothing between groups."
    )


def build_natural_expression_prompt(
    scene: Any,
    pose: Any,
    participant_count: int,
    reference_roles: Iterable[str],
) -> str:
    try:
        scene_description = _NATURAL_SCENES[scene.scene_id]
        expression_plan = _POSE_PLANS[pose.pose_id]
    except KeyError as exc:
        raise ValueError(f"缺少自然表情提示词配置：{exc.args[0]}") from exc

    prompt = f"""Create an image of the person or people shown in the designated subject reference
images, in the selected zoo scene and selected pose.

REFERENCE ROLES
{_reference_role_description(reference_roles)}

IDENTITY
Depict the same person as each participant's subject references. Preserve distinctive facial
features, facial proportions, apparent age, natural skin tone, hairstyle, glasses or accessories,
body proportions, outfit, and other visible personal appearance details. Use the different subject
views to understand the same person's appearance from the target angle. Scene and pose instructions
do not define identity.

Preserve identity while allowing natural changes in the eyelids, cheeks, mouth, eyebrows, and jaw
for the requested expression. An already relaxed reference expression may be retained when it fits
the pose. Keep characteristic features and natural asymmetry rather than replacing the person with
an idealized or perfectly symmetrical face.

GROUP COMPOSITION
{_group_layout(participant_count)}

SELECTED SCENE — {scene.scene_id}: {scene.title}
{scene_description}

SELECTED POSE — {pose.pose_id}: {pose.title}
{pose.description}

HEAD ORIENTATION AND ATTENTION
{expression_plan.head_and_gaze}

FACIAL EXPRESSION — {expression_plan.strategy_id}
{expression_plan.expression}

The expression should feel comfortable and unforced for this person in this situation. Let the
eyes, cheeks, and mouth work together naturally. Do not standardize expressions across participants.

VISUAL STYLE AND COMPOSITION
{_STYLE_AND_COMPOSITION}

{_PHOTO_FACE_RENDERING}

OUTPUT
{_OUTPUT_REQUIREMENTS}"""
    lowered = prompt.lower()
    if any(token in lowered for token in ("{{", "}}", "undefined", "null")):
        raise ValueError("提示词包含未解析变量")
    return prompt.strip()


def build_reference_faithful_prompt(
    scene: Any,
    pose: Any,
    participant_count: int,
    reference_roles: Iterable[str],
    resolved_appearance_requirements: Iterable[str] | None = None,
    resolved_expression: str | None = None,
) -> str:
    try:
        scene_description = _NATURAL_SCENES[scene.scene_id]
        expression_plan = _REFERENCE_FAITHFUL_POSE_PLANS[pose.pose_id]
    except KeyError as exc:
        raise ValueError(f"缺少外观忠实提示词配置：{exc.args[0]}") from exc

    requirements = [
        item.strip()
        for item in (resolved_appearance_requirements or [])
        if item and item.strip()
    ]
    if requirements:
        appearance = "\n".join(f"- {item}" for item in requirements)
    else:
        appearance = "\n".join(
            f"- For PERSON {slot}, match SUBJECT_PRIMARY for the current hairstyle, fringe density "
            "and forehead coverage, eyewear state, and visible accessories. If additional views differ, "
            "do not mix them into a third appearance: follow SUBJECT_PRIMARY. Do not invent or remove "
            "glasses."
            for slot in range(1, participant_count + 1)
        )

    expression = (resolved_expression or expression_plan.expression).strip()
    prompt = f"""Create a reference-faithful image of the subject or subjects in the selected zoo scene
and pose.

REFERENCE ROLES
{_faithful_reference_role_description(reference_roles)}

SUBJECT APPEARANCE
Use the designated SUBJECT photos as the only source of each person's facial appearance. Preserve
the distinctive facial proportions, eye shape, nose shape, lip shape, face contour, natural skin
texture, hairstyle, and fringe shown in those references, interpreted naturally from the requested
viewing angle.

Match each selected SUBJECT_PRIMARY reference for current hairstyle and eyewear unless the product
has an explicit trusted server-side appearance choice. Indoor backgrounds in subject photos do not
define the zoo scene. Do not average conflicting reference states or borrow appearance from another
person.
{appearance}

People shown in any future SCENE_REFERENCE or POSE_REFERENCE are not appearance references for the
subject. Use those images only for their explicitly assigned scene or pose information.

GROUP COMPOSITION
{_faithful_group_layout(participant_count)}

SELECTED SCENE AND POSE
SCENE — {scene.scene_id}: {scene.title}
{scene_description}

POSE — {pose.pose_id}: {pose.title}
{pose.description}

HEAD ORIENTATION AND ATTENTION
{expression_plan.head_and_gaze}

EXPRESSION — {expression_plan.strategy_id}
{expression}

Keep the expression restrained and natural for the selected pose. Allow normal changes in the
eyelids, cheeks, mouth, and jaw without beautifying or redesigning facial features. Do not enlarge
the eyes, raise the mouth corners, narrow the jaw, or sharpen the chin as an expression adjustment.

STYLE AND LIGHTING
{_STYLE_AND_COMPOSITION}

Keep facial detail readable and lighting coherent with the scene. Retain believable skin texture
and natural skin coloration. Environmental color spill may be present, but keep it subtle, broad,
and physically consistent; do not create an isolated green patch or concentrated colored spotlight
on the face. Do not apply heavy beauty retouching, face slimming, eye enlargement, a V-shaped jaw,
or an influencer-style filter.

OUTPUT
{_OUTPUT_REQUIREMENTS}"""
    lowered = prompt.lower()
    if any(token in lowered for token in ("{{", "}}", "undefined", "null")):
        raise ValueError("提示词包含未解析变量")
    return prompt.strip()
