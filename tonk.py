#!/usr/bin/env python3
"""
Tonk (Tunk) Card Game
Play against the computer in your terminal.

Rules summary:
  - 2 players, 5 cards each
  - Draw, lay spreads (sets/runs), hit table spreads, discard
  - Spreads: 3-4 cards same rank (set) OR 3+ sequential same-suit cards (run)
  - Knock: declare you have the lowest hand (penalty if wrong or tied)
  - Tonk out: play all your cards for a double-value win
  - Natural Tonk: initial hand of 49 or 50 pts = instant double-value win
  - Card values: Ace=1, 2-9=face value, 10/J/Q/K=10
"""

import os
import random
from itertools import combinations

# ── ANSI colours ────────────────────────────────────────────────────────────

class C:
    RED     = '\033[91m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    BLUE    = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN    = '\033[96m'
    WHITE   = '\033[97m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'
    RESET   = '\033[0m'

def red(s):     return f"{C.RED}{s}{C.RESET}"
def green(s):   return f"{C.GREEN}{s}{C.RESET}"
def yellow(s):  return f"{C.YELLOW}{s}{C.RESET}"
def cyan(s):    return f"{C.CYAN}{s}{C.RESET}"
def magenta(s): return f"{C.MAGENTA}{s}{C.RESET}"
def bold(s):    return f"{C.BOLD}{s}{C.RESET}"
def dim(s):     return f"{C.DIM}{s}{C.RESET}"

# ── Card constants ───────────────────────────────────────────────────────────

SUITS      = ['♠', '♥', '♦', '♣']
RANKS      = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
RANK_VAL   = {'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
              '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10}
RANK_IDX   = {r: i for i, r in enumerate(RANKS)}   # A=0 … K=12

# ── Card & Deck ──────────────────────────────────────────────────────────────

class Card:
    __slots__ = ('rank', 'suit', 'value')

    def __init__(self, rank: str, suit: str):
        self.rank  = rank
        self.suit  = suit
        self.value = RANK_VAL[rank]

    def __repr__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __eq__(self, other) -> bool:
        return isinstance(other, Card) and self.rank == other.rank and self.suit == other.suit

    def __hash__(self):
        return hash((self.rank, self.suit))

    def colored(self) -> str:
        s = str(self)
        # pad to width 3 so columns stay aligned (e.g. "10♥" vs " A♠")
        padded = s.rjust(3)
        if self.suit in ('♥', '♦'):
            return f"{C.RED}{padded}{C.RESET}"
        return f"{C.WHITE}{padded}{C.RESET}"


class Deck:
    def __init__(self):
        self.cards: list[Card] = [Card(r, s) for s in SUITS for r in RANKS]
        random.shuffle(self.cards)

    def deal(self, n: int) -> list[Card]:
        hand, self.cards = self.cards[:n], self.cards[n:]
        return hand

    def draw(self) -> Card | None:
        return self.cards.pop(0) if self.cards else None

    def refill_from_discard(self, discard_pile: list[Card]):
        """Reshuffle the discard pile (minus the top card) into the stock."""
        if len(discard_pile) <= 1:
            return
        top = discard_pile[-1]
        refill = discard_pile[:-1]
        random.shuffle(refill)
        self.cards.extend(refill)
        del discard_pile[:-1]          # keep only the top card in discard
        print(yellow("  [Deck exhausted – discard pile reshuffled into stock]"))

    def __len__(self):
        return len(self.cards)

# ── Spread helpers ───────────────────────────────────────────────────────────

def _find_sets(cards: list[Card]) -> list[list[Card]]:
    """All valid sets: 3–4 cards of the same rank."""
    by_rank: dict[str, list[Card]] = {}
    for c in cards:
        by_rank.setdefault(c.rank, []).append(c)
    result = []
    for group in by_rank.values():
        if len(group) >= 3:
            for size in (3, 4):
                for combo in combinations(group, size):
                    result.append(list(combo))
    return result


def _find_runs(cards: list[Card]) -> list[list[Card]]:
    """All valid runs: 3+ consecutive cards of the same suit."""
    by_suit: dict[str, list[Card]] = {}
    for c in cards:
        by_suit.setdefault(c.suit, []).append(c)
    result = []
    seen: set[tuple] = set()
    for suit, group in by_suit.items():
        sorted_g = sorted(group, key=lambda c: RANK_IDX[c.rank])
        n = len(sorted_g)
        for start in range(n):
            run = [sorted_g[start]]
            for j in range(start + 1, n):
                if RANK_IDX[sorted_g[j].rank] == RANK_IDX[run[-1].rank] + 1:
                    run.append(sorted_g[j])
                else:
                    break
            for length in range(3, len(run) + 1):
                for si in range(len(run) - length + 1):
                    sub = run[si:si + length]
                    key = tuple(str(c) for c in sub)
                    if key not in seen:
                        seen.add(key)
                        result.append(sub)
    return result


def find_all_spreads(cards: list[Card]) -> list[list[Card]]:
    return _find_sets(cards) + _find_runs(cards)


def best_spread_combo(cards: list[Card]) -> list[list[Card]]:
    """
    Greedy maximisation: find a non-overlapping combination of spreads
    that removes the most point value from the hand.
    """
    all_sp = find_all_spreads(cards)
    if not all_sp:
        return []

    best: list[list[Card]] = []
    best_pts = 0

    def search(remaining_sp, used_ids, combo, pts):
        nonlocal best, best_pts
        if pts > best_pts:
            best_pts = pts
            best = [s[:] for s in combo]
        for i, sp in enumerate(remaining_sp):
            sp_ids = {id(c) for c in sp}
            if not (sp_ids & used_ids):
                search(
                    remaining_sp[i + 1:],
                    used_ids | sp_ids,
                    combo + [sp],
                    pts + sum(c.value for c in sp),
                )

    search(all_sp, set(), [], 0)
    return best


def spread_type(sp: list[Card]) -> str:
    return 'set' if len({c.rank for c in sp}) == 1 else 'run'


def can_extend(card: Card, spread: dict) -> bool:
    """Check whether *card* can legally be appended to a table spread dict."""
    stype = spread['type']
    scards = spread['cards']
    if stype == 'set':
        existing_suits = {c.suit for c in scards}
        return (card.rank == scards[0].rank
                and len(scards) < 4
                and card.suit not in existing_suits)
    # run
    if card.suit != scards[0].suit:
        return False
    min_idx = min(RANK_IDX[c.rank] for c in scards)
    max_idx = max(RANK_IDX[c.rank] for c in scards)
    ci = RANK_IDX[card.rank]
    return ci == min_idx - 1 or ci == max_idx + 1


def hand_value(cards: list[Card]) -> int:
    return sum(c.value for c in cards)


def spread_to_str(spread: dict) -> str:
    return ' '.join(c.colored() for c in spread['cards'])

# ── Display helpers ──────────────────────────────────────────────────────────

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def rule(ch='─', width=62):
    print(dim(ch * width))


def section(title: str):
    rule()
    print(bold(f"  {title}"))
    rule()

# ── Computer AI ──────────────────────────────────────────────────────────────

class AI:
    """Simple heuristic AI for the computer player."""

    @staticmethod
    def should_knock(hand: list[Card], table_spreads: list[dict]) -> bool:
        return hand_value(hand) <= 15

    @staticmethod
    def choose_draw(hand: list[Card], top_discard: Card | None,
                    table_spreads: list[dict]) -> str:
        """Return 'discard' or 'stock'."""
        if top_discard is None:
            return 'stock'
        temp = hand + [top_discard]
        # useful if it completes a spread
        if find_all_spreads(temp):
            return 'discard'
        # useful if it can extend a table spread
        if any(can_extend(top_discard, s) for s in table_spreads):
            return 'discard'
        # take it if it's low value (≤ 3) to reduce hand total
        if top_discard.value <= 3:
            return 'discard'
        return 'stock'

    @staticmethod
    def choose_discard(hand: list[Card]) -> Card:
        """Discard the highest-value card that isn't part of any spread pair."""
        # mark cards that appear in potential pairs (2-card combos toward a spread)
        useful_ids: set[int] = set()
        for c1, c2 in combinations(hand, 2):
            if c1.rank == c2.rank:
                useful_ids |= {id(c1), id(c2)}
            if (c1.suit == c2.suit
                    and abs(RANK_IDX[c1.rank] - RANK_IDX[c2.rank]) == 1):
                useful_ids |= {id(c1), id(c2)}

        # Sort: discard first from non-useful, then by descending value
        candidates = sorted(hand,
                            key=lambda c: (id(c) in useful_ids, -c.value))
        return candidates[0]

# ── Game ─────────────────────────────────────────────────────────────────────

class Game:
    CARDS_PER_HAND = 5

    def __init__(self):
        self.human_name   = "You"
        self.human_hand:  list[Card] = []
        self.comp_hand:   list[Card] = []
        self.human_score  = 0
        self.comp_score   = 0
        self.table_spreads: list[dict] = []
        self.deck:        Deck = Deck()
        self.discard:     list[Card] = []
        self.round_num    = 0
        self.total_rounds = 5

    # ── Screen ───────────────────────────────────────────────────────────────

    def _header(self):
        clear()
        print()
        rule('═')
        print(bold(cyan(f"  {'TONK':^58}")))
        print(bold(cyan(f"  {'Round ' + str(self.round_num) + ' of ' + str(self.total_rounds):^58}")))
        rule('═')
        print(f"  {green('Your score:')} {self.human_score}   "
              f"{red('Computer score:')} {self.comp_score}   "
              + dim("(lower is better)"))
        rule()
        print()

    def _show_board(self, reveal_computer: bool = False):
        self._header()

        # Computer hand
        if reveal_computer:
            comp_cards = ' '.join(c.colored() for c in self.comp_hand)
            comp_val   = f"  {dim('(' + str(hand_value(self.comp_hand)) + ' pts)')}"
        else:
            comp_cards = ' '.join(dim('[?]') for _ in self.comp_hand)
            comp_val   = ''
        print(f"  {red(bold('Computer'))} ({len(self.comp_hand)} cards):  "
              f"{comp_cards}{comp_val}")
        print()

        # Table spreads
        if self.table_spreads:
            print(f"  {yellow(bold('Table spreads:'))}")
            for i, sp in enumerate(self.table_spreads):
                owner = sp['owner']
                print(f"    [{i + 1}] {sp['type'].upper()} "
                      f"{dim('(' + owner + ')')}:  {spread_to_str(sp)}")
            print()

        # Stock & discard
        top = self.discard[-1] if self.discard else None
        top_s = top.colored() if top else dim('empty')
        print(f"  {yellow('Stock:')} {len(self.deck)} cards    "
              f"{yellow('Discard top:')} {top_s}")
        print()

        # Human hand
        print(f"  {green(bold('Your hand:'))}")
        indexed = '  '.join(
            f"{bold('[' + str(i + 1) + ']')}{c.colored()}"
            for i, c in enumerate(self.human_hand)
        )
        print(f"    {indexed}")
        print(f"    {dim('Hand total: ' + str(hand_value(self.human_hand)) + ' pts')}")
        print()

    # ── Input helpers ────────────────────────────────────────────────────────

    def _prompt(self, msg: str, valid: list[str]) -> str:
        valid_lower = [v.lower() for v in valid]
        while True:
            raw = input(cyan(f"  {msg} ")).strip().lower()
            if raw in valid_lower:
                return raw
            print(red(f"  Invalid – choose from: {', '.join(valid)}"))

    def _pause(self, msg: str = "Press Enter to continue…"):
        input(dim(f"\n  {msg}"))

    # ── Round setup ──────────────────────────────────────────────────────────

    def _deal(self):
        self.deck          = Deck()
        self.table_spreads = []
        self.human_hand    = self.deck.deal(self.CARDS_PER_HAND)
        self.comp_hand     = self.deck.deal(self.CARDS_PER_HAND)
        self.discard       = [self.deck.draw()]

    def _check_natural(self, hand: list[Card]) -> bool:
        return hand_value(hand) in (49, 50)

    # ── Human turn ───────────────────────────────────────────────────────────

    def _human_turn(self) -> str:
        """
        Returns one of: 'tonk', 'knock', 'continue', 'deck_empty'
        """
        self._show_board()
        print(f"  {bold(green('── Your turn ──'))}")
        print(f"  [k] Knock  (declare lowest hand – risky!)")
        print(f"  [p] Play")
        action = self._prompt("Action:", ['k', 'p'])

        if action == 'k':
            return 'knock'

        # Draw
        result = self._human_draw()
        if result == 'deck_empty':
            return 'deck_empty'

        # Spread / hit loop
        while True:
            self._show_board()
            if not self.human_hand:
                return 'tonk'
            print(f"  {bold(green('── Spread phase ──'))}")
            print(f"  [l] Lay down a spread")
            print(f"  [h] Hit a table spread")
            print(f"  [d] Done  (go to discard)")
            choice = self._prompt("Choice:", ['l', 'h', 'd'])
            if choice == 'd':
                break
            elif choice == 'l':
                self._human_lay_spread()
            elif choice == 'h':
                self._human_hit_spread()
            if not self.human_hand:
                return 'tonk'

        # Discard
        if self.human_hand:
            self._human_discard()

        return 'tonk' if not self.human_hand else 'continue'

    def _human_draw(self) -> str:
        self._show_board()
        top = self.discard[-1] if self.discard else None
        top_s = top.colored() if top else dim('none')
        print(f"  {bold(green('── Draw phase ──'))}")
        print(f"  [s] Stock pile")
        print(f"  [d] Discard  ({top_s})")
        choice = self._prompt("Draw from:", ['s', 'd'])

        if choice == 'd' and top:
            card = self.discard.pop()
            self.human_hand.append(card)
            print(green(f"\n  You take {card.colored()} from the discard pile."))
        else:
            if not self.deck:
                self.deck.refill_from_discard(self.discard)
            card = self.deck.draw()
            if card is None:
                print(yellow("  The stock pile is empty!"))
                self._pause()
                return 'deck_empty'
            self.human_hand.append(card)
            print(green(f"\n  You drew {card.colored()} from the stock."))

        self._pause()
        return 'ok'

    def _human_lay_spread(self):
        self._show_board()
        print(f"  {bold(green('── Lay a spread ──'))}")
        for i, c in enumerate(self.human_hand):
            print(f"    [{i + 1}] {c.colored()}  {dim(str(c.value) + ' pts')}")
        raw = input(cyan("  Card numbers (e.g. 1 3 5), or Enter to cancel: ")).strip()
        if not raw:
            return
        try:
            indices = [int(x) - 1 for x in raw.split()]
            if len(indices) < 3:
                print(red("  Need at least 3 cards."))
                self._pause()
                return
            selected = [self.human_hand[i] for i in indices]
        except (ValueError, IndexError):
            print(red("  Invalid input."))
            self._pause()
            return

        stype = None
        if len({c.rank for c in selected}) == 1 and 3 <= len(selected) <= 4:
            stype = 'set'
        elif len({c.suit for c in selected}) == 1:
            sorted_sel = sorted(selected, key=lambda c: RANK_IDX[c.rank])
            idxs = [RANK_IDX[c.rank] for c in sorted_sel]
            if idxs == list(range(idxs[0], idxs[0] + len(idxs))):
                stype = 'run'
                selected = sorted_sel

        if stype is None:
            print(red("  Not a valid spread!  "
                      "Need 3–4 same-rank cards (set) or "
                      "3+ sequential same-suit cards (run)."))
            self._pause()
            return

        for c in selected:
            self.human_hand.remove(c)
        self.table_spreads.append(
            {'type': stype, 'cards': selected, 'owner': self.human_name}
        )
        print(green(f"  Spread laid: {' '.join(c.colored() for c in selected)}"))
        self._pause()

    def _human_hit_spread(self):
        if not self.table_spreads:
            print(red("  No spreads on the table yet."))
            self._pause()
            return

        self._show_board()
        print(f"  {bold(green('── Hit a spread ──'))}")
        for i, sp in enumerate(self.table_spreads):
            print(f"    [{i + 1}] {sp['type'].upper()}  {spread_to_str(sp)}")

        try:
            sp_num = int(input(cyan("  Spread number (0 to cancel): ")).strip()) - 1
            if sp_num < 0:
                return
            spread = self.table_spreads[sp_num]
        except (ValueError, IndexError):
            print(red("  Invalid."))
            self._pause()
            return

        print(f"\n  {bold(green('Your hand:'))}")
        for i, c in enumerate(self.human_hand):
            ok = can_extend(c, spread)
            tag = green(" ✓") if ok else ""
            print(f"    [{i + 1}] {c.colored()}{tag}")

        try:
            c_num = int(input(cyan("  Card to add (0 to cancel): ")).strip()) - 1
            if c_num < 0:
                return
            card = self.human_hand[c_num]
        except (ValueError, IndexError):
            print(red("  Invalid."))
            self._pause()
            return

        if can_extend(card, spread):
            self.human_hand.remove(card)
            spread['cards'].append(card)
            if spread['type'] == 'run':
                spread['cards'].sort(key=lambda c: RANK_IDX[c.rank])
            print(green(f"  Added {card.colored()} to the spread!"))
        else:
            print(red(f"  {card} can't be added to that spread."))
        self._pause()

    def _human_discard(self):
        self._show_board()
        print(f"  {bold(green('── Discard ──'))}")
        for i, c in enumerate(self.human_hand):
            print(f"    [{i + 1}] {c.colored()}  {dim(str(c.value) + ' pts')}")
        while True:
            try:
                idx = int(input(cyan(f"  Card to discard (1–{len(self.human_hand)}): ")).strip()) - 1
                if 0 <= idx < len(self.human_hand):
                    card = self.human_hand.pop(idx)
                    self.discard.append(card)
                    print(dim(f"  You discard {card}."))
                    return
                print(red("  Out of range."))
            except ValueError:
                print(red("  Enter a number."))

    # ── Computer turn ────────────────────────────────────────────────────────

    def _comp_turn(self) -> str:
        """Returns 'tonk', 'knock', 'continue', 'deck_empty'."""
        self._show_board()
        comp_turn_label = "── Computer's turn ──"
        print(f"  {bold(magenta(comp_turn_label))}")

        # Knock?
        if AI.should_knock(self.comp_hand, self.table_spreads):
            print(magenta(f"  Computer knocks!  "
                          f"{dim('(hand value: ' + str(hand_value(self.comp_hand)) + ')')}"))
            self._pause()
            return 'knock'

        # Draw
        top = self.discard[-1] if self.discard else None
        if AI.choose_draw(self.comp_hand, top, self.table_spreads) == 'discard' and top:
            card = self.discard.pop()
            self.comp_hand.append(card)
            print(magenta(f"  Computer takes {card.colored()} from discard."))
        else:
            if not self.deck:
                self.deck.refill_from_discard(self.discard)
            card = self.deck.draw()
            if card is None:
                print(yellow("  The stock pile is empty!"))
                self._pause()
                return 'deck_empty'
            self.comp_hand.append(card)
            print(magenta("  Computer draws from stock."))

        # Hit existing spreads
        for sp in self.table_spreads:
            for c in self.comp_hand[:]:
                if can_extend(c, sp):
                    self.comp_hand.remove(c)
                    sp['cards'].append(c)
                    if sp['type'] == 'run':
                        sp['cards'].sort(key=lambda x: RANK_IDX[x.rank])
                    print(magenta(f"  Computer adds {c.colored()} to a table spread."))
                    if not self.comp_hand:
                        self._pause()
                        return 'tonk'

        # Lay spreads
        for sp_cards in best_spread_combo(self.comp_hand):
            stype = spread_type(sp_cards)
            for c in sp_cards:
                self.comp_hand.remove(c)
            sorted_cards = sorted(sp_cards, key=lambda c: RANK_IDX[c.rank])
            self.table_spreads.append(
                {'type': stype, 'cards': sorted_cards, 'owner': 'Computer'}
            )
            print(magenta(f"  Computer lays a {stype}: "
                          f"{' '.join(c.colored() for c in sorted_cards)}"))
            if not self.comp_hand:
                self._pause()
                return 'tonk'

        # Discard
        if self.comp_hand:
            discard_card = AI.choose_discard(self.comp_hand)
            self.comp_hand.remove(discard_card)
            self.discard.append(discard_card)
            print(magenta(f"  Computer discards {discard_card.colored()}."))

        self._pause()
        return 'tonk' if not self.comp_hand else 'continue'

    # ── Round resolution helpers ─────────────────────────────────────────────

    def _resolve_tonk(self, winner: str):
        """winner tonked out – double penalty to the loser."""
        hv = hand_value(self.human_hand)
        cv = hand_value(self.comp_hand)
        self._show_board(reveal_computer=True)
        if winner == 'human':
            penalty = cv * 2
            print(bold(green(f"\n  TONK!  You played all your cards!")))
            print(f"  Computer had {red(str(cv))} pts remaining → "
                  f"double penalty: {red(str(penalty))} pts added to Computer.")
            self.comp_score += penalty
        else:
            penalty = hv * 2
            print(bold(red(f"\n  Computer TONKS!  Computer played all its cards!")))
            print(f"  Your hand had {red(str(hv))} pts remaining → "
                  f"double penalty: {red(str(penalty))} pts added to you.")
            self.human_score += penalty
        self._pause()

    def _resolve_natural(self, who: str):
        """Natural tonk (49/50 on deal) – same as tonk-out: double penalty."""
        hv = hand_value(self.human_hand)
        cv = hand_value(self.comp_hand)
        self._show_board(reveal_computer=True)
        if who == 'both':
            print(bold(yellow("\n  Both players have Natural Tonk! – Push (no scoring).")))
        elif who == 'human':
            penalty = cv * 2
            print(bold(green(f"\n  Natural Tonk!  Your hand = {hv} pts.")))
            print(f"  Computer had {red(str(cv))} pts → double penalty {red(str(penalty))} to Computer.")
            self.comp_score += penalty
        else:
            penalty = hv * 2
            print(bold(red(f"\n  Computer has Natural Tonk!  Computer hand = {cv} pts.")))
            print(f"  Your hand was {red(str(hv))} pts → double penalty {red(str(penalty))} to you.")
            self.human_score += penalty
        self._pause()

    def _resolve_knock(self, knocker: str):
        """Compare hands after a knock."""
        hv = hand_value(self.human_hand)
        cv = hand_value(self.comp_hand)
        self._show_board(reveal_computer=True)

        if knocker == 'human':
            print(bold(cyan(f"\n  You knock!")))
            print(f"  Your hand : {green(str(hv))} pts")
            print(f"  Computer  : {red(str(cv))} pts")
            if hv < cv:
                diff = cv - hv
                print(bold(green(f"\n  You win the knock! +{diff} pts to Computer.")))
                self.comp_score += diff
            elif hv == cv:
                penalty = hv * 2
                print(bold(red(f"\n  Tie – you lose the knock (knocker loses ties)! "
                               f"+{penalty} pts to you.")))
                self.human_score += penalty
            else:
                penalty = (hv - cv) * 2
                print(bold(red(f"\n  Computer had less – double penalty! "
                               f"+{penalty} pts to you.")))
                self.human_score += penalty
        else:
            print(bold(magenta(f"\n  Computer knocks!")))
            print(f"  Computer  : {green(str(cv))} pts")
            print(f"  Your hand : {red(str(hv))} pts")
            if cv < hv:
                diff = hv - cv
                print(bold(red(f"\n  Computer wins the knock! +{diff} pts to you.")))
                self.human_score += diff
            elif cv == hv:
                penalty = cv * 2
                print(bold(green(f"\n  Tie – computer loses the knock! "
                                 f"+{penalty} pts to Computer.")))
                self.comp_score += penalty
            else:
                penalty = (cv - hv) * 2
                print(bold(green(f"\n  You had less – computer double penalty! "
                                 f"+{penalty} pts to Computer.")))
                self.comp_score += penalty
        self._pause()

    def _resolve_deck_empty(self):
        hv = hand_value(self.human_hand)
        cv = hand_value(self.comp_hand)
        self._show_board(reveal_computer=True)
        print(bold(yellow("\n  Deck exhausted – comparing hands…")))
        print(f"  You: {hv} pts   Computer: {cv} pts")
        if hv < cv:
            print(bold(green("  You win this round!")))
            self.comp_score += cv - hv
        elif cv < hv:
            print(bold(red("  Computer wins this round!")))
            self.human_score += hv - cv
        else:
            print(bold(yellow("  It's a tie – no scoring.")))
        self._pause()

    # ── Main round loop ──────────────────────────────────────────────────────

    def _play_round(self):
        self.round_num += 1
        self._deal()

        # Natural Tonk check
        hn = self._check_natural(self.human_hand)
        cn = self._check_natural(self.comp_hand)
        if hn or cn:
            who = 'both' if (hn and cn) else ('human' if hn else 'computer')
            self._resolve_natural(who)
            return

        self._show_board()
        print(bold(yellow(f"  Round {self.round_num} begins!  Good luck!")))
        self._pause("Press Enter to start…")

        while True:
            # Human
            result = self._human_turn()
            if result == 'tonk':
                self._resolve_tonk('human')
                return
            if result == 'knock':
                self._resolve_knock('human')
                return
            if result == 'deck_empty':
                self._resolve_deck_empty()
                return

            # Computer
            result = self._comp_turn()
            if result == 'tonk':
                self._resolve_tonk('computer')
                return
            if result == 'knock':
                self._resolve_knock('computer')
                return
            if result == 'deck_empty':
                self._resolve_deck_empty()
                return

    # ── Entry point ──────────────────────────────────────────────────────────

    def play(self):
        clear()
        print()
        rule('═')
        print(bold(cyan(f"  {'W E L C O M E   T O   T O N K':^58}")))
        rule('═')
        print(f"""
  {bold('How to play:')}
  • Each player gets {self.CARDS_PER_HAND} cards.  Lowest score after all rounds wins.
  • On your turn: optionally Knock, then Draw → Spread/Hit → Discard.
  • {green('Spread')} – 3–4 cards same rank (set)  OR  3+ sequential same-suit (run).
  • {green('Hit')}    – add a card to any spread already on the table.
  • {green('Knock')}  – declare you have the lowest hand.  Tie = you lose.  Wrong = double penalty.
  • {green('Tonk')}   – play all cards → double penalty to opponent.
  • {green('Natural')} – initial hand of 49 or 50 pts → instant Tonk win.
  • Card values: Ace = 1 | 2-9 = face | 10 / J / Q / K = 10
""")
        rule()

        try:
            r = input(cyan(f"  How many rounds? (default {self.total_rounds}): ")).strip()
            if r.isdigit() and int(r) > 0:
                self.total_rounds = int(r)
        except EOFError:
            pass

        input(dim("\n  Press Enter to deal…"))

        for _ in range(self.total_rounds):
            self._play_round()

        # Final results
        clear()
        print()
        rule('═')
        print(bold(cyan(f"  {'G A M E   O V E R':^58}")))
        rule('═')
        print(f"\n  Final scores  {dim('(lower is better)')}")
        print(f"  {green('You:')       } {self.human_score} pts")
        print(f"  {red('Computer:')} {self.comp_score} pts\n")
        rule()
        if self.human_score < self.comp_score:
            print(bold(green(f"  {'🎉  YOU WIN THE GAME!  🎉':^58}")))
        elif self.comp_score < self.human_score:
            print(bold(red(f"  {'💻  COMPUTER WINS  💻':^58}")))
        else:
            tie_msg = "IT'S A TIE!"
            print(bold(yellow(f"  {tie_msg:^58}")))
        rule('═')
        print()


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    try:
        Game().play()
    except KeyboardInterrupt:
        print(f"\n\n{dim('  Game aborted. Goodbye!')}\n")
