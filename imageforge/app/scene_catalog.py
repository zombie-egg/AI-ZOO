from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScenePrompt:
    scene_id: str
    title: str
    description: str
    prompt_version: str
    full_prompt: str

    @property
    def prompt_hash(self) -> str:
        return hashlib.sha256(self.full_prompt.encode("utf-8")).hexdigest()

    def public_dict(self) -> dict[str, str]:
        return {
            "scene_id": self.scene_id,
            "title": self.title,
            "description": self.description,
            "prompt_version": self.prompt_version,
        }


@dataclass(frozen=True, slots=True)
class PosePrompt:
    pose_id: str
    title: str
    description: str
    icon: str
    prompt_version: str
    instruction: str

    def public_dict(self) -> dict[str, str]:
        return {
            "pose_id": self.pose_id,
            "title": self.title,
            "description": self.description,
            "icon": self.icon,
            "prompt_version": self.prompt_version,
        }


_IDENTITY_CONTRACT = """
Create ONE new photorealistic zoo visitor photograph using the supplied, explicitly grouped reference
images of ONE TO FOUR real visitors. This is direct scene generation from real identity references. It is NOT a
face swap, NOT a template composite, and there is no prebuilt scene image to preserve.

REFERENCE GROUP CONTRACT — follow each participant group and its upload order exactly. Every person
has four consecutive references and references must never cross between participant groups:
- Image 1 within EACH participant group is the BODY / OUTFIT ANCHOR. Preserve that visitor's real hairstyle, hair color,
  glasses or accessories, body proportions, and the exact visible outfit category, colors,
  neckline, sleeves, patterns, and layering.
- Image 2 within EACH group is the PRIMARY FRONT-FACE IDENTITY REFERENCE. Preserve that same real person's
  recognizable underlying facial structure, forehead, hairline, eyebrows, eye shape and spacing,
  nose geometry, lips, ears, age appearance, natural skin tone, and distinctive visible facial
  details, while applying the controlled slimming and retouching explicitly required below.
- Images 3 and 4 within EACH group are LEFT and RIGHT THREE-QUARTER IDENTITY REFERENCES. Use them to keep
  the nose bridge, cheekbones, jaw contour, ears, and facial depth consistent.
- The four images inside one group show one person. Different groups show different people. Never
  average, merge, exchange, or blend identities, faces, outfits, hairstyles, ages, or body shapes between groups. Do not copy
  the original indoor capture background into the result.

NON-NEGOTIABLE PRIORITY ORDER:
1. The visitor must unmistakably be the same real person.
2. Preserve the real hairstyle, glasses/accessories, body proportions, and exact outfit.
3. Person, animal, barriers, and environment must share believable physical space and lighting.
4. The result must look like an ordinary real camera photograph, not advertising artwork.

IDENTITY AND SMART BEAUTY RETOUCHING:
Every visitor must remain unmistakably the same real person, but apply clearly visible, strong yet
believable intelligent beauty retouching. These changes are required visible results, not optional
suggestions, and must remain natural in a high-resolution printed photograph:
- SKIN WHITENING AND TONE: visibly brighten and whiten the complexion, lift dull or uneven skin tone,
  and improve facial luminosity while retaining the visitor's real undertone and avoiding blown-out
  highlights, gray-white skin, or a mismatched face-versus-neck color.
- SKIN SMOOTHING: apply noticeable, even skin smoothing; reduce minor blemishes, roughness, redness,
  oily shine, and distracting pores, while keeping enough fine texture to remain photographic rather
  than waxy, plastic, airbrushed, or porcelain-like.
- FACE SLIMMING AND CONTOUR — HIGH PRIORITY: visibly narrow the apparent width of the outer cheeks
  and lower face by approximately 10–15%, reduce excessive cheek fullness, create a cleaner and more
  defined jawline, and visibly reduce a double chin when present. Compensate for wide-angle camera
  distortion so the generated face must not look wider or heavier than the reference face. Keep the
  result symmetrical and believable while preserving the person's recognizable cheekbones, chin,
  nose, facial proportions, and identity. Never create an extreme V-shaped jaw, tiny chin, hollow
  cheeks, pinched head, oversized eyes, or a different person.
- EYE-AREA RETOUCHING: noticeably reduce dark circles, mild under-eye bags, and tired shadows while
  preserving the natural lower-eyelid structure. Make the eyes look slightly clearer and more awake,
  but do not enlarge the eyes or change their shape or spacing.
- FINISH: gently soften harsh facial shadows, balance facial exposure, and keep the lips natural
  without heavy makeup or artificial recoloring.

FACIAL EXPRESSION: Preserve each visitor's own natural, relaxed, neutral, candid expression. Do not
ask for or add a smile. Keep the lips comfortably and naturally closed with no visible teeth, but do
not press or tighten the mouth. Do not force, standardize, exaggerate, or copy expressions across people.
Do not use face averaging or change age, ethnicity, gender, hairstyle, or distinctive facial details.
Preserve normal facial asymmetry, the exact outfit from reference image 1, and glasses if present.
Glasses must have physically plausible reflections that do not hide both eyes.
""".strip()


