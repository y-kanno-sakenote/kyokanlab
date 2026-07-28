# ベース＝十字案 ＋ 緑＝役牌（字牌）扱いのシミュレーション
#
# ・ベースは赤青黄から1枚選ぶ（緑はベースにできない）
# ・役は「ベースの色線3枚」または「ベースの記号線3枚」
# ・加えて【緑は同じカード3枚でいつでも1組にできる】＝麻雀の役牌。十字の外だが特別に許される
#   （理由：全体印象はどの切り口で感じていても共通して湧く）
# ・色も記号も揃った組＝ベースと同一カード3枚は特別ボーナス
#
# 比較対象：緑ワイルド案（緑はどの役にも代用できる＝ジョーカー的）
import random
from collections import Counter
from statistics import median, mean

JOKER = 99
NC = 11
COLOR_OF = [0,0,0,1,1,1,2,2,2,3,3]
SYM_OF   = [0,1,2,0,1,2,0,1,2,3,4]
GREEN = (9, 10)


def make_deck(rng):
    d = [c for c in range(NC) for _ in range(12)] + [JOKER]*4
    rng.shuffle(d)
    return d


def parts(hand, base):
    bc, bs = COLOR_OF[base], SYM_OF[base]
    a = s = x = j = 0
    g = {9:0, 10:0}
    for c in hand:
        if c == JOKER: j += 1; continue
        if c in GREEN: g[c] += 1; continue
        inc, ins = COLOR_OF[c] == bc, SYM_OF[c] == bs
        if inc and ins: x += 1
        elif inc: a += 1
        elif ins: s += 1
    return a, s, x, j, g


def cross_sets(a, s, x, j):
    best = 0
    for x1 in range(x+1):
        for j1 in range(j+1):
            best = max(best, (a+x1+j1)//3 + (s+(x-x1)+(j-j1))//3)
    return best


def max_sets(hand, base, mode):
    """mode: 'yakuhai'（緑は同一3枚で1組）／'wild'（緑はどの役にも代用可）／'none'（緑は使えない）"""
    a, s, x, j, g = parts(hand, base)
    if mode == 'none':
        return cross_sets(a, s, x, j)
    if mode == 'wild':
        return cross_sets(a, s, x, j + g[9] + g[10])
    best = 0
    for jg9 in range(j+1):
        for jg10 in range(j-jg9+1):
            gs = (g[9]+jg9)//3 + (g[10]+jg10)//3
            best = max(best, gs + cross_sets(a, s, x, j-jg9-jg10))
    return best


def kinds_of(hand, base, mode):
    """達成役の内訳（同カード／色そろい／記号そろい／緑）"""
    a, s, x, j, g = parts(hand, base)
    k = Counter()
    if mode == 'yakuhai':
        for gc in GREEN:
            k['緑'] += g[gc]//3
    xr, jr = x, j
    while xr >= 2 and xr + jr >= 3:
        use = min(3, xr); need = 3-use
        if need > jr: break
        k['同カード'] += 1; xr -= use; jr -= need
    ca = a + xr
    k['色そろい'] += (ca+jr)//3
    rem = (ca+jr) % 3
    k['記号そろい'] += (s+rem)//3
    return k


def discard(hand, base, rng, mode):
    bc, bs = COLOR_OF[base], SYM_OF[base]
    def useful(c):
        if c == JOKER: return True
        if c in GREEN: return mode != 'none'
        return COLOR_OF[c] == bc or SYM_OF[c] == bs
    out = [c for c in hand if not useful(c)]
    if out:
        cnt = Counter(out); return min(out, key=lambda c: cnt[c])
    inner = [c for c in hand if c != JOKER] or hand
    cnt = Counter(inner)
    return min(inner, key=lambda c: (c == base)*10 + cnt[c]*2)


def play(n_players, hand_size, rng, mode, target=3):
    deck = make_deck(rng)
    hands = [[deck.pop() for _ in range(hand_size)] for _ in range(n_players)]
    bases = []
    for h in hands:
        cand = [c for c in h if c != JOKER and c not in GREEN]   # 緑はベースにできない
        bases.append(rng.choice(cand) if cand else 0)
    cur, turns, winner = 0, 0, None
    while deck:
        hands[cur].append(deck.pop()); turns += 1
        if max_sets(hands[cur], bases[cur], mode) >= target:
            winner = cur; break
        d = discard(hands[cur], bases[cur], rng, mode); hands[cur].remove(d)
        stolen = False
        for k in range(1, n_players):
            q = (cur+k) % n_players
            if max_sets(hands[q]+[d], bases[q], mode) > max_sets(hands[q], bases[q], mode):
                hands[q].append(d)
                if max_sets(hands[q], bases[q], mode) >= target:
                    winner = q; stolen = True; break
                hands[q].remove(discard(hands[q], bases[q], rng, mode))
                cur = (q+1) % n_players; stolen = True; break
        if winner is not None: break
        if not stolen: cur = (cur+1) % n_players
    ks, K, bonus = [], Counter(), 0
    for p in range(n_players):
        ks.append(min(max_sets(hands[p], bases[p], mode), target))
        kd = kinds_of(hands[p], bases[p], mode)
        tot = 0
        for nm in ('同カード','緑','色そろい','記号そろい'):
            take = min(kd[nm], target-tot)
            if take > 0: K[nm] += take; tot += take
        if kd['同カード'] > 0: bonus += 1
    return dict(turns=turns, ryu=winner is None, ks=ks, K=K, bonus=bonus)


def run(label, hand_size, mode, players=(3,4,5), n_games=600, seed=53):
    rng = random.Random(seed)
    for n in players:
        T, ryu, K, KS, zero, bn = [], 0, Counter(), [], 0, 0
        for _ in range(n_games):
            g = play(n, hand_size, rng, mode)
            T.append(g['turns'])
            if g['ryu']: ryu += 1
            KS += g['ks']; zero += sum(1 for x in g['ks'] if x == 0)
            K += g['K']; bn += g['bonus']
        tot = sum(K.values()) or 1
        br = ' '.join(f"{nm}{100*K[nm]/tot:.0f}%" for nm in ('色そろい','記号そろい','同カード','緑') if K[nm])
        print(f"{label:22s} {n}人 | 手番 {median(T):3.0f} | 流局 {100*ryu/n_games:4.1f}% "
              f"| 平均役 {mean(KS):.2f} 役0 {100*zero/len(KS):4.1f}% | {br} | ボーナス {100*bn/len(KS):4.0f}%")


if __name__ == '__main__':
    print('=== 緑の扱いを比較（ベースは赤青黄のみ／役3組）各600ゲーム ===')
    print('① 緑＝役牌（同じ緑3枚でいつでも1組）:')
    for hs in (10, 9, 8):
        run(f'役牌型 手札{hs}', hs, 'yakuhai', players=(4,))
    print()
    run('役牌型 手札10', 10, 'yakuhai')
    print()
    print('② 緑＝ワイルド（どの役にも代用可）:')
    run('ワイルド型 手札10', 10, 'wild', players=(4,))
    print()
    print('③ 緑は使えない（参考・現状の実質）:')
    run('緑なし 手札10', 10, 'none', players=(4,))
