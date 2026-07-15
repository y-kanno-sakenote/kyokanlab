# キョーカンじゃん v2（正方形カード・きゅうり統一得点）フルルール・テストプレイ
#
# 知覚モデル:
#   サンプル = 33語の強度プロファイル（クラスター強度 × クラスター内の語配分）
#   プレイヤー = プロファイル × 対数正規ノイズ(σ) で知覚し、各クラスターの最強語を「感じた言葉」とする
#   宣言は正直（感じた言葉を上にする）= v2の設計上の最適戦略
#
# 検証項目:
#   ・被り/ピタの発生率（知覚ノイズσ・サンプルの語の明瞭さαへの感度）
#   ・きゅうり獲得分布と0本率（feel-bad指標）
#   ・10本先取の到達ラウンド数
#   ・先アガリがきゅうり首位も取る率（レースと共感のバランス）
import math
import random
from collections import Counter
from statistics import mean, median

CLUSTER_WORDS = {
    '赤濃': ['甘い', 'コク', '濃厚'],
    '赤爽': ['酸っぱい', 'さっぱり', 'フルーティ'],
    '赤滋': ['苦い', 'うま味', '香ばしい'],
    '青華': ['花の香り', '果実様', '甘い香り'],
    '青緑': ['ハーブ', 'グリーンな香り', '木の香り'],
    '青焙': ['スパイシー', 'コーヒー', '香り高い'],
    '黄滑': ['なめらか', 'まろやか', 'クリーミー'],
    '黄鮮': ['しっとり', 'すっきり', 'みずみずしい'],
    '黄印': ['とろける', 'ぷちぷち', 'シャープ'],
    '緑穏': ['バランス', 'きれい', 'やさしい'],
    '緑妙': ['余韻', '奥深い', '不思議'],
}
CLUSTERS = list(CLUSTER_WORDS)
JOKER = 'J'
HAND = 8
TARGET_CUKES = 10
MAX_ROUNDS = 3


def make_sample(rng, alpha):
    """サンプルの真の姿。alpha小=各クラスターに「明瞭な1語」がある / alpha大=語が曖昧"""
    profile = {}
    for c in CLUSTERS:
        strength = math.exp(rng.gauss(0, 1.0))
        shares = [rng.gammavariate(alpha, 1) + 1e-9 for _ in range(3)]
        total = sum(shares)
        for w, s in zip(CLUSTER_WORDS[c], shares):
            profile[w] = strength * s / total
    return profile


class Player:
    def __init__(self, name, profile, rng, sigma):
        self.name = name
        perceived = {w: v * math.exp(rng.gauss(0, sigma)) for w, v in profile.items()}
        self.felt = {c: max(CLUSTER_WORDS[c], key=perceived.get) for c in CLUSTERS}
        cs = {c: sum(perceived[w] for w in CLUSTER_WORDS[c]) for c in CLUSTERS}
        ranked = sorted(CLUSTERS, key=cs.get)
        self.strength_rank = {c: i / (len(CLUSTERS) - 1) for i, c in enumerate(ranked)}
        self.hand = []
        self.locked = []  # キョーカン!で公開済みのクラスター
        self.cukes = 0


def extract_sets(hand, rank):
    """(セットのクラスターリスト, 余りリスト) 感じ方が強いクラスターを優先してジョーカーを配分"""
    cnt = Counter(c for c in hand if c != JOKER)
    jok = hand.count(JOKER)
    order = sorted(cnt, key=lambda c: -rank[c])
    sets, rem = [], {}
    for c in order:
        t, r = divmod(cnt[c], 3)
        sets += [c] * t
        rem[c] = r
    for c in order:
        if jok >= 1 and rem[c] == 2:
            sets.append(c)
            rem[c] = 0
            jok -= 1
    for c in order:
        if jok >= 2 and rem[c] == 1:
            sets.append(c)
            rem[c] = 0
            jok -= 2
    leftovers = [c for c in rem for _ in range(rem[c])] + [JOKER] * jok
    return sets, leftovers


def n_sets(p, extra=None):
    hand = p.hand + ([extra] if extra else [])
    return len(p.locked) + len(extract_sets(hand, p.strength_rank)[0])


