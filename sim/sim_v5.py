# じゃんv5案「軸1枚＋3セット／軸は伏せて最後に一斉」の成立性シミュレーション
#
# ルール案：
#   手札10 = 軸1枚（最初に選び伏せる。以降固定）＋ working 9枚
#   ターン：1枚引いて10→いらない1枚捨てて9
#   アガリ：同クラスタ3枚×3組（軸のクラスタである必要はない）
#   得点：役1本／その役のクラスタが「誰かの軸」と一致で1本／言葉まで一致でさらに1本
#         ＋先アガリ1本
#
# 検証したいこと：
#   ・アガリ速度（手番）と流局
#   ・軸的中率＝自分の役が誰かの軸と一致する率（低すぎると空振り感／高すぎると自明）
#   ・ピタ率（言葉まで一致）
#   ・🥒分布と0本率（feel-bad）
#   ・人数・知覚ノイズσ・サンプルの語の明瞭さαへの感度
import math, random
from collections import Counter
from statistics import mean, median

CLUSTER_WORDS = {
    '赤濃': ['甘い','コク','濃厚'],          '赤爽': ['酸っぱい','さっぱり','フルーティ'],
    '赤滋': ['苦い','うま味','香ばしい'],     '青華': ['花の香り','果実様','甘い香り'],
    '青緑': ['ハーブ','グリーンな香り','木の香り'], '青焙': ['スパイシー','コーヒー','香り高い'],
    '黄滑': ['なめらか','まろやか','クリーミー'],   '黄鮮': ['しっとり','すっきり','みずみずしい'],
    '黄印': ['とろける','ぷちぷち','シャープ'],     '緑穏': ['バランス','きれい','やさしい'],
    '緑妙': ['余韻','奥深い','不思議'],
}
CLUSTERS = list(CLUSTER_WORDS)
JOKER = 'J'
HAND = 10          # 軸1枚を含む
WORK = HAND - 1    # 軸を除いた実働枚数
TARGET = 3


def make_deck(rng):
    d = [c for c in CLUSTERS for _ in range(12)] + [JOKER] * 4
    rng.shuffle(d)
    return d


def make_sample(rng, alpha):
    prof = {}
    for c in CLUSTERS:
        strength = math.exp(rng.gauss(0, 1.0))
        sh = [rng.gammavariate(alpha, 1) + 1e-9 for _ in range(3)]
        t = sum(sh)
        for w, s in zip(CLUSTER_WORDS[c], sh):
            prof[w] = strength * s / t
    return prof


class Player:
    def __init__(self, name, prof, rng, sigma):
        self.name = name
        per = {w: v * math.exp(rng.gauss(0, sigma)) for w, v in prof.items()}
        self.felt_word = {c: max(CLUSTER_WORDS[c], key=per.get) for c in CLUSTERS}
        cs = {c: sum(per[w] for w in CLUSTER_WORDS[c]) for c in CLUSTERS}
        self.rank = {c: i for i, c in enumerate(sorted(CLUSTERS, key=cs.get, reverse=True))}  # 0=最も強く感じた
        self.hand = []          # working（軸を除く）
        self.anchor = None      # 軸のクラスタ
        self.locked = []        # キョーカン公開ぶん（クラスタ）
        self.cukes = 0


def build_sets(hand, rank):
    """同クラスタ3枚の役を貪欲に。強く感じたクラスタ（＝他人も感じているはず）を優先"""
    cnt = Counter(c for c in hand if c != JOKER)
    jok = hand.count(JOKER)
    order = sorted(cnt, key=lambda c: (rank[c], -cnt[c]))
    sets, used = [], Counter()
    for c in sorted(cnt, key=lambda c: (-cnt[c], rank[c])):
        while cnt[c] - used[c] >= 3:
            sets.append(c); used[c] += 3
    for c in order:                       # ジョーカーで補完
        if jok >= 1 and cnt[c] - used[c] == 2:
            sets.append(c); used[c] += 2; jok -= 1
    for c in order:
        if jok >= 2 and cnt[c] - used[c] == 1:
            sets.append(c); used[c] += 1; jok -= 2
    return sets


def n_sets(p, extra=None):
    h = p.hand + ([extra] if extra else [])
    return len(p.locked) + len(build_sets(h, p.rank))


