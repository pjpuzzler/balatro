from __future__ import annotations
import colorsys
import io
import math
from PIL import Image
import random as r

from classes import *
from enums import *

DEFAULT_WIDTH, DEFAULT_HEIGHT = 142, 190

CONSUMABLE_COORDINATES = {
    Tarot.THE_FOOL: [0, 0],
    Tarot.THE_MAGICIAN: [0, 1],
    Tarot.THE_HIGH_PRIESTESS: [0, 2],
    Tarot.THE_EMPRESS: [0, 3],
    Tarot.THE_EMPEROR: [0, 4],
    Tarot.THE_HEIROPHANT: [0, 5],
    Tarot.THE_LOVERS: [0, 6],
    Tarot.THE_CHARIOT: [0, 7],
    Tarot.JUSTICE: [0, 8],
    Tarot.THE_HERMIT: [0, 9],
    Tarot.THE_WHEEL_OF_FORTUNE: [1, 0],
    Tarot.STRENGTH: [1, 1],
    Tarot.THE_HANGED_MAN: [1, 2],
    Tarot.DEATH: [1, 3],
    Tarot.TEMPERANCE: [1, 4],
    Tarot.THE_DEVIL: [1, 5],
    Tarot.THE_TOWER: [1, 6],
    Tarot.THE_STAR: [1, 7],
    Tarot.THE_MOON: [1, 8],
    Tarot.THE_SUN: [1, 9],
    Tarot.JUDGEMENT: [2, 0],
    Tarot.THE_WORLD: [2, 1],
    Planet.ERIS: [2, 3],
    Planet.CERES: [2, 8],
    Planet.PLANET_X: [2, 9],
    Planet.MERCURY: [3, 0],
    Planet.VENUS: [3, 1],
    Planet.EARTH: [3, 2],
    Planet.MARS: [3, 3],
    Planet.JUPITER: [3, 4],
    Planet.SATURN: [3, 5],
    Planet.URANUS: [3, 6],
    Planet.NEPTUNE: [3, 7],
    Planet.PLUTO: [3, 8],
    Spectral.THE_SOUL: [2, 2],
    Spectral.BLACK_HOLE: [3, 9],
    Spectral.FAMILIAR: [4, 0],
    Spectral.GRIM: [4, 1],
    Spectral.INCANTATION: [4, 2],
    Spectral.TALISMAN: [4, 3],
    Spectral.AURA: [4, 4],
    Spectral.WRAITH: [4, 5],
    Spectral.SIGIL: [4, 6],
    Spectral.OUIJA: [4, 7],
    Spectral.ECTOPLASM: [4, 8],
    Spectral.IMMOLATE: [4, 9],
    Spectral.ANKH: [5, 0],
    Spectral.DEJA_VU: [5, 1],
    Spectral.HEX: [5, 2],
    Spectral.TRANCE: [5, 3],
    Spectral.MEDIUM: [5, 4],
    Spectral.CRYPTID: [5, 5],
}
ENHANCER_COORDINATES = {
    Deck.RED: [0, 0],
    Seal.GOLD: [0, 2],
    Deck.NEBULA: [0, 3],
    Enhancement.STONE: [0, 5],
    Enhancement.GOLD: [0, 6],
    Enhancement.BONUS: [1, 1],
    Enhancement.MULT: [1, 2],
    Enhancement.WILD: [1, 3],
    Enhancement.LUCKY: [1, 4],
    Enhancement.GLASS: [1, 5],
    Enhancement.STEEL: [1, 6],
    Deck.BLUE: [2, 0],
    Deck.YELLOW: [2, 1],
    Deck.GREEN: [2, 2],
    Deck.BLACK: [2, 3],
    Deck.PLASMA: [2, 4],
    Deck.GHOST: [2, 6],
    Deck.MAGIC: [3, 0],
    Deck.CHECKERED: [3, 1],
    Deck.ERRATIC: [3, 2],
    Deck.ABANDONED: [3, 3],
    Deck.PAINTED: [3, 4],
    Deck.ANAGLYPH: [4, 2],
    Deck.ZODIAC: [4, 3],
    Seal.PURPLE: [4, 4],
    Seal.RED: [4, 5],
    Seal.BLUE: [4, 6],
}
JOKER_COORDINATES = {
    JokerType.JOKER: [0, 0],
    JokerType.CHAOS_THE_CLOWN: [0, 1],
    JokerType.JOLLY_JOKER: [0, 2],
    JokerType.ZANY_JOKER: [0, 3],
    JokerType.MAD_JOKER: [0, 4],
    JokerType.CRAZY_JOKER: [0, 5],
    JokerType.DROLL_JOKER: [0, 6],
    JokerType.HALF_JOKER: [0, 7],
    JokerType.MERRY_ANDY: [0, 8],
    JokerType.STONE: [0, 9],
    JokerType.JUGGLER: [1, 0],
    JokerType.DRUNKARD: [1, 1],
    JokerType.ACROBAT: [1, 2],
    JokerType.SOCK_AND_BUSKIN: [1, 3],
    JokerType.MIME: [1, 4],
    JokerType.CREDIT_CARD: [1, 5],
    JokerType.GREEDY_JOKER: [1, 6],
    JokerType.LUSTY_JOKER: [1, 7],
    JokerType.WRATHFUL_JOKER: [1, 8],
    JokerType.GLUTTONOUS_JOKER: [1, 9],
    JokerType.TROUBADOUR: [2, 0],
    JokerType.BANNER: [2, 1],
    JokerType.MYSTIC_SUMMIT: [2, 2],
    JokerType.MARBLE_JOKER: [2, 3],
    JokerType.LOYALTY_CARD: [2, 4],
    JokerType.HACK: [2, 5],
    JokerType.MISPRINT: [2, 6],
    JokerType.STEEL_JOKER: [2, 7],
    JokerType.RAISED_FIST: [2, 8],
    JokerType.GOLDEN_JOKER: [2, 9],
    JokerType.BLUEPRINT: [3, 0],
    JokerType.GLASS_JOKER: [3, 1],
    JokerType.SCARY_FACE: [3, 2],
    JokerType.ABSTRACT_JOKER: [3, 3],
    JokerType.DELAYED_GRATIFICATION: [3, 4],
    JokerType.GOLDEN_TICKET: [3, 5],
    JokerType.PAREIDOLIA: [3, 6],
    JokerType.CARTOMANCER: [3, 7],
    JokerType.EVEN_STEVEN: [3, 8],
    JokerType.ODD_TODD: [3, 9],
    JokerType.SCHOLAR: [4, 0],
    JokerType.BUSINESS_CARD: [4, 1],
    JokerType.SUPERNOVA: [4, 2],
    JokerType.MR_BONES: [4, 3],
    JokerType.SEEING_DOUBLE: [4, 4],
    JokerType.THE_DUO: [4, 5],
    JokerType.THE_TRIO: [4, 6],
    JokerType.THE_FAMILY: [4, 7],
    JokerType.THE_ORDER: [4, 8],
    JokerType.THE_TRIBE: [4, 9],
    JokerType.EIGHT_BALL: [5, 0],
    JokerType.FIBONACCI: [5, 1],
    JokerType.JOKER_STENCIL: [5, 2],
    JokerType.SPACE: [5, 3],
    JokerType.MATADOR: [5, 4],
    JokerType.CEREMONIAL_DAGGER: [5, 5],
    JokerType.SHOWMAN: [5, 6],
    JokerType.FORTUNE_TELLER: [5, 7],
    JokerType.HIT_THE_ROAD: [5, 8],
    JokerType.SWASHBUCKLER: [5, 9],
    JokerType.FLOWER_POT: [6, 0],
    JokerType.RIDE_THE_BUS: [6, 1],
    JokerType.SHOOT_THE_MOON: [6, 2],
    JokerType.SMEARED_JOKER: [6, 4],
    JokerType.OOPS_ALL_SIXES: [6, 5],
    JokerType.FOUR_FINGERS: [6, 6],
    JokerType.GROS_MICHEL: [6, 7],
    JokerType.STUNTMAN: [6, 8],
    JokerType.HANGING_CHAD: [6, 9],
    JokerType.DRIVERS_LICENSE: [7, 0],
    JokerType.INVISIBLE_JOKER: [7, 1],
    JokerType.ASTRONOMER: [7, 2],
    JokerType.BURNT_JOKER: [7, 3],
    JokerType.DUSK: [7, 4],
    JokerType.THROWBACK: [7, 5],
    JokerType.THE_IDOL: [7, 6],
    JokerType.BRAINSTORM: [7, 7],
    JokerType.SATELLITE: [7, 8],
    JokerType.ROUGH_GEM: [7, 9],
    JokerType.BLOODSTONE: [8, 0],
    JokerType.ARROWHEAD: [8, 1],
    JokerType.ONYX_AGATE: [8, 2],
    JokerType.CANIO: [8, 3],
    JokerType.TRIBOULET: [8, 4],
    JokerType.YORICK: [8, 5],
    JokerType.CHICOT: [8, 6],
    JokerType.PERKEO: [8, 7],
    JokerType.CERTIFICATE: [8, 8],
    JokerType.BOOTSTRAPS: [8, 9],
    JokerType.EGG: [10, 0],
    JokerType.BURGLAR: [10, 1],
    JokerType.BLACKBOARD: [10, 2],
    JokerType.RUNNER: [10, 3],
    JokerType.ICE_CREAM: [10, 4],
    JokerType.DNA: [10, 5],
    JokerType.SPLASH: [10, 6],
    JokerType.BLUE_JOKER: [10, 7],
    JokerType.SIXTH_SENSE: [10, 8],
    JokerType.CONSTELLATION: [10, 9],
    JokerType.HIKER: [11, 0],
    JokerType.FACELESS_JOKER: [11, 1],
    JokerType.GREEN_JOKER: [11, 2],
    JokerType.SUPERPOSITION: [11, 3],
    JokerType.TODO_LIST: [11, 4],
    JokerType.CAVENDISH: [11, 5],
    JokerType.CARD_SHARP: [11, 6],
    JokerType.RED_CARD: [11, 7],
    JokerType.MADNESS: [11, 8],
    JokerType.SQUARE_JOKER: [11, 9],
    JokerType.SEANCE: [12, 0],
    JokerType.RIFF_RAFF: [12, 1],
    JokerType.VAMPIRE: [12, 2],
    JokerType.SHORTCUT: [12, 3],
    JokerType.HOLOGRAM: [12, 4],
    JokerType.VAGABOND: [12, 5],
    JokerType.BARON: [12, 6],
    JokerType.CLOUD_NINE: [12, 7],
    JokerType.ROCKET: [12, 8],
    JokerType.OBELISK: [12, 9],
    JokerType.MIDAS_MASK: [13, 0],
    JokerType.LUCHADOR: [13, 1],
    JokerType.PHOTOGRAPH: [13, 2],
    JokerType.GIFT_CARD: [13, 3],
    JokerType.TURTLE_BEAN: [13, 4],
    JokerType.EROSION: [13, 5],
    JokerType.RESERVED_PARKING: [13, 6],
    JokerType.MAIL_IN_REBATE: [13, 7],
    JokerType.TO_THE_MOON: [13, 8],
    JokerType.HALLUCINATION: [13, 9],
    JokerType.SLY_JOKER: [14, 0],
    JokerType.WILY_JOKER: [14, 1],
    JokerType.CLEVER_JOKER: [14, 2],
    JokerType.DEVIOUS_JOKER: [14, 3],
    JokerType.CRAFTY_JOKER: [14, 4],
    JokerType.LUCKY_CAT: [14, 5],
    JokerType.BASEBALL_CARD: [14, 6],
    JokerType.BULL: [14, 7],
    JokerType.DIET_COLA: [14, 8],
    JokerType.TRADING_CARD: [14, 9],
    JokerType.FLASH_CARD: [15, 0],
    JokerType.POPCORN: [15, 1],
    JokerType.RAMEN: [15, 2],
    JokerType.SELTZER: [15, 3],
    JokerType.SPARE_TROUSERS: [15, 4],
    JokerType.CAMPFIRE: [15, 5],
    JokerType.SMILEY_FACE: [15, 6],
    JokerType.ANCIENT_JOKER: [15, 7],
    JokerType.WALKIE_TALKIE: [15, 8],
    JokerType.CASTLE: [15, 9],
}
PACK_COORDINATES = {
    Pack.ARCANA: [[0, 0], [0, 1], [0, 2], [0, 3]],
    Pack.CELESTIAL: [[1, 0], [1, 1], [1, 2], [1, 3]],
    Pack.JUMBO_ARCANA: [[2, 0], [2, 1]],
    Pack.MEGA_ARCANA: [[2, 2], [2, 3]],
    Pack.JUMBO_CELESTIAL: [[3, 0], [3, 1]],
    Pack.MEGA_CELESTIAL: [[3, 2], [3, 3]],
    Pack.SPECTRAL: [[4, 0], [4, 1]],
    Pack.JUMBO_SPECTRAL: [[4, 2]],
    Pack.MEGA_SPECTRAL: [[4, 3]],
    Pack.STANDARD: [[6, 0], [6, 1], [6, 2], [6, 3]],
    Pack.JUMBO_STANDARD: [[7, 0], [7, 1]],
    Pack.MEGA_STANDARD: [[7, 2], [7, 3]],
    Pack.BUFFOON: [[8, 0], [8, 1]],
    Pack.JUMBO_BUFFOON: [[8, 2]],
    Pack.MEGA_BUFFOON: [[8, 3]],
}
RANK_COLUMNS = {rank: i for i, rank in enumerate(reversed(Rank))}
SUIT_ROWS = {Suit.HEARTS: 0, Suit.CLUBS: 1, Suit.DIAMONDS: 2, Suit.SPADES: 3}
VOUCHER_COORDINATES = {
    Voucher.OVERSTOCK: [0, 0],
    Voucher.TAROT_MERCHANT: [0, 1],
    Voucher.PLANET_MERCHANT: [0, 2],
    Voucher.CLEARANCE_SALE: [0, 3],
    Voucher.HONE: [0, 4],
    Voucher.GRABBER: [0, 5],
    Voucher.WASTEFUL: [0, 6],
    Voucher.BLANK: [0, 7],
    Voucher.OVERSTOCK_PLUS: [1, 0],
    Voucher.TAROT_TYCOON: [1, 1],
    Voucher.PLANET_TYCOON: [1, 2],
    Voucher.LIQUIDATION: [1, 3],
    Voucher.GLOW_UP: [1, 4],
    Voucher.NACHO_TONG: [1, 5],
    Voucher.RECYCLOMANCY: [1, 6],
    Voucher.ANTIMATTER: [1, 7],
    Voucher.REROLL_SURPLUS: [2, 0],
    Voucher.SEED_MONEY: [2, 1],
    Voucher.CRYSTAL_BALL: [2, 2],
    Voucher.TELESCOPE: [2, 3],
    Voucher.MAGIC_TRICK: [2, 4],
    Voucher.HIEROGLYPH: [2, 5],
    Voucher.DIRECTORS_CUT: [2, 6],
    Voucher.PAINT_BRUSH: [2, 7],
    Voucher.REROLL_GLUT: [3, 0],
    Voucher.MONEY_TREE: [3, 1],
    Voucher.OMEN_GLOBE: [3, 2],
    Voucher.OBSERVATORY: [3, 3],
    Voucher.ILLUSION: [3, 4],
    Voucher.PETROGLYPH: [3, 5],
    Voucher.RETCON: [3, 6],
    Voucher.PALETTE: [3, 7],
}


