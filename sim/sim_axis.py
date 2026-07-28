# じゃん「色固定」ルール案の成立性シミュレーション
#
# ユーザー案：手札から最も感覚に近い1枚を選ぶ→その色に確定→以降その色だけで役を作る
#   → 味の判断が最初の1枚に集約（せーのと同じ動作）。認知負荷は下がるが、
#      集められる札が36枚(緑24)に絞られて「ジャムる（流局多発）」懸念を実測する。
#
# 比較：
#   free       … 現行v2（色自由・任意クラスター3枚で役）
#   axis_smart … 色固定・手札で最多の色を選ぶ（賢い色選択）
#   axis_naive … 色固定・ランダムな1枚の色（＝感覚が手札分布と無関係な最悪ケース）
#   axis2_*    … 上記の色固定で「アガリ2役」に緩めた版
import random
from collections import Counter
from statistics import median, mean

CC = {'赤濃':'R','赤爽':'R','赤滋':'R','青華':'B','青緑':'B','青焙':'B',
      '黄滑':'Y','黄鮮':'Y','黄印':'Y','緑穏':'G','緑妙':'G'}
CLUSTERS = list(CC)
JOKER = 'J'


def make_deck(rng):
    d = [c for c in CLUSTERS for _ in range(12)] + [JOKER] * 4
    rng.shuffle(d)
    return d


def count_sets(cnt, jok):
    """クラスター→枚数のCounterとジョーカー数から作れる役数（同クラスター3枚、Jで補完）"""
    sets = 0
    rem = {}
    for c, n in cnt.items():
        sets += n // 3
        rem[c] = n % 3
    for c in sorted(rem, key=lambda x: -rem[x]):
        if jok >= 1 and rem[c] == 2:
            sets += 1; rem[c] = 0; jok -= 1
    for c in sorted(rem, key=lambda x: -rem[x]):
        if jok >= 2 and rem[c] == 1:
            sets += 1; rem[c] = 0; jok -= 2
    return sets


def sets_free(hand):
    return count_sets(Counter(c for c in hand if c != JOKER), hand.count(JOKER))


def sets_axis(hand, color):
    return count_sets(Counter(c for c in hand if c != JOKER and CC[c] == color), hand.count(JOKER))


def pick_color(hand, rng, smart):
    cols = [CC[c] for c in hand if c != JOKER]
    if not cols:
        return rng.choice('RBYG')
    if smart:
        cnt = Counter(cols); m = max(cnt.values())
        return rng.choice([col for col, v in cnt.items() if v == m])
    return rng.choice(cols)  # ランダムな1枚＝ナイーブ色選択


def discard_free(hand, rng):
    cnt = Counter(c for c in hand if c != JOKER)
    # 役に絡まない孤立クラスターの余りを捨てる
    leftover = []
    for c, n in cnt.items():
        leftover += [c] * (n % 3)
    if leftover:
        return min(leftover, key=lambda c: cnt[c])
    nonj = [c for c in hand if c != JOKER]
    return rng.choice(nonj) if nonj else JOKER


def discard_axis(hand, color, rng):
    off = [c for c in hand if c != JOKER and CC[c] != color]
    if off:
        return rng.choice(off)  # まず他色を捨てる
    cnt = Counter(c for c in hand if c != JOKER)
    leftover = []
    for c, n in cnt.items():
        leftover += [c] * (n % 3)
    if leftover:
        return min(leftover, key=lambda c: cnt[c])
    nonj = [c for c in hand if c != JOKER]
    return rng.choice(nonj) if nonj else JOKER


def play(n_players, hand_size, rng, mode, target):
    deck = make_deck(rng)
    hands = [[deck.pop() for _ in range(hand_size)] for _ in range(n_players)]
    axis = mode != 'free'
    colors = [pick_color(h, rng, mode == 'axis_smart') for h in hands] if axis else [None] * n_players

    def nsets(p, hand=None):
        h = hand if hand is not None else hands[p]
        return sets_axis(h, colors[p]) if axis else sets_free(h)

    def disc(p):
        return discard_axis(hands[p], colors[p], rng) if axis else discard_free(hands[p], rng)

    cur, turns, winner = 0, 0, None
    while deck:
        hands[cur].append(deck.pop()); turns += 1
        if nsets(cur) >= target:
            winner = cur; break
        d = disc(cur); hands[cur].remove(d)
        stolen = False
        for k in range(1, n_players):
            p = (cur + k) % n_players
            if nsets(p, hands[p] + [d]) > nsets(p):
                hands[p].append(d)
                if nsets(p) >= target:
                    winner = p; stolen = True; break
                hands[p].remove(disc(p)); cur = (p + 1) % n_players; stolen = True; break
        if winner is not None:
            break
        if not stolen:
            cur = (cur + 1) % n_players
    final = [nsets(p) for p in range(n_players)]
    return dict(turns=turns, ryukyoku=winner is None, final=final)


def run(mode, target=3, n_games=3000, seed=1):
    rng = random.Random(seed)
    for n_players in (3, 4, 5):
        for hand in (8, 10):
            turns, ryu, zero, allsets = [], 0, 0, []
            for _ in range(n_games):
                g = play(n_players, hand, rng, mode, target)
                turns.append(g['turns'])
                if g['ryukyoku']: ryu += 1
                for s in g['final']:
                    allsets.append(s)
                    if s == 0: zero += 1
            print(f"  {mode:11s} 役{target} {n_players}人 手札{hand} | "
                  f"手番中央 {median(turns):3.0f} | 流局(ジャム) {100*ryu/n_games:4.1f}% | "
                  f"完成役0の人 {100*zero/len(allsets):4.1f}% | 平均完成役 {mean(allsets):.2f}")


if __name__ == '__main__':
    print("=== 現行v2（色自由）基準 ===")
    run('free', 3)
    print("\n=== 色固定・アガリ3役 ===")
    run('axis_smart', 3)
    run('axis_naive', 3)
    print("\n=== 色固定・アガリ2役に緩和 ===")
    run('axis_smart', 2)
    run('axis_naive', 2)
