from __future__ import annotations

import logging
import os

import cv2
import numpy as np

from stratagem_catalog import StratagemCatalog

logger = logging.getLogger("HelldiversParser.StratagemParser")

CONFUSION_GROUPS = (("expendable_napalm", "expendable_anti_tank"),)


class StratagemParser(StratagemCatalog):
    """Recognize stratagem icons with OpenCV template matching.

    Reference icons are loaded from the library, linked to input sequences through
    stratagems.json, and compared with captured loadout slots.
    """

    def __init__(
        self,
        library_dir: str = "stratagem_library",
        threshold: float = 0.65,
        mapping_file: str | None = None,
    ) -> None:
        self.library_dir = library_dir
        self.threshold = threshold
        library_mapping = os.path.join(library_dir, "stratagems.json")
        self.mapping_file = mapping_file or (
            library_mapping if os.path.exists(library_mapping) else "stratagems.json"
        )
        self.templates: dict[str, np.ndarray] = {}
        self.color_shape_masks: dict[str, np.ndarray] = {}
        super().__init__(self.mapping_file)
        self.load_templates()

    def load_templates(self) -> None:
        """Load and binarize raster templates once."""
        self.templates.clear()
        self.color_shape_masks.clear()

        if not os.path.exists(self.library_dir):
            logger.warning(
                "Template library '%s' does not exist. Creating an empty directory.",
                self.library_dir,
            )
            try:
                os.makedirs(self.library_dir, exist_ok=True)
                logger.info("Created empty template directory: %s", self.library_dir)
            except OSError as exc:
                logger.error("Failed to create template directory %s: %s", self.library_dir, exc)
            return

        supported_extensions = (".png", ".jpg", ".jpeg", ".bmp")
        skipped_without_code = 0
        for entry in os.scandir(self.library_dir):
            if entry.is_file() and entry.name.lower().endswith(supported_extensions):
                try:
                    key = os.path.splitext(entry.name)[0]
                    if not self.get_code(key):
                        skipped_without_code += 1
                        continue
                    template_source = cv2.imread(entry.path, cv2.IMREAD_UNCHANGED)
                    if template_source is None:
                        logger.error("Failed to load template: %s", entry.path)
                        continue

                    if template_source.ndim == 3:
                        template_img = cv2.cvtColor(
                            template_source[:, :, :3],
                            cv2.COLOR_BGR2GRAY,
                        )
                    else:
                        template_img = template_source

                    _, binary_template = cv2.threshold(
                        template_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                    )
                    self.templates[key] = binary_template
                    if key in {name for group in CONFUSION_GROUPS for name in group}:
                        self.color_shape_masks[key] = self._color_shape_mask(template_source)

                    if key not in self.display_names:
                        self.display_names[key] = key.replace("_", " ").title()

                except (OSError, cv2.error) as exc:
                    logger.error("Failed to load template %s: %s", entry.name, exc)

        logger.info(
            "Loaded %d stratagem templates from '%s'; skipped without code: %d.",
            len(self.templates),
            self.library_dir,
            skipped_without_code,
        )

    def find_best_match(self, zone_img: np.ndarray) -> tuple[str | None, float]:
        """Return the best match only when it reaches the configured threshold."""
        best_match_name, best_score = self.score_best_match(zone_img)
        if best_match_name is not None and best_score >= self.threshold:
            return best_match_name, best_score
        logger.debug(
            "Best candidate '%s': %.4f, threshold: %.4f",
            best_match_name,
            best_score,
            self.threshold,
        )
        return None, best_score

    def score_best_match(self, zone_img: np.ndarray) -> tuple[str | None, float]:
        """Return the best candidate even when its score is below the threshold."""
        candidates = self.score_candidates(zone_img, limit=1)
        return candidates[0] if candidates else (None, 0.0)

    def score_candidates(
        self,
        zone_img: np.ndarray,
        limit: int = 5,
    ) -> list[tuple[str, float]]:
        """Return ranked candidates while evaluating the image only once."""
        if not self.templates:
            # Retry loading when the library was empty during startup.
            self.load_templates()
            if not self.templates:
                return []

        if zone_img is None:
            return []

        try:
            # Binary silhouettes are stable for both white and yellow game icons.
            zone_gray = cv2.cvtColor(zone_img, cv2.COLOR_BGR2GRAY)
            _, zone_gray = cv2.threshold(zone_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            zone_h, zone_w = zone_gray.shape

            best_match_name = None
            best_score = -1.0
            candidate_scores: dict[str, float] = {}

            for name, binary_template in self.templates.items():
                template_h, template_w = binary_template.shape
                max_side = min(zone_h, zone_w)

                # Search several sizes because UI scale changes with resolution/FOV.
                for scale in (0.55, 0.65, 0.75, 0.85, 0.95):
                    target_h = max(4, int(max_side * scale))
                    target_w = max(4, int(target_h * template_w / template_h))
                    if target_h > zone_h or target_w > zone_w:
                        continue
                    resized_template = cv2.resize(
                        binary_template,
                        (target_w, target_h),
                        interpolation=cv2.INTER_AREA,
                    )
                    result = cv2.matchTemplate(zone_gray, resized_template, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(result)
                    candidate_scores[name] = max(candidate_scores.get(name, -1.0), max_val)
                    if max_val > best_score:
                        best_score = max_val
                        best_match_name = name

            resolved_name = self._resolve_confusion_group(
                zone_img,
                best_match_name,
                candidate_scores,
            )
            ranked = sorted(
                candidate_scores.items(),
                key=lambda candidate: candidate[1],
                reverse=True,
            )
            if resolved_name and ranked and ranked[0][0] != resolved_name:
                ranked = [
                    (resolved_name, candidate_scores[resolved_name]),
                    *(candidate for candidate in ranked if candidate[0] != resolved_name),
                ]
            return ranked[: max(1, limit)]

        except cv2.error as exc:
            logger.error("Template matching failed: %s", exc, exc_info=True)
            return []

    @staticmethod
    def _color_shape_mask(image: np.ndarray) -> np.ndarray:
        """Return separate white and cyan silhouette channels."""
        if image.ndim == 2:
            bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            alpha = None
        else:
            bgr = image[:, :, :3]
            alpha = image[:, :, 3] if image.shape[2] >= 4 else None

        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        white = (hsv[:, :, 1] < 75) & (hsv[:, :, 2] > 140)
        cyan = (
            (hsv[:, :, 0] >= 75) & (hsv[:, :, 0] <= 110) & (hsv[:, :, 1] > 60) & (hsv[:, :, 2] > 70)
        )
        if alpha is not None:
            visible = alpha > 20
            white &= visible
            cyan &= visible
        return np.dstack((white, cyan)).astype(np.uint8)

    def _resolve_confusion_group(
        self,
        zone_img: np.ndarray,
        best_name: str | None,
        candidate_scores: dict[str, float],
    ) -> str | None:
        """Use full-icon color geometry to separate nearly identical launchers."""
        if best_name is None:
            return None

        for group in CONFUSION_GROUPS:
            if best_name not in group or not all(name in self.color_shape_masks for name in group):
                continue

            zone_mask = self._color_shape_mask(zone_img)
            shape_scores = {
                name: self._normalized_shape_similarity(
                    zone_mask,
                    self.color_shape_masks[name],
                )
                for name in group
            }
            shape_best = max(shape_scores, key=shape_scores.get)
            shape_margin = shape_scores[shape_best] - shape_scores[best_name]
            if shape_best != best_name and shape_margin >= 0.06:
                logger.debug(
                    "Resolved similar icons: %s -> %s; template=%s; shape=%s",
                    best_name,
                    shape_best,
                    {name: round(candidate_scores.get(name, 0.0), 4) for name in group},
                    {name: round(score, 4) for name, score in shape_scores.items()},
                )
                return shape_best
            return best_name
        return best_name

    @staticmethod
    def _normalized_shape_similarity(
        zone_mask: np.ndarray,
        template_mask: np.ndarray,
    ) -> float:
        """Compare complete color silhouettes while tolerating small UI offsets."""
        height, width = template_mask.shape[:2]
        normalized_zone = cv2.resize(
            zone_mask,
            (width, height),
            interpolation=cv2.INTER_NEAREST,
        )
        denominator = float(normalized_zone.sum() + template_mask.sum())
        if denominator <= 0:
            return 0.0

        best_score = 0.0
        max_shift = max(4, int(min(height, width) * 0.1))
        shift_step = max(1, max_shift // 6)
        for shift_y in range(-max_shift, max_shift + 1, shift_step):
            for shift_x in range(-max_shift, max_shift + 1, shift_step):
                shifted = np.zeros_like(template_mask)
                dest_x1 = max(0, shift_x)
                dest_y1 = max(0, shift_y)
                dest_x2 = min(width, width + shift_x)
                dest_y2 = min(height, height + shift_y)
                source_x1 = max(0, -shift_x)
                source_y1 = max(0, -shift_y)
                source_x2 = source_x1 + (dest_x2 - dest_x1)
                source_y2 = source_y1 + (dest_y2 - dest_y1)
                shifted[dest_y1:dest_y2, dest_x1:dest_x2] = template_mask[
                    source_y1:source_y2,
                    source_x1:source_x2,
                ]
                intersection = float(np.logical_and(normalized_zone, shifted).sum())
                score = 2.0 * intersection / denominator
                best_score = max(best_score, score)
        return best_score
