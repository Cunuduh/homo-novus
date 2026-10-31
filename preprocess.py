#!/usr/bin/env python3
"""Isolates one body part from a photo: human parsing mask, neutral background, tight crop.

Uses mattmdjaga/segformer_b2_clothes (labels below). Runs on CPU to leave the GPU to the image model.
"""
import numpy as np
from PIL import Image, ImageFilter

MODEL = "mattmdjaga/segformer_b2_clothes"
# 1 hat, 2 hair, 3 glasses, 4 upper clothes, 5 skirt, 6 pants, 7 dress, 8 belt, 9-10 shoes,
# 11 face, 12-13 legs, 14-15 arms, 16 bag, 17 scarf
PARTS = {"face": {1, 2, 3, 11}, "arms": {14, 15}, "torso": {4, 7, 8, 17}, "legs": {5, 6, 9, 10, 12, 13}}
GREY = (128, 128, 128)
_model = None


def _load():
    global _model
    if _model is None:
        from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
        _model = (AutoImageProcessor.from_pretrained(MODEL), AutoModelForSemanticSegmentation.from_pretrained(MODEL).eval())
    return _model


def labels(img):
    import torch
    proc, model = _load()
    small = img.copy(); small.thumbnail((768, 768))
    with torch.inference_mode():
        logits = model(**proc(images=small, return_tensors="pt")).logits
    up = torch.nn.functional.interpolate(logits, size=(img.height, img.width), mode="bilinear", align_corners=False)
    return up.argmax(1)[0].numpy()


def _clean(mask, part):
    """Fills holes the parser leaves. The head becomes its convex hull, which recovers eyes and beard."""
    from scipy import ndimage
    from scipy.spatial import ConvexHull
    from PIL import ImageDraw
    ys, xs = np.where(mask)
    size = max(xs.max() - xs.min(), ys.max() - ys.min())
    k = max(3, int(size * .015))
    mask = ndimage.binary_fill_holes(ndimage.binary_closing(mask, np.ones((k, k)), iterations=2))
    # Drop specks far from the main region.
    lab, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        mask = np.isin(lab, [i + 1 for i, v in enumerate(sizes) if v > sizes.max() * .06])
    if part == "face":
        pts = np.column_stack(np.where(mask))[::7][:, ::-1]
        hull = pts[ConvexHull(pts).vertices]
        im = Image.new("L", (mask.shape[1], mask.shape[0]), 0)
        ImageDraw.Draw(im).polygon([tuple(map(float, q)) for q in hull], fill=255)
        mask = np.asarray(im) > 0
    return mask


def isolate(img, part, pad=.06):
    """Returns the part on neutral grey, cropped to it, or None when the part isn't found."""
    img = img.convert("RGB")
    mask = np.isin(labels(img), list(PARTS[part]))
    if mask.sum() < img.width * img.height * .002:
        return None
    mask = _clean(mask, part)
    ys, xs = np.where(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    p = int(max(x1 - x0, y1 - y0) * pad)
    box = (max(x0 - p, 0), max(y0 - p, 0), min(x1 + p, img.width), min(y1 + p, img.height))
    alpha = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5))
    out = Image.composite(img, Image.new("RGB", img.size, GREY), alpha).crop(box)
    if part == "face":
        # A tight close-up makes the model draw an oversized, doll-like head, so show the head small on a wide canvas.
        side = int(max(out.size) / .38)
        canvas = Image.new("RGB", (side, side), GREY)
        canvas.paste(out, ((side - out.width) // 2, int(side * .08)))
        return canvas
    return out


def cut_out(path):
    """Makes the background transparent, in place. Returns the share of the image kept.

    The parsing model finds the body but misses thin arms and hands, so anything clearly unlike
    the parchment is kept as well, and only regions connected to the body survive.
    """
    from scipy import ndimage
    img = Image.open(path).convert("RGB")
    rgb = np.asarray(img, float)
    person = labels(img) != 0
    near = ndimage.binary_dilation(person, iterations=max(6, img.width // 40))
    # Paper colour fitted as a smooth surface to the area well away from the figure, which handles uneven tone.
    far = ~ndimage.binary_dilation(person, iterations=img.width // 16)
    h, w = person.shape
    yy, xx = np.mgrid[0:h, 0:w]
    xx, yy = xx / w - .5, yy / h - .5
    terms = lambda x, y: np.stack([np.ones_like(x), x, y, x * y, x * x, y * y], -1)
    coef = np.linalg.lstsq(terms(xx[far], yy[far])[::37], rgb[far][::37], rcond=None)[0]
    paper = terms(xx, yy) @ coef
    # Smooth first so paper grain and hatching don't count as figure. Hand outlines count as ink, and filling holes recovers the hands.
    soft = np.asarray(img.filter(ImageFilter.MedianFilter(5)), float)
    delta = soft - paper
    diff = np.abs(delta).sum(2)
    ink = diff > max(44, np.percentile(diff[far], 99.5) * 1.3)
    mask = person | (ink & near)
    mask = ndimage.binary_fill_holes(ndimage.binary_closing(mask, np.ones((5, 5)), iterations=2))
    mask = ndimage.binary_opening(mask, np.ones((3, 3)))
    lab, n = ndimage.label(mask)
    if n > 1:
        sizes = ndimage.sum(mask, lab, range(1, n + 1))
        mask = lab == (int(np.argmax(sizes)) + 1)
    if mask.mean() < .03:
        return float(mask.mean())  # Nothing sensible found: leave the image alone.
    # A uniform light outline keeps the figure readable on the dark page and hides mask errors on every seed.
    width = max(3, img.width // 200)
    outer = ndimage.binary_dilation(mask, iterations=width)
    out = rgb.copy()
    out[outer & ~mask] = (232, 218, 190)
    img = Image.fromarray(out.astype(np.uint8))
    alpha = Image.fromarray((outer * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.1))
    img.putalpha(alpha); img.save(path)
    return float(mask.mean())


def ghost(path, out_path):
    """Keys out everything as light as the paper, inside the figure too, and flips the remaining ink to pale lines."""
    from scipy import ndimage
    img = Image.open(path).convert("RGB")
    rgb = np.asarray(img, float)
    lum = rgb @ np.array([.3, .59, .11])
    far = ~ndimage.binary_dilation(labels(img) != 0, iterations=img.width // 16)
    h, w = lum.shape
    yy, xx = np.mgrid[0:h, 0:w]
    xx, yy = xx / w - .5, yy / h - .5
    terms = lambda x, y: np.stack([np.ones_like(x), x, y, x * y, x * x, y * y], -1)
    coef = np.linalg.lstsq(terms(xx[far], yy[far])[::37], lum[far][::37], rcond=None)[0]
    paper = terms(xx, yy) @ coef
    ink = np.clip((paper - lum - 14) / np.maximum(paper - 45, 1), 0, 1)
    alpha = np.clip(ink ** .7 * 1.15, 0, 1)
    # Inverted tones: the darkest ink becomes the brightest line.
    tone = np.clip(1 - lum / 255, 0, 1)[..., None]
    colour = (np.array([150, 138, 150]) + tone * np.array([105, 112, 100])).clip(0, 255)
    out = np.dstack([colour, alpha * 255]).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(out_path)


if __name__ == "__main__":
    import sys, time
    src, part, out = sys.argv[1:4]
    t = time.time(); r = isolate(Image.open(src), part)
    print(part, None if r is None else r.size, round(time.time() - t, 1), "s")
    if r: r.save(out, quality=95)
