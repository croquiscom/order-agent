"""Screenshot baseline comparison — 스크린샷 베이스라인 비교 유틸리티.

베이스라인 이미지와 현재 스크린샷을 픽셀 단위로 비교합니다.
외부 라이브러리 없이 PNG 바이트 비교로 동작하며,
Pillow가 설치된 경우 시각적 diff 이미지를 생성합니다.

Usage:
    python3 -m core.screenshot_compare <baseline.png> <actual.png> [--threshold 0.01]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CompareResult:
    """스크린샷 비교 결과."""
    match: bool
    diff_ratio: float  # 0.0 = identical, 1.0 = completely different
    message: str
    diff_path: str | None = None  # diff 이미지 경로 (Pillow 사용 시)


BASELINES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "screenshots"


def compare_screenshots(
    baseline_path: Path,
    actual_path: Path,
    threshold: float = 0.01,
    diff_output: Path | None = None,
) -> CompareResult:
    """Compare two PNG screenshots.

    Args:
        baseline_path: 기준 이미지 경로
        actual_path: 실제 캡처 이미지 경로
        threshold: 허용 diff 비율 (0.01 = 1%)
        diff_output: diff 이미지 저장 경로 (선택)

    Returns:
        CompareResult with match status and diff ratio
    """
    if not baseline_path.exists():
        return CompareResult(
            match=False,
            diff_ratio=1.0,
            message=f"Baseline not found: {baseline_path}. "
                    f"Run with --save-baseline to create it.",
        )

    if not actual_path.exists():
        return CompareResult(
            match=False,
            diff_ratio=1.0,
            message=f"Actual screenshot not found: {actual_path}",
        )

    baseline_bytes = baseline_path.read_bytes()
    actual_bytes = actual_path.read_bytes()

    # Fast path: byte-identical
    if baseline_bytes == actual_bytes:
        return CompareResult(match=True, diff_ratio=0.0, message="IDENTICAL")

    # Try pixel comparison with Pillow
    try:
        from PIL import Image
        import io

        img_base = Image.open(io.BytesIO(baseline_bytes)).convert("RGBA")
        img_actual = Image.open(io.BytesIO(actual_bytes)).convert("RGBA")

        # Resize to same dimensions if needed
        if img_base.size != img_actual.size:
            return CompareResult(
                match=False,
                diff_ratio=1.0,
                message=f"Size mismatch: baseline={img_base.size}, actual={img_actual.size}",
            )

        # Pixel-by-pixel comparison
        pixels_base = img_base.load()
        pixels_actual = img_actual.load()
        w, h = img_base.size
        total_pixels = w * h
        diff_pixels = 0
        diff_tolerance = 10  # per-channel tolerance

        diff_img = None
        if diff_output:
            diff_img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
            diff_pixels_data = diff_img.load()

        for y in range(h):
            for x in range(w):
                pb = pixels_base[x, y]
                pa = pixels_actual[x, y]
                pixel_diff = any(
                    abs(pb[c] - pa[c]) > diff_tolerance for c in range(3)
                )
                if pixel_diff:
                    diff_pixels += 1
                    if diff_img:
                        diff_pixels_data[x, y] = (255, 0, 0, 255)
                else:
                    if diff_img:
                        diff_pixels_data[x, y] = (
                            pa[0] // 3, pa[1] // 3, pa[2] // 3, 255
                        )

        diff_ratio = diff_pixels / total_pixels if total_pixels > 0 else 0.0

        diff_path_str = None
        if diff_img and diff_output:
            diff_output.parent.mkdir(parents=True, exist_ok=True)
            diff_img.save(str(diff_output))
            diff_path_str = str(diff_output)

        matched = diff_ratio <= threshold
        pct = f"{diff_ratio * 100:.2f}%"
        msg = (
            f"PASS ({pct} diff)" if matched
            else f"FAIL ({pct} diff, threshold={threshold * 100:.1f}%)"
        )

        return CompareResult(
            match=matched,
            diff_ratio=round(diff_ratio, 6),
            message=msg,
            diff_path=diff_path_str,
        )

    except ImportError:
        # No Pillow — fallback to byte-level comparison
        min_len = min(len(baseline_bytes), len(actual_bytes))
        max_len = max(len(baseline_bytes), len(actual_bytes))
        diff_bytes = sum(
            1 for i in range(min_len)
            if baseline_bytes[i] != actual_bytes[i]
        )
        diff_bytes += max_len - min_len
        diff_ratio = diff_bytes / max_len if max_len > 0 else 0.0

        matched = diff_ratio <= threshold
        msg = (
            f"PASS (byte diff={diff_ratio:.4f}, no Pillow)"
            if matched
            else f"FAIL (byte diff={diff_ratio:.4f}, threshold={threshold})"
        )
        return CompareResult(
            match=matched, diff_ratio=round(diff_ratio, 6), message=msg
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Compare screenshot against baseline")
    parser.add_argument("baseline", help="Baseline PNG path")
    parser.add_argument("actual", help="Actual PNG path")
    parser.add_argument("--threshold", type=float, default=0.01, help="Max diff ratio (default: 0.01 = 1%%)")
    parser.add_argument("--diff-output", help="Save diff image to this path")
    args = parser.parse_args()

    result = compare_screenshots(
        Path(args.baseline),
        Path(args.actual),
        threshold=args.threshold,
        diff_output=Path(args.diff_output) if args.diff_output else None,
    )

    print(f"Result: {result.message}")
    print(f"Diff ratio: {result.diff_ratio}")
    if result.diff_path:
        print(f"Diff image: {result.diff_path}")

    sys.exit(0 if result.match else 1)


if __name__ == "__main__":
    main()