def _apply_edition(sprite: Image.Image, edition: Edition) -> Image.Image:
    match edition:
        case Edition.BASE:
            return sprite
        case Edition.FOIL:
            return _apply_foil(sprite)
        case Edition.HOLO:
            return _apply_holo(sprite)
        case Edition.POLYCHROME:
            return _apply_polychrome(sprite)
        case Edition.NEGATIVE:
            return _apply_negative(sprite)


def _apply_foil(sprite: Image.Image) -> Image.Image:
    width, height = sprite.size
    aspect_ratio = height / width
    texture_details = (0, 0, width, height)
    image_details = (width, height)
    foil = (0, 0)

    foil_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    foil_pixels = foil_overlay.load()
    base_pixels = sprite.load()

    for x in range(width):
        for y in range(height):
            texture_coords = (x / width, y / height)
            uv_x = (
                texture_coords[0] * image_details[0]
                - texture_details[0] * texture_details[2]
            ) / texture_details[2]
            uv_y = (
                texture_coords[1] * image_details[1]
                - texture_details[1] * texture_details[3]
            ) / texture_details[3]
            uv = (uv_x, uv_y)

            adjusted_uv_x = uv[0] - 0.5
            adjusted_uv_y = uv[1] - 0.5
            adjusted_uv = (adjusted_uv_x, adjusted_uv_y)

            r, g, b, a = base_pixels[x, y]
            if a == 0:
                continue
            tex_r, tex_g, tex_b = r / 255.0, g / 255.0, b / 255.0

            low = min(tex_r, min(tex_g, tex_b))
            high = max(tex_r, max(tex_g, tex_b))
            delta = min(high, max(0.5, 1.0 - low))

            scaled_adjusted_uv_y = adjusted_uv_y * aspect_ratio
            ripple_factor = math.sqrt(adjusted_uv_x**2 + scaled_adjusted_uv_y**2)

            fac = max(
                min(
                    2.0
                    * math.sin(
                        (90.0 * ripple_factor + foil[0] * 2.0)
                        + 3.0
                        * (
                            1.0
                            + 0.8 * math.cos(113.1121 * ripple_factor - foil[0] * 3.121)
                        )
                    )
                    - 1.0
                    - max(5.0 - 90.0 * ripple_factor, 0.0),
                    1.0,
                ),
                0.0,
            )

            rotater = (math.cos(foil[0] * 0.1221), math.sin(foil[0] * 0.3512))
            angle = (
                (rotater[0] * adjusted_uv[0] + rotater[1] * adjusted_uv[1])
                / (
                    math.sqrt(rotater[0] ** 2 + rotater[1] ** 2)
                    * math.sqrt(adjusted_uv[0] ** 2 + adjusted_uv[1] ** 2)
                )
                if (rotater[0] ** 2 + rotater[1] ** 2) > 0
                and (adjusted_uv[0] ** 2 + adjusted_uv[1] ** 2) > 0
                else 0
            )
            fac2 = max(
                min(
                    5.0
                    * math.cos(
                        foil[1] * 0.3
                        + angle
                        * 3.14
                        * (2.2 + 0.9 * math.sin(foil[0] * 1.65 + 0.2 * foil[1]))
                    )
                    - 4.0
                    - max(
                        2.0
                        - 20.0 * math.sqrt(adjusted_uv[0] ** 2 + adjusted_uv[1] ** 2),
                        0.0,
                    ),
                    1.0,
                ),
                0.0,
            )
            fac3 = 0.3 * max(
                min(
                    2.0
                    * math.sin(
                        foil[0] * 5.0
                        + uv[0] * 3.0
                        + 3.0 * (1.0 + 0.5 * math.cos(foil[0] * 7.0))
                    )
                    - 1.0,
                    1.0,
                ),
                -1.0,
            )
            fac4 = 0.3 * max(
                min(
                    2.0
                    * math.sin(
                        foil[0] * 6.66
                        + uv[1] * 3.8
                        + 3.0 * (1.0 + 0.5 * math.cos(foil[0] * 3.414))
                    )
                    - 1.0,
                    1.0,
                ),
                -1.0,
            )

            maxfac = max(
                max(fac, max(fac2, max(fac3, max(fac4, 0.0))))
                + 2.2 * (fac + fac2 + fac3 + fac4),
                0.0,
            )

            foil_r = tex_r - delta + delta * maxfac * 0.3
            foil_g = tex_g - delta + delta * maxfac * 0.3
            foil_b = tex_b + delta * maxfac * 1.9
            foil_alpha = min(1.0, 0.5 * 1.0 + 0.8 * min(0.7, maxfac * 0.2))

            final_foil_alpha = foil_alpha * (a / 255.0)

            foil_pixels[x, y] = (
                int(max(0, min(1, foil_r)) * 255),
                int(max(0, min(1, foil_g)) * 255),
                int(max(0, min(1, foil_b)) * 255),
                int(max(0, min(1, foil_alpha - 0.1)) * 255),
            )

    return Image.alpha_composite(sprite, foil_overlay)


