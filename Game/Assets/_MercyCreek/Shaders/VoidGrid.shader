// 出逃结局的"没有渲染的世界"：灰白底 + 世界坐标网格线，越远越淡，像一张还没画完的格子纸。
Shader "MercyCreek/VoidGrid"
{
    Properties
    {
        _Base ("Base", Color) = (0.78, 0.78, 0.76, 1)
        _Line ("Line", Color) = (0.42, 0.42, 0.42, 1)
        _Cell ("Cell Size (m)", Float) = 1
        _Width ("Line Width", Range(0.001, 0.2)) = 0.025
        _FadeDist ("Fade Distance", Float) = 28
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

            CBUFFER_START(UnityPerMaterial)
                half4 _Base, _Line;
                float _Cell, _Width, _FadeDist;
            CBUFFER_END

            struct A { float4 pos : POSITION; float3 n : NORMAL; };
            struct V { float4 pos : SV_POSITION; float3 wp : TEXCOORD0; float3 n : TEXCOORD1; };

            V vert(A i)
            {
                V o;
                o.wp = TransformObjectToWorld(i.pos.xyz);
                o.n = TransformObjectToWorldNormal(i.n);
                o.pos = TransformWorldToHClip(o.wp);
                return o;
            }

            float gridLine(float2 p)
            {
                float2 g = abs(frac(p / _Cell - 0.5) - 0.5) * _Cell;
                float2 w = fwidth(p) * 1.2 + _Width * 0.5;
                float2 l = 1 - smoothstep(_Width * 0.5, w, g);
                return max(l.x, l.y);
            }

            half4 frag(V i) : SV_Target
            {
                // 按法线选投影面：地面用 xz，墙用 xy / zy
                float3 an = abs(normalize(i.n));
                float2 p = an.y > 0.5 ? i.wp.xz : (an.x > an.z ? i.wp.zy : i.wp.xy);
                float g = gridLine(p);
                float d = distance(i.wp, _WorldSpaceCameraPos);
                float fade = saturate(d / _FadeDist);
                half3 c = lerp(_Base.rgb, _Line.rgb, g * (1 - fade));
                c = lerp(c, _Base.rgb * 1.08, fade * fade);
                return half4(c, 1);
            }
            ENDHLSL
        }
    }
}
