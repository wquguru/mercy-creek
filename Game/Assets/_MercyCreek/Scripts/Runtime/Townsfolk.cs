using UnityEngine;

namespace MercyCreek
{
    /// <summary>
    /// 街上定格的镇民（群演）。第 3 稿起玩家走近时木头脑袋跟着转；第 5 稿起整个身子转过来（docs/GAME_DESIGN.md）。
    /// </summary>
    [RequireComponent(typeof(Npc))]
    public class Townsfolk : MonoBehaviour
    {
        public float notice = 9f;

        Npc _npc;
        Transform _player;
        float _restYaw;

        void Start()
        {
            _npc = GetComponent<Npc>();
            _player = Camera.main ? Camera.main.transform : null;
            _restYaw = transform.eulerAngles.y;
        }

        void Update()
        {
            int loop = LoopMemory.Loop;
            if (loop < 3 || !_player) return;
            var d = _player.position - transform.position; d.y = 0;
            if (d.magnitude > notice || Sfx.Indoors(_player.position)) { _npc.Face(_restYaw); return; }
            _npc.LookAtPlayer(0.5f);
            Story.I?.NoticeTownsfolk();
            if (loop >= 5) _npc.Face(Mathf.Atan2(d.x, d.z) * Mathf.Rad2Deg);
        }
    }
}
