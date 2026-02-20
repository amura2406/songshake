"""Standardized music taxonomy for consistent enrichment tagging.

Values sourced from Wikipedia music genre/mood/instrument lists and
curated for use in the Gemini enrichment prompt. This is the single
source of truth for valid tag values.
"""

# fmt: off
GENRES: list[str] = [
    # Pop
    "Pop", "Synth-pop", "Dance-pop", "Electropop", "Dream-pop", "Bedroom pop",
    "Hyperpop", "K-pop", "J-pop", "Indie pop",
    # Rock
    "Rock", "Alternative", "Indie", "Punk", "Grunge", "Shoegaze",
    "New wave", "Post-punk", "Psychedelic", "Progressive", "Art rock",
    "Experimental", "Noise", "Industrial", "Classic rock", "Hard rock",
    # Metal
    "Metal", "Heavy metal", "Thrash metal", "Death metal", "Black metal",
    # Electronic / Dance
    "Electronic", "Dance", "House", "Techno", "Trance", "Ambient",
    "Drum and bass", "Dubstep", "Future bass", "Chillwave", "Retrowave",
    "Lo-fi", "Trap", "Phonk", "EDM",
    # Hip-hop / R&B
    "Hip-hop", "R&B", "Contemporary R&B", "Neo-soul", "Soul", "Funk",
    "Drill", "Boom bap", "Cloud rap",
    # Latin
    "Latin pop", "Reggaeton", "Urbano latino", "Bachata", "Salsa",
    "Cumbia", "Bossa nova", "Bolero", "Corrido", "Mariachi", "Flamenco",
    # Other
    "Jazz", "Blues", "Country", "Folk", "Acoustic", "Singer-songwriter",
    "Classical", "Gospel", "Disco", "Reggae", "Dancehall", "Ska", "Dub",
    "Afrobeats", "World", "Sertanejo", "MPB",
]

MOODS: list[str] = [
    # Positive / High energy
    "Energetic", "Happy", "Upbeat", "Uplifting", "Euphoric", "Celebratory",
    # Romantic / Sensual
    "Romantic", "Sensual", "Seductive", "Tender", "Dreamy",
    # Sad / Reflective
    "Melancholic", "Sad", "Nostalgic", "Bittersweet", "Wistful", "Lonely",
    # Dark / Intense
    "Aggressive", "Angry", "Dark", "Intense", "Rebellious",
    # Calm / Chill
    "Calm", "Relaxed", "Peaceful", "Chill", "Atmospheric",
    # Groove / Fun
    "Groovy", "Funky", "Danceable", "Catchy", "Playful",
    # Cinematic / Epic
    "Cinematic", "Epic", "Dramatic", "Mysterious", "Haunting",
    # Confident / Bold
    "Confident", "Empowering", "Bold", "Sophisticated", "Contemplative",
]

INSTRUMENTS: list[str] = [
    # Vocals
    "Vocals",
    # Strings
    "Guitar", "Electric guitar", "Acoustic guitar", "Bass", "Bass guitar",
    "Strings", "Violin", "Cello", "Harp", "Mandolin", "Banjo", "Ukulele",
    "Sitar", "Oud",
    # Keys
    "Piano", "Keyboard", "Synthesizer", "Organ", "Accordion",
    # Synth types
    "Bass synth", "Pad synth", "Lead synth",
    # Drums / Percussion
    "Drums", "Drum machine", "Percussion",
    "Congas", "Bongos", "Timbales", "Maracas", "Cajón", "Tabla",
    "Tambourine", "Cowbell", "Claps", "Handclaps",
    "Vibraphone", "Xylophone", "Steel drums",
    # Wind / Brass
    "Trumpet", "Saxophone", "Flute", "Clarinet", "Trombone",
    "French horn", "Oboe", "Harmonica", "Didgeridoo",
    # Electronic
    "Turntables", "Sampler", "Vocoder", "Talk box",
]

VOCAL_TYPES: list[str] = ["Vocals", "Instrumental"]
# fmt: on


def genres_prompt_list() -> str:
    """Return genres as a comma-separated string for Gemini prompts."""
    return ", ".join(GENRES)


def moods_prompt_list() -> str:
    """Return moods as a comma-separated string for Gemini prompts."""
    return ", ".join(MOODS)


def instruments_prompt_list() -> str:
    """Return instruments as a comma-separated string for Gemini prompts."""
    return ", ".join(INSTRUMENTS)
