# v3色決め打ち：サンプルが偏って「みんな同じ色に行く」ときの成立性
#
# 懸念：全員が同色を選ぶと、
#   ①誰もその色を捨てない → キョーカン!の供給が枯れる
#   ②物理枚数不足（青36枚 vs 5人×役3組9枚=45枚）
# → ジャム（流局）が復活しないかを、色の偏り度 bias で測る。
#   bias=0: 各自が手札最多色を選ぶ（バラつく） / bias=1: 全員が同じ色（青）に強制
from collections import Counter
from statistics import median, mean
import random
from sim_axis import make_deck, sets_axis, discard_axis, pick_color, CC, JOKER


def role_clusters(hand, color):
    cnt = Counter(c for c in hand if c != JOKER and CC[c] == color)
    return {c for c, n in cnt.items() if n >= 3}


def play_bias(n_players, hand, rng, bias, bias_color='B', target=3):
    deck = make_deck(rng)
    hands = [[deck.pop() for _ in range(hand)] for _ in range(n_players)]
    colors = [bias_color if rng.random() < bias else pick_color(h, rng, True)
              for h in hands]

    def nsets(p, h=None):
        return sets_axis(hands[p] if h is None else h, colors[p])

    def disc(p):
        return discard_axis(hands[p], colors[p], rng)

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
    rc = [role_clusters(hands[p], colors[p]) for p in range(n_players)]
    overlap = 0
    for p in range(n_players):
        others = set().union(*(rc[q] for q in range(n_players) if q != p)) if n_players > 1 else set()
        if rc[p] & others:
            overlap += 1
    same_color_all = len(set(colors)) == 1
    return dict(turns=turns, ryu=winner is None, final=final, overlap=overlap,
                sameall=same_color_all)


def run(n_games=3000, seed=3, hand=10):
    rng = random.Random(seed)
    print(f"手札{hand}・役3・各{n_games}ゲーム")
    print(f"{'偏り':>4} {'人数':>3} | {'手番':>4} {'流局(ジャム)':>9} {'役0の人':>7} "
          f"{'平均役':>6} {'ｸﾗｽﾀ被り率':>9} {'全員同色率':>8}")
    for bias in (0.0, 0.5, 0.8, 1.0):
        for n_players in (3, 4, 5):
            T, R, Z, S, O, SA, N = [], 0, 0, [], 0, 0, 0
            for _ in range(n_games):
                g = play_bias(n_players, hand, rng, bias)
                T.append(g['turns'])
                if g['ryu']: R += 1
                for s in g['final']:
                    S.append(s)
                    if s == 0: Z += 1
                O += g['overlap']; N += n_players
                if g['sameall']: SA += 1
            print(f"{bias:>4.1f} {n_players:>4} | {median(T):>4.0f} "
                  f"{100*R/n_games:>8.1f}% {100*Z/len(S):>6.1f}% "
                  f"{mean(S):>6.2f} {100*O/N:>8.1f}% {100*SA/n_games:>7.1f}%")
        print()


if __name__ == '__main__':
    run()
