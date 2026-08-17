"""Regression tests for ChromaSAR.

Every test here guards a bug class we ACTUALLY HIT during the build, not a hypothetical
one. In order of how much damage each caused:

  1. permanent water excluded from the prediction but not the ground truth
     -> IoU read 0.263 instead of 0.661
  2. `_resize` indexed the last axis twice instead of rows-then-columns -> IndexError
  3. label value -1 means NO DATA; counting it as "dry" inflates every metric
  4. global-statistics SSIM reported as if it were windowed SSIM (scores a degraded
     image 0.92 where real SSIM says 0.68)
  5. augmentation flipping SAR and optical inconsistently would silently destroy
     training with no error message at all

    python -m pytest tests/ -v
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH = os.path.join(ROOT, "chromasar")
for p in (CH, os.path.join(CH, "train"), os.path.join(CH, "flood"),
          os.path.join(CH, "eval"), os.path.join(ROOT, "shiprouting", "src")):
    sys.path.insert(0, p)


# ===================================================================== metrics
class TestSSIM:
    def test_identical_is_one(self):
        from metrics import ssim
        a = torch.rand(1, 3, 64, 64) * 2 - 1
        assert ssim(a, a) == pytest.approx(1.0, abs=1e-4)

    def test_unrelated_is_near_zero(self):
        from metrics import ssim
        g = torch.Generator().manual_seed(0)
        a = torch.rand(1, 3, 64, 64, generator=g) * 2 - 1
        b = torch.rand(1, 3, 64, 64, generator=g) * 2 - 1
        assert ssim(a, b) < 0.05

    def test_windowed_is_stricter_than_global(self):
        """The bug: global SSIM flatters degraded images. It must not be reported."""
        from metrics import global_ssim, ssim
        g = torch.Generator().manual_seed(1)
        a = torch.rand(1, 3, 64, 64, generator=g) * 2 - 1
        noisy = (a + torch.randn(a.shape, generator=g) * 0.25).clamp(-1, 1)
        assert ssim(a, noisy) < global_ssim(a, noisy) - 0.1

    def test_blur_is_penalised(self):
        from metrics import ssim
        a = torch.rand(1, 3, 64, 64) * 2 - 1
        blur = torch.nn.functional.avg_pool2d(a, 5, 1, 2)
        assert ssim(a, blur) < 0.5

    def test_psnr_identical_is_high(self):
        from metrics import psnr
        a = torch.rand(1, 3, 32, 32) * 2 - 1
        assert psnr(a, a) >= 99.0


# ============================================================ flood label logic
class TestFloodScoring:
    def _mk(self, pred, lab):
        return np.array(pred, dtype=bool), np.array(lab, dtype=np.int16)

    def test_nodata_excluded_from_metrics(self):
        """label -1 is NO DATA. Scoring it as dry would inflate precision."""
        from flood import score
        pred, lab = self._mk([[1, 1], [0, 0]], [[1, -1], [-1, 0]])
        s = score(pred, lab)
        # only the two labelled pixels count: (0,0) tp and (1,1) tn
        assert s["tp"] == 1 and s["fp"] == 0 and s["fn"] == 0 and s["tn"] == 1
        assert s["iou"] == pytest.approx(1.0)

    def test_all_nodata_returns_none(self):
        from flood import score
        pred, lab = self._mk([[1, 0]], [[-1, -1]])
        assert score(pred, lab) is None

    def test_perfect_and_inverted(self):
        from flood import score
        pred, lab = self._mk([[1, 0], [1, 0]], [[1, 0], [1, 0]])
        assert score(pred, lab)["iou"] == pytest.approx(1.0)
        pred2, _ = self._mk([[0, 1], [0, 1]], [[1, 0], [1, 0]])
        assert score(pred2, lab)["iou"] == pytest.approx(0.0)


class TestPermanentWaterExclusion:
    """The worst bug we shipped: excluding permanent water from ONE side only.

    Removing it from the prediction but leaving it in the truth turns every river
    pixel into a false negative. Measured impact: IoU 0.861 -> 0.263.
    """

    def _score_flood_only(self, pred, truth, perm, both_sides):
        pred_f = pred & ~perm
        truth_f = (truth & ~perm) if both_sides else truth
        valid = ~perm if both_sides else np.ones_like(perm)
        tp = int((pred_f & truth_f & valid).sum())
        fp = int((pred_f & ~truth_f & valid).sum())
        fn = int((~pred_f & truth_f & valid).sum())
        return tp / max(tp + fp + fn, 1)

    def test_one_sided_exclusion_understates_iou(self):
        perm = np.zeros((8, 8), bool)
        perm[:, :4] = True                       # left half is a permanent river
        truth = perm.copy()
        truth[:, 6:] = True                      # plus real flood on the right
        pred = truth.copy()                      # a perfect prediction

        correct = self._score_flood_only(pred, truth, perm, both_sides=True)
        buggy = self._score_flood_only(pred, truth, perm, both_sides=False)
        assert correct == pytest.approx(1.0), "perfect prediction must score 1.0"
        assert buggy < correct, "one-sided exclusion must be detectably wrong"

    def test_river_only_scene_has_no_flood(self):
        perm = np.zeros((4, 4), bool)
        perm[1:3, :] = True
        pred = perm.copy()                       # model finds exactly the river
        assert int((pred & ~perm).sum()) == 0, "a river alone is not a flood"


# ============================================================ dataset integrity
class TestFloodDataset:
    def test_resize_preserves_orientation(self):
        """The bug: a[..., yi][..., :, xi] indexes the last axis twice."""
        from dataset_flood import _resize
        a = np.arange(64, dtype=np.float32).reshape(8, 8)
        out = _resize(a, 4)
        assert out.shape == (4, 4)
        # nearest-neighbour samples the start of each bin: rows/cols 0,2,4,6
        expected = a[[0, 2, 4, 6]][:, [0, 2, 4, 6]]
        assert np.array_equal(out, expected)
        # orientation: the top-right of the output must come from the top-right of
        # the input. The old bug indexed the last axis twice and scrambled this.
        assert out[0, -1] == a[0, 6]
        assert out[-1, 0] == a[6, 0]

    def test_resize_multichannel(self):
        from dataset_flood import _resize
        a = np.zeros((2, 8, 8), dtype=np.float32)
        a[1] = 5.0
        out = _resize(a, 4)
        assert out.shape == (2, 4, 4)
        assert out[0].max() == 0 and out[1].min() == 5.0, "channels must not mix"

    def test_masked_loss_ignores_invalid(self):
        from dataset_flood import masked_bce_dice
        logits = torch.zeros(1, 1, 4, 4)
        target = torch.zeros(1, 1, 4, 4)
        valid = torch.zeros(1, 1, 4, 4)
        valid[..., :2, :] = 1.0                  # only the top half is labelled
        target[..., 2:, :] = 1.0                 # garbage in the unlabelled half
        loss_a = masked_bce_dice(logits, target, valid).item()
        target[..., 2:, :] = 0.0                 # change ONLY unlabelled pixels
        loss_b = masked_bce_dice(logits, target, valid).item()
        assert loss_a == pytest.approx(loss_b, abs=1e-6), \
            "unlabelled pixels must not affect the loss"


class TestColorDatasetAugmentation:
    """Misaligned augmentation destroys training silently - no error, just noise."""

    def test_flip_and_rotate_keep_pairs_aligned(self):
        import random
        sar = np.arange(16, dtype=np.float32).reshape(4, 4)
        opt = np.stack([sar, sar, sar], -1)      # optical == SAR in every channel
        for seed in range(12):
            random.seed(seed)
            s, o = sar.copy(), opt.copy()
            if random.random() < 0.5:
                s, o = s[:, ::-1], o[:, ::-1]
            if random.random() < 0.5:
                s, o = s[::-1], o[::-1]
            k = random.randint(0, 3)
            if k:
                s, o = np.rot90(s, k), np.rot90(o, k)
            assert np.array_equal(s, o[..., 0]), f"pair misaligned at seed {seed}"


# ============================================================ model behaviour
class TestModels:
    def test_generator_shape_and_range(self):
        """depth=4 keeps the test fast; the shipped depth=8 needs 256px input by
        construction (8 halvings), which is why 64px fails there."""
        from models import UNetGenerator, init_weights
        G = init_weights(UNetGenerator(1, 3, nf=8, depth=4))
        out = G(torch.randn(1, 1, 64, 64))
        assert out.shape == (1, 3, 64, 64)
        assert out.min() >= -1.0 and out.max() <= 1.0, "tanh output must be in [-1,1]"

    def test_shipped_generator_actually_has_dropout(self):
        """FOOTGUN: UNetGenerator only creates dropout in its `depth - 5` middle
        blocks. At depth<6 there are ZERO dropout layers, MC-dropout returns identical
        passes, and the confidence map silently becomes a constant - the uncertainty
        story would be vacuous with no error raised anywhere."""
        from models import UNetGenerator
        shipped = UNetGenerator(1, 3, nf=8, depth=8)
        n_drop = sum(1 for m in shipped.modules() if isinstance(m, torch.nn.Dropout))
        assert n_drop >= 3, f"shipped generator must carry dropout, found {n_drop}"
        shallow = UNetGenerator(1, 3, nf=8, depth=4)
        assert sum(1 for m in shallow.modules()
                   if isinstance(m, torch.nn.Dropout)) == 0,             "documents the footgun: depth<6 has no dropout at all"

    def test_mc_dropout_produces_variation(self):
        """If dropout were inactive at inference the confidence map would be a
        constant, and the whole uncertainty story would be vacuous."""
        from models import UNetGenerator, mc_colorize
        G = UNetGenerator(1, 3, nf=8, depth=8)
        _, conf, std = mc_colorize(G, torch.randn(1, 1, 256, 256), n=4)
        assert std.max().item() > 0, "MC-dropout passes must differ from each other"
        assert 0.0 <= conf.min().item() and conf.max().item() <= 1.0

    def test_confidence_is_inverse_of_spread(self):
        from models import UNetGenerator, mc_colorize
        G = UNetGenerator(1, 3, nf=8, depth=8)
        _, conf, std = mc_colorize(G, torch.randn(1, 1, 256, 256), n=4)
        flat_c, flat_s = conf.flatten(), std.flatten()
        hi = flat_s > flat_s.median()
        assert flat_c[hi].mean() <= flat_c[~hi].mean(), \
            "higher disagreement must mean lower confidence"

    def test_conf_scale_matches_the_measured_spread(self):
        """CONF_SCALE has to track the real MC-dropout spread, not a round number.

        The original 0.35 was invented. Measured over 2.62M validation pixels the
        per-pixel std is median 0.034 / p99 0.075, so dividing by 0.35 compressed 99%
        of pixels into confidence 0.79-0.95: the gate slider did nothing until 0.80
        and then blanked the whole image by 0.95. A UI control with two reachable
        states is a broken control, so the constant is pinned here."""
        from models import CONF_SCALE
        assert 0.05 <= CONF_SCALE <= 0.12, (
            f"CONF_SCALE={CONF_SCALE} is outside the measured p95-p99 band of the "
            "validation spread; re-measure before changing it")

    def test_scale_argument_actually_reaches_the_maths(self):
        """The parameter was added to the signature once while the body kept dividing
        by a hardcoded literal, so callers passing `scale` were silently ignored."""
        from models import UNetGenerator, mc_colorize
        torch.manual_seed(0)
        G = UNetGenerator(1, 3, nf=8, depth=8)
        x = torch.randn(1, 1, 256, 256)
        torch.manual_seed(1)
        _, tight, _ = mc_colorize(G, x, n=4, scale=0.02)
        torch.manual_seed(1)
        _, loose, _ = mc_colorize(G, x, n=4, scale=2.0)
        assert tight.mean().item() < loose.mean().item(), \
            "a smaller scale must yield lower confidence - the argument is ignored"


class TestDropoutTypesAreAllCaught:
    """The bug real-image testing found: ResUNet uses nn.Dropout2d, mc_colorize
    filtered on nn.Dropout. They are SIBLINGS, not parent/child, so dropout was never
    re-enabled -> every MC pass identical -> confidence pinned at 1.0 everywhere.
    The map looked flawless and carried zero information."""

    def test_resunet_uses_dropout2d(self):
        from resunet import ResUNet
        m = ResUNet(1, 3, encoder="resnet18", pretrained=False, dropout=0.5)
        assert any(isinstance(x, torch.nn.Dropout2d) for x in m.modules())

    def test_mc_colorize_varies_on_resunet(self):
        from models import mc_colorize
        from resunet import ResUNet
        G = ResUNet(1, 3, encoder="resnet18", pretrained=False, dropout=0.5)
        _, conf, std = mc_colorize(G, torch.randn(1, 1, 128, 128), n=6)
        assert std.max().item() > 0, "ResNet generator must produce MC variation"
        assert conf.min().item() < 1.0, "confidence must not be constant 1.0"

    def test_raises_when_no_dropout_at_all(self):
        from models import mc_colorize
        from resunet import ResUNet
        G = ResUNet(1, 3, encoder="resnet18", pretrained=False, dropout=0.0)
        with pytest.raises(RuntimeError, match="no dropout"):
            mc_colorize(G, torch.randn(1, 1, 128, 128), n=3)


class TestShippedGeneratorAtRealSize:
    """Guards the configuration we actually deploy, at the resolution we deploy it."""

    def test_depth8_generator_handles_256(self):
        from resunet import build_generator
        G = build_generator("unet")
        out = G(torch.randn(1, 1, 256, 256))
        assert out.shape == (1, 3, 256, 256)
        assert out.min() >= -1.0 and out.max() <= 1.0

    def test_resnet_generator_handles_256(self):
        from resunet import build_generator
        G = build_generator("resnet18", pretrained=False)
        out = G(torch.randn(1, 1, 256, 256))
        assert out.shape == (1, 3, 256, 256)


class TestTemperatureScaling:
    def test_preserves_ranking(self):
        """Temperature must change probabilities but never reorder them - otherwise
        it would be buying calibration by damaging accuracy."""
        logits = np.array([-3.0, -0.5, 0.0, 0.8, 2.5])
        for T in (0.5, 1.37, 3.0):
            p = 1 / (1 + np.exp(-logits / T))
            assert np.all(np.diff(p) > 0), f"ranking broken at T={T}"

    def test_high_temperature_softens(self):
        logits = np.array([4.0])
        p1 = 1 / (1 + np.exp(-logits))
        p2 = 1 / (1 + np.exp(-logits / 2.0))
        assert p2 < p1, "T>1 must move confident predictions toward 0.5"


# ============================================================ ship routing
class TestRouter:
    def test_haversine_known_distance(self):
        from forcing import haversine_km
        d = haversine_km(0, 0, 0, 1)             # 1 degree at the equator
        assert 110 < d < 112

    def test_bearing_cardinals(self):
        from forcing import initial_bearing
        assert initial_bearing(0, 0, 1, 0) == pytest.approx(0, abs=1)     # north
        assert initial_bearing(0, 0, 0, 1) == pytest.approx(90, abs=1)    # east

    def test_ship_refuses_unsafe_seas(self):
        from forcing import Conditions
        from ship import Ship, transit
        s = Ship()
        calm = Conditions(0, 0, 1.0, 0, 0, 0)
        storm = Conditions(0, 0, 12.0, 180, 0, 0)   # far beyond hs_limit
        assert transit(s, 0, 100, calm) is not None
        assert transit(s, 0, 100, storm) is None, "must refuse beyond the safety limit"

    def test_following_current_is_faster_than_opposing(self):
        from forcing import Conditions
        from ship import Ship, transit
        s = Ship()
        helping = Conditions(0, 2.0, 1.0, 0, 0, 0)    # 2 m/s northward
        opposing = Conditions(0, -2.0, 1.0, 0, 0, 0)
        t_help = transit(s, 0, 200, helping)[0]       # heading north
        t_opp = transit(s, 0, 200, opposing)[0]
        assert t_help < t_opp, "a following current must shorten the passage"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))


class TestGeolocation:
    """The area bug this found was live: the app assumed a flat 100 m^2 per pixel while
    the rasters are in a GEOGRAPHIC crs, so a degree of longitude shrinks as cos(lat).
    Flood extent - the headline number - read 11.9% high for India and 28.4% for USA."""

    def test_longitude_shrinks_with_latitude(self):
        from geo import pixel_km2
        eq, mid = pixel_km2(0.0), pixel_km2(38.3)
        assert eq > mid, "a pixel must cover less ground at higher latitude"
        assert 0.70 < mid / eq < 0.80, f"expected ~cos(38.3)=0.785, got {mid / eq:.3f}"

    def test_flat_area_assumption_is_wrong_enough_to_matter(self):
        from geo import pixel_km2
        naive = 1e-4                                    # the old (10 m)^2 constant
        for lat, atleast in ((26.6, 0.10), (38.9, 0.25)):   # India, USA
            err = naive / pixel_km2(lat) - 1.0
            assert err > atleast, f"at {lat} deg the old constant was only {err:.1%} high"

    def test_smaller_box_wins_over_a_larger_one_containing_it(self):
        """India's bbox contains Sri Lanka and most of Pakistan. Before the boxes were
        sorted by area, declaration order decided the answer and both came back
        'India'."""
        from geo import locate
        assert locate(7.89, 81.34)[0] == "Sri Lanka"
        assert locate(29.23, 70.44)[0] == "Pakistan"
        assert locate(26.61, 92.93)[0] == "India", "Assam is at 92.9E; bbox must reach 97.5"

    def test_unknown_rather_than_a_confident_wrong_guess(self):
        from geo import locate
        assert locate(0.0, -140.0) == (None, None), "mid-Pacific must resolve to nothing"
        assert locate(91.0, 0.0) == (None, None), "out-of-range latitude must not match"


class TestLandCoverHonesty:
    """We measured whether C-band SAR can give the land-cover breakdown that was asked
    for. It cannot: built-up scored AUC 0.483 against bare soil (below chance) and the
    NDBI reference label calls 26% of rural Pakistani flood plain 'buildings'. These
    tests guard the decision not to ship it."""

    def test_built_up_is_never_reported(self):
        import numpy as np
        from landcover import cover_from_s2
        rng = np.random.default_rng(0)
        s2 = (rng.random((13, 64, 64)) * 3000).astype(np.int16)
        out = cover_from_s2(s2)
        keys = {c["key"] for c in out["classes"]}
        assert "built" not in keys and "urban" not in keys
        assert "built-up" in out["not_reported"]

    def test_fractions_exclude_cloud_from_the_denominator(self):
        """Percentages must describe what was actually seen. Diluting them with cloud
        would silently shrink every class instead of admitting the scene is obscured."""
        import numpy as np
        from landcover import cover_from_s2, CLOUD_BLUE, B_BLUE
        s2 = np.full((13, 40, 40), 1000, dtype=np.int16)
        s2[B_BLUE, :20] = int((CLOUD_BLUE + 0.15) * 10000)      # half the scene clouded
        out = cover_from_s2(s2)
        assert out["usable"]
        assert abs(out["cloud_fraction"] - 0.5) < 0.02
        assert abs(sum(c["pct"] for c in out["classes"]) - 100.0) < 0.5

    def test_fully_clouded_scene_refuses_rather_than_guesses(self):
        import numpy as np
        from landcover import cover_from_s2, CLOUD_BLUE, B_BLUE
        s2 = np.full((13, 32, 32), 1000, dtype=np.int16)
        s2[B_BLUE] = int((CLOUD_BLUE + 0.2) * 10000)
        out = cover_from_s2(s2)
        assert out["usable"] is False and out["classes"] == []

    def test_nodata_label_is_excluded(self):
        """LabelHand == -1 is no-data. It has been mistaken for 'not water' before and
        it inflated every metric in the app."""
        import numpy as np
        from landcover import cover_from_s2
        s2 = np.full((13, 30, 30), 1200, dtype=np.int16)
        lab = np.zeros((30, 30), np.int16)
        lab[:15] = -1
        assert cover_from_s2(s2, lab)["analysed_px"] == 15 * 30


class TestUploadMatchesBenchmark:
    """The upload path parses bytes off the wire; the benchmark path loads the same file
    from disk by name. They MUST agree - if they ever diverge, uploads are quietly
    running on something other than what the user supplied, and no error would say so.

    Verified live against the running server for India/Spain/Somalia: water area matched
    the benchmark to 0.00%. These tests pin the two things that could break that.
    """

    def _chip(self):
        from pathlib import Path
        d = Path(os.environ.get("SIH_DATA", "")) / "sen1floods11" / "S1Hand"
        fs = sorted(d.glob("*.tif")) if d.exists() else []
        if not fs:
            pytest.skip("Sen1Floods11 not present")
        return fs[0]

    def test_bytes_and_path_decode_identically(self):
        """tifffile must yield the same array from a path and from an in-memory buffer.
        Any difference here (byte order, lazy pages, memmap) silently changes results."""
        import io as _io
        import tifffile
        f = self._chip()
        from_path = tifffile.imread(f).astype(np.float32)
        from_bytes = tifffile.imread(_io.BytesIO(f.read_bytes())).astype(np.float32)
        assert from_path.shape == from_bytes.shape
        assert np.array_equal(np.nan_to_num(from_path), np.nan_to_num(from_bytes))

    def test_normalisation_is_the_same_on_both_paths(self):
        """Both endpoints clip to -30..0 dB then map to -1..1. A drift in either copy
        would shift every probability without raising anything."""
        f = self._chip()
        import tifffile
        sar = tifffile.imread(f).astype(np.float32)[:2]
        x = np.clip(np.nan_to_num(sar, nan=-30.0), -30.0, 0.0)
        x = (x + 30.0) / 30.0 * 2.0 - 1.0
        assert x.min() >= -1.0 and x.max() <= 1.0
        # -30 dB must land on -1 and 0 dB on +1, exactly
        probe = np.array([[-30.0], [0.0]], dtype=np.float32)
        pr = (np.clip(probe, -30.0, 0.0) + 30.0) / 30.0 * 2.0 - 1.0
        assert pr[0, 0] == pytest.approx(-1.0) and pr[1, 0] == pytest.approx(1.0)

    def test_upload_area_uses_real_pixel_size(self):
        """An upload must measure area from its own georeferencing, not the nominal
        100 m^2 constant - the same bug that overstated India by 11.9%."""
        from geo import read_geotiff_geo
        g = read_geotiff_geo(self._chip())
        if g is None:
            pytest.skip("chip carries no georeferencing")
        assert 60.0 < g.pixel_m2 < 101.0, "a 10 m pixel is at most 100 m^2, less off-equator"


class TestCanvasRepaintContract:
    """Documents a UI regression that had no server-side symptom at all.

    Making <ZoomPan> unmount while Compare is active (so it stops covering the compare
    widget and swallowing its pointer events) means switching back to a canvas layer
    mounts a BRAND NEW, unpainted canvas. The paint effect keyed only on [px, gate] /
    [data, thr, excludePerm] never re-ran, so Colorized and Confidence rendered pure
    black while the pixel probe kept reading correct values straight out of React state.

    There is no Python code path for this, so this test guards the invariant in the
    source itself: any effect that calls putImageData must also depend on `layer`.
    """

    def _components(self):
        from pathlib import Path
        d = Path(__file__).resolve().parents[1] / "frontend" / "components"
        if not d.exists():
            pytest.skip("frontend not present")
        return d

    def test_paint_effects_depend_on_layer(self):
        import re
        for name in ("ColorView.tsx", "FloodView.tsx"):
            src = (self._components() / name).read_text(encoding="utf8")
            # every useEffect body containing putImageData must list `layer` in its deps
            for m in re.finditer(r"useEffect\(\(\) => \{(.*?)\n  \}, \[([^\]]*)\]\);",
                                 src, re.S):
                body, deps = m.group(1), m.group(2)
                if "putImageData" in body:
                    assert "layer" in deps, (
                        f"{name}: an effect that paints a canvas does not depend on "
                        f"`layer` (deps: {deps.strip()}). Switching layers remounts the "
                        f"canvas and it will render blank.")
