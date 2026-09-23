"""Bundled demo catalog used when TMDB/RapidAPI credentials aren't configured.

Lets the whole flow — preferences, brief, pool, swiping, matching, rounds,
history — be exercised locally without any external API keys. Posters are
placeholder images (deterministic per title), not real artwork.
"""
from __future__ import annotations

import random

OTT_PLATFORMS = ["Netflix", "Prime Video", "JioHotstar", "Zee5", "SonyLIV", "Aha", "Sun NXT"]


def _poster(seed: str) -> str:
    return f"https://picsum.photos/seed/{seed.replace(' ', '-').lower()}/500/750"


def _ott(seed: str, count: int) -> list[dict]:
    rnd = random.Random(seed)
    picks = rnd.sample(OTT_PLATFORMS, k=min(count, len(OTT_PLATFORMS)))
    return [{"name": name, "url": None} for name in picks]


# (title, media_type, year, language, genres, imdb_rating, runtime_minutes, synopsis, ott_count)
_CATALOG = [
    ("Everything Everywhere All at Once", "movie", 2022, "en", {"fun", "intense"}, 8.0, 139,
     "A laundromat owner discovers she must jump across parallel universes to save reality.", 2),
    ("3 Idiots", "movie", 2009, "hi", {"fun"}, 8.4, 170,
     "Two friends search for their long-lost college buddy, unraveling what happened after graduation.", 3),
    ("Andhadhun", "movie", 2018, "hi", {"intense", "scary"}, 8.2, 139,
     "A blind pianist becomes entangled in a murder he may or may not have witnessed.", 2),
    ("Drishyam", "movie", 2013, "ta", {"intense"}, 8.2, 160,
     "A man goes to extraordinary lengths to protect his family after a fatal accident.", 2),
    ("RRR", "movie", 2022, "te", {"intense", "fun"}, 7.9, 187,
     "Two revolutionaries form an unlikely bond before their paths diverge in colonial India.", 4),
    ("KGF: Chapter 2", "movie", 2022, "kn", {"intense"}, 8.2, 168,
     "A rising crime lord fights to hold onto power over a gold mine empire.", 3),
    ("The Dark Knight", "movie", 2008, "en", {"intense"}, 9.0, 152,
     "Batman faces the Joker, a criminal mastermind bent on chaos.", 2),
    ("Parasite", "movie", 2019, "en", {"intense"}, 8.5, 132,
     "A poor family schemes to become employed by a wealthy household, with unforeseen consequences.", 2),
    ("The Conjuring", "movie", 2013, "en", {"scary"}, 7.5, 112,
     "Paranormal investigators help a family terrorized by a dark presence in their farmhouse.", 3),
    ("Tumbbad", "movie", 2018, "hi", {"scary", "intense"}, 8.2, 104,
     "A man is haunted by a mythical goddess and the curse of unlimited treasure.", 2),
    ("Pariyerum Perumal", "movie", 2018, "ta", {"intense"}, 8.6, 145,
     "A law student's friendship exposes deep-rooted caste discrimination in his town.", 2),
    ("96", "movie", 2018, "ta", {"romantic"}, 8.5, 158,
     "Former classmates reconnect at a reunion and revisit a love left unspoken.", 3),
    ("Jab We Met", "movie", 2007, "hi", {"romantic", "fun"}, 7.9, 138,
     "A chance train encounter changes the lives of a heartbroken man and a free-spirited woman.", 2),
    ("Rockstar", "movie", 2011, "hi", {"romantic", "intense"}, 7.7, 159,
     "A musician's heartbreak fuels his rise to fame, at great personal cost.", 2),
    ("Arjun Reddy", "movie", 2017, "te", {"romantic", "intense"}, 8.1, 182,
     "A brilliant but self-destructive surgeon spirals after losing the love of his life.", 2),
    ("Lucia", "movie", 2013, "kn", {"intense", "scary"}, 8.3, 155,
     "A man's dreams and reality blur after he starts taking an experimental drug.", 1),
    ("Kantara", "movie", 2022, "kn", {"intense", "scary"}, 8.2, 150,
     "A forest guard clashes with a local hero over land tied to a folk deity's wrath.", 2),
    ("Queen", "movie", 2013, "hi", {"fun"}, 8.2, 146,
     "Left at the altar, a woman takes her honeymoon alone and discovers herself.", 3),
    ("Andaz Apna Apna", "movie", 1994, "hi", {"fun"}, 8.1, 160,
     "Two broke, scheming suitors compete for the same wealthy heiress's hand.", 2),
    ("Vikram Vedha", "movie", 2017, "ta", {"intense"}, 8.4, 147,
     "A cop hunts a gangster who tells him stories that blur the line between right and wrong.", 2),
    ("Super Deluxe", "movie", 2019, "ta", {"intense"}, 8.3, 176,
     "Four intersecting stories collide in one strange, unforgettable day in Chennai.", 1),
    ("Fidaa", "movie", 2017, "te", {"romantic", "fun"}, 7.4, 144,
     "An NRI doctor falls for a headstrong village girl during a visit home.", 2),
    ("Ustad Hotel", "movie", 2012, "en", {"fun"}, 8.1, 122,
     "A young man finds purpose working in his grandfather's modest restaurant.", 2),
    ("Inception", "movie", 2010, "en", {"intense"}, 8.8, 148,
     "A thief who steals secrets from dreams takes on one final, impossible job.", 2),
    ("La La Land", "movie", 2016, "en", {"romantic", "fun"}, 8.0, 128,
     "A jazz pianist and an aspiring actress chase their dreams and each other in LA.", 2),
    ("Get Out", "movie", 2017, "en", {"scary", "intense"}, 7.7, 104,
     "A young man uncovers a horrifying secret when he meets his girlfriend's family.", 3),
    ("Hereditary", "movie", 2018, "en", {"scary"}, 7.3, 127,
     "A family unravels after the death of their secretive grandmother reveals dark truths.", 2),
    ("Manichitrathazhu", "movie", 2000, "en", {"scary", "fun"}, 8.7, 175,
     "A family confronts a legend of a spirit locked away in a forbidden room.", 1),
    ("Chhichhore", "movie", 2019, "hi", {"fun", "intense"}, 8.2, 143,
     "College friends reunite to help one of their sons through a crisis, reliving old memories.", 2),
    ("Soorarai Pottru", "movie", 2020, "ta", {"intense", "fun"}, 8.6, 153,
     "A man defies the odds to start India's first low-cost airline.", 2),
    ("The Family Man", "tv", 2019, "hi", {"intense", "fun"}, 8.7, 50,
     "A middle-class intelligence officer juggles saving the nation and keeping his family together.", 3),
    ("Money Heist", "tv", 2017, "en", {"intense"}, 8.2, 50,
     "A criminal mastermind leads a group through the largest heist in history.", 1),
    ("Mirzapur", "tv", 2018, "hi", {"intense"}, 8.5, 55,
     "Power, crime and revenge collide across two families in a lawless town.", 3),
    ("Stranger Things", "tv", 2016, "en", {"scary", "intense"}, 8.6, 50,
     "Kids in a small town uncover supernatural forces and a government conspiracy.", 1),
    ("Panchayat", "tv", 2020, "hi", {"fun"}, 8.9, 35,
     "An engineering graduate adjusts to life as a secretary in a remote village panchayat.", 2),
    ("Aspirants", "tv", 2021, "hi", {"fun", "intense"}, 9.1, 40,
     "Three friends navigate the grueling, all-consuming pursuit of a civil services exam.", 1),
    ("Sacred Games", "tv", 2018, "hi", {"intense", "scary"}, 8.6, 55,
     "A cop races against time after a cryptic tip from a fugitive crime boss.", 1),
    ("Friends", "tv", 1994, "en", {"fun", "romantic"}, 8.9, 22,
     "Six friends navigate life, love and careers in 1990s New York City.", 2),
    ("The Office", "tv", 2005, "en", {"fun"}, 8.9, 22,
     "A mockumentary following the everyday lives of office employees at a paper company.", 2),
    ("Dark", "tv", 2017, "en", {"intense", "scary"}, 8.7, 60,
     "Families unravel a time-bending mystery after children vanish from their town.", 1),
]

_LANGUAGE_ISO = {"hi": "Hindi", "en": "English", "ta": "Tamil", "te": "Telugu", "kn": "Kannada"}


def _era_of(year: int) -> str:
    if year < 2000:
        return "classic"
    if year <= 2020:
        return "2000_2020"
    return "recent"


def full_catalog() -> list[dict]:
    titles = []
    for idx, (title, media_type, year, lang, moods, rating, runtime, synopsis, ott_count) in enumerate(_CATALOG):
        titles.append({
            "tmdb_id": 900000 + idx,
            "media_type": media_type,
            "title": title,
            "year": year,
            "language": lang,
            "moods": moods,
            "era": _era_of(year),
            "poster_url": _poster(title),
            "imdb_rating": rating,
            "runtime": runtime,
            "synopsis": synopsis,
            "ott_platforms": _ott(title, ott_count),
        })
    return titles
