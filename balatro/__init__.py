from __future__ import annotations
import base64
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import random as r

from .constants import *
from .classes import *
from .enums import *
from .jokers import *

__version__ = "1.0.0"


def format_number(number: float) -> str:
    if number != number:
        return "nan"
    if number == float("inf"):
        return "naneinf"
    assert number >= 0
    if number >= 1e11:
        return f"{number:.3e}".replace("+", "")
    if number >= 100 or number.is_integer():
        return f"{number:,.0f}"
    return f"{number:,.1f}" if number >= 10 else f"{number:,.2f}"


class Run:
    def __init__(
        self, deck: Deck, stake: Stake = Stake.WHITE, seed: str | None = None
    ) -> None:
        r.seed(seed)

        self._deck: Deck = deck
        self._stake: Stake = stake
        self._money: int = 14 if self._deck is Deck.YELLOW else 4
        self._ante: int = 0
        self._round: int = 0

        self._poker_hand_info: dict[PokerHand : list[int, int]] = {
            poker_hand: [1, 0] for poker_hand in PokerHand
        }
        self._vouchers: set[Voucher] = set()
        self._tags: list[Tag] = []

        self._deck_cards: list[Card] = [
            (
                self._get_random_card()
                if self._deck is Deck.ERRATIC
                else Card(rank, suit)
            )
            for suit in Suit
            for rank in Rank
        ]

        self._jokers: list[BaseJoker] = []
        self._consumables: list[Consumable] = []

        match self._deck:
            case Deck.MAGIC:
                self._vouchers.add(Voucher.CRYSTAL_BALL)
                self._consumables.extend(
                    [Consumable(Tarot.THE_FOOL), Consumable(Tarot.THE_FOOL)]
                )
            case Deck.NEBULA:
                self._vouchers.add(Voucher.TELESCOPE)
            case Deck.GHOST:
                self._consumables.append(Consumable(Spectral.HEX))
            case Deck.ABANDONED:
                self._deck_cards = [
                    card for card in self._deck_cards if not self._is_face_card(card)
                ]
            case Deck.CHECKERED:
                for card in self._deck_cards:
                    if card.suit is Suit.CLUBS:
                        card.suit = Suit.SPADES
                    elif card.suit is Suit.DIAMONDS:
                        card.suit = Suit.HEARTS
            case Deck.ZODIAC:
                self._vouchers.update(
                    [
                        Voucher.TAROT_MERCHANT,
                        Voucher.PLANET_MERCHANT,
                        Voucher.OVERSTOCK,
                    ]
                )

        self._num_played_hands: int = 0
        self._first_hand: bool | None = None
        self._first_discard: bool | None = None
        self._round_poker_hands: list[PokerHand] | None = None
        self._num_unused_discards: int = 0
        self._num_blinds_skipped: int = 0

        self._round_score: float | None = None
        self._round_goal: float | None = None
        self._chips: int | None = None
        self._mult: float | None = None
        self._hands: int | None = None
        self._discards: int | None = None
        self._hand: list[Card] | None = None
        self._deck_cards_left: list[Card] | None = None

        self._reroll_cost: int | None = None
        self._used_chaos: bool | None = None
        self._shop_cards: list[tuple[BaseJoker | Consumable | Card, int]] | None = None
        self._shop_packs: list[tuple[Pack, int]] | None = None
        self._opened_pack: Pack | None = None
        self._pack_items: list[BaseJoker | Consumable | Card] | None = None
        self._pack_choices_left: int | None = None
        self._unique_planet_cards_used: set[Planet] = set()
        self._boss_blind_pool: list[Blind] = []
        self._finisher_blind_pool: list[Blind] = []
        self._num_tarot_cards_used: int = 0
        self._fool_next: Tarot | Planet | None = None
        self._hand_size_penalty: int = 0
        self._num_ectoplasms_used: int = 0
        self._gros_michel_extinct: bool = False
        self._boss_blind_disabled: bool | None = None
        self._forced_selected_card_index: int | None = None

        self._new_ante()

        self._state: State = State.SELECTING_BLIND

    def _repr_html_(self) -> str:
        match self._state:
            case State.IN_SHOP:
                return self._repr_in_shop()
            case State.OPENING_PACK:
                return self._repr_opening_pack()
            case State.PLAYING_BLIND:
                return self._repr_playing_blind()
            case State.SELECTING_BLIND:
                return self._repr_selecting_blind()
            case State.GAME_OVER:
                raise NotImplementedError

    def _add_card(self, card: Card) -> None:
        self._deck_cards.append(card)
        for joker in self._jokers:
            joker._on_card_added(card)

    def _add_joker(self, joker: BaseJoker) -> None:
        self._jokers.append(joker)
        for other_joker in self._jokers:
            other_joker._on_jokers_moved()

    def _buy_shop_item(
        self, section_index: int, item_index: int, buy_and_use: bool = False
    ) -> tuple[BaseJoker | Consumable | Card | Pack | Voucher, int]:
        assert self._state is State.IN_SHOP

        assert section_index in [0, 1, 2]

        section_items = [self._shop_cards, self._shop_vouchers, self._shop_packs][
            section_index
        ]

        assert 0 <= item_index < len(section_items)

        item, cost = section_items[item_index]

        assert self._available_money >= cost

        if buy_and_use:
            assert isinstance(item, Consumable)
        else:
            match item:
                case BaseJoker():
                    assert (
                        len(self._jokers) < self.joker_slots
                        or item.edition is Edition.NEGATIVE
                    )
                case Consumable():
                    assert len(self._consumables) < self.consumable_slots

        self._money -= cost
        return section_items.pop(item_index)

    def _calculate_buy_cost(
        self, item: BaseJoker | Consumable | Card | Voucher | Pack, coupon: bool = False
    ) -> int:
        if coupon and not isinstance(item, Voucher):
            return 0

        edition_cost = 0
        discount_percent = (
            0.5
            if Voucher.LIQUIDATION in self._vouchers
            else 0.75 if Voucher.CLEARANCE_SALE in self._vouchers else 1.0
        )

        match item:
            case BaseJoker():
                if item.is_rental:
                    return 1

                base_cost = JOKER_BASE_COSTS[item.joker_type]
                edition_cost = EDITION_COSTS[item.edition]
            case Consumable():
                match item.card:
                    case Tarot():
                        base_cost = 3
                    case Planet():
                        if JokerType.ASTRONOMER in self._jokers:
                            return 0
                        base_cost = 3
                    case Spectral():
                        base_cost = 4
                edition_cost = EDITION_COSTS[
                    Edition.NEGATIVE if item.is_negative else Edition.BASE
                ]
            case Card():
                base_cost = 1
                edition_cost = EDITION_COSTS[item.edition]
            case Voucher():
                base_cost = 10
                discount_percent = 1.0
            case Pack():
                if (
                    item.name.endswith("CELESTIAL")
                    and JokerType.ASTRONOMER in self._jokers
                ):
                    return 0
                if item.name.startswith("MEGA"):
                    base_cost = 8
                elif item.name.startswith("JUMBO"):
                    base_cost = 6
                else:
                    base_cost = 4

        buy_cost = (base_cost + edition_cost) * discount_percent
        return max(round(buy_cost - 0.001), 1)

    def _calculate_sell_value(self, item: Sellable) -> int:
        return max(1, self._calculate_buy_cost(item) // 2) + item.extra_sell_value

    def _chance(self, hit: int, pool: int) -> bool:
        hit *= 2 ** self._jokers.count(JokerType.OOPS_ALL_SIXES)
        return hit >= pool or (r.randint(1, pool) <= hit)

    def _close_pack(self) -> None:
        self._hand = None

        self._opened_pack = None
        self._pack_items = None
        self._pack_choices_left = None
        self._hand = None
        self._deck_cards_left = None

        if self._shop_cards is None:
            self._state = State.SELECTING_BLIND

            if self._tags and self._tags[-1] in TAG_PACKS:
                self._open_pack(TAG_PACKS[self._tags.pop()])
        else:
            self._state = State.IN_SHOP

    def _create_joker(
        self,
        joker_type: JokerType,
        edition: Edition = Edition.BASE,
        is_eternal: bool = False,
        is_perishable: bool = False,
        is_rental: bool = False,
    ) -> BaseJoker:
        joker = JOKER_CLASSES[joker_type](
            edition=edition,
            is_eternal=is_eternal,
            is_perishable=is_perishable,
            is_rental=is_rental,
        )
        joker._on_created(self)
        return joker

    def _deal(self, after_hand_played: bool = False) -> bool:
        hand_size = self.hand_size

        if (
            not self._deck_cards_left
            or hand_size <= 0
            or self._hands is not None
            and self._hands <= 0
        ):
            return False

        num_cards = (
            3
            if self._boss_blind_disabled is False
            and self._blind is Blind.THE_SERPENT
            and (not self._first_hand or not self._first_discard)
            else min(len(self._deck_cards_left), max(0, hand_size - len(self._hand)))
        )
        deal_indices = sorted(
            r.sample(range(len(self._deck_cards_left)), num_cards), reverse=True
        )
        for i in deal_indices:
            self._hand.append(self._deck_cards_left.pop(i))

        self._sort_hand()

        if self._boss_blind_disabled is False:
            match self._blind:
                case Blind.THE_HOUSE:
                    if self._first_hand:
                        for hand_card in self._hand:
                            hand_card.flipped = True
                case Blind.THE_WHEEL:
                    for hand_card in self._hand:
                        hand_card.flipped = self._chance(1, 7)
                case Blind.THE_FISH:
                    if after_hand_played:
                        for hand_card in self._hand:
                            hand_card.flipped = True
                case Blind.CERULEAN_BELL:
                    self._forced_selected_card_index = r.randint(0, len(self._hand) - 1)

        return True

    def _destroy_card(self, card: Card) -> None:
        try:
            self._deck_cards.remove(card)

            for joker in self._jokers:
                joker._on_card_destroyed(card)
        except ValueError:
            pass

    def _destroy_joker(self, joker: BaseJoker) -> None:
        if joker.is_eternal:
            return
        try:
            i = self._jokers.index(joker)
            self._jokers.pop(i)
            for other_joker in self._jokers:
                other_joker._on_jokers_moved()
        except ValueError:
            pass

    def _disable_boss_blind(self) -> None:
        if self._boss_blind_disabled:
            return

        self._boss_blind_disabled = True

        for card in self._deck_cards:
            card.debuffed = False
            card.flipped = False

        for joker in self._jokers:
            if joker._perishable_rounds_left > 0:
                joker.debuffed = False
            joker.flipped = False

        match self._blind:
            case Blind.THE_WALL:
                self._round_goal //= 2
            case Blind.THE_WATER:
                self._discards = self._discards_each_round
            case Blind.THE_NEEDLE:
                self._hands = self._hands_each_round
            case Blind.VIOLET_VESSEL:
                self._round_goal //= 3
            case Blind.CERULEAN_BELL:
                self._forced_selected_card_index = None

    def _discard(self, discard_indices: list[int]) -> None:
        discarded_cards = [self._hand[i] for i in discard_indices]

        for joker in self._jokers[:]:
            joker._on_discard(discarded_cards)

        for i in sorted(discard_indices, reverse=True):
            self._hand.pop(i)

    def _end_hand(
        self,
        played_cards: list[Card],
        scored_card_indices: list[int],
        poker_hands_played: list[PokerHand],
        hand_not_allowed: bool = False,
    ) -> None:
        if hand_not_allowed:
            for joker in self._jokers:
                joker._on_boss_blind_triggered()

        if self._round_score >= self._round_goal:
            # print(f"Round Ended: {format_number(self._round_score)}")
            self._end_round(poker_hands_played[0])
            return

        if self._hands == 0:  # game over
            if self._chips >= self._round_goal // 4:
                for joker in self._jokers:
                    if joker == JokerType.MR_BONES:  # saved by mr. bones
                        self._destroy_joker(joker)
                        self._end_round(poker_hands_played[0], saved=True)
                        return
            self._game_over()
        else:
            if not self._deal(after_hand_played=True):
                self._game_over()

    def _end_round(
        self, last_poker_hand_played: PokerHand, saved: bool = False
    ) -> None:
        for held_card in self._hand:
            self._trigger_held_card_round_end(held_card, last_poker_hand_played)

            match held_card:
                case Seal.RED:
                    self._trigger_held_card_round_end(held_card, last_poker_hand_played)

            for joker in self._jokers:
                for _ in range(joker._on_card_held_retriggers(held_card)):
                    self._trigger_held_card_round_end(held_card, last_poker_hand_played)

        self._disable_boss_blind()

        interest_amt = (
            0
            if self._deck is Deck.GREEN
            else (1 + self._jokers.count(JokerType.TO_THE_MOON))
        )
        interest = min(
            (
                20
                if Voucher.MONEY_TREE in self._vouchers
                else 10 if Voucher.SEED_MONEY in self._vouchers else 5
            )
            * interest_amt,
            (max(0, self._money) // 5 * interest_amt),
        )

        for joker in self._jokers[:]:
            joker._on_round_ended()

        cash_out = (
            (0 if saved else self.blind_reward)
            + (2 if self._deck is Deck.GREEN else 1) * self._hands
            + (1 if self._deck is Deck.GREEN else 0) * self._discards
            + interest
        )
        self._money += cash_out

        self._round_score = None
        self._round_goal = None
        self._hands = None
        self._num_unused_discards += self._discards
        self._discards = None
        self._hand = None
        self._deck_cards_left = None
        self._chips = None
        self._mult = None
        self._first_hand = None
        self._first_discard = None
        self._round_poker_hands = None
        self._boss_blind_disabled = None
        self._forced_selected_card_index = None

        self._next_blind()

        self._populate_shop()
        self._state = State.IN_SHOP

    def _game_over(self) -> None:
        self._round_score = None
        self._round_goal = None
        self._hands = None
        self._num_unused_discards += self._discards
        self._discards = None
        self._hand = None
        self._deck_cards_left = None
        self._chips = None
        self._mult = None
        self._first_hand = None
        self._first_discard = None
        self._round_poker_hands = None
        self._boss_blind_disabled = None
        self._forced_selected_card_index = None

        self._state = State.GAME_OVER

    def _get_card_suits(self, card: Card, force_base_suit: bool = False) -> list[Suit]:
        if (card.debuffed and not force_base_suit) or card.is_stone_card:
            return []
        if card == Enhancement.WILD:
            return list(Suit)
        if JokerType.SMEARED_JOKER in self._jokers:
            red_suits, black_suits = [Suit.HEARTS, Suit.DIAMONDS], [
                Suit.SPADES,
                Suit.CLUBS,
            ]
            return red_suits if card.suit in red_suits else black_suits
        return [card.suit]

    def _get_poker_hands(self, played_cards: list[Card]) -> dict[PokerHand, set[int]]:
        poker_hands = {}

        flush_straight_len = 4 if (JokerType.FOUR_FINGERS in self._jokers) else 5
        max_straight_gap = 2 if (JokerType.SHORTCUT in self._jokers) else 1

        suit_counts = Counter()
        for played_card in played_cards:
            suit_counts.update(self._get_card_suits(played_card, force_base_suit=True))

        # flush check
        flush_suit, flush_suit_count = (
            suit_counts.most_common(1)[0] if suit_counts else (None, 0)
        )
        if flush_suit_count >= flush_straight_len:  # flush
            poker_hands[PokerHand.FLUSH] = [
                i
                for i, card in enumerate(played_cards)
                if flush_suit in self._get_card_suits(card, force_base_suit=True)
            ]

        rank_counts = Counter(
            played_card.rank
            for played_card in played_cards
            if not played_card.is_stone_card
        )

        # straight check
        if len(rank_counts) >= flush_straight_len:
            sorted_ranks = sorted(rank_counts)

            longest_straight = set()
            cur_straight = set()
            for i in range(len(sorted_ranks)):
                cur_straight.add(sorted_ranks[i])
                if len(cur_straight) > len(longest_straight):
                    longest_straight = cur_straight
                if (
                    i < len(sorted_ranks) - 1
                    and int(sorted_ranks[i + 1]) - int(sorted_ranks[i])
                    > max_straight_gap
                ):
                    cur_straight = set()

            if (
                int(min(longest_straight)) <= max_straight_gap + 1
                and Rank.ACE in rank_counts
            ):
                longest_straight.add(Rank.ACE)

            if len(longest_straight) >= flush_straight_len:  # straight
                straight = list(longest_straight)
                straight_indices = [
                    i for i, card in enumerate(played_cards) if card in straight
                ]
                if PokerHand.FLUSH in poker_hands:  # straight flush
                    poker_hands[PokerHand.STRAIGHT_FLUSH] = straight_indices
                poker_hands[PokerHand.STRAIGHT] = straight_indices

        # rank-matching checks
        for rank, n in rank_counts.most_common():
            if n == 5:  # 5oak
                poker_hands[PokerHand.FIVE_OF_A_KIND] = list(range(5))
                if PokerHand.FLUSH in poker_hands:  # flush five
                    poker_hands[PokerHand.FLUSH_FIVE] = list(range(5))
            if n >= 4:  # 4oak
                poker_hands[PokerHand.FOUR_OF_A_KIND] = [
                    i for i, card in enumerate(played_cards) if card.rank is rank
                ][:4]
            if n >= 3:  # 3oak
                poker_hands[PokerHand.THREE_OF_A_KIND] = [
                    i for i, card in enumerate(played_cards) if card.rank is rank
                ][:3]
            if n >= 2:  # pair
                if (
                    PokerHand.THREE_OF_A_KIND in poker_hands
                    and played_cards[poker_hands[PokerHand.THREE_OF_A_KIND][0]].rank
                    is not rank
                ):  # full house
                    poker_hands[PokerHand.FULL_HOUSE] = list(range(5))
                    if PokerHand.FLUSH in poker_hands:  # flush house
                        poker_hands[PokerHand.FLUSH_HOUSE] = list(range(5))
                if (
                    PokerHand.PAIR in poker_hands
                    and played_cards[poker_hands[PokerHand.PAIR][0]] != rank
                ):  # two pair
                    poker_hands[PokerHand.TWO_PAIR] = (
                        poker_hands[PokerHand.PAIR]
                        + [
                            i
                            for i, card in enumerate(played_cards)
                            if card.rank is rank
                        ][:2]
                    )
                poker_hands[PokerHand.PAIR] = [
                    i for i, card in enumerate(played_cards) if card.rank is rank
                ][:2]

        # high card
        if not rank_counts:
            # (all stone cards - default to high card)
            poker_hands[PokerHand.HIGH_CARD] = []
        else:
            poker_hands[PokerHand.HIGH_CARD] = [
                i
                for i, card in enumerate(played_cards)
                if card.rank is max(rank_counts)
            ][:1]

        return poker_hands

    def _get_random_card(self, restricted_ranks: list[Rank] | None = None) -> Card:
        ranks = restricted_ranks if restricted_ranks is not None else list(Rank)
        card = Card(r.choice(ranks), r.choice(list(Suit)))

        return card

    def _get_random_consumable(self, consumable_type: type) -> Consumable:
        match consumable_type.__name__:
            case Tarot.__name__:
                card_pool = list(Tarot)
            case Planet.__name__:
                card_pool = [
                    unlocked_poker_hand.planet
                    for unlocked_poker_hand in self._unlocked_poker_hands
                ]
            case Spectral.__name__:
                card_pool = list(Spectral)[:-2]

        prohibited_consumable_cards = set()
        if JokerType.SHOWMAN not in self._jokers:
            prohibited_consumable_cards.update(
                consumable.card for consumable in self.consumables
            )

            if self._shop_cards is not None:
                prohibited_consumable_cards.update(
                    shop_card[0].card
                    for shop_card in self._shop_cards
                    if isinstance(shop_card, tuple)
                    and isinstance(shop_card[0], Consumable)
                )

            if self._opened_pack is not None:
                prohibited_consumable_cards.update(
                    pack_item.card
                    for pack_item in self._pack_items
                    if isinstance(pack_item, Consumable)
                )

        return Consumable(
            r.choice(
                [card for card in card_pool if card not in prohibited_consumable_cards]
            )
            if len(prohibited_consumable_cards) < len(card_pool)
            else card_pool[0]
        )

    def _get_random_joker(
        self,
        rarity: Rarity | None = None,
        allow_stickers: bool = False,
    ) -> BaseJoker:
        if rarity is None:
            rarity = r.choices(
                list(JOKER_BASE_RARITY_WEIGHTS),
                weights=JOKER_BASE_RARITY_WEIGHTS.values(),
                k=1,
            )[0]

        prohibited_joker_types = set()
        if JokerType.SHOWMAN not in self._jokers:
            prohibited_joker_types.update(joker.joker_type for joker in self.jokers)

            if self._shop_cards is not None:
                prohibited_joker_types.update(
                    shop_card[0].joker_type
                    for shop_card in self._shop_cards
                    if isinstance(shop_card, tuple)
                    and isinstance(shop_card[0], BaseJoker)
                )

            if self._opened_pack is not None:
                prohibited_joker_types.update(
                    pack_item.joker_type
                    for pack_item in self._pack_items
                    if isinstance(pack_item, BaseJoker)
                )

        if self._gros_michel_extinct:
            prohibited_joker_types.add(JokerType.GROS_MICHEL)
        if not self._gros_michel_extinct:
            prohibited_joker_types.add(JokerType.CAVENDISH)
        deck_card_enhancements = {
            deck_card.enhancement for deck_card in self._deck_cards
        }
        if Enhancement.GOLD not in deck_card_enhancements:
            prohibited_joker_types.add(JokerType.GOLDEN_TICKET)
        if Enhancement.STEEL not in deck_card_enhancements:
            prohibited_joker_types.add(JokerType.STEEL_JOKER)
        if Enhancement.STONE not in deck_card_enhancements:
            prohibited_joker_types.add(JokerType.STONE)
        if Enhancement.LUCKY not in deck_card_enhancements:
            prohibited_joker_types.add(JokerType.LUCKY_CAT)
        if Enhancement.GLASS not in deck_card_enhancements:
            prohibited_joker_types.add(JokerType.GLASS_JOKER)

        joker_type = r.choice(
            [
                joker_type
                for joker_type in JOKER_TYPE_RARITIES[rarity]
                if joker_type not in prohibited_joker_types
            ]
        )

        edition_chances = (
            JOKER_EDITION_CHANCES_GLOW_UP
            if Voucher.GLOW_UP in self._vouchers
            else (
                JOKER_EDITION_CHANCES_HONE
                if Voucher.HONE in self._vouchers
                else JOKER_EDITION_CHANCES
            )
        )
        edition = r.choices(
            list(edition_chances), weights=edition_chances.values(), k=1
        )[0]

        is_eternal, is_perishable, is_rental = False, False, False
        if allow_stickers:
            roll = r.random()
            if (
                self._stake >= Stake.BLACK
                and joker_type not in NON_ETERNAL_JOKERS
                and roll < 0.3
            ):
                is_eternal = True
            elif (
                self._stake >= Stake.ORANGE
                and joker_type not in NON_PERISHABLE_JOKERS
                and roll < 0.6
            ):
                is_perishable = True

            if self._stake is Stake.GOLD and r.random() < 0.3:
                is_rental = True

        return self._create_joker(
            joker_type,
            edition=edition,
            is_eternal=is_eternal,
            is_perishable=is_perishable,
            is_rental=is_rental,
        )

    def _get_round_goal(self, blind: Blind) -> float:
        round_goal = (
            float(
                ANTE_BASE_CHIPS[
                    (
                        2
                        if self._stake >= Stake.PURPLE
                        else 1 if self._stake >= Stake.GREEN else 0
                    )
                ][self.ante]
            )
            * BLIND_INFO[blind][1]
        ) * (2 if self._deck is Deck.PLASMA else 1)

        return float("nan") if round_goal == float("inf") else round_goal

    def _is_face_card(self, card: Card) -> bool:
        return (
            card
            in [
                Rank.KING,
                Rank.QUEEN,
                Rank.JACK,
            ]
            or JokerType.PAREIDOLIA in self._jokers
        )

    def _lucky_check(self) -> bool:
        triggered = False
        if self._chance(1, 5):
            self._mult += 20
            triggered = True
        if self._chance(1, 15):
            self._money += 20
            triggered = True
        return triggered

    def _new_ante(self) -> None:
        self._ante += 1

        self._ante_tags: list[
            tuple[Tag, PokerHand | None], tuple[Tag, PokerHand | None]
        ] = [None, None]
        for i in range(2):
            tag = r.choice(
                [
                    tag
                    for tag in Tag
                    if self._ante > 1 or tag not in PROHIBITED_ANTE_1_TAGS
                ]
            )
            extra = None

            if tag is Tag.ORBITAL:
                extra = r.choice(self._unlocked_poker_hands)

            self._ante_tags[i] = (tag, extra)

        self._random_boss_blind()

        self._shop_vouchers: list[tuple[Voucher, int]] | None = None
        self._rerolled_boss_blind: bool = False
        self._cards_played_ante: set[int] = set()

        self._blind: Blind = Blind.SMALL_BLIND

    def _next_blind(self) -> None:
        match self._blind:
            case Blind.SMALL_BLIND:
                self._blind = Blind.BIG_BLIND
            case Blind.BIG_BLIND:
                self._blind = self._boss_blind
            case _:
                for joker in self._jokers:
                    joker._on_boss_defeated()
                self._new_ante()

    def _open_pack(self, pack: Pack) -> None:
        self._state = State.OPENING_PACK

        self._opened_pack = pack

        for joker in self._jokers:
            joker._on_pack_opened()

        if pack.name.startswith("MEGA"):
            self._pack_choices_left, of_up_to = 2, 5
        elif pack.name.startswith("JUMBO"):
            self._pack_choices_left, of_up_to = 1, 5
        else:
            self._pack_choices_left, of_up_to = 1, 3

        self._pack_items = []

        match pack:
            case Pack.BUFFOON | Pack.JUMBO_BUFFOON | Pack.MEGA_BUFFOON:
                for _ in range(of_up_to - 1):
                    self._pack_items.append(self._get_random_joker(allow_stickers=True))
            case Pack.ARCANA | Pack.JUMBO_ARCANA | Pack.MEGA_ARCANA:
                for _ in range(of_up_to):
                    if Spectral.THE_SOUL not in self._pack_items and r.random() < 0.003:
                        self._pack_items.append(Consumable(Spectral.THE_SOUL))
                    else:
                        self._pack_items.append(
                            self._get_random_consumable(
                                (
                                    Spectral
                                    if Voucher.OMEN_GLOBE in self._vouchers
                                    and r.random() < 0.2
                                    else Tarot
                                )
                            )
                        )

                self._hand = []
                self._deck_cards_left = self._deck_cards.copy()
                if not self._deal():
                    self._game_over()
            case Pack.CELESTIAL | Pack.JUMBO_CELESTIAL | Pack.MEGA_CELESTIAL:
                for _ in range(of_up_to):
                    if (
                        Spectral.BLACK_HOLE not in self._pack_items
                        and r.random() < 0.003
                    ):
                        self._pack_items.append(Consumable(Spectral.BLACK_HOLE))
                    else:
                        self._pack_items.append(self._get_random_consumable(Planet))
            case Pack.SPECTRAL | Pack.JUMBO_SPECTRAL | Pack.MEGA_SPECTRAL:
                for _ in range(of_up_to - 1):
                    if (
                        Spectral.BLACK_HOLE not in self._pack_items
                        and r.random() < 0.003
                    ):
                        self._pack_items.append(Consumable(Spectral.BLACK_HOLE))
                    elif (
                        Spectral.THE_SOUL not in self._pack_items and r.random() < 0.003
                    ):
                        self._pack_items.append(Consumable(Spectral.THE_SOUL))
                    else:
                        self._pack_items.append(self._get_random_consumable(Spectral))

                self._hand = []
                self._deck_cards_left = self._deck_cards.copy()
                if not self._deal():
                    self._game_over()
            case Pack.STANDARD | Pack.JUMBO_STANDARD | Pack.MEGA_STANDARD:
                edition_chances = (
                    CARD_EDITION_CHANCES_GLOW_UP
                    if Voucher.GLOW_UP in self._vouchers
                    else (
                        CARD_EDITION_CHANCES_HONE
                        if Voucher.HONE in self._vouchers
                        else CARD_EDITION_CHANCES
                    )
                )

                for _ in range(of_up_to):
                    pack_card = self._get_random_card()
                    pack_card.edition = r.choices(
                        list(edition_chances), weights=edition_chances.values(), k=1
                    )[0]
                    if r.random() < 0.4:
                        pack_card.enhancement = r.choice(list(Enhancement))
                    if r.random() < 0.2:
                        pack_card.seal = r.choice(list(Seal))

                    self._pack_items.append(pack_card)

    def _populate_shop(self) -> None:
        coupon = False
        if Tag.COUPON in self._tags:
            coupon = True
            self._tags.remove(Tag.COUPON)

        self._reroll_cost = (
            5
            - 2 * (Voucher.REROLL_SURPLUS in self._vouchers)
            - 2 * (Voucher.REROLL_GLUT in self._vouchers)
        )
        if Tag.DSIX in self._tags:
            self._tags.remove(Tag.DSIX)
            self._reroll_cost = 0

        self._used_chaos = False

        self._populate_shop_cards(coupon=coupon)

        needed_vouchers = 0
        if self._shop_vouchers is None:
            self._shop_vouchers = []
            needed_vouchers = 1
        while Tag.VOUCHER in self._tags:
            self._tags.remove(Tag.VOUCHER)
            needed_vouchers += 1

        if needed_vouchers > 0:
            voucher_list = list(Voucher)
            possible_vouchers = []
            for base_voucher, upgraded_voucher in zip(
                voucher_list[:16], voucher_list[16:]
            ):
                if upgraded_voucher in self._vouchers:
                    continue
                possible_voucher = (
                    upgraded_voucher if base_voucher in self._vouchers else base_voucher
                )
                if possible_voucher in self._shop_vouchers:
                    continue
                possible_vouchers.append(possible_voucher)

            for _ in range(needed_vouchers):
                voucher = r.choice(possible_vouchers)
                buy_cost = self._calculate_buy_cost(voucher, coupon=coupon)
                self._shop_vouchers.append((voucher, buy_cost))
                possible_vouchers.remove(voucher)

        self._shop_packs = r.choices(
            list(SHOP_BASE_PACK_WEIGHTS),
            weights=SHOP_BASE_PACK_WEIGHTS.values(),
            k=2,
        )
        if self._round == 1:
            self._shop_packs[0] = Pack.BUFFOON
        for i, pack in enumerate(self._shop_packs):
            buy_cost = self._calculate_buy_cost(pack, coupon=coupon)
            self._shop_packs[i] = (pack, buy_cost)

    def _populate_shop_cards(self, coupon: bool = False) -> None:
        shop_card_weights = SHOP_BASE_CARD_WEIGHTS.copy()
        if Voucher.MAGIC_TRICK in self._vouchers:
            shop_card_weights[Card] = 4
        if Voucher.TAROT_TYCOON in self._vouchers:
            shop_card_weights[Tarot] = 32
        elif Voucher.TAROT_MERCHANT in self._vouchers:
            shop_card_weights[Tarot] = 9.6
        if Voucher.PLANET_TYCOON in self._vouchers:
            shop_card_weights[Planet] = 32
        elif Voucher.PLANET_MERCHANT in self._vouchers:
            shop_card_weights[Planet] = 9.6
        if self._deck is Deck.GHOST:
            shop_card_weights[Spectral] = 2

        if self._shop_cards is None:
            self._shop_cards = []

        k = (
            4
            if Voucher.OVERSTOCK_PLUS in self._vouchers
            else 3 if Voucher.OVERSTOCK in self._vouchers else 2
        ) - len(self._shop_cards)

        self._shop_cards.extend(
            r.choices(
                list(shop_card_weights),
                weights=shop_card_weights.values(),
                k=k,
            )
        )
        joker_tags_used = 0
        for tag in self._tags:
            if joker_tags_used == k:
                break
            if tag is Tag.UNCOMMON or tag is Tag.RARE:
                self._shop_cards[len(self._shop_cards) - k + joker_tags_used] = (
                    BaseJoker
                )
                joker_tags_used += 1

        for i in range(len(self._shop_cards) - k, len(self._shop_cards)):
            match self._shop_cards[i].__name__:
                case BaseJoker.__name__:
                    buy_cost = None

                    rarity = None
                    for tag in self._tags[:]:
                        if tag is Tag.UNCOMMON or tag is Tag.RARE:
                            self._tags.remove(tag)
                            rarity = Rarity[tag.name]
                            buy_cost = 0
                            break

                    joker = self._get_random_joker(
                        rarity=rarity,
                        allow_stickers=True,
                    )

                    if joker.edition is Edition.BASE:
                        for tag in self._tags[:]:
                            if tag.name in Edition._member_map_:
                                self._tags.remove(tag)
                                joker.edition = Edition[tag.name]
                                buy_cost = 0
                                break

                    if buy_cost is None:
                        buy_cost = self._calculate_buy_cost(joker, coupon=coupon)
                    self._shop_cards[i] = (joker, buy_cost)
                case Tarot.__name__ | Planet.__name__ | Spectral.__name__:
                    consumable = self._get_random_consumable(self._shop_cards[i])
                    buy_cost = self._calculate_buy_cost(consumable, coupon=coupon)
                    self._shop_cards[i] = (consumable, buy_cost)
                case Card.__name__:
                    card = self._get_random_card()
                    if Voucher.ILLUSION in self._vouchers:
                        card.edition = r.choices(
                            list(CARD_EDITION_CHANCES_ILLUSION),
                            weights=CARD_EDITION_CHANCES_ILLUSION.values(),
                            k=1,
                        )[0]
                        if r.random() < 0.4:
                            card.enhancement = r.choice(list(Enhancement))
                        # not in the game code despite it being in the voucher description (bug?)
                        # if r.random() < 0.2:
                        #     card.seal = r.choice(list(Seal))
                    buy_cost = self._calculate_buy_cost(card, coupon=coupon)
                    self._shop_cards[i] = (card, buy_cost)

    def _random_boss_blind(self) -> None:
        self._boss_blind: Blind = None
        if self._is_finisher_ante:
            if not self._finisher_blind_pool:
                self._finisher_blind_pool = list(BLIND_INFO)[-5:]
            self._boss_blind = r.choice(self._finisher_blind_pool)
            self._finisher_blind_pool.remove(self._boss_blind)
        else:
            if not self._boss_blind_pool:
                self._boss_blind_pool = list(BLIND_INFO)[2:-5]
            self._boss_blind = r.choice(
                [
                    blind
                    for blind in self._boss_blind_pool
                    if self.ante >= BLIND_INFO[blind][0]
                ]
            )
            self._boss_blind_pool.remove(self._boss_blind)

    def _repr_frame(self) -> str:
        with open("resources/fonts/m6x11plus.ttf", "rb") as f:
            font_base64 = base64.b64encode(f.read()).decode("utf-8")

        blind_base64 = base64.b64encode(self._blind._repr_png_()).decode("utf-8")
        stake_base64 = base64.b64encode(self._stake._repr_png_()).decode("utf-8")

        html = f"""
        <style>
        @font-face {{
            font-family: 'm6x11plus';
            src: url(data:font/ttf;base64,{font_base64});
        }}
        * {{
            font-family: 'm6x11plus', monospace;
        }}
        </style>
        <div style='height: 546px; width: 1084px; display: flex; flex-direction: row;'>
            <div style='height: 540px; width: 300px; background-color: #333b3d; padding: 6px 6px 0 6px;'>
        """
        if self._state is State.PLAYING_BLIND:
            round_goal = format_number(self._round_goal)
            blind_reward = self.blind_reward

            html += f"""
                <div style='display: flex; height: 51.6px; width: 100%; background-color: {BLIND_COLORS[self._blind]}; border-radius: 12px; color: white; align-items: center; justify-content: center; font-size: 38.4px; text-shadow: 3.6px 3.6px rgba(0, 0, 0, 0.5)'>{self._blind.value}</div>
                <div style='display: flex; height: 102px; width: 100%; background-color: {BLIND_COLORS[self._blind]+"55"}; border-radius: 12px; color: white; align-items: center; justify-content: center; font-size: 31.2px; margin-top: 6px'>
                    <img style='filter: drop-shadow(6px 6px rgba(0, 0, 0, 0.5));' src='data:image/png;base64,{blind_base64}'/>
                    <div style='filter: drop-shadow(0px 3px rgba(0, 0, 0, 0.5)); display: flex; flex-direction: column; height: 60%; width: 50%; background-color: #172022; border-radius: 12px; align-items: center; justify-content: center; font-size: 43.2px; margin-left: 6px; padding: 6px'>
                        <div style='display: flex; align-items: center; justify-content: center; color: #e35646; font-size: {43.2 - max(0, len(round_goal) - 3) * 2.1}px'>
                            <img style='margin-right: 5px; height: 32.4px; width: 32.4px' src='data:image/png;base64,{stake_base64}'/>
                            {round_goal}
                        </div>
                        <div style='font-size: 19.2px; display: flex; align-items: center; justify-content: center; width: 100%;'>
                            {f'<span style="color: white;">No Reward</span>' if (blind_reward == 0) else f'<span style="color: white; font-size: {19.2 - max(0, blind_reward - 6) * 2.4}px">Reward:</span><span style="color: #d7af54; margin-left: 6px;">{"$" * blind_reward}</span>'}
                        </div>
                    </div>
                </div>
            """
        elif self._shop_cards is not None:
            from .sprites import SHOP_SIGN

            html += f"""
                <img style='width: 280px; margin-left: 9px; margin-top: 16px' src='data:image/png;base64,{base64.b64encode(SHOP_SIGN).decode("utf-8")}'/>
            """
        elif self._state is State.SELECTING_BLIND or self._state is State.OPENING_PACK:
            html += f"""
                <div style='display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; height: 159.6px; width: 100%; color: white; font-size: 31.2px; text-shadow: 2px 2px rgba(0, 0, 0, 0.5)'>
                    Choose your<br/>next Blind
            """
            if Voucher.DIRECTORS_CUT in self._vouchers:
                html += f"""
                    <button style='display: flex; justify-content: center; align-items: center; margin-top: 3px; background-color: {"#4f4f4f" if self._available_money < 10 or (Voucher.RETCON not in self._vouchers and self._rerolled_boss_blind) else"#e35646"}; border-radius: 12px; text-align: center; height: 50px; width: 150px; color: white; font-size: 19.2px; text-shadow: 1px 1px rgba(0, 0, 0, 0.5); filter: drop-shadow(3.6px 3.6px rgba(0, 0, 0, 0.5))'>Reroll Boss<br/>$10</button>
                """
            html += "</div>"

        html += f"""
                <div style='display: flex; height: 60px; width: 100%; background-color: #172022; border-radius: 12px; color: white; align-items: center; justify-content: center; font-size: 24px; margin-top: 6px'>
                    Round<br/>score
                    <div style='display: flex; height: 75%; width: 66%; background-color: #3a4b50; border-radius: 12px; color: white; align-items: center; justify-content: center; font-size: {43.2 - (0 if self.round_score < 1_000_000 else (len(format_number(self.round_score)) - 6) * 2.4)}px; margin-left: 18px;'>
                        <img style='margin-right: 8.4px; height: 32.4px; width: 32.4px' src='data:image/png;base64,{stake_base64}'/>
                        {format_number(self.round_score)}
                    </div>
                </div>
                <div style='display: flex; height: 300px; width: 100%; margin-top: 8.4px'>
                    <div style='display: flex; flex-direction: column; align-items: center; height: 100%; width: 47%;'>
        """

        poker_hand_shorthand = {
            PokerHand.FIVE_OF_A_KIND: "5 of a Kind",
            PokerHand.STRAIGHT_FLUSH: "Str. Flush",
            PokerHand.FOUR_OF_A_KIND: "4 of a Kind",
            PokerHand.THREE_OF_A_KIND: "3 of a Kind",
        }

        unlocked_poker_hands = self._unlocked_poker_hands

        for poker_hand in PokerHand:
            html += f"""
                        <div style="font-size: 15.6px; width: 100%; height: 31.2px; border-radius: 6px; color: white; background-color: DarkGray; margin: 2.4px; display: flex; align-items: center; justify-content: center; padding: 0 1.2px 0 1.2px; filter: drop-shadow(0 2.4px DimGray); opacity: {1 if poker_hand in unlocked_poker_hands else 0.33}">
                            <span style="display: flex; justify-content: center; align-items: center; color: #172022; background-color: {POKER_HAND_LEVEL_COLORS[min(7, self._poker_hand_info[poker_hand][0])]}; border-radius: 6px; width: 33.6px;">lvl.{self._poker_hand_info[poker_hand][0]}</span>
                            <span style="margin: 0 auto; text-shadow: 1.2px 1.2px rgba(0, 0, 0, 0.5)">{poker_hand_shorthand.get(poker_hand, poker_hand.value)}</span>
                            <span style="display: flex; justify-content: center; align-items: center; color: orange; background-color: #333b3d; border-radius: 6px; width: 20.4px;">{self._poker_hand_info[poker_hand][1]}</span>
                        </div>
            """

        html += f"""
                    </div>
                    <div style="display: grid; grid-template-rows: auto auto auto; grid-template-columns: 50% 50%; gap: 7px; width: 53%; padding: 0 6px 0 6px; height: 192px;">
                        <div style="height: 60px; display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #172022; border-radius: 12px; grid-column: 1; font-size: 19.2px; color: white;">
                            Hands
                            <div style='display: flex; align-items: center; justify-content: center; height: 60%; margin-bottom: 4.8px; width: 80%; background-color: #3a4b50; border-radius: 12px; margin-top: 2.4px; color: #3e8cf1; font-size: 43.2px; text-shadow: 2.4px 2.4px rgba(0, 0, 0, 0.65)'>
                                {self.hands}
                            </div>
                        </div>
                        <div style="height: 60px; display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #172022; border-radius: 12px; grid-column: 2; font-size: 19.2px; color: white;">
                            Discards
                            <div style='display: flex; align-items: center; justify-content: center; height: 60%; margin-bottom: 4.8px; width: 80%; background-color: #3a4b50; border-radius: 12px; margin-top: 2.4px; color: #e35646; font-size: 43.2px; text-shadow: 2.4px 2.4px rgba(0, 0, 0, 0.65)'>
                                {self.discards}
                            </div>
                        </div>

                        <div style="height: 60px; display: flex; align-items: center; justify-content: center; background-color: #172022; border-radius: 12px; grid-column: 1 / span 2;">
                            <div style='display: flex; align-items: center; justify-content: center; height: 85%; width: 85%; background-color: #3a4b50; border-radius: 12px; color: #d7af54; font-size: 50.4px; text-shadow: 3.6px 3.6px rgba(0, 0, 0, 0.65)'>
                                ${self._money}
                            </div>
                        </div>

                        <div style="height: 60px; display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #172022; border-radius: 12px; grid-column: 1; font-size: 19.2px; color: white;">
                            Ante
                            <div style='display: flex; align-items: center; justify-content: center; height: 60%; margin-bottom: 4.8px; width: 80%; background-color: #3a4b50; border-radius: 12px; margin-top: 2.4px; font-size: 43.2px; text-shadow: 2.4px 2.4px rgba(0, 0, 0, 0.65)'>
                                <span style='color: orange'>{self.ante}</span><span style='color: white; font-size: 19.2px; margin-left: 2.4px;'>/</span><span style='color: white; font-size: 19.2px; margin-left: 6px;'>8</span>
                            </div>
                        </div>
                        <div style="height: 60px; display: flex; flex-direction: column; align-items: center; justify-content: center; background-color: #172022; border-radius: 12px; grid-column: 2; font-size: 19.2px; color: white;">
                            Round
                            <div style='display: flex; align-items: center; justify-content: center; height: 60%; margin-bottom: 4.8px; width: 80%; background-color: #3a4b50; border-radius: 12px; margin-top: 2.4px; color: orange; font-size: 43.2px; text-shadow: 2.4px 2.4px rgba(0, 0, 0, 0.65)'>
                                {self._round}
                            </div>
                        </div>
                    </div>
                    <div style='position: absolute; height: 102px; width: 162px; bottom: 10px; display: grid; grid-template-columns: repeat(4, 1fr); grid-template-rows: repeat(2, 1fr); gap: 0px; margin: 3.6px 3.6px 3.6px 140.4px; background-color: #1d2829; border-radius: 12px'>
        """

        vouchers = list(Voucher)
        slots_left = 8
        for voucher1, voucher2 in zip(vouchers[:16], vouchers[16:]):
            if slots_left == 0:
                break
            if voucher2 in self._vouchers:
                html += f"""
                        <div style='position: relative; display: flex; justify-content: center; align-items: center; height: 45.6px;'>
                            <img src='data:image/png;base64,{base64.b64encode(voucher1._repr_png_()).decode("utf-8")}' style='filter: drop-shadow(2.4px 2.4px rgba(0, 0, 0, 0.5)); position: absolute; height: 45.6px; transform: rotate(-8deg) translate(-3.6px); z-index: 1;'/>
                            <img src='data:image/png;base64,{base64.b64encode(voucher2._repr_png_()).decode("utf-8")}' style='filter: drop-shadow(2.4px 2.4px rgba(0, 0, 0, 0.5)); position: absolute; height: 45.6px; transform: rotate(8deg) translate(3.6px); z-index: 2;'/>
                        </div>
                """
                slots_left -= 1

        for voucher1, voucher2 in zip(vouchers[:16], vouchers[16:]):
            if slots_left == 0:
                break
            if voucher1 in self._vouchers and voucher2 not in self._vouchers:
                html += f"""
                        <div style='position: relative; display: flex; justify-content: center; align-items: center; height: 45.6px;'>
                            <img src='data:image/png;base64,{base64.b64encode(voucher1._repr_png_()).decode("utf-8")}' style='filter: drop-shadow(2.4px 2.4px rgba(0, 0, 0, 0.5)); height: 45.6px;'/>
                        </div>
                """
                slots_left -= 1

        joker_images = [
            base64.b64encode(joker._repr_png_(card_back=self._deck)).decode("utf-8")
            for joker in self._jokers
        ]
        consumable_images = [
            base64.b64encode(consumable._repr_png_()).decode("utf-8")
            for consumable in self._consumables
        ]
        tag_images = [
            base64.b64encode(tag._repr_png_()).decode("utf-8") for tag in self._tags
        ]

        html += f"""
                    </div>
                </div>
            </div>
            <div style='height: 546px; width: 772px; background-color: {PACK_BACKGROUND_COLORS[" ".join(self._opened_pack.value.split(" ")[-2:])] if self._opened_pack is not None else BLIND_COLORS[self._blind] if self._state is State.PLAYING_BLIND and self._is_boss_blind else "#365a46"}'>
                <div style='position: absolute; height: 132px; width: 492px; background-color: rgba(0, 0, 0, 0.1); border-radius: 12px; left: 336px; top: 42px; display: flex; align-items: center; justify-content: space-evenly;'>
                    {' '.join(f"""
                        <img src='data:image/png;base64,{joker_images[i]}' style='width: {68.88 if joker.joker_type is JokerType.WEE_JOKER else 98.4}px; position: relative; z-index: {i+1}; margin-left: {-(98.4 * max(0, len(self._jokers) - 5))/(len(self._jokers) - 1) if i > 0 else 0}px; filter: drop-shadow(0px 8.4px rgba(0, 0, 0, 0.5))'/>
                    """ for i, joker in enumerate(self._jokers))}
                </div>
                <span style='color: white; font-size: 14px; position: absolute; left: 348px; top: 175.2px'>{len(self._jokers)}/{self.joker_slots}</span>
                <div style='position: absolute; height: 132px; width: 196.8px; background-color: rgba(0, 0, 0, 0.1); border-radius: 12px; left: 840px; top: 42px; display: flex; align-items: center; justify-content: space-evenly;'>
                    {' '.join(f"""
                        <img src='data:image/png;base64,{consumable_images[i]}' style='width: 98.4px; position: relative; z-index: {i+1}; margin-left: {-(98.4 * max(0, len(self._consumables) - 2))/(len(self._consumables) - 1) if i > 0 else 0}px; filter: drop-shadow(-6px 8.4px rgba(0, 0, 0, 0.5))'/>
                    """ for i, consumable in enumerate(self._consumables))}
                </div>
                <span style='color: white; font-size: 14px; position: absolute; left: 1014px; top: 175.2px'>{len(self._consumables)}/{self.consumable_slots}</span>

                <img src='data:image/png;base64,{base64.b64encode(self._deck._repr_png_()).decode("utf-8")}' style='position: absolute; bottom: 42px; left: 938.4px; width: 98.4px; filter: drop-shadow(-6px 6px Gray) drop-shadow(-3.6px 3.6px Gray) drop-shadow(-1.2px 1.2px Gray) drop-shadow(-14.4px 2.4px rgba(0, 0, 0, 0.2));'/>
                <span style='color: white; font-size: 14px; position: absolute; left: 996px; bottom: 16px'>{len(self.deck_cards_left)}/{len(self._deck_cards)}</span>

                <div style='display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 5px; position: absolute; height: 500px; width: 37px; bottom: 35px; left: 1048px'>
                    {' '.join(f"""
                        <img src='data:image/png;base64,{tag_images[i]}' style='width: 37px; position: relative; filter: drop-shadow(-3px 3px rgba(0, 0, 0, 0.5))'/>
                    """ for i, tag in enumerate(self._tags))}
                </div>
            </div>
        </div>
        """

        return html

    def _repr_in_shop(self) -> str:
        reroll_cost = self.reroll_cost
        can_reroll = self._available_money >= reroll_cost

        html = f"""
        <div style='position: absolute; display: flex; flex-direction: column; width: 564px; height: 348px; left: 342px; bottom: 9px; background-color: #1d2829; border-radius: 12px 12px 0 0; border-top: 1px solid #e35646; border-left: 1px solid #e35646; border-right: 1px solid #e35646;'>
            <div style='display: flex; height: 50%'>
                <div style='width: 25%; padding: 6px 0 6px 6px; display: flex; flex-direction: column; justify-content: center; align-items: center;'>
                    <div style='text-align: center; margin-bottom: 2.4px; width: 100%; height: 50%;'>
                        <button style='background-color: #e35646; color: white; padding: 1.2px 6px; width: 100%; height: 100%; border-radius: 12px; font-size: 19.2px; text-shadow: 0 1.2px rgba(0, 0, 0, 0.5)'>Next<br/>Round</button>
                    </div>
                    <div style='text-align: center; width: 100%; height: 50%;'>
                        <button style='background-color: {'#5cb284' if can_reroll else '#4f4f4f'}; color: {'white' if can_reroll else '#646464'}; padding: 1.2px 6px; width: 100%; height: 100%; border-radius: 12px; font-size: 19.2px; text-shadow: 0 1.2px rgba(0, 0, 0, 0.5)'>Reroll<br><span style='font-size: 33.6px;'>${reroll_cost}</span></button>
                    </div>
                </div>
                <div style='width: 75%; background-color: #3a4b50; border-radius: 12px; padding: 6px; margin: 6px;'>
                    <div style='display: flex; flex-wrap: wrap; align-items: center; justify-content: space-evenly; transform: translateY(-13.2px)'>
        """
        for item, cost in self._shop_cards:
            png_bytes = item._repr_png_()
            png_base64 = base64.b64encode(png_bytes).decode("utf-8")
            item_html = f"<img style='width: {68.88 if isinstance(item, BaseJoker) and item.joker_type is JokerType.WEE_JOKER else 98.4}px; filter: drop-shadow(0px 3.6px rgba(0, 0, 0, 0.5))' src='data:image/png;base64,{png_base64}'/>"

            html += f"""
                    <div style='display: flex; flex-direction: column; align-items: center;'>
                        <div style='display: flex; justify-content: center; align-items: center; width: 36px; height: 18px; background-color: #333b3d; border-radius: 6px 6px 0 0; border: 2.4px solid #172022';><strong style='color: #d7af54; font-size:19.2px;'>${cost}</strong></div>
                        <div style='text-align: center;'>{item_html}</div>
                    </div>
            """
        html += f"""
                    </div>
                </div>
            </div>
            <div style='position: absolute; color: #3a4b50; font-size: 20px; transform: rotate(-90deg); left: -32px; bottom: 77px;'>ANTE {self.ante} VOUCHER</div>
            <div style='display: flex; height: 50%;'>
                <div style='width: 50%; border: 6px solid #3a4b50; border-radius: 12px; padding: 6px; margin: 6px;'>
                    <div style='display: flex; flex-wrap: wrap; justify-content: center; transform: translateY(-19.2px)'>
        """
        for voucher, cost in self._shop_vouchers:
            png_bytes = voucher._repr_png_()
            png_base64 = base64.b64encode(png_bytes).decode("utf-8")
            voucher_html = f"<img style='width: 98.4px; filter: drop-shadow(0px 3.6px rgba(0, 0, 0, 0.5))' src='data:image/png;base64,{png_base64}'/>"

            html += f"""
                        <div style='display: flex; flex-direction: column; align-items: center;'>
                            <div style='display: flex; justify-content: center; align-items: center; width: 36px; height: 18px; background-color: #333b3d; border-radius: 6px 6px 0 0; border: 2.4px solid #172022';><strong style='color: #d7af54; font-size:19.2px;'>${cost}</strong></div>
                            <div style='text-align: center;'>{voucher_html}</div>
                        </div>
            """
        html += """
                    </div>
                </div>
                <div style='width: 50%; background-color: #3a4b50; border-radius: 12px; padding: 6px; margin: 6px;'>
                    <div style='display: flex; flex-wrap: wrap; justify-content: center; transform: translateY(-21.6px)'>
        """
        for pack, cost in self._shop_packs:
            png_bytes = pack._repr_png_()
            png_base64 = base64.b64encode(png_bytes).decode("utf-8")
            pack_html = f"<img src='data:image/png;base64,{png_base64}' style='height: 150px; filter: drop-shadow(0px 3.6px rgba(0, 0, 0, 0.5))'/>"

            html += f"""
                        <div style='display: flex; flex-direction: column; align-items: center;'>
                            <div style='display: flex; justify-content: center; align-items: center; width: 36px; height: 18px; background-color: #333b3d; border-radius: 6px 6px 0 0; border: 2.4px solid #172022';><strong style='color: #d7af54; font-size:19.2px;'>${cost}</strong></div>
                            <div style='text-align: center;'>{pack_html}</div>
                        </div>
            """
        html += """
                    </div>
                </div>
            </div>
        </div>
        """

        return html + self._repr_frame()

    def _repr_opening_pack(self) -> str:
        pack_item_images = [
            base64.b64encode(item._repr_png_()).decode("utf-8")
            for item in self._pack_items
        ]

        html = f"""
            <div style='position: absolute; height: 132px; width: 574px; left: 335px; bottom: 85px; display: flex; align-items: center; justify-content: center; gap: {5 if isinstance(self._pack_items[0], Consumable) else 15}px'>
                {' '.join(f"""
                    <img src='data:image/png;base64,{pack_item_images[i]}' style='width: {68.88 if isinstance(item, BaseJoker) and item.joker_type is JokerType.WEE_JOKER else 98.4}px; filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); position: relative;'/>
                """ for i, item in enumerate(self._pack_items))}
            </div>
            <div style='display: flex; flex-direction: column; align-items: center; color: white; height: 61px; width: 170px; background-color: #333b3d; border-top: 1px solid white; border-left: 1px solid white; border-right: 1px solid white; border-radius: 10px 10px 0 0; position: absolute; left: 538px; bottom: 9px'>
                <span style='font-size: 26px; margin-top: 3px;'>{" ".join(self._opened_pack.value.split(" ")[-2:])}</span>
                <span style='font-size: 20px; margin-top: 3px;'>Choose {self._pack_choices_left}</span>
            </div>
            <div style='display: flex; align-items: flex-start; justify-content: center; padding: 8px; font-size: 20px; color: white; height: 32px; width: 55px; background-color: #3f5357; border-radius: 10px; position: absolute; left: 724px; bottom: 17px; filter: drop-shadow(-2px 3px rgba(0, 0, 0, 0.5));'>
                Skip
            </div>
        """

        if self._hand is not None:
            card_images = [
                base64.b64encode(card._repr_png_()).decode("utf-8")
                for card in self._hand
            ]

            html += f"""
                <div style='height: 132px; width: 574px; position: absolute; bottom: 240px; left: 335px; display: flex; align-items: center; justify-content: space-evenly;'>
                        {' '.join(f"""
                            <img src='data:image/png;base64,{card_images[i]}' style='width: 98.4px; position: relative; filter: drop-shadow(0px 5px rgba(0, 0, 0, 0.5)); z-index: {i+1}; margin-left: {-(98.4 * max(0, len(self._hand) - 5))/(len(self._hand) - 1) if i > 0 else 0}px; transform: rotate({-((len(self._hand) - 1) / 2 - i) * 1}deg) translateY({abs((len(self._hand) - 1) / 2 - i) * 3}px)'/>
                        """ for i, card in enumerate(self._hand))}
                </div>
            """
        return html + self._repr_frame()

    def _repr_playing_blind(self) -> str:
        card_images = [
            base64.b64encode(card._repr_png_(card_back=self._deck)).decode("utf-8")
            for card in self._hand
        ]

        html = f"""
            <div style='height: 132px; width: 574px; position: absolute; bottom: 50px; left: 335px; display: flex; background-color: rgba(0, 0, 0, 0.1); border-radius: 12px; align-items: center; justify-content: space-evenly;'>
                    {' '.join(f"""
                        <img src='data:image/png;base64,{card_images[i]}' style='width: 98.4px; position: relative; z-index: {i+1}; margin-left: {-(98.4 * max(0, len(self._hand) - 5))/(len(self._hand) - 1) if i > 0 else 0}px; transform: rotate({-((len(self._hand) - 1) / 2 - i) * 1}deg) translateY({abs((len(self._hand) - 1) / 2 - i) * 2 - 8 - (30 if self._forced_selected_card_index == i else 0)}px)'/>
                    """ for i, card in enumerate(self._hand))}
            </div>
            <span style='color: white; font-size: 14px; position: absolute; left: 604px; bottom: 31px'>{len(self._hand)}/{self.hand_size}</span>
        """
        return html + self._repr_frame()

    def _repr_selecting_blind(self) -> str:
        stake_base64 = base64.b64encode(self._stake._repr_png_()).decode("utf-8")

        round_goal = format_number(self._get_round_goal(Blind.SMALL_BLIND))
        blind_reward = (
            0 if (self._stake >= Stake.RED) else BLIND_INFO[Blind.SMALL_BLIND][2]
        )

        html = f"""
            <div style='position: absolute; background-color: #333b3d; width: 160px; height: {360 if self._blind is Blind.SMALL_BLIND else 320}px; bottom: 9px; border-radius: 10px 10px 0 0; display: flex; align-items: center; justify-content: center; left: 350px; border-top: 2px solid {BLIND_COLORS[Blind.SMALL_BLIND]}; border-left: 2px solid {BLIND_COLORS[Blind.SMALL_BLIND]}; border-right: 2px solid {BLIND_COLORS[Blind.SMALL_BLIND]}; opacity: {1 if self._blind is Blind.SMALL_BLIND else 0.75}'>
                <button style='filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); width: 75%; height: 30px; display: flex; align-items: center; justify-content: center; background-color: {"#dc8c32" if self._blind is Blind.SMALL_BLIND else "#4f4f4f"}; color: white; font-size: 19px; border-radius: 10px; position: absolute; top: 10px; text-shadow: 1.2px 1.2px rgba(0, 0, 0, 0.5)'>Select</button>
                <div style='filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); width: 80%; height: 25px; display: flex; align-items: center; justify-content: center; background-color: {BLIND_COLORS[Blind.SMALL_BLIND]}; color: white; font-size: 19px; border-radius: 10px; position: absolute; top: 46px; text-shadow: 1.2px 1.2px rgba(0, 0, 0, 0.5)'>Small Blind</div>
                <img style='filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); position: absolute; top: 81px' src='data:image/png;base64,{base64.b64encode(Blind.SMALL_BLIND._repr_png_()).decode("utf-8")}'/>
                <div style='filter: drop-shadow(0px 3px rgba(0, 0, 0, 0.5)); position: absolute; top: 154px; display: flex; flex-direction: column; height: 50px; width: 80%; background-color: #172022; border-radius: 12px; align-items: center; justify-content: center; font-size: 43.2px; padding: 6px'>
                    <div style='display: flex; align-items: center; justify-content: center; color: #e35646; font-size: {36 - max(0, len(round_goal) - 3) * 1.8}px'>
                        <img style='margin-right: 5px; height: 32.4px; width: 32.4px' src='data:image/png;base64,{stake_base64}'/>
                        {round_goal}
                    </div>
                    <div style='font-size: 17px; display: flex; align-items: center; justify-content: center; width: 100%;'>
                        {f'' if (blind_reward == 0) else f'<span style="color: white; font-size: {17 - max(0, blind_reward - 6) * 2}px">Reward:</span><span style="color: #d7af54; margin-left: 6px;">{"$" * blind_reward}+</span>'}
                    </div>
                </div>
        """

        if self._blind is Blind.SMALL_BLIND:
            html += f"""
                <div style='filter: drop-shadow(0px 3px rgba(0, 0, 0, 0.5)); position: absolute; top: 228px; display: flex; flex-direction: column; height: 57px; width: 80%; background-color: #172022; border-radius: 12px; align-items: center; justify-content: center; font-size: 43.2px; padding: 4px 6px'>
                    <div style='display: flex; align-items: center; justify-content: center;'>
                        <img style='margin-right: 3px; width: 37px; filter: drop-shadow(-3px 3px rgba(0, 0, 0, 0.5))' src='data:image/png;base64,{base64.b64encode(self._ante_tags[0][0]._repr_png_()).decode("utf-8")}'/>
                        <button style='display: flex; justify-content: center; align-items: center; background-color: {"#4f4f4f" if self._blind is not Blind.SMALL_BLIND else"#e35646"}; border-radius: 12px; text-align: center; height: 48px; width: 100px; color: white; font-size: 17px; text-shadow: 1px 1px rgba(0, 0, 0, 0.5); filter: drop-shadow(3.6px 3.6px rgba(0, 0, 0, 0.5))'>Skip Blind</button>
                    </div>
                </div>
            """

        html += "</div>"

        round_goal = format_number(self._get_round_goal(Blind.BIG_BLIND))
        blind_reward = BLIND_INFO[Blind.BIG_BLIND][2]

        html += f"""
            <div style='position: absolute; background-color: #333b3d; width: 160px; height: {360 if self._blind is Blind.BIG_BLIND else 320}px; bottom: 9px; border-radius: 10px 10px 0 0; display: flex; align-items: center; justify-content: center; left: 540px; border-top: 2px solid {BLIND_COLORS[Blind.BIG_BLIND]}; border-left: 2px solid {BLIND_COLORS[Blind.BIG_BLIND]}; border-right: 2px solid {BLIND_COLORS[Blind.BIG_BLIND]}; opacity: {1 if self._blind is Blind.BIG_BLIND else 0.75}'>
                <button style='filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); width: 75%; height: 30px; display: flex; align-items: center; justify-content: center; background-color: {"#dc8c32" if self._blind is Blind.BIG_BLIND else "#4f4f4f"}; color: white; font-size: 19px; border-radius: 10px; position: absolute; top: 10px; text-shadow: 1.2px 1.2px rgba(0, 0, 0, 0.5)'>Select</button>
                <div style='filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); width: 80%; height: 25px; display: flex; align-items: center; justify-content: center; background-color: {BLIND_COLORS[Blind.BIG_BLIND]}; color: white; font-size: 19px; border-radius: 10px; position: absolute; top: 46px; text-shadow: 1.2px 1.2px rgba(0, 0, 0, 0.5)'>Big Blind</div>
                <img style='filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); position: absolute; top: 81px' src='data:image/png;base64,{base64.b64encode(Blind.BIG_BLIND._repr_png_()).decode("utf-8")}'/>
                <div style='filter: drop-shadow(0px 3px rgba(0, 0, 0, 0.5)); position: absolute; top: 154px; display: flex; flex-direction: column; height: 50px; width: 80%; background-color: #172022; border-radius: 12px; align-items: center; justify-content: center; font-size: 43.2px; padding: 6px'>
                    <div style='display: flex; align-items: center; justify-content: center; color: #e35646; font-size: {36 - max(0, len(round_goal) - 3) * 2}px'>
                        <img style='margin-right: 5px; height: 32.4px; width: 32.4px' src='data:image/png;base64,{stake_base64}'/>
                        {round_goal}
                    </div>
                    <div style='font-size: 17px; display: flex; align-items: center; justify-content: center; width: 100%;'>
                        {f'' if (blind_reward == 0) else f'<span style="color: white; font-size: {17 - max(0, blind_reward - 6) * 2}px">Reward:</span><span style="color: #d7af54; margin-left: 6px;">{"$" * blind_reward}+</span>'}
                    </div>
                </div>
        """

        if not self._is_boss_blind:
            html += f"""
                <div style='filter: drop-shadow(0px 3px rgba(0, 0, 0, 0.5)); position: absolute; top: 228px; display: flex; flex-direction: column; height: 57px; width: 80%; background-color: #172022; border-radius: 12px; align-items: center; justify-content: center; font-size: 43.2px; padding: 4px 6px'>
                    <div style='display: flex; align-items: center; justify-content: center;'>
                        <img style='margin-right: 3px; width: 37px; filter: drop-shadow(-3px 3px rgba(0, 0, 0, 0.5))' src='data:image/png;base64,{base64.b64encode(self._ante_tags[1][0]._repr_png_()).decode("utf-8")}'/>
                        <button style='display: flex; justify-content: center; align-items: center; background-color: {"#4f4f4f" if self._blind is not Blind.BIG_BLIND else"#e35646"}; border-radius: 12px; text-align: center; height: 48px; width: 100px; color: white; font-size: 17px; text-shadow: 1px 1px rgba(0, 0, 0, 0.5); filter: drop-shadow(3.6px 3.6px rgba(0, 0, 0, 0.5))'>Skip Blind</button>
                    </div>
                </div>
            """

        html += "</div>"

        round_goal = format_number(self._get_round_goal(self._boss_blind))
        blind_reward = BLIND_INFO[self._boss_blind][2]

        html += f"""
            <div style='position: absolute; background-color: #333b3d; width: 160px; height: {360 if self._is_boss_blind else 320}px; bottom: 9px; border-radius: 10px 10px 0 0; display: flex; align-items: center; justify-content: center; left: 730px; border-top: 2px solid {BLIND_COLORS[self._boss_blind]}; border-left: 2px solid {BLIND_COLORS[self._boss_blind]}; border-right: 2px solid {BLIND_COLORS[self._boss_blind]}; opacity: {1 if self._is_boss_blind else 0.75}'>
                <button style='filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); width: 75%; height: 30px; display: flex; align-items: center; justify-content: center; background-color: {"#dc8c32" if self._is_boss_blind else "#4f4f4f"}; color: white; font-size: 19px; border-radius: 10px; position: absolute; top: 10px; text-shadow: 1.2px 1.2px rgba(0, 0, 0, 0.5)'>Select</button>
                <div style='filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); width: 80%; height: 25px; display: flex; align-items: center; justify-content: center; background-color: {BLIND_COLORS[self._boss_blind]}; color: white; font-size: 19px; border-radius: 10px; position: absolute; top: 46px; text-shadow: 1.2px 1.2px rgba(0, 0, 0, 0.5)'>{self._boss_blind.value}</div>
                <img style='filter: drop-shadow(0px 2px rgba(0, 0, 0, 0.5)); position: absolute; top: 81px' src='data:image/png;base64,{base64.b64encode(self._boss_blind._repr_png_()).decode("utf-8")}'/>
                <div style='filter: drop-shadow(0px 3px rgba(0, 0, 0, 0.5)); position: absolute; top: 154px; display: flex; flex-direction: column; height: 50px; width: 80%; background-color: #172022; border-radius: 12px; align-items: center; justify-content: center; font-size: 43.2px; padding: 6px'>
                    <div style='display: flex; align-items: center; justify-content: center; color: #e35646; font-size: {36 - max(0, len(round_goal) - 3) * 2}px'>
                        <img style='margin-right: 5px; height: 32.4px; width: 32.4px' src='data:image/png;base64,{stake_base64}'/>
                        {round_goal}
                    </div>
                    <div style='font-size: 17px; display: flex; align-items: center; justify-content: center; width: 100%;'>
                        {f'' if (blind_reward == 0) else f'<span style="color: white; font-size: {17 - max(0, blind_reward - 6) * 2}px">Reward:</span><span style="color: #d7af54; margin-left: 6px;">{"$" * blind_reward}+</span>'}
                    </div>
                </div>
            </div>
        """
        return html + self._repr_frame()

    def _sort_hand(self, by_suit: bool = False) -> None:
        if by_suit:
            self._hand.sort(
                key=lambda card: (
                    card.is_stone_card,
                    list(Suit).index(card.suit),
                    list(Rank).index(card.rank),
                )
            )
        else:
            self._hand.sort(
                key=lambda card: (
                    card.is_stone_card,
                    list(Rank).index(card.rank),
                    list(Suit).index(card.suit),
                )
            )

    def _trigger_scored_card(
        self,
        scored_card: Card,
        played_cards: list[Card],
        scored_card_indices: list[int],
        poker_hands_played: list[PokerHand],
    ) -> None:
        self._chips += scored_card.chips

        match scored_card:
            case Enhancement.BONUS:
                self._chips += 30
            case Enhancement.MULT:
                self._mult += 4
            case Enhancement.GLASS:
                self._mult *= 2
            case Enhancement.LUCKY:
                if self._lucky_check():
                    for joker in self._jokers:
                        joker._on_lucky_card_triggered()

        match scored_card:
            case Seal.GOLD:
                self._money += 3

        match scored_card:
            case Edition.FOIL:
                self._chips += 50
            case Edition.HOLO:
                self._mult += 10
            case Edition.POLYCHROME:
                self._mult *= 1.5

        for joker in self._jokers:
            joker._on_card_scored(
                scored_card, played_cards, scored_card_indices, poker_hands_played
            )

    def _trigger_held_card(self, held_card: Card) -> None:
        match held_card:
            case Enhancement.STEEL:
                self._mult *= 1.5

        for joker in self._jokers:
            joker._on_card_held(held_card)

    def _trigger_held_card_round_end(
        self, held_card: Card, last_poker_hand_played: PokerHand
    ) -> None:
        match held_card:
            case Enhancement.GOLD:
                self._money += 3

        match held_card:
            case Seal.BLUE:
                if self.consumable_slots > len(self._consumables):
                    self._consumables.append(Consumable(last_poker_hand_played.planet))

    def _update_shop_costs(self) -> None:
        for i, (shop_card, cost) in enumerate(self._shop_cards):
            updated_cost = self._calculate_buy_cost(shop_card)
            if updated_cost < cost:
                self._shop_cards[i] = (shop_card, updated_cost)

        for i, (pack, cost) in enumerate(self._shop_packs):
            updated_cost = self._calculate_buy_cost(pack)
            if updated_cost < cost:
                self._shop_packs[i] = (pack, updated_cost)

    def _use_consumable(
        self, consumable: Consumable, selected_card_indices: list[int] | None = None
    ) -> None:
        if selected_card_indices is not None:
            assert self._hand is not None
            assert 1 <= len(selected_card_indices) <= 5
            assert all(0 <= i < len(self._hand) for i in selected_card_indices)
            assert len(set(selected_card_indices)) == len(selected_card_indices)

            selected_cards = [self._hand[i] for i in selected_card_indices]
        else:
            selected_cards = []

        match consumable.card:
            case Tarot():
                match consumable.card:
                    case Tarot.THE_FOOL:
                        assert (
                            self._fool_next is not None
                            and self._fool_next is not Tarot.THE_FOOL
                        )

                        self._consumables.append(Consumable(self._fool_next))
                    case Tarot.THE_MAGICIAN:
                        assert 1 <= len(selected_cards) <= 2

                        for card in selected_cards:
                            card.enhancement = Enhancement.LUCKY
                    case Tarot.THE_HIGH_PRIESTESS:
                        for _ in range(
                            min(
                                2,
                                self.consumable_slots - len(self._consumables) + 1,
                            )
                        ):
                            self._consumables.append(
                                self._get_random_consumable(Planet)
                            )
                    case Tarot.THE_EMPRESS:
                        assert 1 <= len(selected_cards) <= 2

                        for card in selected_cards:
                            card.enhancement = Enhancement.MULT
                    case Tarot.THE_EMPEROR:
                        for _ in range(
                            min(
                                2,
                                self.consumable_slots - len(self._consumables) + 1,
                            )
                        ):
                            self._consumables.append(self._get_random_consumable(Tarot))
                    case Tarot.THE_HEIROPHANT:
                        assert 1 <= len(selected_cards) <= 2

                        for card in selected_cards:
                            card.enhancement = Enhancement.BONUS
                    case Tarot.THE_LOVERS:
                        assert len(selected_cards) == 1

                        selected_cards[0].enhancement = Enhancement.WILD
                    case Tarot.THE_CHARIOT:
                        assert len(selected_cards) == 1

                        selected_cards[0].enhancement = Enhancement.STEEL
                    case Tarot.JUSTICE:
                        assert len(selected_cards) == 1

                        selected_cards[0].enhancement = Enhancement.GLASS
                    case Tarot.THE_HERMIT:
                        self._money += max(0, min(20, self._money))
                    case Tarot.THE_WHEEL_OF_FORTUNE:
                        assert self._jokers

                        valid_jokers = [
                            joker
                            for joker in self._jokers
                            if joker.edition is Edition.BASE
                        ]

                        assert valid_jokers

                        if self._chance(1, 4):
                            r.choice(valid_jokers).edition = r.choices(
                                list(UPGRADED_EDITION_WEIGHTS),
                                weights=UPGRADED_EDITION_WEIGHTS.values(),
                                k=1,
                            )[0]
                    case Tarot.STRENGTH:
                        assert 1 <= len(selected_cards) <= 2

                        ranks = list(Rank)
                        for card in selected_cards:
                            card.rank = ranks[(ranks.index(card.rank) - 1) % 13]
                    case Tarot.THE_HANGED_MAN:
                        assert 1 <= len(selected_cards) <= 2

                        for card in selected_cards:
                            self._destroy_card(card)
                    case Tarot.DEATH:
                        assert len(selected_cards) == 2

                        left, right = selected_cards
                        left.suit = right.suit
                        left.rank = right.rank
                        left.enhancement = right.enhancement
                        left.seal = right.seal
                        left.edition = right.edition
                    case Tarot.TEMPERANCE:
                        assert self._jokers

                        self._money += min(
                            50,
                            sum(
                                self._calculate_sell_value(joker)
                                for joker in self._jokers
                            ),
                        )
                    case Tarot.THE_DEVIL:
                        assert len(selected_cards) == 1

                        selected_cards[0].enhancement = Enhancement.GOLD
                    case Tarot.THE_TOWER:
                        assert len(selected_cards) == 1

                        selected_cards[0].enhancement = Enhancement.STONE
                    case Tarot.THE_STAR:
                        assert 1 <= len(selected_cards) <= 3

                        for card in selected_cards:
                            card.suit = Suit.DIAMONDS
                    case Tarot.THE_MOON:
                        assert 1 <= len(selected_cards) <= 3

                        for card in selected_cards:
                            card.suit = Suit.CLUBS
                    case Tarot.THE_SUN:
                        assert 1 <= len(selected_cards) <= 3

                        for card in selected_cards:
                            card.suit = Suit.HEARTS
                    case Tarot.JUDGEMENT:
                        assert len(self._jokers) < self.joker_slots

                        self._add_joker(self._get_random_joker())
                    case Tarot.THE_WORLD:
                        assert 1 <= len(selected_cards) <= 3

                        for card in selected_cards:
                            card.suit = Suit.SPADES

                self._num_tarot_cards_used += 1
                self._fool_next = consumable.card
            case Planet():
                self._poker_hand_info[consumable.card.poker_hand][0] += 1

                for joker in self._jokers:
                    joker._on_planet_used()

                self._fool_next = consumable.card
                self._unique_planet_cards_used.add(consumable.card)
            case Spectral():
                match consumable.card:
                    case Spectral.FAMILIAR:
                        assert self._hand

                        i = r.randint(0, len(self._hand) - 1)
                        self._destroy_card(self._hand[i])
                        self._hand.pop(i)

                        for _ in range(3):
                            random_face_card = self._get_random_card(
                                restricted_ranks=[Rank.KING, Rank.QUEEN, Rank.JACK]
                            )
                            random_face_card.enhancement = r.choice(list(Enhancement))
                            self._add_card(random_face_card)
                            self._hand.append(random_face_card)
                    case Spectral.GRIM:
                        assert self._hand

                        i = r.randint(0, len(self._hand) - 1)
                        self._destroy_card(self._hand[i])
                        self._hand.pop(i)

                        for _ in range(2):
                            random_ace = self._get_random_card(
                                restricted_ranks=[Rank.ACE]
                            )
                            random_ace.enhancement = r.choice(list(Enhancement))
                            self._add_card(random_ace)
                            self._hand.append(random_ace)
                    case Spectral.INCANTATION:
                        assert self._hand

                        i = r.randint(0, len(self._hand) - 1)
                        self._destroy_card(self._hand[i])
                        self._hand.pop(i)

                        for _ in range(4):
                            random_numbered_card = self._get_random_card(
                                restricted_ranks=[
                                    Rank.TEN,
                                    Rank.NINE,
                                    Rank.EIGHT,
                                    Rank.SEVEN,
                                    Rank.SIX,
                                    Rank.FIVE,
                                    Rank.FOUR,
                                    Rank.THREE,
                                    Rank.TWO,
                                ]
                            )
                            random_numbered_card.enhancement = r.choice(
                                list(Enhancement)
                            )
                            self._add_card(random_numbered_card)
                            self._hand.append(random_numbered_card)
                    case Spectral.TALISMAN:
                        assert len(selected_cards) == 1

                        selected_cards[0].seal = Seal.GOLD
                    case Spectral.AURA:
                        assert len(selected_cards) == 1

                        selected_cards[0].edition = r.choices(
                            list(UPGRADED_EDITION_WEIGHTS),
                            weights=UPGRADED_EDITION_WEIGHTS.values(),
                            k=1,
                        )[0]
                    case Spectral.WRAITH:
                        assert len(self._jokers) < self.joker_slots

                        self._add_joker(self._get_random_joker(rarity=Rarity.RARE))
                        self._money = 0
                    case Spectral.SIGIL:
                        assert self._hand

                        random_suit = r.choice(list(Suit))
                        for card in self._hand:
                            card.suit = random_suit
                    case Spectral.OUIJA:
                        assert self._hand
                        assert self.hand_size > 1

                        random_rank = r.choice(list(Rank))
                        for card in self._hand:
                            card.rank = random_rank
                        self._hand_size_penalty += 1
                    case Spectral.ECTOPLASM:
                        assert self._jokers
                        assert self.hand_size > 1

                        r.choice(self._jokers).edition = Edition.NEGATIVE
                        self._hand_size_penalty += 1 + self._num_ectoplasms_used
                        self._num_ectoplasms_used += 1
                    case Spectral.IMMOLATE:
                        assert self._hand

                        for _ in range(5):
                            if not self._hand:
                                break
                            i = r.randint(0, len(self._hand) - 1)
                            self._destroy_card(self._hand[i])
                            self._hand.pop(i)
                        self._money += 20
                    case Spectral.ANKH:
                        assert self._jokers

                        copied_joker = r.choice(self._jokers)
                        joker_copy = self._create_joker(
                            copied_joker.joker_type,
                            (
                                Edition.BASE
                                if copied_joker.edition is Edition.NEGATIVE
                                else copied_joker.edition
                            ),
                            copied_joker.is_eternal,
                            copied_joker.is_perishable,
                            copied_joker.is_rental,
                        )
                        for joker in self._jokers:
                            if joker is copied_joker:
                                continue
                            self._destroy_joker(joker)
                        self._add_joker(joker_copy)
                    case Spectral.DEJA_VU:
                        assert len(selected_cards) == 1

                        selected_cards[0].seal = Seal.RED
                    case Spectral.HEX:
                        assert self._jokers

                        valid_jokers = [
                            joker
                            for joker in self._jokers
                            if joker.edition is Edition.BASE
                        ]

                        assert valid_jokers

                        random_joker = r.choice(valid_jokers)
                        random_joker.edition = Edition.POLYCHROME

                        for joker in self._jokers:
                            if joker is random_joker:
                                continue
                            self._destroy_joker(joker)
                    case Spectral.TRANCE:
                        assert len(selected_cards) == 1

                        selected_cards[0].seal = Seal.BLUE
                    case Spectral.MEDIUM:
                        assert len(selected_cards) == 1

                        selected_cards[0].seal = Seal.PURPLE
                    case Spectral.CRYPTID:
                        assert len(selected_cards) == 1

                        for _ in range(2):
                            card_copy = replace(selected_cards[0])
                            self._add_card(card_copy)
                            self._hand.append(card_copy)
                    case Spectral.THE_SOUL:
                        assert len(self._jokers) < self.joker_slots

                        self._add_joker(self._get_random_joker(rarity=Rarity.LEGENDARY))
                    case Spectral.BLACK_HOLE:
                        for poker_hand in PokerHand:
                            self._poker_hand_info[poker_hand][0] += 1

    def buy_and_use_shop_item(self, section_index: int, item_index: int) -> None:
        item, cost = self._buy_shop_item(section_index, item_index, buy_and_use=True)
        try:
            self._use_consumable(item)
        except AssertionError:
            [self._shop_cards, self._shop_vouchers, self._shop_packs][
                section_index
            ].insert(item_index, (item, cost))
            self._money += cost

            assert False

    def buy_shop_item(self, section_index: int, item_index: int) -> None:
        item, cost = self._buy_shop_item(section_index, item_index)

        match item:
            case BaseJoker():
                self._add_joker(item)
            case Consumable():
                self._consumables.append(item)
            case Card():
                self._add_card(item)
            case Pack():
                self._open_pack(item)
            case Voucher():
                self._vouchers.add(item)
                match item:
                    case Voucher.OVERSTOCK | Voucher.OVERSTOCK_PLUS:
                        self._populate_shop_cards()
                    case Voucher.CLEARANCE_SALE | Voucher.LIQUIDATION:
                        self._update_shop_costs()
                    case Voucher.REROLL_SURPLUS | Voucher.REROLL_GLUT:
                        self._reroll_cost = max(0, self._reroll_cost - 2)

    def choose_pack_item(
        self, item_index: int, selected_card_indices: list[int] | None = None
    ) -> None:
        assert self._state is State.OPENING_PACK

        assert 0 <= item_index < len(self._pack_items)
        assert selected_card_indices is None or self._hand is not None

        item = self._pack_items[item_index]

        match item:
            case BaseJoker():
                assert (
                    len(self._jokers) < self.joker_slots
                    or item.edition is Edition.NEGATIVE
                )

                self._add_joker(item)
            case Consumable():
                self._use_consumable(item, selected_card_indices)
            case Card():
                self._add_card(item)

        self._pack_items.pop(item_index)

        self._pack_choices_left -= 1
        if self._pack_choices_left == 0:
            self._close_pack()

    def discard(self, discard_indices: list[int]) -> None:
        assert self._state is State.PLAYING_BLIND

        assert self._discards > 0
        assert 1 <= len(discard_indices) <= 5
        assert all(0 <= i < len(self._hand) for i in discard_indices)
        assert len(set(discard_indices)) == len(discard_indices)

        self._discard(discard_indices)

        self._discards -= 1
        self._first_discard = False

        if not self._deal():
            self._game_over()

    def next_round(self) -> None:
        assert self._state is State.IN_SHOP

        self._reroll_cost = None
        self._used_chaos = None
        self._shop_cards = None
        self._shop_packs = None

        self._state = State.SELECTING_BLIND

    def play_hand(self, card_indices: list[int]) -> None:
        assert self._state is State.PLAYING_BLIND

        assert 1 <= len(card_indices) <= 5
        assert all(0 <= i < len(self._hand) for i in card_indices)
        assert len(set(card_indices)) == len(card_indices)
        assert (
            self._forced_selected_card_index is None
            or self._forced_selected_card_index in card_indices
        )

        self._hands -= 1
        self._num_played_hands += 1

        played_cards = [self._hand[i] for i in card_indices]

        for i in sorted(card_indices, reverse=True):
            self._hand.pop(i)

        for played_card in played_cards:
            played_card.flipped = False

        poker_hands = self._get_poker_hands(played_cards)
        poker_hands_played = sorted(poker_hands, reverse=True)
        poker_hand_card_indices = poker_hands[poker_hands_played[0]]
        scored_card_indices = (
            list(range(len(played_cards)))
            if JokerType.SPLASH in self._jokers
            else [
                i
                for i, card in enumerate(played_cards)
                if i in poker_hand_card_indices or card.is_stone_card
            ]
        )

        poker_hand_level = self._poker_hand_info[poker_hands_played[0]][0]
        poker_hand_base_chips, poker_hand_base_mult = HAND_BASE_SCORE[
            poker_hands_played[0]
        ]
        poker_hand_chips_scaling, poker_hand_mult_scaling = HAND_SCALING[
            poker_hands_played[0]
        ]
        poker_hand_chips, poker_hand_mult = (
            poker_hand_base_chips + poker_hand_chips_scaling * (poker_hand_level - 1),
            poker_hand_base_mult + poker_hand_mult_scaling * (poker_hand_level - 1),
        )
        self._chips = poker_hand_chips
        self._mult = poker_hand_mult

        boss_blind_triggered = False

        if self._boss_blind_disabled is False:
            match self._blind:
                case Blind.THE_OX:
                    if self._poker_hand_info[poker_hands_played[0]][1] == max(
                        times_played
                        for hand_level, times_played in self._poker_hand_info.values()
                    ):
                        self._money = 0
                        boss_blind_triggered = True
                case Blind.THE_ARM:
                    if self._poker_hand_info[poker_hands_played[0]][0] > 1:
                        boss_blind_triggered = True
                    self._poker_hand_info[poker_hands_played[0]][0] = max(
                        1, self._poker_hand_info[poker_hands_played[0]][0] - 1
                    )
                case Blind.THE_PSYCHIC:
                    if len(played_cards) < 5:
                        self._end_hand(
                            played_cards,
                            scored_card_indices,
                            poker_hands_played,
                            hand_not_allowed=True,
                        )
                        return
                case Blind.THE_EYE:
                    if poker_hands_played[0] in self._round_poker_hands:
                        self._end_hand(
                            played_cards,
                            scored_card_indices,
                            poker_hands_played,
                            hand_not_allowed=True,
                        )
                        return
                case Blind.THE_MOUTH:
                    if (
                        self._round_poker_hands
                        and poker_hands_played[0] is not self._round_poker_hands[0]
                    ):
                        self._end_hand(
                            played_cards,
                            scored_card_indices,
                            poker_hands_played,
                            hand_not_allowed=True,
                        )
                        return
                case Blind.THE_TOOTH:
                    self._money -= 1 * len(played_cards)
                case Blind.THE_FLINT:
                    self._chips //= 2
                    self._mult //= 2
                    boss_blind_triggered = True

        for joker in self._jokers:
            joker._on_hand_played(played_cards, scored_card_indices, poker_hands_played)

        self._poker_hand_info[poker_hands_played[0]][1] += 1

        for i in scored_card_indices:
            scored_card = played_cards[i]

            if scored_card.debuffed:
                boss_blind_triggered = True

            self._trigger_scored_card(
                scored_card, played_cards, scored_card_indices, poker_hands_played
            )

            match scored_card:
                case Seal.RED:
                    self._trigger_scored_card(
                        scored_card,
                        played_cards,
                        scored_card_indices,
                        poker_hands_played,
                    )

            for joker in self._jokers:
                for _ in range(
                    joker._on_card_scored_retriggers(
                        scored_card,
                        played_cards,
                        scored_card_indices,
                        poker_hands_played,
                    )
                ):
                    self._trigger_scored_card(
                        scored_card,
                        played_cards,
                        scored_card_indices,
                        poker_hands_played,
                    )

        for held_card in self._hand:
            self._trigger_held_card(held_card)

            match held_card:
                case Seal.RED:
                    self._trigger_held_card(held_card)

            for joker in self._jokers:
                for _ in range(joker._on_card_held_retriggers(held_card)):
                    self._trigger_held_card(held_card)

        for joker in self._jokers:
            match joker:
                case Edition.FOIL:
                    self._chips += 50
                case Edition.HOLO:
                    self._mult += 10

            joker._on_independent(played_cards, scored_card_indices, poker_hands_played)
            if boss_blind_triggered:
                joker._on_boss_blind_triggered()

            for other_joker in self._jokers:
                other_joker._on_dependent(joker)

            match joker:
                case Edition.POLYCHROME:
                    self._mult *= 1.5

        if Voucher.OBSERVATORY in self._vouchers:
            for consumable in self._consumables:
                if consumable.card is poker_hands_played[0].planet:
                    self._mult *= 1.5

        self._mult = round(self._mult, 9)  # floating-point imprecision
        score = (
            ((self._chips + self._mult) / 2) ** 2
            if self._deck is Deck.PLASMA
            else self._chips * self._mult
        )
        self._round_score += score

        # un-debuff cards

        for joker in self._jokers[:]:
            joker._on_end_hand(played_cards, scored_card_indices, poker_hands_played)

        for i in scored_card_indices:
            scored_card = played_cards[i]
            match scored_card:
                case Enhancement.GLASS:
                    if self._chance(1, 4):
                        self._destroy_card(scored_card)

        self._round_poker_hands.append(poker_hands_played[0])
        self._first_hand = False

        if self._boss_blind_disabled is False:
            match self._blind:
                case Blind.THE_HOOK:
                    if len(self._hand) >= 2:
                        self._discard(r.sample(range(len(self._hand)), 2))
                    elif len(self._hand) == 1:
                        self._discard([0])
                case Blind.CRIMSON_HEART:
                    for joker in self._jokers:
                        if joker.debuffed and joker._perishable_rounds_left > 0:
                            joker.debuffed = False
                    r.choice(
                        [joker for joker in self._jokers if not joker.debuffed]
                    ).debuffed = True

        self._end_hand(
            played_cards, scored_card_indices, poker_hands_played
        )  # comment out when testing scores

    def move_joker(self, joker_index: int, new_index: int) -> None:
        assert self._state is not State.GAME_OVER

        assert self._jokers
        assert 0 <= joker_index < len(self._jokers)
        assert 0 <= new_index < len(self._jokers)
        assert new_index != joker_index

        self._jokers.insert(new_index, self._jokers.pop(joker_index))

        for joker in self._jokers:
            joker._on_jokers_moved()

    def reroll(self) -> None:
        assert self._state is State.IN_SHOP

        reroll_cost = self.reroll_cost

        assert self._available_money >= reroll_cost

        for joker in self._jokers:
            joker._on_shop_rerolled()

        self._money -= reroll_cost

        if not self._used_chaos and JokerType.CHAOS_THE_CLOWN in self._jokers:
            self._used_chaos = True
        else:
            self._reroll_cost += 1

        self._shop_cards = None
        self._populate_shop_cards()

    def reroll_boss_blind(self) -> None:
        assert self._state is State.SELECTING_BLIND

        assert Voucher.DIRECTORS_CUT in self._vouchers
        if Voucher.RETCON not in self._vouchers:
            assert not self._rerolled_boss_blind
        assert self._available_money >= 10

        self._money -= 10

        self._random_boss_blind()

        self._rerolled_boss_blind = True

    def select_blind(self) -> None:
        assert self._state is State.SELECTING_BLIND

        self._round += 1
        self._round_score = 0
        self._round_goal = self._get_round_goal(self._blind)
        self._hands = self._hands_each_round
        self._discards = self._discards_each_round
        self._hand = []
        self._deck_cards_left = self._deck_cards.copy()
        self._round_poker_hands = []
        self._first_hand = True
        self._first_discard = True
        if self._is_boss_blind:
            self._boss_blind_disabled = False

        match self._blind:
            case Blind.THE_CLUB:
                for card in self._deck_cards:
                    if card.suit is Suit.CLUBS:
                        card.debuffed = True
            case Blind.THE_GOAD:
                for card in self._deck_cards:
                    if card.suit is Suit.SPADES:
                        card.debuffed = True
            case Blind.THE_WATER:
                self._discards = 0
            case Blind.THE_WINDOW:
                for card in self._deck_cards:
                    if card.suit is Suit.DIAMONDS:
                        card.debuffed = True
            case Blind.THE_PLANT:
                for card in self._deck_cards:
                    if self._is_face_card(card):
                        card.debuffed = True
            case Blind.THE_PILLAR:
                for card in self._deck_cards:
                    if id(card) in self._cards_played_ante:
                        card.debuffed = True
            case Blind.THE_NEEDLE:
                self._hands = 1
            case Blind.THE_HEAD:
                for card in self._deck_cards:
                    if card.suit is Suit.HEARTS:
                        card.debuffed = True
            case Blind.THE_MARK:
                for card in self._deck_cards:
                    if self._is_face_card(card):
                        card.flipped = True
            case Blind.AMBER_ACORN:
                for joker in self._jokers:
                    joker.flipped = True
                r.shuffle(self._jokers)
            case Blind.VERDANT_LEAF:
                for card in self._deck_cards:
                    card.debuffed = True
            case Blind.CRIMSON_HEART:
                r.choice(
                    [joker for joker in self._jokers if not joker.debuffed]
                ).debuffed = True

        while Tag.JUGGLE in self._tags:
            self._tags.remove(Tag.JUGGLE)
            self._hands += 3

        for joker in self._jokers[:]:
            if joker in self._jokers:
                joker._on_blind_selected()

        if not self._deal():
            self._game_over()
        else:
            self._state = State.PLAYING_BLIND

    def sell_item(self, section_index: int, item_index: int) -> None:
        assert self._state is not State.GAME_OVER

        assert section_index in [0, 1]

        section_items = [self._jokers, self._consumables][section_index]

        assert 0 <= item_index < len(section_items)

        sold_item = section_items[item_index]
        joker_sold = isinstance(sold_item, BaseJoker)

        if joker_sold:
            assert not sold_item.is_eternal

            if self._boss_blind_disabled is False and self._blind is Blind.VERDANT_LEAF:
                self._disable_boss_blind()

        for joker in self._jokers:
            joker._on_item_sold(sold_item)

        section_items.pop(item_index)

        if joker_sold:
            for joker in self._jokers:
                joker._on_jokers_moved()

        self._money += self._calculate_sell_value(sold_item)

    def skip_blind(self) -> None:
        assert self._state is State.SELECTING_BLIND
        assert not self._is_boss_blind

        tag, extra = self._ante_tags[self._blind is Blind.BIG_BLIND]

        self._next_blind()

        self._num_blinds_skipped += 1

        num_tags = 1
        while tag is not Tag.DOUBLE and Tag.DOUBLE in self._tags:
            self._tags.remove(Tag.DOUBLE)
            num_tags += 1

        for _ in range(num_tags):
            match tag:
                case Tag.BOSS:
                    self._random_boss_blind()
                case Tag.HANDY:
                    self._money += 1 * self._num_played_hands
                case Tag.GARBAGE:
                    self._money += 1 * self._num_unused_discards
                case Tag.TOP_UP:
                    for _ in range(min(2, self.joker_slots - len(self._jokers))):
                        self._add_joker(self._get_random_joker(Rarity.COMMON))
                case Tag.SPEED:
                    self._money += 5 * self._num_blinds_skipped
                case Tag.ORBITAL:
                    self._poker_hand_info[extra][0] += 3
                case Tag.ECONOMY:
                    self._money += max(0, min(40, self._money))
                case _:
                    self._tags.append(tag)

        if self._tags and self._tags[-1] in TAG_PACKS:
            self._open_pack(TAG_PACKS[self._tags.pop()])

    def skip_pack(self) -> None:
        assert self._state is State.OPENING_PACK

        for joker in self.jokers:
            joker._on_pack_skipped()

        self._close_pack()

    def use_consumable(
        self, consumable_index: int, selected_card_indices: list[int] | None = None
    ) -> None:
        assert self._state is not State.GAME_OVER

        assert 0 <= consumable_index < len(self._consumables)
        assert selected_card_indices is None or self._hand is not None

        consumable = self._consumables[consumable_index]
        self._use_consumable(consumable, selected_card_indices)
        self._consumables.pop(consumable_index)

    @property
    def _available_money(self) -> int:
        return max(0, self._money + 20 * self._jokers.count(JokerType.CREDIT_CARD))

    @property
    def _discards_each_round(self) -> int:
        discards_each_round = 3

        if self._deck is Deck.RED:
            discards_each_round += 1

        if self._stake >= Stake.BLUE:
            discards_each_round -= 1

        if Voucher.WASTEFUL in self._vouchers:
            discards_each_round += 1
        if Voucher.RECYCLOMANCY in self._vouchers:
            discards_each_round += 1
        if Voucher.PETROGLYPH in self._vouchers:
            discards_each_round -= 1

        for joker in self.jokers:
            match joker:
                case JokerType.DRUNKARD:
                    discards_each_round += 1
                case JokerType.MERRY_ANDY:
                    discards_each_round += 3

        return discards_each_round

    @property
    def _hands_each_round(self) -> int:
        hands_each_round = 4

        match self._deck:
            case Deck.BLUE:
                hands_each_round += 1
            case Deck.BLACK:
                hands_each_round -= 1

        if Voucher.GRABBER in self._vouchers:
            hands_each_round += 1
        if Voucher.NACHO_TONG in self._vouchers:
            hands_each_round += 1
        if Voucher.HIEROGLYPH in self._vouchers:
            hands_each_round -= 1

        return hands_each_round

    @property
    def _is_boss_blind(self) -> bool:
        return self._blind not in [Blind.SMALL_BLIND, Blind.BIG_BLIND]

    @property
    def _is_finisher_ante(self) -> bool:
        return self.ante % 8 == 0

    @property
    def _unlocked_poker_hands(self) -> list[PokerHand]:
        return [
            poker_hand
            for i, poker_hand in enumerate(PokerHand)
            if i > 2 or self._poker_hand_info[poker_hand][1] > 0
        ]

    @property
    def ante(self) -> int:
        ante = self._ante

        if Voucher.HIEROGLYPH in self._vouchers:
            ante -= 1
        if Voucher.PETROGLYPH in self._vouchers:
            ante -= 1

        return ante

    @property
    def ante_tags(
        self,
    ) -> list[tuple[Tag, PokerHand | None], tuple[Tag, PokerHand | None]]:
        return self._ante_tags

    @property
    def blind(self) -> Blind:
        return self._blind

    @property
    def blind_reward(self) -> int:
        return (
            0
            if (self._stake >= Stake.RED and self._blind is Blind.SMALL_BLIND)
            else BLIND_INFO[self._blind][2]
        )

    @property
    def boss_blind(self) -> Blind:
        return self._boss_blind

    @property
    def consumable_slots(self) -> int:
        consumable_slots = 2 + sum(
            consumable.is_negative for consumable in self._consumables
        )

        match self._deck:
            case Deck.MAGIC:
                consumable_slots += 1
            case Deck.NEBULA:
                consumable_slots -= 1

        if Voucher.CRYSTAL_BALL in self._vouchers:
            consumable_slots += 1

        return consumable_slots

    @property
    def consumables(self) -> list[Consumable]:
        return self._consumables

    @property
    def deck(self) -> Deck:
        return self._deck

    @property
    def deck_breakdown(self) -> dict[Suit | Rank, int]:
        deck_breakdown = {
            **{suit: 0 for suit in Suit},
            **{rank: 0 for rank in Rank},
        }

        for deck_card in self.deck_cards_left:
            if deck_card.flipped or deck_card.is_stone_card:
                continue
            deck_breakdown[deck_card.suit] += 1
            deck_breakdown[deck_card.rank] += 1

        return deck_breakdown

    @property
    def deck_cards(self) -> list[Card]:
        return self._deck_cards

    @property
    def deck_cards_left(self) -> list[Card]:
        return (
            self._deck_cards_left
            if self._deck_cards_left is not None
            else self._deck_cards
        )

    @property
    def discards(self) -> int:
        return (
            self._discards if self._discards is not None else self._discards_each_round
        )

    @property
    def hand(self) -> list[Card] | None:
        return self._hand

    @property
    def hand_size(self) -> int:
        hand_size = 8

        if self.deck is Deck.PAINTED:
            hand_size -= 2

        if Voucher.PAINT_BRUSH in self._vouchers:
            hand_size += 1
        if Voucher.PALETTE in self._vouchers:
            hand_size += 1

        for joker in self.jokers:
            match joker:
                case JokerType.STUNTMAN:
                    hand_size -= 2
                case JokerType.TURTLE_BEAN:
                    hand_size += joker.hand_size_increase
                case JokerType.JUGGLER:
                    hand_size += 1
                case JokerType.MERRY_ANDY:
                    hand_size -= 1
                case JokerType.TROUBADOUR:
                    hand_size += 2

        hand_size -= self._hand_size_penalty

        if self._boss_blind_disabled is False and self._blind is Blind.THE_MANACLE:
            hand_size -= 1

        return hand_size

    @property
    def hands(self) -> int | None:
        return self._hands if self._hands is not None else self._hands_each_round

    @property
    def joker_slots(self) -> int:
        joker_slots = 5

        match self._deck:
            case Deck.BLACK:
                joker_slots += 1
            case Deck.PAINTED:
                joker_slots -= 1

        if Voucher.ANTIMATTER in self._vouchers:
            joker_slots += 1

        joker_slots += self._jokers.count(Edition.NEGATIVE)

        return joker_slots

    @property
    def jokers(self) -> list[BaseJoker]:
        return self._jokers

    @property
    def money(self) -> int:
        return self._money

    @property
    def poker_hand_info(self) -> dict[PokerHand : list[int, int]]:
        return self._poker_hand_info

    @property
    def reroll_cost(self) -> int | None:
        if self._reroll_cost is None:
            return None
        return (
            0
            if not self._used_chaos and JokerType.CHAOS_THE_CLOWN in self._jokers
            else self._reroll_cost
        )

    @property
    def round(self) -> int:
        return self._round

    @property
    def round_score(self) -> float:
        return self._round_score if self._round_score is not None else 0

    @property
    def shop_cards(self) -> list[tuple[BaseJoker | Consumable | Card, int]] | None:
        return self._shop_cards

    @property
    def shop_packs(self) -> list[tuple[Pack, int]] | None:
        return self._shop_packs

    @property
    def shop_vouchers(self) -> list[tuple[Voucher, int]] | None:
        return self._shop_vouchers

    @property
    def stake(self) -> Stake:
        return self._stake

    @property
    def state(self) -> State:
        return self._state

    @property
    def tags(self) -> list[Tag]:
        return self._tags

    @property
    def vouchers(self) -> set[Voucher]:
        return self._vouchers
