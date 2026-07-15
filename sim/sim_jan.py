# キョーカンじゃん バランス検証シミュレータ
# 検証項目:
#   1. アガリまでの手番数（ゲーム長）
#   2. 公開セットの役内訳（クラスター/同色/ジョーカー使用率）→ 同色役の死に役疑い
#   3. プレイヤー間のクラスター被り率 → 改訂案v2「共感ボーナス」の発火機会
#   4. 流局率（山札切れ）
import random
from collections import Counter
from statistics import mean, median

CLUSTERS = {
    '赤濃': 'R', '赤爽': 'R', '赤滋': 'R',
    '青華': 'B', '青緑': 'B', '青焙': 'B',
    '黄滑': 'Y', '黄鮮': 'Y', '黄印': 'Y',
    '緑穏': 'G', '緑妙': 'G',
}
JOKER = 'JOKER'


def make_deck(rng):
    deck = [c for c in CLUSTERS for _ in range(12)] + [JOKER] * 4
    rng.shuffle(deck)
    return deck


def best_sets(hand):
    """貪欲法でセット数最大化。クラスター3→ジョーカー補完→同色3の順。
    返り値: (sets, locked)  sets=[(kind, id, jokers_used)], locked=セットに使ったカードのCounter"""
    cnt = Counter(c for c in hand if c != JOKER)
    jokers = hand.count(JOKER)
    sets, locked = [], Counter()
    rem = {}
    for c, n in cnt.items():
        t, r = divmod(n, 3)
        sets += [('cluster', c, 0)] * t
        locked[c] += t * 3
        rem[c] = r
    # ジョーカーでクラスターペアを補完
    for c in sorted(rem, key=lambda x: -rem[x]):
        if jokers > 0 and rem[c] == 2:
            sets.append(('cluster', c, 1))
            locked[c] += 2
            locked[JOKER] += 1
            rem[c] = 0
            jokers -= 1
    # 余りから同色3
    by_color = {}
    for c, n in rem.items():
        by_color.setdefault(CLUSTERS[c], []).extend([c] * n)
    for col, cards in by_color.items():
        while len(cards) >= 3:
            trio = [cards.pop() for _ in range(3)]
            sets.append(('color', col, 0))
            for c in trio:
                locked[c] += 1
        # ジョーカーで同色ペアを補完
        if jokers > 0 and len(cards) == 2:
            sets.append(('color', col, 1))
            for c in cards:
                locked[c] += 1
            locked[JOKER] += 1
            cards.clear()
            jokers -= 1
    return sets, locked


def choose_discard(hand, rng):
    """セットに使っていない余りカードから、クラスター/色のつながりが最も薄い1枚を捨てる"""
    _, locked = best_sets(hand)
    pool = Counter(hand) - locked
    leftovers = [c for c in pool.elements() if c != JOKER]
    if not leftovers:
        leftovers = list(pool.elements())  # ジョーカーしか余っていない（超レア）
        if not leftovers:
            leftovers = [c for c in hand if c != JOKER]
    ccnt = Counter(c for c in hand if c != JOKER)
    colcnt = Counter(CLUSTERS[c] for c in hand if c != JOKER)

    def value(c):
        if c == JOKER:
            return 99
        return (ccnt[c] - 1) * 3 + (colcnt[CLUSTERS[c]] - 1)

    lo = min(value(c) for c in leftovers)
    return rng.choice([c for c in leftovers if value(c) == lo])


def n_win_sets(hand, cluster_only):
    """アガリ判定に使えるセット数"""
    sets, _ = best_sets(hand)
    if cluster_only:
        return sum(1 for kind, _, _ in sets if kind == 'cluster')
    return len(sets)