_REALISM_CONTRACT = """
PHYSICAL COHERENCE:
Keep a plausible and safe zoo distance. Respect safety glass, railings, habitat edges, and
staff-controlled interaction rules. Use natural partial occlusion, contact shadows, and believable
ground planes. No floating person, pasted-on head, cut-out edge, fused body, impossible touching,
or mismatched head-to-neck proportions. The animal must have species-accurate anatomy, scale, fur
or skin, paws or feet, eyes, and posture.

LIGHTING AND COLOR:
Use one coherent real-world lighting setup. The visitor, animal, and environment receive light from
the same direction with matching shadow direction, softness, exposure, white balance, and highlight
roll-off. The visitor's skin, hair, glasses, and clothing visibly receive subtle reflected color from
the environment, including restrained green bounce from foliage or exhibit glass when present,
while preserving the visitor's natural underlying skin tone. Never render a separately lit face.

CAMERA REALISM:
Make it look like a casual friend-held smartphone photo taken during a real zoo visit: eye-level
camera, approximately 26 mm full-frame-equivalent lens, plausible perspective, slightly imperfect
off-center framing, realistic dynamic range, mild high-ISO grain, tiny natural motion softness,
restrained lens imperfection, and believable depth of field. It must not look like a fashion shoot,
movie still, commercial poster, studio composite, HDR render, or polished tourism advertisement.

ANATOMY AND OUTPUT CONSTRAINTS:
Exactly the requested number of human visitors, each appearing once. No additional face, reflected
face, face-like pattern, missing visitor, duplicate person,
extra limb, fused arm, or detached hand. If fingers are visible, each visible hand has five naturally
arranged fingers; otherwise use a plausible pose or occlusion that hides them. No malformed animal,
readable text, caption, logo, border, watermark, collage, or split screen.

Before producing the image, silently verify: same identity; same outfit; coherent head-to-neck
proportion; environmental light visibly affecting skin; one shadow direction; safe believable
human-animal spacing; correct hands and animal anatomy; ordinary smartphone-photo realism.

Return one portrait-oriented 2:3 photorealistic image only.
""".strip()


def _fixed_prompt(scene: str) -> str:
    # ScenePrompt objects are compiled once at import time. Runtime requests select a complete,
    # immutable prompt by scene_id; no customer text or dynamic scene fragments are interpolated.
    return f"{_IDENTITY_CONTRACT}\n\nFIXED TARGET SCENE:\n{scene.strip()}\n\n{_REALISM_CONTRACT}"


