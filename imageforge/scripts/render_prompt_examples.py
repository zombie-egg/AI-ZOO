from __future__ import annotations

import argparse

from app.prompt_builder import NATURAL_EXPRESSION_PROMPT_VERSION
from app.scene_catalog import POSES, compose_generation_prompt, get_scene


def main() -> None:
    parser = argparse.ArgumentParser(description="Render production prompt examples without images or secrets")
    parser.add_argument("--scene", default="PANDA_CASUAL_01")
    args = parser.parse_args()
    scene = get_scene(args.scene)
    for pose in POSES:
        prompt = compose_generation_prompt(
            scene,
            pose,
            prompt_version=NATURAL_EXPRESSION_PROMPT_VERSION,
        )
        print(f"\n{'=' * 24} {scene.scene_id} / {pose.pose_id} {'=' * 24}\n")
        print(prompt)


if __name__ == "__main__":
    main()
