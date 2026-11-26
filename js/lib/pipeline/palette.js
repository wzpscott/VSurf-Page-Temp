// PCA scores are percentile-scaled to [0, 1] in the exported PLY.
// Return linear RGB for Three.js; keep all three principal components.
export function pcaColor(scores, palette = 'perceptual', reverse = false) {
    const [x, y, z] = scores.map(v => reverse ? 1 - v : v);
    if (palette === 'rgb') {
        return [x, y, z].map(v => {
            const linear = v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
            return linear * 0.85 + 0.15;
        });
    }
    const lightness = 0.68 + 0.20 * x;
    const a = (y - 0.5) * 0.32, b = (z - 0.5) * 0.32;
    const convert = chroma => {
        const l = (lightness + 0.3963377774 * a * chroma + 0.2158037573 * b * chroma) ** 3;
        const m = (lightness - 0.1055613458 * a * chroma - 0.0638541728 * b * chroma) ** 3;
        const s = (lightness - 0.0894841775 * a * chroma - 1.2914855480 * b * chroma) ** 3;
        return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s];
    };
    const inGamut = rgb => rgb.every(v => v >= 0 && v <= 1);
    let rgb = convert(1);
    if (inGamut(rgb)) return rgb;
    // Compress chroma instead of clipping channels, preserving hue/lightness.
    let low = 0, high = 1;
    for (let i = 0; i < 12; i++) {
        const mid = (low + high) / 2;
        if (inGamut(convert(mid))) low = mid;
        else high = mid;
    }
    return convert(low);
}