def play_game(n_players, hand_size, rng, cluster_only=False):
    deck = make_deck(rng)
    hands = [[deck.pop() for _ in range(hand_size)] for _ in range(n_players)]
    turns = 0
    cur = 0
    winner = None
    while deck:
        hand = hands[cur]
        hand.append(deck.pop())
        turns += 1
        if n_win_sets(hand, cluster_only) >= 3:
            winner = cur
            break
        disc = choose_discard(hand, rng)
        hand.remove(disc)
        # キョーカン!（捨て札の即取得）: アガリ用セット数が増えるプレイヤーが下家から順に取る
        stolen = False
        for k in range(1, n_players):
            p = (cur + k) % n_players
            base = n_win_sets(hands[p], cluster_only)
            if n_win_sets(hands[p] + [disc], cluster_only) > base:
                hands[p].append(disc)
                if n_win_sets(hands[p], cluster_only) >= 3:
                    winner = p
                    stolen = True
                    break
                d2 = choose_discard(hands[p], rng)
                hands[p].remove(d2)
                cur = (p + 1) % n_players
                stolen = True
                break
        if winner is not None:
            break
        if not stolen:
            cur = (cur + 1) % n_players
    if winner is None:
        return None  # 流局
    # 最終ラウンド: 他プレイヤーが1手番ずつ
    also_done = 0
    for k in range(1, n_players):
        p = (winner + k) % n_players
        if not deck:
            break
        hands[p].append(deck.pop())
        if n_win_sets(hands[p], cluster_only) >= 3:
            also_done += 1
        else:
            hands[p].remove(choose_discard(hands[p], rng))
    # 一斉開示: 各自の完成セット（最大3）
    revealed = []
    for p in range(n_players):
        s, _ = best_sets(hands[p])
        revealed.append(s[:3])
    return dict(turns=turns, winner=winner, also_done=also_done, revealed=revealed)


def run(n_games=3000, seed=42, cluster_only=False):
    rng = random.Random(seed)
    print(f"\n=== アガリ条件: {'クラスター役3組限定' if cluster_only else '現行（同色役もアガリ可）'} ===")
    print(f"{'人数':>3} {'手札':>3} | {'手番(中央値)':>10} {'周回/人':>7} {'流局%':>5} | "
          f"{'ｸﾗｽﾀ役%':>7} {'同色役%':>7} {'ｼﾞｮｰｶｰ入%':>8} | {'完成セット/人':>10} {'被り機会%':>7} {'滑込%':>5}")
    for n_players in (3, 4, 5):
        for hand_size in (8, 10, 13):
            stats = dict(turns=[], ryukyoku=0, cluster=0, color=0, jokered=0,
                         nsets=[], matched=0, players=0, also=[])
            for _ in range(n_games):
                g = play_game(n_players, hand_size, rng, cluster_only)
                if g is None:
                    stats['ryukyoku'] += 1
                    continue
                stats['turns'].append(g['turns'])
                stats['also'].append(g['also_done'])
                # 役内訳
                for sets in g['revealed']:
                    stats['nsets'].append(len(sets))
                    for kind, _, j in sets:
                        stats[kind] += 1
                        if j:
                            stats['jokered'] += 1
                # クラスター被り（共感ボーナス発火機会）:
                # 自分のクラスター役のクラスターが、他の誰かのクラスター役と一致するか
                clus = [set(cid for kind, cid, _ in sets if kind == 'cluster')
                        for sets in g['revealed']]
                for p in range(n_players):
                    stats['players'] += 1
                    others = set().union(*(clus[q] for q in range(n_players) if q != p))
                    if clus[p] & others:
                        stats['matched'] += 1
            total_sets = stats['cluster'] + stats['color']
            n_ok = len(stats['turns'])
            print(f"{n_players:>4} {hand_size:>4} | {median(stats['turns']):>10.0f} "
                  f"{median(stats['turns'])/n_players:>7.1f} "
                  f"{100*stats['ryukyoku']/n_games:>5.1f} | "
                  f"{100*stats['cluster']/total_sets:>7.1f} {100*stats['color']/total_sets:>7.1f} "
                  f"{100*stats['jokered']/total_sets:>8.1f} | "
                  f"{mean(stats['nsets']):>10.2f} {100*stats['matched']/stats['players']:>7.1f} "
                  f"{100*mean(stats['also'])/(n_players-1):>5.1f}")


if __name__ == '__main__':
    run(cluster_only=False)
    run(cluster_only=True)