def _apply_holo(sprite: Image.Image) -> Image.Image:
    width, height = sprite.size
    holo = (0, 0)
    texture_details = (0, 0, width, height)
    image_details = (width, height)
    holo_alpha = 0.3

    holo_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    holo_pixels = holo_overlay.load()

    for x in range(width):
        for y in range(height):
            texture_coords = (x / width, y / height)
            uv_x = (
                texture_coords[0] * image_details[0]
                - texture_details[0] * texture_details[2]
            ) / texture_details[2]
            uv_y = (
                texture_coords[1] * image_details[1]
                - texture_details[1] * texture_details[3]
            ) / texture_details[3]
            uv = (uv_x, uv_y)

            r, g, b, a = sprite.getpixel((x, y))
            if a == 0:
                continue

            hsl = colorsys.rgb_to_hls(0.5 * 0, 0.5 * 0, 0.5 * 1)
            # r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0
            # hsl = colorsys.rgb_to_hls(
            #     0.5 * r_norm + 0.5 * 0, 0.5 * g_norm + 0.5 * 0, 0.5 * b_norm + 0.5 * 1
            # )

            t = 0
            floored_uv_x = math.floor(uv_x * texture_details[2]) / texture_details[2]
            floored_uv_y = math.floor(uv_y * texture_details[3]) / texture_details[3]
            floored_uv = (floored_uv_x, floored_uv_y)
            uv_scaled_centered_x = (floored_uv[0] - 0.5) * 250.0
            uv_scaled_centered_y = (floored_uv[1] - 0.5) * 250.0
            uv_scaled_centered = (uv_scaled_centered_x, uv_scaled_centered_y)

            field_part1_x = uv_scaled_centered[0] + 50.0 * math.sin(-t / 143.6340)
            field_part1_y = uv_scaled_centered[1] + 50.0 * math.cos(-t / 99.4324)
            field_part1 = (field_part1_x, field_part1_y)
            field_part2_x = uv_scaled_centered[0] + 50.0 * math.cos(t / 53.1532)
            field_part2_y = uv_scaled_centered[1] + 50.0 * math.cos(t / 61.4532)
            field_part2 = (field_part2_x, field_part2_y)
            field_part3_x = uv_scaled_centered[0] + 50.0 * math.sin(-t / 87.53218)
            field_part3_y = uv_scaled_centered[1] + 50.0 * math.sin(-t / 49.0000)
            field_part3 = (field_part3_x, field_part3_y)

            field = (
                1.0
                + (
                    math.cos(
                        math.sqrt(field_part1[0] ** 2 + field_part1[1] ** 2) / 19.483
                    )
                    + math.sin(
                        math.sqrt(field_part2[0] ** 2 + field_part2[1] ** 2) / 33.155
                    )
                    * math.cos(field_part2[1] / 15.73)
                    + math.cos(
                        math.sqrt(field_part3[0] ** 2 + field_part3[1] ** 2) / 27.193
                    )
                    * math.sin(field_part3[0] / 21.92)
                )
            ) / 2.0

            res = 0.5 + 0.5 * math.cos(holo[0] * 2.612 + (field - 0.5) * 3.14)

            gridsize = 0.79
            fac = 0.5 * max(
                0.0,
                7.0 * abs(math.cos(uv_x * gridsize * 20.0)) - 6.0,
                max(
                    0.0,
                    7.0 * math.cos(uv_y * gridsize * 45.0 + uv_x * gridsize * 20.0)
                    - 6.0,
                ),
                max(
                    0.0,
                    7.0 * math.cos(uv_y * gridsize * 45.0 - uv_x * gridsize * 20.0)
                    - 6.0,
                ),
            )

            h = hsl[0] + res + fac
            l = hsl[1] * 1.3
            s = hsl[2] * 0.6 + 0.4

            modified_r, modified_g, modified_b = colorsys.hls_to_rgb(h, l, s)

            holo_pixels[x, y] = (
                int(max(0, min(1, modified_r * 0.9)) * 255),
                int(max(0, min(1, modified_g * 0.8)) * 255),
                int(max(0, min(1, modified_b * 1.2)) * 255),
                int(max(0, min(1, holo_alpha)) * 255),
            )

    return Image.alpha_composite(sprite, holo_overlay)


