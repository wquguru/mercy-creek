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
            if (args.Length > 0) s = string.Format(s, args);
            // 界面字体是静态图集，<i> 会报错且不生效：旁白改用暖灰色区分
            return s.Replace("<i>", "<color=#d4c2a2>").Replace("</i>", "</color>");
        }

        public static bool Has(string key) => Table.ContainsKey(key);

        /// <summary>"格斯：……"</summary>
        public static string Line(string speakerKey, string key, params object[] args) =>
            $"<color=#e8c48a>{T(speakerKey)}</color>{T("ui.colon")}{T(key, args)}";

        static readonly Dictionary<string, (string zh, string en)> Table = new()
        {
            // ---------- 界面 ----------
            ["ui.colon"] = ("：", ": "),
            ["ui.loop"] = ("Mercy Creek · 第 {0} 稿", "Mercy Creek · Draft {0}"),
            ["ui.memory"] = ("记忆 {0} · Tab 打开记忆本", "Memories {0} · Tab to review"),
            ["ui.remembered"] = ("<i>（你决定记住这个。）</i>", "<i>(You decide to remember this.)</i>"),
            ["ui.full"] = ("<i>（你隐约知道，这一稿记不住更多了。）</i>", "<i>(Somehow you know this draft will hold no more.)</i>"),
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
            ["menu.hint"] = ("WASD 移动 · Shift 快走 · E 交互 · 1–4 选择对话 · Tab 记忆本 · Esc 暂停", "WASD move · Shift hurry · E interact · 1–4 choose · Tab memories · Esc pause"),
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
            ["name.driver"] = ("车夫", "The Driver"),
            ["name.townsfolk"] = ("镇民", "Townsfolk"),

            // ---------- 时间表 ----------
            ["ev.start"] = ("下午三点。你手里是那只有缺口的杯子。", "Three o'clock. In your hand, the chipped glass."),
            ["ev.gus.day"] = ("今天会是个好日子，内尔。", "Gonna be a fine day, Nell."),
            ["ev.gus.slip"] = ("今天会是个好日子，玛莎——内尔。", "Gonna be a fine day, Martha—Nell."),
            ["ev.repeat"] = ("<i>他刚才说过一模一样的话。一字不差。</i>", "<i>He just said that. Word for word.</i>"),
            ["ev.door"] = ("<i>门被推开。一个陌生人走进来，靴子上全是土。</i>", "<i>The door swings open. A stranger walks in, boots caked in dust.</i>"),
            ["ev.crane.glance"] = ("<i>他在门口停了一下，看了你一眼。像是认出了你。</i>", "<i>He pauses in the doorway and looks at you. As if he knows you.</i>"),
            ["ev.crane.order"] = ("威士忌。", "Whiskey."),
            ["ev.crane.early"] = ("你比上一稿醒得早。", "You woke earlier than last draft."),
            ["ev.crane.clock"] = ("钟又停在三点了。", "Clock's stopped at three again."),
            ["ev.crane.leave"] = ("<i>陌生人合上笔记本，上了楼。四号房的门在他身后关上。</i>", "<i>The stranger closes his notebook and goes upstairs. The door of Room 4 shuts behind him.</i>"),
            ["ev.red"] = ("<i>光线变红了。你突然很想记住点什么。</i>", "<i>The light turns red. Suddenly you want to hold on to something.</i>"),
            ["ev.red1"] = ("<i>光线变红了。这个下午快结束了——你得记住点什么，带到下一稿。</i>", "<i>The light turns red. The afternoon is ending—remember something, and carry it into the next draft.</i>"),
            ["ev.wrongnote"] = ("<i>钢琴在同一个地方弹错了一个音。</i>", "<i>The piano hits a wrong note. Same place as always.</i>"),

            // ---------- 物件与碎片 ----------
            ["p.clock"] = ("看那座钟", "Look at the clock"),
            ["f.clock"] = ("落地钟停在三点整。钟摆在走，指针不动。", "The grandfather clock stands at three sharp. The pendulum swings; the hands do not."),
            ["f.clock.r"] = ("三点整。永远是三点整。", "Three o'clock. Always three o'clock."),
            ["p.mirror"] = ("看镜子", "Look in the mirror"),
            ["f.mirror"] = ("镜子里没有你。只有一个没有脸的木头人偶，穿着你的围裙，和你一起抬起手。\n你回头看格斯、看教授——他们也都没有脸。你一直都知道吗？", "You aren't in the mirror. A faceless wooden mannequin in your apron raises its hand when you do.\nYou turn to Gus, to the Professor—none of them have faces. Have you always known?"),
            ["f.mirror.lag"] = ("镜子里的人偶抬手——比你慢了半拍。", "The mannequin in the mirror raises its hand—half a beat behind you."),
            ["f.mirror.r"] = ("你不敢再看镜子太久。", "You don't look in the mirror for long anymore."),
            ["p.door"] = ("推门", "Push the door"),
            ["f.door"] = ("门外的街道在阳光里一动不动，连尘土都悬在半空，像一幅画在布上的背景。你没有迈出去。", "The street outside is perfectly still in the sun. Even the dust hangs in midair, like a backdrop painted on canvas. You don't step out."),
            ["f.door.r"] = ("你知道外面什么都没有。", "You know there's nothing out there."),
            ["p.glass"] = ("看杯子", "Look at the glass"),
            ["f.glass"] = ("杯沿的缺口在老地方。昨天你明明换了一只新杯子——缺口跟着它一起换过来了。", "The chip in the rim is where it always is. You're sure you took a new glass yesterday—the chip came with it."),
            ["f.glass.r"] = ("这只杯子在等你发现什么。", "This glass is waiting for you to notice something."),
            ["p.calendar"] = ("翻日历", "Flip the calendar"),
            ["f.calendar"] = ("你一页一页往后翻。每一页都是：1882 年 6 月 14 日。", "You flip page after page. Every one reads: June 14, 1882."),
            ["f.calendar.r"] = ("6 月 14 日。你开始怀疑没有 15 日。", "June 14. You begin to doubt there is a 15th."),
            ["p.letter"] = ("拉开抽屉", "Open the drawer"),
            ["f.letter"] = ("抽屉里有一封信，写着你的名字。笔迹是你自己的。\n“别信钟。去四号房。”", "In the drawer, a letter with your name on it. The handwriting is yours.\n\"Don't trust the clock. Go to Room 4.\""),
            ["f.letter.r"] = ("“别信钟。去四号房。”你什么时候写的？", "\"Don't trust the clock. Go to Room 4.\" When did you write this?"),
            ["f.letter.locked"] = ("抽屉卡住了。你从没想过要打开它。", "The drawer is stuck. You've never once thought to open it."),
            ["p.notebook"] = ("看笔记本", "Read the notebook"),
            ["f.notebook"] = ("笔记本摊开着。最后一行墨迹还没干：\n“她会走过来，看这本笔记本。”", "The notebook lies open. The last line is still wet:\n\"She'll come over and read this notebook.\""),
            ["f.notebook.r"] = ("他在写你接下来要做的事。", "He's writing down what you're about to do."),
            ["p.dartboard"] = ("看飞镖靶", "Look at the dartboard"),
            ["f.dartboard"] = ("三支飞镖扎在同一个洞里。每天都是。", "Three darts in the same hole. Every day."),
            ["p.bottles"] = ("看酒瓶", "Look at the bottles"),
            ["f.bottles"] = ("标签上的字你每天都读，却从来想不起写的是什么。", "You read these labels every day and can never recall what they say."),

            // ---------- 二楼四号房 ----------
            ["p.room4"] = ("开门", "Open the door"),
            ["f.room4.locked"] = ("四号房锁着。门缝里有很轻的、规律的咔哒声，像打字机。", "Room 4 is locked. Through the crack comes a faint, steady clicking, like a typewriter."),
            ["f.room4.crane"] = ("门锁着。陌生人刚刚进去，可里面听不到脚步声。", "Locked. The stranger just went in, yet you hear no footsteps inside."),
            ["f.room4.open"] = ("你记得的东西够多了。门锁自己弹开了。", "You remember enough now. The lock clicks open by itself."),
            ["p.typewriter"] = ("看打字机", "Look at the typewriter"),
            ["f.typewriter"] = ("屋里没有人。打字机在自己打字，纸上写着：\n“……内尔推开了四号房的门，看见了打字机。这是第 {0} 稿。她终于醒了。”", "The room is empty. The typewriter is typing on its own:\n\"...Nell opened the door of Room 4 and saw the typewriter. This is Draft {0}. At last, she woke.\""),

            // ---------- 后门 ----------
            ["p.backdoor"] = ("拉开门闩", "Lift the latch"),
            ["f.backdoor.locked"] = ("后门的门闩锈死了。你从没见过谁用这扇门。", "The back door latch is rusted shut. You've never seen anyone use it."),
            ["f.backdoor.open"] = ("门闩松了。门外……什么都没有。", "The latch gives. Outside there is... nothing."),
            ["f.void"] = ("<i>没有天，没有地。只有一张还没画完的格子纸。</i>", "<i>No sky, no ground. Only a sheet of graph paper, half drawn.</i>"),

            // ---------- 对话：格斯 ----------
            ["d.gus.hello"] = ("今天怎么样，格斯？", "How's the day looking, Gus?"),
            ["r.gus.hello"] = ("今天会是个好日子，内尔。", "Gonna be a fine day, Nell."),
            ["d.gus.martha"] = ("你刚才叫我玛莎？", "You called me Martha?"),
            ["r.gus.martha"] = ("……今天会是个好日子，内尔。\n<i>他擦杯子的手停了一秒。</i>", "...Gonna be a fine day, Nell.\n<i>His rag stops on the glass for a second.</i>"),
            ["f.name"] = ("<i>他叫过你“玛莎”。玛莎是谁？上一个站在这个吧台后面的人？</i>", "<i>He called you \"Martha\". Who's Martha? The one who stood behind this bar before you?</i>"),
            ["d.gus.who"] = ("玛莎是谁？", "Who is Martha?"),
            ["r.gus.who"] = ("今天会是个好日子，内尔。今天会是个好日子，内尔。今天会是——\n<i>他卡住了。</i>", "Gonna be a fine day, Nell. Gonna be a fine day, Nell. Gonna be—\n<i>He's stuck.</i>"),

            // ---------- 对话：教授 ----------
            ["d.prof.hello"] = ("这首曲子叫什么？", "What's this tune called?"),
            ["r.prof.hello"] = ("没有名字。它只有开头，我从没弹到过结尾。", "It hasn't got a name. Only a beginning. I've never once played it to the end."),
            ["d.prof.wrong"] = ("你刚才弹错了一个音。", "You hit a wrong note just now."),
            ["r.prof.wrong"] = ("错了吗？那一定是 {0}。我每次都在同一个地方……失手。", "Did I? Must have been {0}. Same spot every time... a slip of the hand."),
            ["f.piano"] = ("<i>他每次都在同一处弹错一个音。这一次是 {0}。</i>", "<i>He fumbles the same spot every time. This time it was {0}.</i>"),
            ["d.prof.onpurpose"] = ("你是故意弹错的。", "You miss that note on purpose."),
            ["r.prof.onpurpose"] = ("总得有人记住些什么。你记下来了吗？C、A、G……", "Somebody's got to remember something. Did you keep them? C, A, G..."),
            ["f.cage"] = ("<i>C、A、G、E。CAGE——笼子。</i>", "<i>C, A, G, E. CAGE.</i>"),
            ["d.prof.notyet"] = ("你在提醒我什么？", "What are you trying to tell me?"),
            ["r.prof.notyet"] = ("多听几遍。一遍只够听到一个字母。", "Listen a few more times. You'll only catch one letter each time through."),

            // ---------- 对话：陌生人 ----------
            ["d.crane.hello"] = ("要再来一杯吗，先生？", "Another drink, mister?"),
            ["r.crane.hello"] = ("不用。我只是来看看这一稿写得怎么样。", "No. Just here to see how this draft reads."),
            ["d.crane.writing"] = ("你在写什么？", "What are you writing?"),
            ["r.crane.writing"] = ("<i>他把笔记本转过来给你看。最后一行墨迹还没干：</i>\n“她会问我在写什么。”", "<i>He turns the notebook toward you. The last line is still wet:</i>\n\"She'll ask what I'm writing.\""),
            ["d.crane.you"] = ("你在写我。", "You're writing me."),
            ["r.crane.you"] = ("不。我在读你。写你的人不在这里。", "No. I'm reading you. The one who writes you isn't here."),
            ["d.crane.fine"] = ("这里一切都很好。", "Everything here is fine."),
            ["r.crane.fine"] = ("<i>他看了你很久，合上笔记本。</i>\n那就照这样写。", "<i>He looks at you for a long time, then closes the notebook.</i>\nThen it stays as written."),
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
            ["end.awaken.sub"] = ("第 {0} 稿 · 你在 {1} 分 {2} 秒后醒来", "Draft {0} · You woke after {1} min {2} sec"),
            ["frag.telegram"] = ("作废的电报", "The telegram"),
            ["frag.grave"] = ("玛莎的墓", "Martha's grave"),

            // ---------- 记忆本 ----------
            ["book.title"] = ("记 忆 本", "W H A T   Y O U   R E M E M B E R"),
            ["book.time"] = ("第 {0} 稿 · 这个下午还剩 {1}:{2:00}", "Draft {0} · {1}:{2:00} left this afternoon"),
            ["book.empty"] = ("（还什么都没记住）", "(Nothing remembered yet)"),
            ["book.next"] = ("下一步", "Next"),
            ["book.close"] = ("Tab 关闭", "Tab to close"),
            ["frag.clock.d"] = ("钟停在三点，钟摆却在走。", "The clock reads three; the pendulum still swings."),
            ["frag.mirror.d"] = ("镜子里的你，是一个没有脸的木头人偶。", "In the mirror, you are a faceless wooden mannequin."),
            ["frag.door.d"] = ("外面的世界是画上去的。", "The world outside is painted."),
            ["frag.glass.d"] = ("杯沿的缺口永远在同一个地方。", "The chip in the glass never moves."),
            ["frag.calendar.d"] = ("每一页都是 1882 年 6 月 14 日。", "Every page reads June 14, 1882."),
            ["frag.letter.d"] = ("你自己写的信：别信钟。去四号房。", "A letter in your own hand: don't trust the clock. Go to Room 4."),
            ["frag.notebook.d"] = ("陌生人在笔记本上写你接下来要做的事。", "The stranger writes down what you'll do next."),
            ["frag.name.d"] = ("格斯叫过你“玛莎”。", "Gus once called you \"Martha\"."),
            ["frag.piano.d"] = ("教授每一稿都在同一处弹错一个音。", "Every draft, the Professor fumbles a note at the same spot."),
            ["frag.cage.d"] = ("C、A、G、E——笼子。", "C, A, G, E—a cage."),
            ["frag.telegram.d"] = ("电报上说：上一稿作废了。", "The telegram says the last draft was void."),
            ["frag.grave.d"] = ("玛莎的墓碑旁，还有一块空白的。", "Beside Martha's headstone stands a blank one."),
            ["hint.none"] = ("每个下午只能记住一件事。找找这里不对劲的地方。", "You can only keep one thing each afternoon. Look for what's wrong here."),
            ["hint.awaken"] = ("你记得够多了。四号房的门在等你。", "You remember enough. Room 4 is waiting."),
            ["hint.escape"] = ("连日子都是假的。去街道西头，撕开那块画布。", "Even the date is false. Go to the west end of the street and tear open the canvas."),
            ["hint.calendar"] = ("画布挡住了路。要是连时间也是假的……", "The canvas blocks the road. If even time is false..."),
            ["hint.street"] = ("街道是真的吗？走到西头看看。", "Is the street real? Walk to its west end."),
            ["hint.count"] = ("记住四件事，四号房的门就会打开（{0}/4）。", "Remember four things and Room 4 will open ({0}/4)."),

            // ---------- 稿数卡 / 开场 ----------
            ["card.void"] = ("第 {0} 稿 —— 作废", "Draft {0} — void"),
            ["card.draft"] = ("第 {0} 稿", "Draft {0}"),
            ["card.skip"] = ("按任意键继续", "Press any key"),
            ["intro.1"] = ("MERCY CREEK · 第 {0} 稿", "MERCY CREEK · Draft {0}"),
            ["intro.2"] = ("1882 年 6 月 14 日，下午三点。", "June 14, 1882. Three in the afternoon."),
            ["intro.3"] = ("酒馆女招待内尔站在吧台后，手里是那只有缺口的杯子。", "Nell, who serves at the saloon, stands behind the bar, the chipped glass in her hand."),
            ["intro.4"] = ("她不知道，这个下午已经写过十一遍了。", "She doesn't know this afternoon has been written eleven times before."),
            ["menu.endday"] = ("结束这个下午", "End this afternoon"),

            // ---------- 街道（第 2 稿起） ----------
            ["ev.street"] = ("<i>……又是这个下午。可这一次，门外传来了马蹄声。街道好像被写出来了。</i>", "<i>...This afternoon again. But this time there are hoofbeats outside. Somehow, the street has been written in.</i>"),
            ["ev.hooves"] = ("<i>门外传来马蹄声和车轮声，停在了门口。</i>", "<i>Hoofbeats and the roll of wheels outside. They stop at the door.</i>"),
            ["ev.townsfolk"] = ("<i>街上的人偶，一个接一个转过头来看你。</i>", "<i>One by one, the mannequins in the street turn their heads toward you.</i>"),
            ["p.canvas"] = ("看画布", "Look at the canvas"),
            ["f.canvas"] = ("街道尽头立着一块巨大的画布，上面画着继续往西的路。颜料早就干了。你永远走不到那里。", "At the end of the street stands a vast canvas, painted with the road going on west. The paint is long dry. You will never reach it."),
            ["f.canvas.r"] = ("画布后面有风。画布后面……有什么？", "Wind seeps from behind the canvas. Behind it... what?"),
            ["p.canvas.tear"] = ("撕开画布", "Tear the canvas"),
            ["f.canvas.tear"] = ("你抓住画布的接缝，用力一扯。后面……什么都没有。", "You grab the seam and pull. Behind it there is... nothing."),
            ["p.telegraph"] = ("看电报机", "Look at the telegraph"),
            ["f.telegram"] = ("电报机自己咔哒作响，吐出一截纸带：\n“致克兰先生：第 {0} 稿作废。女招待已改名。请检查第 {1} 稿。——作者”", "The telegraph clacks on its own and spits out a strip of tape:\n\"To Mr. Crane: Draft {0} void. Barmaid renamed. Kindly review Draft {1}. —The Author\""),
            ["f.telegram.r"] = ("电报机还在响。作者还在改。", "The telegraph is still clacking. The author is still revising."),
            ["p.grave"] = ("看墓碑", "Read the headstone"),
            ["f.grave"] = ("墓碑上刻着：“玛莎 · 卒于 1882 年 6 月 14 日。”\n旁边还有一块新立的墓碑，上面一个字都没有。", "The headstone reads: \"Martha · Died June 14, 1882.\"\nBeside it stands a new headstone with nothing written on it."),
            ["f.grave.r"] = ("空白墓碑前的土是新翻的。", "The earth before the blank stone is freshly turned."),
            ["p.graveblank"] = ("看空白的墓碑", "Look at the blank headstone"),
            ["f.graveblank"] = ("一块空白的墓碑。土是新翻的。它在等一个名字。", "A blank headstone over fresh earth. It is waiting for a name."),
            ["p.tbd"] = ("看门上的纸条", "Read the note"),
            ["f.tbd"] = ("门上钉着一张纸条，墨迹很新：“待写。”", "A note is nailed to the door, the ink still fresh: \"To be written.\""),
            ["p.coach"] = ("看马车", "Look at the coach"),
            ["f.coach"] = ("车厢里空无一人。座位上压着一张车票：“Mercy Creek——单程。”", "The coach is empty. A ticket lies on the seat: \"Mercy Creek — one way.\""),
            ["p.horse"] = ("看马", "Look at the horse"),
            ["f.horse"] = ("两匹木头马，关节处磨得发亮。作者还没给它们画上皮毛。", "Two wooden horses, joints worn shiny. The author hasn't painted their coats yet."),
            ["p.driver"] = ("看车夫", "Look at the driver"),
            ["f.driver"] = ("车夫一动不动地坐着。他从来不下车。", "The driver sits perfectly still. He never gets down."),
            ["p.townsfolk"] = ("看他", "Look at them"),
            ["f.townsfolk"] = ("他停在半步之间，像作者写到一半，忘了他。", "Frozen mid-step, as if the author forgot them halfway through a sentence."),
            ["f.townsfolk.3"] = ("你走过的时候，那颗木头脑袋跟着你转了过来。", "As you pass, the wooden head turns to follow you."),
            ["p.sheet"] = ("看乐谱", "Look at the sheet music"),
            ["f.sheet"] = ("乐谱上有人用铅笔圈了几个音：{0}。页边写着一行小字：“连起来读。”", "Someone has circled notes in pencil: {0}. In the margin: \"Read them together.\""),
            ["f.sheet.empty"] = ("乐谱干干净净。只在第十六小节的一个音符上方，有一个铅笔点。", "The sheet music is clean, save for a pencil dot above one note in bar sixteen."),
            ["d.crane.telegram"] = ("谁给你发的电报？", "Who sends you the telegrams?"),
            ["r.crane.telegram"] = ("写这个故事的人。他总觉得这个下午还不对。", "The one writing this story. He keeps thinking this afternoon isn't right yet."),
            ["d.gus.grave"] = ("玛莎死了吗？", "Is Martha dead?"),
            ["r.gus.grave"] = ("……没有谁死了，内尔。只是被划掉了。", "...Nobody died, Nell. She just got crossed out."),
        };
    }
}
