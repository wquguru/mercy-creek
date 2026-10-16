// 楼梯旁的老镜子：按屏幕坐标采样反射相机的画面（MirrorReflection.cs），压暗、偏暖、边缘发灰，像银层老化的玻璃。
Shader "MercyCreek/Mirror"
{
    Properties
    {
        _ReflTex ("Reflection", 2D) = "black" {}
        _Tint ("Tint", Color) = (0.82, 0.78, 0.7, 1)
        _Fog ("Edge Fog", Color) = (0.32, 0.3, 0.27, 1)
        _Shine ("Specular Sheen", Range(0, 0.2)) = 0.04
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" "Queue" = "Geometry" }
        Cull Off
        Pass
        {
            Name "Unlit"
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            TEXTURE2D(_ReflTex); SAMPLER(sampler_ReflTex);
            CBUFFER_START(UnityPerMaterial)
                half4 _Tint, _Fog;
                half _Shine;
            CBUFFER_END

            struct A { float4 pos : POSITION; float2 uv : TEXCOORD0; };
            struct V { float4 pos : SV_POSITION; float4 sp : TEXCOORD0; float2 uv : TEXCOORD1; float3 wp : TEXCOORD2; };

            V vert(A i)
            {
                V o;
                o.wp = TransformObjectToWorld(i.pos.xyz);
                o.pos = TransformWorldToHClip(o.wp);
                o.sp = ComputeScreenPos(o.pos);
                o.uv = i.uv;
                return o;
            }

            float hash(float2 p) { return frac(sin(dot(p, float2(12.9898, 78.233))) * 43758.5453); }

            half4 frag(V i) : SV_Target
            {
                float2 suv = i.sp.xy / i.sp.w;
                half3 refl = SAMPLE_TEXTURE2D(_ReflTex, sampler_ReflTex, suv).rgb;
                // 银层老化：越靠边越灰、越暗，再撒一点斑
                float2 c = abs(i.uv - 0.5) * 2;
                float edge = saturate(pow(max(c.x, c.y * 0.9), 4));
                float spots = smoothstep(0.985, 1.0, hash(floor(i.uv * 140))) * 0.5;
                half3 col = refl * _Tint.rgb;
                col = lerp(col, _Fog.rgb * (0.4 + 0.6 * dot(refl, half3(0.3, 0.6, 0.1))), edge * 0.65 + spots);
                col += _Shine * (1 - edge);
                return half4(col, 1);
            }
            ENDHLSL
        }
    }
}
