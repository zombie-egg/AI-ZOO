from __future__ import annotations

import argparse

from app.prompt_builder import (
    NATURAL_EXPRESSION_PROMPT_VERSION,
    REFERENCE_FAITHFUL_PROMPT_VERSION,
)
from app.scene_catalog import POSES, compose_generation_prompt, get_scene


def main() -> None:
    parser = argparse.ArgumentParser(description="Render production prompt examples without images or secrets")
    parser.add_argument("--scene", default="PANDA_CASUAL_01")
    parser.add_argument(
        "--version",
        choices=(NATURAL_EXPRESSION_PROMPT_VERSION, REFERENCE_FAITHFUL_PROMPT_VERSION),
        default=REFERENCE_FAITHFUL_PROMPT_VERSION,
    )
    parser.add_argument(
        "--failure-sample",
        action="store_true",
        help="Render the supplied red-panda/BACK diagnostic case without embedding any image",
    )
    args = parser.parse_args()
    scene = get_scene("RED_PANDA_VIEW_01" if args.failure_sample else args.scene)
    poses = (next(pose for pose in POSES if pose.pose_id == "BACK"),) if args.failure_sample else POSES
    for pose in poses:
        appearance = None
        expression = None
        reference_roles = None
        if args.failure_sample:
            appearance = (
                "The subject is not wearing glasses. Keep the dense fringe covering the forehead "
                "as shown in the primary subject reference, adapted naturally to the selected head angle.",
            )
            expression = (
                "Keep a relaxed neutral expression consistent with the subject reference, with a "
                "comfortable mouth and naturally attentive eyes. Do not introduce a smile for this test."
            )
            reference_roles = (
                "SUBJECT_PRIMARY — PERSON 1 — current appearance authority and primary front-face identity view; its captured smile is optional",
                "SUBJECT_ADDITIONAL — PERSON 1 — left three-quarter facial identity and depth view for the same person",
                "SUBJECT_ADDITIONAL — PERSON 1 — body, outfit, hairstyle, and accessory context; it does not set the target expression",
                "SUBJECT_ADDITIONAL — PERSON 1 — right three-quarter facial identity and depth view for the same person",
            )
        prompt = compose_generation_prompt(
            scene,
            pose,
            prompt_version=args.version,
            reference_roles=reference_roles,
            resolved_appearance_requirements=appearance,
            resolved_expression=expression,
        )
        print(f"\n{'=' * 24} {scene.scene_id} / {pose.pose_id} {'=' * 24}\n")
        print(prompt)


if __name__ == "__main__":
    main()