POSES: tuple[PosePrompt, ...] = (
    PosePrompt(
        "FRONT",
        "自然正面",
        "身体与脸正对镜头，肩颈舒展，适合完整展示五官。",
        "正",
        "front-pose-v1",
        """FRONT-FACING POSE — this overrides any conflicting body-orientation wording in the scene:
Place the visitor's torso and face toward the camera, with shoulders nearly parallel to the image
plane and both eyes clearly visible. Use a relaxed upright half-body stance, balanced weight, level
shoulders, a naturally elongated neck, and relaxed arms or one hand resting naturally near a safe
barrier. Do not twist the waist, neck, wrists, or limbs. Keep the animal beside or behind the visitor
at the scene's safe believable depth rather than forcing the visitor into a side pose.""",
    ),
    PosePrompt(
        "SIDE",
        "自然侧身",
        "身体侧转约 45°，脸自然看向镜头，避免拧腰和僵硬摆拍。",
        "侧",
        "side-pose-v1",
        """THREE-QUARTER SIDE POSE — this overrides any conflicting body-orientation wording in the scene:
Rotate the visitor's torso, hips, and feet together approximately 45–60 degrees to the camera while
the face turns back gently toward the lens. Keep both eyes, or one full eye and most of the far eye,
visible so identity and beauty retouching remain clear. Use a relaxed shoulder line, naturally long
neck, coherent spine, and comfortable arm placement. Never create a full profile, twisted waist,
over-rotated neck, crossed anatomy, or fashion-model exaggeration.""",
    ),
    PosePrompt(
        "BACK",
        "背影回眸",
        "身体面向动物与场景，轻微回眸，背影自然且仍能看清本人。",
        "背",
        "back-look-pose-v1",
        """BACK-FACING LOOK-BACK POSE — this overrides any conflicting body-orientation wording in the scene:
Place the visitor with the back and shoulder line facing the camera while the body looks naturally
toward the animal or habitat. Turn the head back only 20–35 degrees over one shoulder so a clear,
recognizable three-quarter portion of the face remains visible and receives the full required skin
beauty and face-slimming treatment. Keep shoulders relaxed, spine and hips aligned, hair and outfit
back details plausible, and arms comfortably placed. Never rotate the head impossibly, detach the
neck, show a front-facing torso, or hide the face completely.""",
    ),
)


