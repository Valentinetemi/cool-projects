// Matter Bending -- single-pass glow/bloom for a GLSL TOP.
//
// Alternative to the Blur TOP -> Composite(Add) chain described in
// docs/TOUCHDESIGNER_GUIDE.md step 5. Wire your rendered particle TOP into
// this GLSL TOP's first input (sTD2DInputs[0]) and this does a cheap
// multi-tap blur of the bright areas, added back over the original --
// the "water glow" look, in one node.
//
// TouchDesigner GLSL TOPs expect a `main()` writing `fragColor`; sTD2DInputs
// and TDOutputSwizzle are provided by TouchDesigner's built-in uniforms/
// includes, consistent with its standard GLSL TOP template.

uniform float uThreshold;   // brightness cutoff before a pixel starts blooming (try 0.35)
uniform float uIntensity;   // bloom strength multiplier (try 1.5)
uniform float uRadiusPx;    // blur sample radius in pixels (try 6.0)

out vec4 fragColor;

void main()
{
    vec2 res = uTD2DInfos[0].res.zw; // input resolution in pixels
    vec2 uv = vUV.st;

    vec4 original = texture(sTD2DInputs[0], uv);

    vec3 bloomSum = vec3(0.0);
    float weightSum = 0.0;
    const int TAPS = 8;

    for (int i = 0; i < TAPS; i++)
    {
        float angle = (float(i) / float(TAPS)) * 6.28318530718;
        vec2 offset = vec2(cos(angle), sin(angle)) * (uRadiusPx / res);
        vec3 sample = texture(sTD2DInputs[0], uv + offset).rgb;

        float brightness = max(sample.r, max(sample.g, sample.b));
        float contribution = max(brightness - uThreshold, 0.0);

        bloomSum += sample * contribution;
        weightSum += contribution;
    }

    vec3 bloom = weightSum > 0.0 ? (bloomSum / weightSum) : vec3(0.0);
    vec3 result = original.rgb + bloom * uIntensity;

    fragColor = TDOutputSwizzle(vec4(result, original.a));
}
