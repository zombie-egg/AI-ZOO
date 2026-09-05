from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: facefusion_similarity.py SOURCE CANDIDATE FACEFUSION_ROOT", file=sys.stderr)
        return 2
    source, candidate, root = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    sys.path.insert(0, str(root))
    try:
        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis
    except ImportError as exc:
        print(f"InsightFace Python 依赖未安装：{exc}", file=sys.stderr)
        return 3

    analyser = FaceAnalysis(name="buffalo_l", root=str(root / ".assets"), providers=["CPUExecutionProvider"])
    analyser.prepare(ctx_id=-1, det_size=(640, 640))
    first = analyser.get(cv2.imread(str(source)))
    second = analyser.get(cv2.imread(str(candidate)))
    if not first or not second:
        print("0.0")
        return 0
    embedding_a = first[0].normed_embedding
    embedding_b = second[0].normed_embedding
    similarity = float(np.dot(embedding_a, embedding_b))
    print(max(0.0, min(1.0, similarity)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

