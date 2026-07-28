# 記号共通化で可能になった新役のシミュレーション
#
# カードは 色×記号：0=あか○ 1=あか〰 2=あか☆ 3=あお○ 4=あお〰 5=あお☆
#                  6=き○  7=き〰  8=き☆  9=みどり＋ 10=みどり□   99=ジョーカー
# 役の候補：
#   同カード  … 同じ色・同じ記号 ×3（現行v4の役）
#   三色      … 同じ記号を あか・あお・き で1枚ずつ（＝同じ方向を3つの切り口で感じた）
#   同色そろい … 同じ色で ○〰☆ を1枚ずつ（＝その切り口をひととおり）
#   ※みどりは記号を共有しないので同カード役のみ（麻雀の字牌と同じ扱い）
#
# アガリ：役3組。うち1組は「軸（アンカー）のカードを含む組」（v4条件）
# 測るもの：手番／流局／役の内訳／役0の人／軸条件の達成しやすさ
import random
from itertools import combinations_with_replacement
from collections import Counter
from statistics import median, mean

JOKER = 99
NC = 11
COLOR_OF = [0,0,0,1,1,1,2,2,2,3,3]   # 0=あか 1=あお 2=き 3=みどり
SYM_OF   = [0,1,2,0,1,2,0,1,2,3,4]   # 0=○ 1=〰 2=☆ 3=＋ 4=□

TRIPLE = [('同カード', {c:3}, {c}) for c in range(NC)]
TRICOL = [('三色', {s:1, s+3:1, s+6:1}, {s, s+3, s+6}) for s in (0,1,2)]
RUN    = [('同色そろい', {b:1, b+1:1, b+2:1}, {b, b+1, b+2}) for b in (0,3,6)]


def build_types(tricolor, run):
    t = list(TRIPLE)
    if tricolor: t += TRICOL
    if run:      t += RUN
    return t


def feasible(need, have, jok):
    """need=クラスタ→必要枚数。手札haveとジョーカーで満たせるか"""
    short = 0
    for c, n in need.items():
        d = n - have[c]
        if d > 0:
            short += d
            if short > jok: return False
    return True


def merge(sets):
    need = {}
    for _, req, _ in sets:
        for c, n in req.items():
            need[c] = need.get(c, 0) + n
    return need


def analyze(hand, anchor, types, target=3, max_mixed=99):
    """(達成できる最大役数, アガリ可否, 役の内訳)。アガリ＝target組・軸を含む組あり・混成役はmax_mixed組まで"""
    have = [0]*NC; jok = 0
    for c in hand:
        if c == JOKER: jok += 1
        else: have[c] += 1
    best_k, best_plan = 0, []
    win = False
    for k in range(target, 0, -1):
        found = None
        for combo in combinations_with_replacement(types, k):
            if sum(1 for nm, _, _ in combo if nm != '同カード') > max_mixed: continue
            if not feasible(merge(combo), have, jok): continue
            if found is None: found = combo
            if k == target and any(anchor in cov for _, _, cov in combo):
                win = True; found = combo; break
        if found is not None:
            best_k, best_plan = k, list(found)
            break
    return best_k, win, best_plan


def used_clusters(plan):
    u = Counter()
    for _, req, _ in plan:
        for c, n in req.items(): u[c] += n
    return u


def discard(hand, anchor, types, rng):
    """役に使われていない札から捨てる。軸の札は残す"""
    _, _, plan = analyze(hand, anchor, types)
    used = used_clusters(plan)
    have = Counter(c for c in hand if c != JOKER)
    left = []
    for c, n in have.items():
        left += [c] * max(0, n - used[c])
    if not left:
        left = [c for c in hand if c != JOKER] or [JOKER]
    cnt = Counter(c for c in hand if c != JOKER)
    return min(left, key=lambda c: (c == anchor) * 10 + cnt[c] * 2 + (COLOR_OF[c] == COLOR_OF[anchor]))


def make_deck(rng):
    d = [c for c in range(NC) for _ in range(12)] + [JOKER]*4
    rng.shuffle(d)
    return d


def play(n_players, hand_size, rng, types):
    deck = make_deck(rng)
    hands = [[deck.pop() for _ in range(hand_size)] for _ in range(n_players)]
    anchors = []
    for h in hands:
        nonj = [c for c in h if c != JOKER]
        anchors.append(rng.choice(nonj) if nonj else 0)
    cur, turns, winner = 0, 0, None
    while deck:
        hands[cur].append(deck.pop()); turns += 1
        k, win, _ = analyze(hands[cur], anchors[cur], types)
        if win:
            winner = cur; break
        d = discard(hands[cur], anchors[cur], types, rng)
        hands[cur].remove(d)
        stolen = False
        for j in range(1, n_players):
            q = (cur + j) % n_players
            k0, _, _ = analyze(hands[q], anchors[q], types)
            k1, w1, _ = analyze(hands[q] + [d], anchors[q], types)
            if w1 or k1 > k0:
                hands[q].append(d)
                if w1:
                    winner = q; stolen = True; break
                hands[q].remove(discard(hands[q], anchors[q], types, rng))
                cur = (q + 1) % n_players; stolen = True; break
        if winner is not None: break
        if not stolen: cur = (cur + 1) % n_players
    finals = []
    for p in range(n_players):
        k, _, plan = analyze(hands[p], anchors[p], types)
        finals.append((k, plan))
    return dict(turns=turns, ryu=winner is None, finals=finals, winner=winner)


def run(label, tricolor, run_, n_games=500, hand_size=10, seed=17):
    types = build_types(tricolor, run_)
    rng = random.Random(seed)
    for n_players in (3, 4, 5):
        T, ryu, kinds, ks, zero, slots = [], 0, Counter(), [], 0, 0
        for _ in range(n_games):
            g = play(n_players, hand_size, rng, types)
            T.append(g['turns'])
            if g['ryu']: ryu += 1
            for k, plan in g['finals']:
                ks.append(k); slots += 1
                if k == 0: zero += 1
                for nm, _, _ in plan: kinds[nm] += 1
        tot = sum(kinds.values()) or 1
        br = ' '.join(f"{nm}{100*v/tot:.0f}%" for nm, v in kinds.most_common())
        print(f"{label:14s} {n_players}人 | 手番 {median(T):3.0f} | 流局 {100*ryu/n_games:4.1f}% "
              f"| 平均役 {mean(ks):.2f} 役0 {100*zero/slots:4.1f}% | {br}")


if __name__ == '__main__':
    print('=== 手札10・アガリ=役3組（うち1組は軸を含む） / 各500ゲーム ===')
    run('①同カードのみ',   False, False)
    print()
    run('②＋三色',         True,  False)
    print()
    run('③＋同色そろい',   False, True)
    print()
    run('④三色＋同色',     True,  True)
