using System;
using System.Collections;
using System.Collections.Concurrent;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading;
using Unity.Collections;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 录制试玩：`-record &lt;目录&gt;`（一般和 `-playbot` 一起用）。按固定帧率逐帧截 JPG，
    /// 游戏声音用 AudioRenderer 离线渲染成 audio.f32（与画面逐帧对齐，录制时扬声器静音）；
    /// frames.tsv 记下每帧的稿数、本轮时间、时间倍速和屏幕上的字，剪辑时据此挑段、剔掉快进段。
    /// 用离线取景而不是录屏：录屏要系统权限，而且编码慢时会掉帧。
    /// </summary>
    public class Recorder : MonoBehaviour
    {
        const int Fps = 30;
        string _dir;
        int _frame;
        StreamWriter _tsv;
        FileStream _audio;
        NativeArray<float> _buf;
        readonly BlockingCollection<(string, byte[])> _queue = new(64);
        Thread _writer;
        Hud _hud; LoopDirector _dir2;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        static void Boot()
        {
            if (Arg("-record") == null) return;
            var go = new GameObject("Recorder");
            DontDestroyOnLoad(go);
            go.AddComponent<Recorder>();
        }

        void Awake()
        {
            _dir = Arg("-record");
            Directory.CreateDirectory(Path.Combine(_dir, "frames"));
            _tsv = new StreamWriter(Path.Combine(_dir, "frames.tsv")) { AutoFlush = true };
            _tsv.WriteLine("frame\tloop\telapsed\ttimescale\tsaying");
            _audio = new FileStream(Path.Combine(_dir, "audio.f32"), FileMode.Create);
            File.WriteAllText(Path.Combine(_dir, "audio.txt"),
                $"rate={AudioSettings.outputSampleRate} channels={Channels} format=f32le fps={Fps}\n");
            // 磁盘写入放到后台线程，主线程只做读回和 JPG 编码
            _writer = new Thread(() => { foreach (var (p, b) in _queue.GetConsumingEnumerable()) File.WriteAllBytes(p, b); }) { IsBackground = true };
            _writer.Start();
            Time.captureFramerate = Fps;
            AudioRenderer.Start();
            StartCoroutine(Loop());
        }

        static int Channels => AudioSettings.speakerMode == AudioSpeakerMode.Mono ? 1 : 2;

        IEnumerator Loop()
        {
            var eof = new WaitForEndOfFrame();
            while (true)
            {
                yield return eof;
                var tex = ScreenCapture.CaptureScreenshotAsTexture();
                _queue.Add((Path.Combine(_dir, "frames", $"{_frame:000000}.jpg"), tex.EncodeToJPG(90)));
                Destroy(tex);

                int n = AudioRenderer.GetSampleCountForCaptureFrame() * Channels;
                if (!_buf.IsCreated || _buf.Length != n) { if (_buf.IsCreated) _buf.Dispose(); _buf = new NativeArray<float>(n, Allocator.Persistent); }
                AudioRenderer.Render(_buf);
                var bytes = new byte[n * 4];
                Buffer.BlockCopy(_buf.ToArray(), 0, bytes, 0, bytes.Length);
                _audio.Write(bytes, 0, bytes.Length);

                if (!_hud) _hud = FindFirstObjectByType<Hud>();
                if (!_dir2) _dir2 = FindFirstObjectByType<LoopDirector>();
                string say = _hud ? Regex.Replace(_hud.Saying ?? "", "<[^>]+>", "").Replace("\n", " / ").Replace("\t", " ") : "";
                _tsv.WriteLine($"{_frame}\t{LoopMemory.Loop}\t{(_dir2 ? _dir2.Elapsed : -1f):F2}\t{Time.timeScale:F2}\t{say}");
                _frame++;
            }
        }

        void OnApplicationQuit()
        {
            AudioRenderer.Stop();
            _queue.CompleteAdding();
            _writer?.Join(10000);
            _audio?.Dispose();
            _tsv?.Dispose();
            if (_buf.IsCreated) _buf.Dispose();
            Debug.Log($"[Recorder] {_frame} frames");
        }

        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == name) return a[i + 1];
            return null;
        }
    }
}
