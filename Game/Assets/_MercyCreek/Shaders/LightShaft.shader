// 窗口光柱切片：边缘柔化、窗棂遮挡、沿光线方向衰减、与场景深度软相交、缓慢流动的浮尘噪声。
Shader "MercyCreek/LightShaft"
{
    Properties
    {
        [HDR] _ShaftColor ("Color (set by script)", Color) = (1, 0.85, 0.6, 1)
        _EdgeSoft ("Edge Softness", Range(0.01, 0.5)) = 0.12
        _Mullion ("Mullion Width", Range(0, 0.05)) = 0.018
        _DepthFade ("Depth Fade", Float) = 0.5
        _NearFade ("Camera Near Fade", Float) = 1.2
        _NoiseScale ("Dust Noise Scale", Float) = 2.2
        _NoiseSpeed ("Dust Noise Speed", Float) = 0.06
        _NoiseAmount ("Dust Noise Amount", Range(0, 1)) = 0.55
    }
    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent+10" "RenderPipeline" = "UniversalPipeline" "IgnoreProjector" = "True" }
        Pass
        {
            Name "Shaft"
            Blend One One
            ZWrite Off
            Cull Off

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/DeclareDepthTexture.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _ShaftColor;
                float _EdgeSoft, _Mullion, _DepthFade, _NearFade, _NoiseScale, _NoiseSpeed, _NoiseAmount;
            CBUFFER_END

            struct Attributes { float4 positionOS : POSITION; float2 uv : TEXCOORD0; float2 uv2 : TEXCOORD1; };
            struct Varyings
            {
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float along : TEXCOORD1;
                float4 screenPos : TEXCOORD2;
                float3 positionWS : TEXCOORD3;
            };

            Varyings vert(Attributes i)
            {
                Varyings o;
                VertexPositionInputs p = GetVertexPositionInputs(i.positionOS.xyz);
                o.positionCS = p.positionCS;
                o.positionWS = p.positionWS;
                o.screenPos = ComputeScreenPos(p.positionCS);
                o.uv = i.uv;
                o.along = i.uv2.x;
                return o;
            }

            float hash(float3 p) { p = frac(p * 0.3183099 + 0.1); p *= 17.0; return frac(p.x * p.y * p.z * (p.x + p.y + p.z)); }
            float vnoise(float3 x)
            {
                float3 i = floor(x), f = frac(x);
                f = f * f * (3.0 - 2.0 * f);
                return lerp(lerp(lerp(hash(i), hash(i + float3(1,0,0)), f.x), lerp(hash(i + float3(0,1,0)), hash(i + float3(1,1,0)), f.x), f.y),
                            lerp(lerp(hash(i + float3(0,0,1)), hash(i + float3(1,0,1)), f.x), lerp(hash(i + float3(0,1,1)), hash(i + float3(1,1,1)), f.x), f.y), f.z);
            }

            half4 frag(Varyings i) : SV_Target
            {
                float2 e = min(i.uv, 1.0 - i.uv);
                float edge = smoothstep(0.0, _EdgeSoft, e.x) * smoothstep(0.0, _EdgeSoft, e.y);

                // 窗棂：中间一根竖棂，两根横棂（与 Blender 白模的窗一致）
                float m = 1.0;
                m *= smoothstep(_Mullion * 0.5, _Mullion, abs(i.uv.x - 0.5));
                m *= smoothstep(_Mullion * 0.5, _Mullion, abs(i.uv.y - 1.0 / 3.0));
                m *= smoothstep(_Mullion * 0.5, _Mullion, abs(i.uv.y - 2.0 / 3.0));

                float along = smoothstep(0.0, 0.06, i.along) * pow(saturate(1.0 - i.along), 1.4);

                float2 suv = i.screenPos.xy / i.screenPos.w;
                float sceneZ = LinearEyeDepth(SampleSceneDepth(suv), _ZBufferParams);
                float fragZ = i.screenPos.w;
                float soft = saturate((sceneZ - fragZ) / _DepthFade);
                float nearFade = saturate((fragZ - 0.3) / _NearFade);

                float3 q = i.positionWS * _NoiseScale + float3(0, -_Time.y * _NoiseSpeed, _Time.y * _NoiseSpeed * 0.6);
                float n = vnoise(q) * 0.6 + vnoise(q * 2.7) * 0.4;
                float dust = lerp(1.0, n * 1.6, _NoiseAmount);

                float a = edge * m * along * soft * nearFade * dust;
                return half4(_ShaftColor.rgb * a, 0);
            }
            ENDHLSL
        }
    }
}
