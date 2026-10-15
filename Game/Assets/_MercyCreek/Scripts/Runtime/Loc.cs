using System.Collections.Generic;
using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 文本表：所有给玩家看的字都从这里取，键 → (中文, English)。剧情以 docs/GAME_DESIGN.md 为准。
    /// </summary>
    public static partial class Loc
    {
        public enum Lang { Zh, En }

        static Lang? _lang;
        public static Lang Current
        {
            get
            {
                if (_lang == null)
                {
                    int saved = PlayerPrefs.GetInt("lang", -1);
                    _lang = saved >= 0 ? (Lang)saved
                        : Application.systemLanguage is SystemLanguage.Chinese or SystemLanguage.ChineseSimplified or SystemLanguage.ChineseTraditional
                            ? Lang.Zh : Lang.En;
                }
                return _lang.Value;
            }
            set { _lang = value; PlayerPrefs.SetInt("lang", (int)value); }
        }

        public static string T(string key, params object[] args)
        {
            if (!Table.TryGetValue(key, out var e)) { Debug.LogWarning("[Loc] missing " + key); return key; }
            string s = Current == Lang.Zh ? e.zh : e.en;
            return args.Length > 0 ? string.Format(s, args) : s;
        }

        public static bool Has(string key) => Table.ContainsKey(key);

        /// <summary>"格斯：……"</summary>
        public static string Line(string speakerKey, string key, params object[] args) =>
            $"<color=#e8c48a>{T(speakerKey)}</color>{T("ui.colon")}{T(key, args)}";

        static readonly Dictionary<string, (string zh, string en)> Table = new()
        {
            // ---------- 界面 ----------
            ["ui.colon"] = ("：", ": "),
            ["ui.loop"] = ("Mercy Creek · 第 {0} 次", "Mercy Creek · Draft {0}"),
            ["ui.memory"] = ("记忆 {0}", "Memories {0}"),
            ["ui.remembered"] = ("<i>（你决定记住这个。）</i>", "<i>(You decide to remember this.)</i>"),
            ["ui.full"] = ("<i>（你隐约知道，这一轮记不住更多了。）</i>", "<i>(You sense you can't hold on to anything more this time.)</i>"),
            ["ui.again"] = ("<i>……又是这个下午。</i>", "<i>...This afternoon again.</i>"),
            ["ui.ellipsis"] = ("<i>……</i>", "<i>...</i>"),
            ["ui.talk"] = ("和{0}说话", "Talk to {0}"),
            ["ui.leave"] = ("（走开）", "(Leave)"),
            ["ui.sleep"] = ("躺下，结束这个下午", "Lie down and end this afternoon"),

            // ---------- 菜单 ----------
            ["menu.title"] = ("MERCY CREEK", "MERCY CREEK"),
            ["menu.tagline"] = ("每天下午三点，一切重来。", "Every afternoon at three, it all begins again."),
            ["menu.new"] = ("开始", "Begin"),
            ["menu.continue"] = ("继续 · 第 {0} 稿", "Continue · Draft {0}"),
            ["menu.settings"] = ("设置", "Settings"),
            ["menu.quit"] = ("退出", "Quit"),
            ["menu.resume"] = ("继续", "Resume"),
            ["menu.totitle"] = ("回到标题", "Back to title"),
            ["menu.back"] = ("返回", "Back"),
            ["menu.paused"] = ("暂停", "Paused"),
            ["menu.sens"] = ("鼠标灵敏度  ◂ {0} ▸", "Mouse sensitivity  ◂ {0} ▸"),
            ["menu.master"] = ("总音量  ◂ {0}% ▸", "Master volume  ◂ {0}% ▸"),
            ["menu.music"] = ("音乐音量  ◂ {0}% ▸", "Music volume  ◂ {0}% ▸"),
            ["menu.lang"] = ("语言  ◂ 中文 ▸", "Language  ◂ English ▸"),
            ["menu.invert"] = ("反转 Y 轴  ◂ {0} ▸", "Invert Y  ◂ {0} ▸"),
            ["menu.on"] = ("开", "On"),
            ["menu.off"] = ("关", "Off"),
            ["menu.hint"] = ("WASD 移动 · Shift 快走 · E 交互 · 1–4 选择对话 · Esc 暂停", "WASD move · Shift walk faster · E interact · 1–4 choose · Esc pause"),
            ["menu.share"] = ("保存分享卡片", "Save share card"),
            ["menu.saved"] = ("已保存到 {0}", "Saved to {0}"),
            ["menu.credits"] = ("单人 + AI 制作 · 资产来自 CC0 / 自制 · 字体 Noto Serif SC（SIL OFL）", "Made by one person with AI · CC0 & original assets · Font: Noto Serif SC (SIL OFL)"),
            ["share.memories"] = ("记住的东西", "What you remembered"),

            // ---------- 人名 ----------
            ["name.nell"] = ("内尔", "Nell"),
            ["name.gus"] = ("格斯", "Gus"),
            ["name.prof"] = ("教授", "The Professor"),
            ["name.crane"] = ("陌生人", "The Stranger"),
            ["name.crane.known"] = ("克兰", "Crane"),

            // ---------- 时间表 ----------
            ["ev.start"] = ("下午三点。你手里是那只有缺口的杯子。", "Three o'clock. In your hand, the chipped glass."),
            ["ev.gus.day"] = ("今天会是个好日子，内尔。", "Gonna be a fine day, Nell."),
            ["ev.gus.slip"] = ("今天会是个好日子，玛莎——内尔。", "Gonna be a fine day, Martha—Nell."),
            ["ev.repeat"] = ("<i>他刚才说过一模一样的话。一字不差。</i>", "<i>He just said that. Word for word.</i>"),
            ["ev.door"] = ("<i>门被推开。一个陌生人走进来，靴子上全是土。</i>", "<i>The door swings open. A stranger walks in, boots caked in dust.</i>"),
            ["ev.crane.glance"] = ("<i>他在门口停了一下，看了你一眼。像是认出了你。</i>", "<i>He stops in the doorway and looks at you. As if he knows you.</i>"),
            ["ev.crane.order"] = ("威士忌。", "Whiskey."),
            ["ev.crane.early"] = ("你比上一稿醒得早。", "You woke earlier than in the last draft."),
            ["ev.crane.clock"] = ("钟又停在三点了。", "Clock's stopped at three again."),
            ["ev.crane.leave"] = ("<i>陌生人合上笔记本，上了楼。四号房的门在他身后关上。</i>", "<i>The stranger closes his notebook and goes upstairs. The door of Room 4 shuts behind him.</i>"),
            ["ev.red"] = ("<i>光线变红了。你突然很想记住点什么。</i>", "<i>The light turns red. You badly want to remember something.</i>"),
            ["ev.wrongnote"] = ("<i>钢琴在同一个地方弹错了一个音。</i>", "<i>The piano hits a wrong note. Same place as always.</i>"),

            // ---------- 物件与碎片 ----------
            ["p.clock"] = ("看那座钟", "Look at the clock"),
            ["f.clock"] = ("落地钟停在三点整。钟摆在走，指针不动。", "The grandfather clock reads three exactly. The pendulum swings; the hands don't move."),
            ["f.clock.r"] = ("三点整。永远是三点整。", "Three o'clock. Always three o'clock."),
            ["p.mirror"] = ("看镜子", "Look in the mirror"),
            ["f.mirror"] = ("镜子里没有你。只有一个没有脸的木头人偶，穿着你的围裙，和你一起抬起手。", "You aren't in the mirror. A faceless wooden mannequin in your apron raises its hand when you do."),
            ["f.mirror.lag"] = ("镜子里的人偶抬手——比你慢了半拍。", "The mannequin in the mirror raises its hand—half a beat behind you."),
            ["f.mirror.r"] = ("你不敢再看镜子太久。", "You don't look in the mirror for long anymore."),
            ["p.door"] = ("推门", "Push the door"),
            ["f.door"] = ("门外的街道在阳光里一动不动，连尘土都悬在半空，像一幅画在布上的背景。你没有迈出去。", "The street outside is perfectly still in the sun. Even the dust hangs in midair, like a painted backdrop. You don't step out."),
            ["f.door.r"] = ("你知道外面什么都没有。", "You know there's nothing out there."),
            ["p.glass"] = ("看杯子", "Look at the glass"),
            ["f.glass"] = ("杯沿的缺口在老地方。昨天你明明换了一只新杯子——缺口跟着它一起换过来了。", "The chip in the rim is where it always is. Yesterday you swapped it for a new glass—the chip came along."),
            ["f.glass.r"] = ("这只杯子在等你发现什么。", "This glass is waiting for you to notice something."),
            ["p.calendar"] = ("翻日历", "Flip the calendar"),
            ["f.calendar"] = ("你一页一页往后翻。每一页都是：1882 年 6 月 14 日。", "You flip page after page. Every one reads: June 14, 1882."),
            ["f.calendar.r"] = ("6 月 14 日。你开始怀疑没有 15 日。", "June 14. You begin to doubt there is a 15th."),
            ["p.letter"] = ("拉开抽屉", "Open the drawer"),
            ["f.letter"] = ("抽屉里有一封信，写着你的名字。笔迹是你自己的。\n“别信钟。去四号房。”", "In the drawer, a letter with your name on it. The handwriting is yours.\n\"Don't trust the clock. Go to Room 4.\""),
            ["f.letter.r"] = ("“别信钟。去四号房。”你什么时候写的？", "\"Don't trust the clock. Go to Room 4.\" When did you write this?"),
            ["f.letter.locked"] = ("抽屉卡住了。你从没想过要打开它。", "The drawer is stuck. It never occurred to you to open it."),
            ["p.notebook"] = ("看笔记本", "Read the notebook"),
            ["f.notebook"] = ("笔记本摊开着。最后一行墨迹还没干：\n“她会走过来，看这本笔记本。”", "The notebook lies open. The last line is still wet:\n\"She'll come over and read this notebook.\""),
            ["f.notebook.r"] = ("他在写你接下来要做的事。", "He writes down what you're about to do."),
            ["p.dartboard"] = ("看飞镖靶", "Look at the dartboard"),
            ["f.dartboard"] = ("三支飞镖扎在同一个洞里。每天都是。", "Three darts in the same hole. Every day."),
            ["p.bottles"] = ("看酒瓶", "Look at the bottles"),
            ["f.bottles"] = ("标签上的字你每天都读，却从来想不起写的是什么。", "You read these labels every day and can never recall what they say."),

            // ---------- 二楼四号房 ----------
            ["p.room4"] = ("开门", "Open the door"),
            ["f.room4.locked"] = ("四号房锁着。门缝里有很轻的、规律的咔哒声，像打字机。", "Room 4 is locked. Through the gap comes a faint, steady clicking, like a typewriter."),
            ["f.room4.crane"] = ("门锁着。陌生人刚刚进去，可里面听不到脚步声。", "Locked. The stranger just went in, but there are no footsteps inside."),
            ["f.room4.open"] = ("你记得的东西够多了。门锁自己弹开了。", "You remember enough now. The lock clicks open by itself."),
            ["p.typewriter"] = ("看打字机", "Look at the typewriter"),
            ["f.typewriter"] = ("屋里没有人。打字机在自己打字，纸上写着：\n“……内尔推开了四号房的门，看见了打字机。这是第 {0} 稿。她终于醒了。”", "The room is empty. The typewriter types by itself:\n\"...Nell opened the door of Room 4 and saw the typewriter. This is draft {0}. At last, she woke up.\""),

            // ---------- 后门 ----------
            ["p.backdoor"] = ("拉开门闩", "Lift the latch"),
            ["f.backdoor.locked"] = ("后门的门闩锈死了。你从没见过谁用这扇门。", "The back door latch is rusted shut. You've never seen anyone use it."),
            ["f.backdoor.open"] = ("门闩松了。门外……什么都没有。", "The latch gives. Outside there is... nothing."),
            ["f.void"] = ("<i>没有天，没有地。只有一张还没画完的格子纸。</i>", "<i>No sky, no ground. Only unfinished graph paper.</i>"),

            // ---------- 对话：格斯 ----------
            ["d.gus.hello"] = ("今天怎么样，格斯？", "How's the day, Gus?"),
            ["r.gus.hello"] = ("今天会是个好日子，内尔。", "Gonna be a fine day, Nell."),
            ["d.gus.martha"] = ("你刚才叫我玛莎？", "You called me Martha?"),
            ["r.gus.martha"] = ("……今天会是个好日子，内尔。\n<i>他擦杯子的手停了一秒。</i>", "...Gonna be a fine day, Nell.\n<i>His hand stops on the glass for a second.</i>"),
            ["f.name"] = ("<i>他叫过你“玛莎”。玛莎是谁？上一个站在这个吧台后面的人？</i>", "<i>He called you \"Martha\". Who's Martha? Whoever stood behind this bar before you?</i>"),
            ["d.gus.who"] = ("玛莎是谁？", "Who is Martha?"),
            ["r.gus.who"] = ("今天会是个好日子，内尔。今天会是个好日子，内尔。今天会是——\n<i>他卡住了。</i>", "Gonna be a fine day, Nell. Gonna be a fine day, Nell. Gonna be—\n<i>He's stuck.</i>"),

            // ---------- 对话：教授 ----------
            ["d.prof.hello"] = ("这首曲子叫什么？", "What's this tune called?"),
            ["r.prof.hello"] = ("没有名字。它只有开头，我从没弹到过结尾。", "It hasn't got a name. It only has a beginning. I've never reached the end."),
            ["d.prof.wrong"] = ("你刚才弹错了一个音。", "You hit a wrong note just now."),
            ["r.prof.wrong"] = ("错了吗？那一定是 {0}。我每次都在同一个地方……失手。", "Did I? Must have been {0}. Same spot every time... a slip of the hand."),
            ["f.piano"] = ("<i>他每次都在同一处弹错一个音。这一次是 {0}。</i>", "<i>He fumbles the same spot every time. This time it was {0}.</i>"),
            ["d.prof.onpurpose"] = ("你是故意弹错的。", "You're doing it on purpose."),
            ["r.prof.onpurpose"] = ("总得有人记住些什么。你记下来了吗？C、A、G……", "Someone has to remember something. Did you write them down? C, A, G..."),
            ["f.cage"] = ("<i>C、A、G、E。CAGE——笼子。</i>", "<i>C, A, G, E. CAGE.</i>"),
            ["d.prof.notyet"] = ("你在提醒我什么？", "What are you trying to tell me?"),
            ["r.prof.notyet"] = ("多听几遍。一遍只够听到一个字母。", "Listen a few more times. Each time is only enough for one letter."),

            // ---------- 对话：陌生人 ----------
            ["d.crane.hello"] = ("要再来一杯吗，先生？", "Another drink, mister?"),
            ["r.crane.hello"] = ("不用。我只是来看看这一稿写得怎么样。", "No. I'm just here to see how this draft turned out."),
            ["d.crane.writing"] = ("你在写什么？", "What are you writing?"),
            ["r.crane.writing"] = ("<i>他把笔记本转过来给你看。最后一行墨迹还没干：</i>\n“她会问我在写什么。”", "<i>He turns the notebook toward you. The last line is still wet:</i>\n\"She'll ask what I'm writing.\""),
            ["d.crane.you"] = ("你在写我。", "You're writing me."),
            ["r.crane.you"] = ("不。我在读你。写你的人不在这里。", "No. I'm reading you. The one who writes you isn't here."),
            ["d.crane.fine"] = ("这里一切都很好。", "Everything here is fine."),
            ["r.crane.fine"] = ("<i>他看了你很久，合上笔记本。</i>\n那就照这样写。", "<i>He looks at you for a long time, then closes the notebook.</i>\nThen we'll keep it this way."),
            ["d.crane.room4"] = ("四号房里是什么？", "What's in Room 4?"),
            ["r.crane.room4"] = ("你知道的事够多了，门自然会开。", "When you know enough, the door will open on its own."),

            // ---------- 结局 ----------
            ["end.reset"] = ("重 置", "R E S E T"),
            ["end.reset.sub"] = ("你选择了留下。明天下午三点见，内尔。", "You chose to stay. See you at three tomorrow, Nell."),
            ["end.escape"] = ("出 逃", "E S C A P E"),
            ["end.escape.sub"] = ("世界只写到这里。你走出了最后一行。", "The world was only written this far. You walked off the last line."),
            ["end.awaken"] = ("觉 醒", "A W A K E"),
            ["frag.clock"] = ("停摆的钟", "The stopped clock"),
            ["frag.mirror"] = ("镜中人偶", "The mannequin in the mirror"),
            ["frag.door"] = ("画布街道", "The painted street"),
            ["frag.glass"] = ("杯沿缺口", "The chipped glass"),
            ["frag.calendar"] = ("6 月 14 日", "June 14"),
            ["frag.letter"] = ("自己的信", "Your own letter"),
            ["frag.notebook"] = ("陌生人的笔记", "The stranger's notes"),
            ["frag.name"] = ("玛莎", "Martha"),
            ["frag.piano"] = ("错音", "The wrong note"),
            ["frag.cage"] = ("C·A·G·E", "C·A·G·E"),
            ["end.awaken.sub"] = ("第 {0} 稿 · 你在 {1} 分 {2} 秒后醒来", "Draft {0} · You woke after {1} min {2} s"),
        };
    }
}