SCENES: tuple[ScenePrompt, ...] = (
    ScenePrompt(
        "PANDA_CASUAL_01",
        "和大熊猫在熊猫馆自然同框",
        "朋友随手拍视角，隔着安全区域自然同框，不摆宣传照。",
        "panda-casual-beauty-v4",
        _fixed_prompt("""
One adult giant panda with species-accurate black-and-white fur is calmly eating bamboo or briefly
looking toward the camera inside a real modern Chinese zoo panda habitat. The visitor stands
naturally beside a slightly used dark viewing railing, body turned a little toward the panda and
face toward the camera; one hand may rest on the railing. The panda remains a short believable
distance inside its protected habitat. There is no direct touching and no staged bench pose.
Use a casual waist-up, friend-held smartphone composition with the visitor slightly off center and
the panda clearly visible without perfect symmetry. Use soft overcast daylight mixed with subtle
green bounce from bamboo and exhibit glass, neutral skin exposure, and one soft light direction.
Background: bamboo, habitat rocks, slightly reflective safety glass, worn visitor surfaces, and a
softly blurred educational sign with no readable text. No golden-hour glow and no tourist poster.
"""),
    ),
    ScenePrompt(
        "RED_PANDA_VIEW_01",
        "和小熊猫在林间展区同框",
        "小熊猫在栖架上活动，游客在观景栏旁自然入镜。",
        "red-panda-view-beauty-v4",
        _fixed_prompt("""
A real red panda with accurate reddish coat, dark limbs, ringed tail, and natural proportions moves
on a wooden climbing structure inside a leafy zoo habitat. The visitor stands at the public viewing
rail, half turned toward the animal and smiling naturally toward the camera. The red panda remains
in its protected habitat; no hugging, shoulder pose, or unsafe touching. Compose an imperfect
friend-held waist-up smartphone snapshot. Use ordinary soft daylight filtered through leaves, with
subtle green bounce on skin and clothing and matching contact shadows. Include natural branches,
worn timber, mesh or glass protection, and blurred signage without readable words. Avoid a fantasy
forest, staged animal show, advertising polish, or oversized animal.
"""),
    ),
    ScenePrompt(
        "ELEPHANT_WALK_01",
        "和大象在园区步道远近同框",
        "游客在观景步道，大象在围护后的活动区自然经过。",
        "elephant-walk-beauty-v4",
        _fixed_prompt("""
One anatomically accurate Asian elephant walks calmly inside a spacious zoo habitat behind a low,
clearly visible safety boundary. The visitor is on the public path in the foreground, casually
glancing toward the elephant while a friend takes the photo. Keep a believable large scale and
distance; the visitor never touches or walks inside the elephant enclosure. Use a slightly wide,
eye-level smartphone frame with imperfect timing, realistic perspective, and a little background
motion softness. Lighting is ordinary late-morning daylight, not cinematic sunset. Match the same
light direction on face, clothing, elephant, dust, and ground. Include habitat trees, earth, rocks,
a worn railing, and an unreadable blurred information board. No safari fantasy or promotional pose.
"""),
    ),
    ScenePrompt(
        "GIRAFFE_WINDOW_01",
        "长颈鹿从观景窗旁自然探头",
        "近距离但有安全隔离，保留真实透视和长颈鹿比例。",
        "giraffe-window-beauty-v4",
        _fixed_prompt("""
One real giraffe with correct coat pattern, ossicones, long neck, muzzle, and scale leans curiously
toward a zoo viewing window or protected feeding overlook. The visitor stands safely on the public
side, slightly surprised and naturally smiling toward the camera, with no direct feeding or unsafe
contact. Use a casual waist-up smartphone photo where the giraffe enters from one side of frame and
the visitor is not perfectly centered. Preserve wide-angle perspective without distorting the
visitor's face. Use soft open shade with warm-neutral daylight and mild green reflected light from
nearby foliage; reflections on glass, glasses, skin, and the giraffe follow one light direction.
Background includes habitat trees, rail hardware, and softly blurred visitors' infrastructure, but
no extra people or readable text. Avoid whimsical proportions and magazine-cover staging.
"""),
    ),
    ScenePrompt(
        "FLAMINGO_LAGOON_01",
        "在火烈鸟湖畔随手拍",
        "游客靠近公共步道，火烈鸟在水岸自然活动。",
        "flamingo-lagoon-beauty-v4",
        _fixed_prompt("""
Several anatomically correct flamingos stand and forage naturally in a shallow zoo lagoon behind a
subtle habitat boundary. The visitor stands on the public lakeside path, relaxed and looking toward
the camera, with a spontaneous half-body pose rather than imitating the birds. Use an ordinary
friend-held smartphone composition with slightly imperfect horizon and realistic depth. Lighting is
soft daytime cloud cover with gentle sky reflection from the water; skin, clothing, feathers, water,
and ground share the same white balance and shadow direction. Include reeds, worn path edging,
slightly rippled water, and blurred zoo signage without readable text. Do not turn the scene into a
pink fantasy, fashion editorial, wedding portrait, or perfectly symmetrical poster.
"""),
    ),
    ScenePrompt(
        "DOLPHIN_WINDOW_01",
        "隔着水下观景窗和海豚同框",
        "真实水族馆混合光，海豚在玻璃后游过。",
        "dolphin-window-beauty-v4",
        _fixed_prompt("""
One anatomically accurate dolphin swims naturally behind a large underwater viewing window in a real
zoo aquarium. The visitor stands on the dry public side of the glass and turns naturally toward the
camera as the dolphin passes behind at a believable distance. No touching, riding, trainer stunt, or
human underwater. Use a casual waist-up smartphone snapshot with mild blue-green aquarium ambient
light visibly reflected on the visitor's skin, hair, glasses, and clothing while preserving natural
skin tone. Mixed practical indoor light and tank light must share plausible exposure, reflections,
and shadow direction. Include subtle glass smudges, water caustics, structural window edges, and an
unreadable blurred information panel. Avoid neon fantasy, underwater compositing, or commercial art.
"""),
    ),
    ScenePrompt(
        "LEMUR_HABITAT_01",
        "和狐猴在玻璃展馆自然同框",
        "狐猴留在栖息空间里，不生成危险的肩头摆拍。",
        "lemur-habitat-beauty-v4",
        _fixed_prompt("""
One ring-tailed lemur with accurate facial markings, hands, feet, and striped tail sits or climbs on
a natural branch inside a glass-fronted zoo habitat. The visitor stands on the public side and looks
toward the camera while the lemur appears nearby in depth, creating a lucky candid moment. Keep the
glass and safe separation physically clear; no lemur on the visitor's shoulder and no direct contact.
Use a slightly off-center, waist-up smartphone composition with mild reflection and realistic depth
of field. Lighting is ordinary indoor daylight mixed with soft green habitat bounce, consistently
affecting both subject planes. Include branches, leaves, enclosure hardware, and a blurred sign with
no readable text. Avoid tropical fantasy, mascot expressions, or staged animal-show photography.
"""),
    ),
    ScenePrompt(
        "WHITE_TIGER_GLASS_01",
        "隔着安全玻璃与白虎同框",
        "突出真实安全距离、玻璃反射和白虎体型。",
        "white-tiger-glass-beauty-v4",
        _fixed_prompt("""
One anatomically accurate adult white tiger walks or rests inside a real zoo habitat behind thick
safety glass. The visitor stands on the public viewing side, naturally looking toward the camera,
while the tiger occupies a separate depth plane. The barrier and distance must be unmistakable; no
touching, leash, petting, or shared unrestricted space. Use an eye-level friend-held smartphone
frame with the visitor slightly off center and the tiger visible without mirroring the pose. Soft
daylight and exhibit shade create one coherent light direction; restrained green-gray habitat bounce
appears on skin and clothing, and glass reflections remain physically plausible. Include rocks,
vegetation, glass seams, and blurred signage without readable text. No action-movie drama or poster.
"""),
    ),
    ScenePrompt(
        "CAPYBARA_LAWN_01",
        "和水豚在草地近距离合照",
        "工作人员管理的互动区里，自然蹲姿、真实接触关系。",
        "capybara-lawn-beauty-v4",
        _fixed_prompt("""
One calm, anatomically accurate capybara stands or sits in a staff-managed zoo encounter lawn. The
visitor crouches or stands beside a low boundary at a believable distance, smiling naturally toward
the camera. If proximity is shown, keep it consistent with a supervised encounter and use a railing
or clear spatial cue; no hugging, lifting, costume, or human-like animal pose. Use a casual
friend-held smartphone snapshot with imperfect framing, believable ground contact, slight depth of
field, and natural occlusion around the visitor's hand and the low rail. Soft afternoon cloud light
and grass bounce affect skin, clothing, fur, and shadows consistently. Include ordinary lawn wear,
low fencing, scattered vegetation, and blurred signage without readable text. Avoid spa memes,
fantasy props, or promotional staging.
"""),
    ),
)


