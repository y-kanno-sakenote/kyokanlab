# じゃんv4案：色自由・役＝同色3枚×3組・最初の1枚必須・同クラスタでボーナス
#
# 検証：
#  ・同色3枚は緩いので「配った瞬間アガリ（初手アガリ）」が多発しないか
#  ・アガリ速度（手番）／流局
#  ・ボーナス（同クラスタまで揃う）率＝ボーナス狙いが機能するか
#  ・端札率＝役に使えない札の割合（＝捨てに判断の余地があるか）
# 参考比較：v2（同クラスタ3枚×3組・色自由）
import random
from collections import Counter
from statistics import median, mean

CL_COLOR = ['R','R','R','B','B','B','Y','Y','Y','G','G']  # クラスタindex→色
JOKER = 99


def make_deck(rng):
    d = [c for c in range(11) for _ in range(12)] + [JOKER]*4
    rng.shuffle(d)
    return d


def count_by(keys, jok):
    """keys=各札のキー（色 or クラスタ）のCounter, jok=ジョーカー数 → 3枚組の最大数"""
    sets = 0
    rem = {}
    for k, n in keys.items():
        sets += n // 3
        rem[k] = n % 3
    for k in sorted(rem, key=lambda x: -rem[x]):
        if jok >= 1 and rem[k] == 2:
            sets += 1; rem[k] = 0; jok -= 1
    for k in sorted(rem, key=lambda x: -rem[x]):
        if jok >= 2 and rem[k] == 1:
            sets += 1; rem[k] = 0; jok -= 2
    return sets


def sets_v4(hand):   # 同色3枚
    return count_by(Counter(CL_COLOR[c] for c in hand if c != JOKER), hand.count(JOKER))


def sets_v2(hand):   # 同クラスタ3枚
    return count_by(Counter(c for c in hand if c != JOKER), hand.count(JOKER))


def detail_v4(hand):
    """v4の役を、同クラスタ優先で組んだときの (総役数, ボーナス役数, 端札数)"""
    jok = hand.count(JOKER)
    ccnt = Counter(c for c in hand if c != JOKER)
    bonus = 0; used = Counter()
    for c in sorted(ccnt, key=lambda x: -ccnt[x]):
        while ccnt[c] - used[c] >= 3:
            bonus += 1; used[c] += 3
    # 残りを色でまとめて基本役
    rest = []
    for c, n in ccnt.items():
        rest += [c] * (n - used[c])
    colcnt = Counter(CL_COLOR[c] for c in rest)
    base = count_by(colcnt, jok)
    total = bonus + base
    # 端札：色でも3枚に満たない余り
    colrem = {col: n % 3 for col, n in colcnt.items()}
    tan = sum(colrem.values())
    return total, bonus, tan


def discard_v4(hand, anchor_color, rng):
    """役に使えない端を捨てる。端がなければ最少色の1枚。anchorの色は温存。"""
    ccnt = Counter(c for c in hand if c != JOKER)
    colcnt = Counter(CL_COLOR[c] for c in hand if c != JOKER)
    cand = [c for c in hand if c != JOKER]
    if not cand:
        return JOKER
    def val(c):
        col = CL_COLOR[c]
        base = colcnt[col]                 # その色が手札に何枚あるか（多いほど残す）
        if col == anchor_color: base += 3  # アンカー色は温存
        return base * 3 + ccnt[c]          # 同クラスタも少し重視
    lo = min(val(c) for c in cand)
    return rng.choice([c for c in cand if val(c) == lo])


def discard_v2(hand, anchor_color, rng):
    ccnt = Counter(c for c in hand if c != JOKER)
    cand = [c for c in hand if c != JOKER] or [JOKER]
    def val(c):
        if c == JOKER: return 99
        return ccnt[c]
    lo = min(val(c) for c in cand)
    return rng.choice([c for c in cand if val(c) == lo])


def can_win(hand, mode):
    if mode == 'v2':
        return sets_v2(hand) >= 3
    t, b, _ = detail_v4(hand)
    if mode == 'v4a':      # 3組＋うち1組は同クラスタ必須
        return t >= 3 and b >= 1
    return t >= 3          # v4：同色3枚×3組のみ


def progress(hand, mode):  # キョーカン用：役数が増えるか
    return sets_v2(hand) if mode == 'v2' else detail_v4(hand)[0]


def play(n_players, hand_size, rng, mode):
    deck = make_deck(rng)
    hands = [[deck.pop() for _ in range(hand_size)] for _ in range(n_players)]
    disc = discard_v2 if mode == 'v2' else discard_v4
    anchors = []
    for h in hands:
        cc = Counter(CL_COLOR[c] for c in h if c != JOKER)
        anchors.append(cc.most_common(1)[0][0] if cc else 'R')
    initial_win = sum(1 for h in hands if can_win(h, mode))
    cur, turns, winner = 0, 0, None
    while deck:
        hands[cur].append(deck.pop()); turns += 1
        if can_win(hands[cur], mode):
            winner = cur; break
        d = disc(hands[cur], anchors[cur], rng); hands[cur].remove(d)
        stolen = False
        for k in range(1, n_players):
            q = (cur + k) % n_players
            if progress(hands[q] + [d], mode) > progress(hands[q], mode):
                hands[q].append(d)
                if can_win(hands[q], mode):
                    winner = q; stolen = True; break
                hands[q].remove(disc(hands[q], anchors[q], rng)); cur = (q + 1) % n_players
                stolen = True; break
        if winner is not None: break
        if not stolen: cur = (cur + 1) % n_players
    finals = [progress(h, mode) for h in hands]
    tot = bon = tan = 0
    for h in hands:
        if mode.startswith('v4'):
            t, b, tn = detail_v4(h); tot += t; bon += b; tan += tn
    return dict(turns=turns, ryu=winner is None, initwin=initial_win,
                finals=finals, tot=tot, bon=bon, tan=tan, handsum=hand_size*n_players)


def run(mode, n_games=3000, seed=5):
    rng = random.Random(seed)
    print(f"--- {mode} ---")
    print(f"{'人数':>3}{'手札':>4} | {'手番':>4} {'初手ｱｶﾞﾘ':>7} {'流局':>5} {'平均役':>6} "
          f"{'ﾎﾞｰﾅｽ率':>7} {'端札率':>6}")
    for np_ in (3, 4, 5):
        for hs in (8, 10):
            T, R, IW, S, TOT, BON, TAN = [], 0, 0, [], 0, 0, 0
            for _ in range(n_games):
                g = play(np_, hs, rng, mode)
                T.append(g['turns'])
                if g['ryu']: R += 1
                IW += g['initwin']
                S += g['finals']
                TOT += g['tot']; BON += g['bon']; TAN += g['tan']
            bz = f"{100*BON/TOT:>6.1f}%" if TOT else "   —  "
            tz = f"{100*TAN/(hs*np_*n_games):>5.1f}%" if mode.startswith('v4') else "   — "
            print(f"{np_:>3}{hs:>4} | {median(T):>4.0f} {100*IW/(np_*n_games):>6.1f}% "
                  f"{100*R/n_games:>4.1f}% {mean(S):>6.2f} {bz} {tz}")


if __name__ == '__main__':
    run('v4')    # 同色3枚×3組のみ
    print()
    run('v4a')   # ＋うち1組は同クラスタ必須
    print()
    run('v2')    # 参考：同クラスタ3枚×3組