def _apply_polychrome(sprite: Image.Image) -> Image.Image:
    width, height = sprite.size
    polychrome_val = (0, 0)  # Static polychrome values (tilt0)
    texture_details = (0, 0, width, height)
    image_details = (width, height)

    polychrome_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_pixels = polychrome_overlay.load()
    base_pixels = sprite.load()

    for x in range(width):
        for y in range(height):
            r, g, b, a = base_pixels[x, y]
            if a == 0:
                continue
            tex_r, tex_g, tex_b = r / 255.0, g / 255.0, b / 255.0

            brightness = 0.299 * tex_r + 0.587 * tex_g + 0.114 * tex_b

            low = min(tex_r, tex_g, tex_b)
            high = max(tex_r, tex_g, tex_b)
            delta = high - low

            saturation_fac = 1.0 - max(0.0, 0.05 * (1.1 - delta))
            saturated_r, saturated_g, saturated_b = (
                tex_r * saturation_fac,
                tex_g * saturation_fac,
                tex_b,
            )

            hsl = colorsys.rgb_to_hls(saturated_r, saturated_g, saturated_b)

            texture_coords = (x / width, y / height)
            uv_x = (
                texture_coords[0] * image_details[0]
                - texture_details[0] * texture_details[2]
            ) / texture_details[2]
            uv_y = (
                texture_coords[1] * image_details[1]
                - texture_details[1] * texture_details[3]
            ) / texture_details[3]
            uv = (uv_x, uv_y)

            floored_uv_x = math.floor(uv_x * texture_details[2]) / texture_details[2]
            floored_uv_y = math.floor(uv_y * texture_details[3]) / texture_details[3]
            floored_uv = (floored_uv_x, floored_uv_y)
            uv_scaled_centered_x = (floored_uv[0] - 0.5) * 50.0
            uv_scaled_centered_y = (floored_uv[1] - 0.5) * 50.0
            uv_scaled_centered = (uv_scaled_centered_x, uv_scaled_centered_y)

            field_part1_x = uv_scaled_centered[0] + 50.0 * math.sin(0)  # time = 0
            field_part1_y = uv_scaled_centered[1] + 50.0 * math.cos(0)  # time = 0
            field_part1 = (field_part1_x, field_part1_y)
            field_part2_x = uv_scaled_centered[0] + 50.0 * math.cos(0)  # time = 0
            field_part2_y = uv_scaled_centered[1] + 50.0 * math.cos(0)  # time = 0
            field_part2 = (field_part2_x, field_part2_y)
            field_part3_x = uv_scaled_centered[0] + 50.0 * math.sin(0)  # time = 0
            field_part3_y = uv_scaled_centered[1] + 50.0 * math.sin(0)  # time = 0
            field_part3 = (field_part3_x, field_part3_y)

            field = (
                1.0
                + (
                    math.cos(
                        math.sqrt(field_part1[0] ** 2 + field_part1[1] ** 2) / 19.483
                    )
                    + math.sin(
                        math.sqrt(field_part2[0] ** 2 + field_part2[1] ** 2) / 33.155
                    )
                    * math.cos(field_part2[1] / 15.73)
                    + math.cos(
                        math.sqrt(field_part3[0] ** 2 + field_part3[1] ** 2) / 27.193
                    )
                    * math.sin(field_part3[0] / 21.92)
                )
            ) / 2.0

            res = 0.5 + 0.5 * math.cos(polychrome_val[0] * 2.612 + (field - 0.5) * 3.14)

            h = hsl[0] + res + polychrome_val[1] * 0.04
            l = min(0.6, hsl[1] + 0.5)
            s = hsl[2] + 0.5

            modified_r, modified_g, modified_b = colorsys.hls_to_rgb(h, l, s)

            effect_intensity = 0.1 if brightness > 0.9 else 0.5
            # effect_intensity = 0.8
            overlay_r = modified_r
            overlay_g = modified_g
            overlay_b = modified_b
            overlay_alpha = effect_intensity

            overlay_pixels[x, y] = (
                int(max(0, min(1, overlay_r)) * 255),
                int(max(0, min(1, overlay_g)) * 255),
                int(max(0, min(1, overlay_b)) * 255),
                int(overlay_alpha * 255),
            )

    return Image.alpha_composite(sprite, polychrome_overlay)