def discard(p, rng):
    """役に使えない端を捨てる。強く感じたクラスタ（狙い）は温存"""
    cnt = Counter(c for c in p.hand if c != JOKER)
    used = Counter()
    for c in sorted(cnt, key=lambda c: (-cnt[c], p.rank[c])):
        used[c] = (cnt[c] // 3) * 3
    leftovers = []
    for c, n in cnt.items():
        leftovers += [c] * (n - used[c])
    cand = leftovers or [c for c in p.hand if c != JOKER] or p.hand
    # 枚数が少なく・弱く感じたクラスタから捨てる
    return min(cand, key=lambda c: (cnt.get(c, 0) * 3 - p.rank.get(c, 99) * 0.1))


def play_round(players, rng):
    deck = make_deck(rng)
    n = len(players)
    for p in players:
        dealt = [deck.pop() for _ in range(HAND)]
        # 軸＝配られた中で「最も強く感じたクラスタ」の1枚（正直に選ぶ）。無ければ任意
        nonj = [c for c in dealt if c != JOKER]
        p.anchor = min(nonj, key=lambda c: p.rank[c]) if nonj else CLUSTERS[0]
        dealt.remove(p.anchor)
        p.hand = dealt          # working 9枚
        p.locked = []
    cur, turns, winner = 0, 0, None
    while deck:
        p = players[cur]
        p.hand.append(deck.pop()); turns += 1
        if n_sets(p) >= TARGET:
            winner = cur; break
        d = discard(p, rng); p.hand.remove(d)
        stolen = False
        for k in range(1, n):                      # キョーカン（下家優先）
            q = players[(cur + k) % n]
            if n_sets(q, extra=d) > n_sets(q):
                q.hand.append(d)
                if n_sets(q) >= TARGET:
                    winner = players.index(q); stolen = True; break
                q.hand.remove(discard(q, rng))
                cur = (players.index(q) + 1) % n; stolen = True; break
        if winner is not None: break
        if not stolen: cur = (cur + 1) % n
    # 最終ラウンド1巡
    if winner is not None:
        for k in range(1, n):
            q = players[(winner + k) % n]
            if not deck: break
            q.hand.append(deck.pop())
            if n_sets(q) < TARGET: q.hand.remove(discard(q, rng))
    return winner, turns, deck


def score_round(players, winner, use_color=False):
    """軸プールと照合：役1／(色一致1)／クラスタ一致1／言葉まで一致1（＋先アガリ1）"""
    n = len(players)
    finals = [(p.locked + build_sets(p.hand, p.rank))[:TARGET] for p in players]
    gains = []
    st = dict(col=0, hit=0, pita=0, tot=0, any_hit_players=0)
    for i, p in enumerate(players):
        g = len(finals[i]); st['tot'] += len(finals[i]); got = False
        for cl in finals[i]:
            oth = [q for j, q in enumerate(players) if j != i]
            if use_color and any(q.anchor[0] == cl[0] for q in oth):   # 先頭文字＝色
                g += 1; st['col'] += 1
            same = [q for q in oth if q.anchor == cl]
            if same:
                g += 1; st['hit'] += 1; got = True
                if any(q.felt_word[cl] == p.felt_word[cl] for q in same):
                    g += 1; st['pita'] += 1
        if got: st['any_hit_players'] += 1
        if winner == i: g += 1
        gains.append(g)
    for p, g in zip(players, gains):
        p.cukes += g
    return gains, finals, st


def run(n_games=2000, n_players=4, sigma=0.6, alpha=0.3, seed=11, label='', use_color=False):
    rng = random.Random(seed)
    T, G, ryu, zero, slots, hitp = [], [], 0, 0, 0, 0
    S = Counter()
    anchor_div = []
    for _ in range(n_games):
        prof = make_sample(rng, alpha)
        ps = [Player(f'P{i}', prof, rng, sigma) for i in range(n_players)]
        w, t, deck = play_round(ps, rng)
        T.append(t)
        if w is None: ryu += 1
        g, finals, st = score_round(ps, w, use_color)
        G += g
        for k, v in st.items(): S[k] += v
        slots += n_players
        zero += sum(1 for x in g if x == 0)
        anchor_div.append(len({p.anchor for p in ps}))
    print(f"{label:14s} {n_players}人 σ={sigma} α={alpha} | 手番 {median(T):3.0f} | 流局 {100*ryu/n_games:4.1f}% "
          f"| 🥒/R {mean(G):4.2f} (0本 {100*zero/slots:4.1f}%) "
          f"| 色一致 {100*S['col']/S['tot']:4.1f}% 軸的中 {100*S['hit']/S['tot']:4.1f}% ピタ {100*S['pita']/S['tot']:4.1f}% "
          f"| 誰かの軸を当てた人 {100*S['any_hit_players']/slots:4.1f}%")


if __name__ == '__main__':
    print('=== v5案A：役1・クラスタ一致1・言葉1（色ティアなし） ===')
    for np_ in (3, 4, 5):
        run(n_players=np_, label='基準')
    print()
    print('=== v5案B：役1・色一致1・クラスタ一致1・言葉1（せーのと同じ階段） ===')
    for np_ in (3, 4, 5):
        run(n_players=np_, label='基準', use_color=True)
    print()
    for sg in (0.3, 1.0):
        run(n_players=4, sigma=sg, label='知覚ばらつき', use_color=True)
    run(n_players=4, alpha=2.0, label='語が曖昧', use_color=True)