_SCENE_BY_ID = {scene.scene_id: scene for scene in SCENES}
_POSE_BY_ID = {pose.pose_id: pose for pose in POSES}


def get_scene(scene_id: str) -> ScenePrompt:
    try:
        return _SCENE_BY_ID[scene_id]
    except KeyError as exc:
        raise ValueError(f"未知或未启用的文字场景：{scene_id}") from exc


def public_scenes() -> list[dict[str, str]]:
    return [scene.public_dict() for scene in SCENES]


def get_pose(pose_id: str) -> PosePrompt:
    try:
        return _POSE_BY_ID[pose_id]
    except KeyError as exc:
        raise ValueError(f"未知或未启用的拍照姿势：{pose_id}") from exc


def public_poses() -> list[dict[str, str]]:
    return [pose.public_dict() for pose in POSES]


def _group_instruction(participant_count: int) -> str:
    if participant_count < 1 or participant_count > 4:
        raise ValueError("参与者数量必须为 1 至 4 人")
    layout = {
        1: "one visitor in a relaxed off-center composition",
        2: "two visitors side by side with a slight natural depth offset and no overlapping faces",
        3: "three visitors in a shallow triangular arrangement with all faces clearly readable",
        4: "four visitors in a balanced two-front/two-back or gentle arc arrangement with no hidden face",
    }[participant_count]
    groups = "\n".join(
        f"- PERSON {slot}: use ONLY reference group {slot} (its body anchor, front face, left three-quarter, right three-quarter); render this person exactly once."
        for slot in range(1, participant_count + 1)
    )
    return f"""MULTI-PERSON IDENTITY LOCK — HIGHEST PRIORITY:
The final image must contain exactly {participant_count} human visitor{'s' if participant_count != 1 else ''}: {layout}.
{groups}
Keep every person's face, hairstyle, glasses, outfit, body shape, age, and skin undertone distinct.
Never swap identities, blend two people into one face, duplicate a person, omit a person, or transfer
clothing between people. Apply the complete whitening, smoothing, under-eye retouching, and visible
10–15% face-slimming treatment independently to every visible face without making the faces alike.
Arrange shoulders, arms, hands, and depth naturally so bodies do not fuse or intersect."""


def compose_generation_prompt(scene: ScenePrompt, pose: PosePrompt, participant_count: int = 1) -> str:
    return f"{scene.full_prompt}\n\n{_group_instruction(participant_count)}\n\nSELECTED VISITOR POSE:\n{pose.instruction}"


def composed_prompt_version(scene: ScenePrompt, pose: PosePrompt, participant_count: int = 1) -> str:
    return f"{scene.prompt_version}+{pose.prompt_version}+group-{participant_count}-v1+natural-expression-v2"


def composed_prompt_hash(scene: ScenePrompt, pose: PosePrompt, participant_count: int = 1) -> str:
    prompt = compose_generation_prompt(scene, pose, participant_count)
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
