# じゃん「ベースカード＝十字」案のシミュレーション
#
# 案：最初にベースカード1枚を決める（例：あかの○）。
#     以降つくれる役は、ベースの
#        ・色そろい …… ベースと同じ色の3枚（記号は自由）
#        ・記号そろい … ベースと同じ記号の3枚（色は自由）
#     色も記号も揃った3枚（＝ベースとまったく同じカード×3）は特別ボーナス。
#     つまりベースは色×記号グリッド上に「十字」を引き、その中だけで役を作る。
#
# カード：0..10 = あか○ あか〰 あか☆ / あお○ あお〰 あお☆ / き○ き〰 き☆ / みどり＋ みどり□
import random
from collections import Counter
from statistics import median, mean

JOKER = 99
NC = 11
COLOR_OF = [0,0,0,1,1,1,2,2,2,3,3]
SYM_OF   = [0,1,2,0,1,2,0,1,2,3,4]


def make_deck(rng):
    d = [c for c in range(NC) for _ in range(12)] + [JOKER]*4
    rng.shuffle(d)
    return d


def classify(hand, base):
    """十字の内訳： a=色線のみ / s=記号線のみ / x=両方(ベースと同一カード) / j=ジョーカー / out=十字の外"""
    bc, bs = COLOR_OF[base], SYM_OF[base]
    a = s = x = j = out = 0
    for c in hand:
        if c == JOKER: j += 1; continue
        inc, ins = COLOR_OF[c] == bc, SYM_OF[c] == bs
        if inc and ins: x += 1
        elif inc: a += 1
        elif ins: s += 1
        else: out += 1
    return a, s, x, j, out


def max_sets(hand, base, want_bonus=False):
    """作れる役数の最大。want_bonus=Trueなら『同一カード3枚の組を1つ含む』条件つきで最大化"""
    a, s, x, j, _ = classify(hand, base)
    best = -1
    for x1 in range(x+1):                 # ベース同一カードを色線に何枚回すか
        for j1 in range(j+1):             # ジョーカーを色線に何枚回すか
            if want_bonus:
                # 同一カード3枚の組を1つ作る（x と j から3枚）
                for xb in range(min(3, x)+1):
                    jb = 3 - xb
                    if jb > j: continue
                    xr, jr = x - xb, j - jb
                    for x2 in range(xr+1):
                        for j2 in range(jr+1):
                            k = 1 + (a + x2 + j2)//3 + (s + (xr-x2) + (jr-j2))//3
                            best = max(best, k)
            else:
                k = (a + x1 + j1)//3 + (s + (x-x1) + (j-j1))//3
                best = max(best, k)
        if want_bonus: break              # 上の内側ループで網羅済み
    return max(best, 0)


def plan_kinds(hand, base):
    """達成役の内訳を推定（色そろい/記号そろい/同カード）"""
    a, s, x, j, _ = classify(hand, base)
    # 同カード役を優先的に作る
    kinds = Counter()
    xr, jr = x, j
    while xr + jr >= 3 and xr >= 1:
        use_x = min(3, xr); use_j = 3 - use_x
        if use_j > jr: break
        kinds['同カード'] += 1; xr -= use_x; jr -= use_j
    # 残りを色線・記号線へ
    ca = a + xr; cs = s
    kinds['色そろい'] += (ca + jr)//3
    rem = (ca + jr) % 3
    kinds['記号そろい'] += (cs + rem)//3
    return kinds


def discard(hand, base, rng):
    """十字の外の札から捨てる。無ければ端を捨てる"""
    bc, bs = COLOR_OF[base], SYM_OF[base]
    out = [c for c in hand if c != JOKER and COLOR_OF[c] != bc and SYM_OF[c] != bs]
    if out:
        cnt = Counter(out)
        return min(out, key=lambda c: cnt[c])
    inner = [c for c in hand if c != JOKER]
    if not inner: return JOKER
    cnt = Counter(inner)
    # ベースと同一カードは残す
    return min(inner, key=lambda c: (c == base)*10 + cnt[c])


def play(n_players, hand_size, rng, base_aside, target=3):
    deck = make_deck(rng)
    hands = [[deck.pop() for _ in range(hand_size)] for _ in range(n_players)]
    bases = []
    for i, h in enumerate(hands):
        nonj = [c for c in h if c != JOKER]
        b = rng.choice(nonj) if nonj else 0
        bases.append(b)
        if base_aside: h.remove(b)        # ベースは伏せて別置き＝手札から抜く
    cur, turns, winner = 0, 0, None
    while deck:
        hands[cur].append(deck.pop()); turns += 1
        if max_sets(hands[cur], bases[cur]) >= target:
            winner = cur; break
        d = discard(hands[cur], bases[cur], rng); hands[cur].remove(d)
        stolen = False
        for k in range(1, n_players):
            q = (cur + k) % n_players
            if max_sets(hands[q] + [d], bases[q]) > max_sets(hands[q], bases[q]):
                hands[q].append(d)
                if max_sets(hands[q], bases[q]) >= target:
                    winner = q; stolen = True; break
                hands[q].remove(discard(hands[q], bases[q], rng))
                cur = (q + 1) % n_players; stolen = True; break
        if winner is not None: break
        if not stolen: cur = (cur + 1) % n_players
    ks, kinds, bonus = [], Counter(), 0
    for p in range(n_players):
        k = min(max_sets(hands[p], bases[p]), target)
        ks.append(k)
        kd = plan_kinds(hands[p], bases[p])
        tot = 0
        for nm in ('同カード','色そろい','記号そろい'):
            take = min(kd[nm], target - tot)
            if take > 0: kinds[nm] += take; tot += take
        if kd['同カード'] > 0 and k >= 1: bonus += 1
    return dict(turns=turns, ryu=winner is None, ks=ks, kinds=kinds, bonus=bonus)


def run(label, hand_size, base_aside, players=(3,4,5), n_games=600, seed=31):
    rng = random.Random(seed)
    for n in players:
        T, ryu, K, KS, zero, slots, bn = [], 0, Counter(), [], 0, 0, 0
        for _ in range(n_games):
            g = play(n, hand_size, rng, base_aside)
            T.append(g['turns'])
            if g['ryu']: ryu += 1
            KS += g['ks']; slots += n
            zero += sum(1 for x in g['ks'] if x == 0)
            K += g['kinds']; bn += g['bonus']
        tot = sum(K.values()) or 1
        br = ' '.join(f"{nm}{100*K[nm]/tot:.0f}%" for nm in ('色そろい','記号そろい','同カード'))
        print(f"{label:24s} {n}人 | 手番 {median(T):4.0f} | 流局 {100*ryu/n_games:4.1f}% "
              f"| 平均役 {mean(KS):.2f} 役0 {100*zero/slots:4.1f}% | {br} | ボーナス達成 {100*bn/slots:4.1f}%")


if __name__ == '__main__':
    print('=== ベース＝十字案（役3組）／各600ゲーム ===')
    print('A. ベースも手札に含めて役に使える:')
    for hs in (8, 10):
        run(f'ベース使用可 手札{hs}', hs, False)
        print()
    print('B. ベースは伏せて別置き（手札から抜く）:')
    for hs in (10, 11):
        run(f'ベース別置き 手札{hs}', hs, True)
        print()