def discard(p, rng):
    _, leftovers = extract_sets(p.hand, p.strength_rank)
    cand = [c for c in leftovers if c != JOKER] or leftovers
    cnt = Counter(c for c in p.hand if c != JOKER)

    def value(c):
        if c == JOKER:
            return 99
        return (cnt[c] - 1) * 3 + 2 * p.strength_rank[c]

    lo = min(value(c) for c in cand)
    pick = rng.choice([c for c in cand if abs(value(c) - lo) < 1e-9])
    p.hand.remove(pick)
    return pick


def lock_set(p, card):
    """捨て札cardでクラスター役を完成→公開して固定"""
    need = 2
    while need and card in p.hand:
        p.hand.remove(card)
        need -= 1
    while need:
        p.hand.remove(JOKER)
        need -= 1
    p.locked.append(card)


def play_round(players, rng, log=None):
    """1ラウンド=1サンプル。returns (winner_index or None, turns)"""
    deck = [c for c in CLUSTERS for _ in range(12)] + [JOKER] * 4
    rng.shuffle(deck)
    for p in players:
        p.hand = [deck.pop() for _ in range(HAND)]
        p.locked = []
    n = len(players)
    cur, turns, winner = 0, 0, None
    while deck:
        p = players[cur]
        p.hand.append(deck.pop())
        turns += 1
        if n_sets(p) >= 3:
            winner = cur
            if log is not None:
                log.append(f"T{turns} {p.name}：ツモって「**アガリ！**」")
            break
        d = discard(p, rng)
        if log is not None:
            log.append(f"T{turns} {p.name}：ツモ→捨て[{d}]")
        stolen = False
        for k in range(1, n):  # 下家優先
            q = players[(cur + k) % n]
            if n_sets(q, extra=d) > n_sets(q):
                lock_set(q, d)
                if log is not None:
                    log.append(f"　　→ {q.name}「**キョーカン！**」 [{d}]の役を公開（紋章上向き・言葉は秘密）")
                if n_sets(q) >= 3:
                    winner = players.index(q)
                    if log is not None:
                        log.append(f"　　→ そのまま3組目、{q.name}「**アガリ！**」")
                else:
                    discard(q, rng)
                    cur = (players.index(q) + 1) % n
                stolen = True
                break
        if winner is not None:
            break
        if not stolen:
            cur = (cur + 1) % n
    # 最終ラウンド（1巡）
    if winner is not None:
        for k in range(1, n):
            q = players[(winner + k) % n]
            if not deck:
                break
            q.hand.append(deck.pop())
            if n_sets(q) < 3:
                discard(q, rng)
    return winner, turns


def score_round(players, winner, log=None):
    """一斉開示ときゅうり3スイープ＋投票。returns 各人の獲得本数リスト"""
    n = len(players)
    revealed = []
    for p in players:
        sets, _ = extract_sets(p.hand, p.strength_rank)
        clusters = (p.locked + sets)[:3]
        revealed.append(clusters)
        if log is not None:
            disp = '　'.join(f"[{c}↑{p.felt[c]}]" for c in clusters) or '（役なし）'
            log.append(f"{p.name}：{disp}")
    gained = [0] * n
    for i, p in enumerate(players):
        gained[i] += len(revealed[i])  # 役1
        for c in set(revealed[i]):
            others = [j for j in range(n) if j != i and c in revealed[j]]
            if others:
                gained[i] += 1  # 被り1
                if any(players[j].felt[c] == p.felt[c] for j in others):
                    gained[i] += 1  # ピタ1
    if winner is not None:
        gained[winner] += 1  # 先アガリ
    # 投票: 自分と最も深く合った人へ
    votes = Counter()
    for i, p in enumerate(players):
        best, best_a = None, -1
        for j in range(n):
            if j == i:
                continue
            a = 0
            for c in set(revealed[i]) & set(revealed[j]):
                a += 2 if players[j].felt[c] == p.felt[c] else 1
            if a > best_a:
                best, best_a = j, a
        votes[best] += 1
    top = max(votes.values())
    winners_of_vote = [j for j, v in votes.items() if v == top]
    gained[winners_of_vote[0]] += 1  # 同数は先勝ち（簡略化）
    for i, p in enumerate(players):
        p.cukes += gained[i]
    return gained, revealed