def _apply_negative(sprite: Image.Image) -> Image.Image:
    width, height = sprite.size
    new_sprite = Image.new("RGBA", (width, height))

    for x in range(width):
        for y in range(height):
            r, g, b, a = sprite.getpixel((x, y))

            # if a <= 0:
            #     new_sprite.putpixel((x, y), (0, 0, 0, 0))
            #     continue

            r_norm, g_norm, b_norm = r / 255.0, g / 255.0, b / 255.0

            h, l, s = colorsys.rgb_to_hls(r_norm, g_norm, b_norm)

            l = 1.0 - l
            h = -h + 0.2
            # h %= 1.0

            r_new_norm, g_new_norm, b_new_norm = colorsys.hls_to_rgb(h, l, s)

            constant_r = 79 / 255.0
            constant_g = 99 / 255.0
            constant_b = 103 / 255.0

            r_new_norm += 0.8 * constant_r
            g_new_norm += 0.8 * constant_g
            b_new_norm += 0.8 * constant_b

            r_new = int(r_new_norm * 255)
            g_new = int(g_new_norm * 255)
            b_new = int(b_new_norm * 255)

            new_sprite.putpixel((x, y), (r_new, g_new, b_new, a))

    return new_sprite


def get_sprite(
    item: BaseJoker | Consumable | Card | Voucher | Stake | Tag | Blind | Deck | Pack,
    as_image: bool = True,
) -> bytes:
    match item:
        case BaseJoker():
            joker_sheet = Image.open("resources/textures/Jokers.png")

            match item.joker_type:
                case JokerType.HALF_JOKER:
                    WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT // 1.7
                case JokerType.SQUARE_JOKER:
                    WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_WIDTH
                case JokerType.PHOTOGRAPH:
                    WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT // 1.2
                case _:
                    WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT

            i, j = JOKER_COORDINATES.get(item.joker_type, [0, 0])
            x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
            x2, y2 = x1 + WIDTH, y1 + HEIGHT
            sprite = joker_sheet.crop((x1, y1, x2, y2))

            sprite = _apply_edition(sprite, item.edition)

            match item.joker_type:
                case JokerType.WEE_JOKER:
                    WIDTH, HEIGHT = int(WIDTH * 0.7), int(HEIGHT * 0.7)
                    sprite = sprite.resize((WIDTH, HEIGHT))
                case (
                    JokerType.CANIO
                    | JokerType.TRIBOULET
                    | JokerType.YORICK
                    | JokerType.CHICOT
                    | JokerType.PERKEO
                ):
                    i, j = i + 1, j
                    x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
                    x2, y2 = x1 + WIDTH, y1 + HEIGHT
                    face_sprite = joker_sheet.crop((x1, y1, x2, y2))
                    sprite = Image.alpha_composite(sprite, face_sprite)
                case JokerType.HOLOGRAM:
                    i, j = 9, 2
                    x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
                    x2, y2 = x1 + WIDTH, y1 + HEIGHT
                    face_sprite = joker_sheet.crop((x1, y1, x2, y2))
                    sprite = Image.alpha_composite(sprite, face_sprite)

            if item.debuffed:
                raise NotImplementedError
        case Consumable():
            consumable_sheet = Image.open("resources/textures/Tarots.png")

            i, j = CONSUMABLE_COORDINATES[item.card]
            x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
            x2, y2 = x1 + DEFAULT_WIDTH, y1 + DEFAULT_HEIGHT
            sprite = consumable_sheet.crop((x1, y1, x2, y2))

            sprite = _apply_edition(
                sprite, Edition.NEGATIVE if item.is_negative else Edition.BASE
            )

            if item.card is Spectral.THE_SOUL:
                enhancers_sheet = Image.open("resources/textures/Enhancers.png")
                i, j = 1, 0
                x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
                x2, y2 = x1 + DEFAULT_WIDTH, y1 + DEFAULT_HEIGHT
                soul_sprite = enhancers_sheet.crop((x1, y1, x2, y2))
                sprite = Image.alpha_composite(sprite, soul_sprite)
        case Card():
            deck_sheet = Image.open("resources/textures/8BitDeck.png")
            enhancers_sheet = Image.open("resources/textures/Enhancers.png")

            i, j = ENHANCER_COORDINATES.get(item.enhancement, (0, 1))
            x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
            x2, y2 = x1 + DEFAULT_WIDTH, y1 + DEFAULT_HEIGHT
            back_sprite = enhancers_sheet.crop((x1, y1, x2, y2))

            if not item.is_stone_card:
                i, j = SUIT_ROWS[item.suit], RANK_COLUMNS[item.rank]
                x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
                x2, y2 = x1 + DEFAULT_WIDTH, y1 + DEFAULT_HEIGHT
                card_sprite = deck_sheet.crop((x1, y1, x2, y2))
                sprite = Image.alpha_composite(back_sprite, card_sprite)
            else:
                sprite = back_sprite

            sprite = _apply_edition(sprite, item.edition)

            if item.seal is not None:
                i, j = ENHANCER_COORDINATES[item.seal]
                x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
                x2, y2 = x1 + DEFAULT_WIDTH, y1 + DEFAULT_HEIGHT
                seal_sprite = enhancers_sheet.crop((x1, y1, x2, y2))
                sprite = Image.alpha_composite(sprite, seal_sprite)

            if item.debuffed:
                raise NotImplementedError
        case Voucher():
            voucher_sheet = Image.open("resources/textures/Vouchers.png")

            i, j = VOUCHER_COORDINATES[item]
            x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
            x2, y2 = x1 + DEFAULT_WIDTH, y1 + DEFAULT_HEIGHT
            sprite = voucher_sheet.crop((x1, y1, x2, y2))
        case Deck():
            enhancers_sheet = Image.open("resources/textures/Enhancers.png")

            i, j = ENHANCER_COORDINATES[item]
            x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
            x2, y2 = x1 + DEFAULT_WIDTH, y1 + DEFAULT_HEIGHT
            sprite = enhancers_sheet.crop((x1, y1, x2, y2))
        case Pack():
            pack_sheet = Image.open("resources/textures/boosters.png")

            # i, j = r.choice(PACK_COORDINATES[item])
            i, j = PACK_COORDINATES[item][0]
            x1, y1 = DEFAULT_WIDTH * j, DEFAULT_HEIGHT * i
            x2, y2 = x1 + DEFAULT_WIDTH, y1 + DEFAULT_HEIGHT
            sprite = pack_sheet.crop((x1, y1, x2, y2))
        case _:
            raise NotImplementedError

    if as_image:
        return sprite
    with io.BytesIO() as buffer:
        sprite.save(buffer, "png")
        return buffer.getvalue()