def run_stats(n_games=600, n_players=4, sigma=0.6, alpha=0.3, seed=7):
    rng = random.Random(seed)
    turns_all, gained_all, zero_rate = [], [], 0
    kabu, pita, races = 0, 0, []
    end_round = Counter()
    slots = 0
    for _ in range(n_games):
        profile = make_sample(rng, alpha)
        players = [Player(f"P{i}", profile, rng, sigma) for i in range(n_players)]
        leader_hits = 0
        for rd in range(1, MAX_ROUNDS + 1):
            winner, turns = play_round(players, rng)
            turns_all.append(turns)
            gained, revealed = score_round(players, winner)
            gained_all += gained
            zero_rate += sum(1 for g in gained if g == 0)
            slots += n_players
            for i in range(n_players):
                cl = set(revealed[i])
                if any(cl & set(revealed[j]) for j in range(n_players) if j != i):
                    kabu += 1
                    if any(players[j].felt[c] == players[i].felt[c]
                           for c in cl for j in range(n_players)
                           if j != i and c in revealed[j]):
                        pita += 1
            if winner is not None and rd == 1:
                races.append(winner)
            if max(p.cukes for p in players) >= TARGET_CUKES:
                end_round[rd] += 1
                break
        else:
            end_round['3R満了'] += 1
        if races and races[-1] is not None:
            leader = max(range(n_players), key=lambda i: players[i].cukes)
            leader_hits = int(leader == races[-1])
        run_stats.race_hits = getattr(run_stats, 'race_hits', 0) + leader_hits
    print(f"σ={sigma} α={alpha} {n_players}人 | 手番中央値 {median(turns_all):.0f}"
          f" | きゅうり/R {mean(gained_all):.2f}本 (0本率 {100*zero_rate/slots:.1f}%)"
          f" | 被り率 {100*kabu/slots:.0f}% ピタ率 {100*pita/slots:.0f}%"
          f" | 10本到達: R2まで {100*(end_round[1]+end_round[2])/n_games:.0f}%"
          f" R3 {100*end_round[3]/n_games:.0f}% 未達 {100*end_round['3R満了']/n_games:.0f}%"
          f" | 1R先アガリ=最終首位 {100*run_stats.race_hits/n_games:.0f}%")
    run_stats.race_hits = 0


def transcript(seed=11, n_players=3, sigma=0.6, alpha=0.3):
    rng = random.Random(seed)
    profile = make_sample(rng, alpha)
    names = ['あかり', 'ばん', 'ちよ']
    players = [Player(names[i], profile, rng, sigma) for i in range(n_players)]
    lines = ["# キョーカンじゃん v2 テストプレイ実況（シミュレーション卓）", ""]
    top = sorted(profile, key=profile.get, reverse=True)[:5]
    lines.append(f"サンプルの真の姿（神視点）：{'、'.join(top)}")
    for p in players:
        strong = sorted(CLUSTERS, key=lambda c: -p.strength_rank[c])[:3]
        felt = '、'.join(f"{c}={p.felt[c]}" for c in strong)
        lines.append(f"- {p.name}の感じ方（強い順）：{felt}")
    lines.append("")
    total = Counter()
    for rd in (1, 2):
        lines.append(f"## ラウンド{rd}")
        log = []
        winner, turns = play_round(players, rng, log)
        lines += log
        lines.append("")
        lines.append("### 一斉開示（↑=上にした言葉）")
        gained, _ = score_round(players, winner, lines)
        lines.append("")
        lines.append("### きゅうり")
        for p, g in zip(players, gained):
            lines.append(f"- {p.name}：+{g}本（累計{p.cukes}本）")
        lines.append("")
        if max(p.cukes for p in players) >= TARGET_CUKES:
            lines.append(f"**{max(players, key=lambda p: p.cukes).name}が10本到達！ゲーム終了**")
            break
    return '\n'.join(lines)


if __name__ == '__main__':
    print("== パラメータ感度（4人・600ゲーム×3R）==")
    for sigma in (0.3, 0.6, 1.0):
        for alpha in (0.3, 2.0):
            run_stats(sigma=sigma, alpha=alpha)
    print("\n== 人数感度（σ=0.6 α=0.3）==")
    for np_ in (3, 5):
        run_stats(n_players=np_)
    with open('testplay_transcript.md', 'w') as f:
        f.write(transcript())
    print("\n実況ログ → testplay_transcript.md")
