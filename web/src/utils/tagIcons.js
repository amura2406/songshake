/**
 * Icon mappings for genre, mood, and instrument taxonomy.
 *
 * Uses category-level grouping (~25 icons) rather than per-value mapping
 * for maintainability. Returns Lucide React component names or Material
 * Icon ligatures depending on which library has the best icon.
 */
import {
    Sparkles,
    Guitar,
    Skull,
    Waves,
    Mic,
    Sun,
    Music,
    TreePine,
    Globe,
    Disc,
    Zap,
    Heart,
    CloudRain,
    Flame,
    Moon,
    PartyPopper,
    Clapperboard,
    Crown,
    Music2,
    Wind,
    Radio,
} from 'lucide-react';

// ─── Genre category mapping ────────────────────────────────────────
const GENRE_GROUPS = [
    {
        icon: Sparkles,
        values: [
            'Pop', 'Synth-pop', 'Dance-pop', 'Electropop', 'Dream-pop',
            'Bedroom pop', 'Hyperpop', 'K-pop', 'J-pop', 'Indie pop',
        ],
    },
    {
        icon: Guitar,
        values: [
            'Rock', 'Alternative', 'Indie', 'Punk', 'Grunge', 'Shoegaze',
            'New wave', 'Post-punk', 'Psychedelic', 'Progressive', 'Art rock',
            'Experimental', 'Noise', 'Industrial', 'Classic rock', 'Hard rock',
        ],
    },
    {
        icon: Skull,
        values: ['Metal', 'Heavy metal', 'Thrash metal', 'Death metal', 'Black metal'],
    },
    {
        icon: Waves,
        values: [
            'Electronic', 'Dance', 'House', 'Techno', 'Trance', 'Ambient',
            'Drum and bass', 'Dubstep', 'Future bass', 'Chillwave', 'Retrowave',
            'Lo-fi', 'Trap', 'Phonk', 'EDM',
        ],
    },
    {
        icon: Mic,
        values: [
            'Hip-hop', 'R&B', 'Contemporary R&B', 'Neo-soul', 'Soul', 'Funk',
            'Drill', 'Boom bap', 'Cloud rap',
        ],
    },
    {
        icon: Sun,
        values: [
            'Latin pop', 'Reggaeton', 'Urbano latino', 'Bachata', 'Salsa',
            'Cumbia', 'Bossa nova', 'Bolero', 'Corrido', 'Mariachi', 'Flamenco',
            'Sertanejo', 'MPB',
        ],
    },
    {
        icon: Music,
        values: ['Jazz', 'Blues'],
    },
    {
        icon: TreePine,
        values: ['Country', 'Folk', 'Acoustic', 'Singer-songwriter'],
    },
    {
        icon: Globe,
        values: ['Reggae', 'Dancehall', 'Ska', 'Dub', 'Afrobeats', 'World'],
    },
    {
        icon: Disc,
        values: ['Disco'],
    },
    {
        // Classical / Gospel — Material Icon "church"
        materialIcon: 'church',
        values: ['Classical', 'Gospel'],
    },
];

// ─── Mood category mapping ─────────────────────────────────────────
const MOOD_GROUPS = [
    {
        icon: Zap,
        values: ['Energetic', 'Happy', 'Upbeat', 'Uplifting', 'Euphoric', 'Celebratory'],
    },
    {
        icon: Heart,
        values: ['Romantic', 'Sensual', 'Seductive', 'Tender', 'Dreamy'],
    },
    {
        icon: CloudRain,
        values: ['Melancholic', 'Sad', 'Nostalgic', 'Bittersweet', 'Wistful', 'Lonely'],
    },
    {
        icon: Flame,
        values: ['Aggressive', 'Angry', 'Dark', 'Intense', 'Rebellious'],
    },
    {
        icon: Moon,
        values: ['Calm', 'Relaxed', 'Peaceful', 'Chill', 'Atmospheric'],
    },
    {
        icon: PartyPopper,
        values: ['Groovy', 'Funky', 'Danceable', 'Catchy', 'Playful'],
    },
    {
        icon: Clapperboard,
        values: ['Cinematic', 'Epic', 'Dramatic', 'Mysterious', 'Haunting'],
    },
    {
        icon: Crown,
        values: ['Confident', 'Empowering', 'Bold', 'Sophisticated', 'Contemplative'],
    },
];

// ─── Instrument category mapping ───────────────────────────────────
const INSTRUMENT_GROUPS = [
    {
        icon: Mic,
        values: ['Vocals'],
    },
    {
        icon: Guitar,
        values: ['Guitar', 'Electric guitar', 'Acoustic guitar'],
    },
    {
        // Bass — Material Icon "nightlife"
        materialIcon: 'nightlife',
        values: ['Bass', 'Bass guitar'],
    },
    {
        icon: Music2,
        values: [
            'Strings', 'Violin', 'Cello', 'Harp', 'Mandolin', 'Banjo',
            'Ukulele', 'Sitar', 'Oud',
        ],
    },
    {
        // Piano — Material Icon "piano"
        materialIcon: 'piano',
        values: ['Piano', 'Keyboard', 'Organ', 'Accordion'],
    },
    {
        icon: Waves,
        values: ['Synthesizer', 'Bass synth', 'Pad synth', 'Lead synth'],
    },
    {
        icon: Disc,
        values: [
            'Drums', 'Drum machine', 'Percussion', 'Congas', 'Bongos',
            'Timbales', 'Maracas', 'Cajón', 'Tabla', 'Tambourine', 'Cowbell',
            'Claps', 'Handclaps', 'Vibraphone', 'Xylophone', 'Steel drums',
        ],
    },
    {
        icon: Wind,
        values: [
            'Trumpet', 'Saxophone', 'Flute', 'Clarinet', 'Trombone',
            'French horn', 'Oboe', 'Harmonica', 'Didgeridoo',
        ],
    },
    {
        icon: Radio,
        values: ['Turntables', 'Sampler', 'Vocoder', 'Talk box'],
    },
];

// ─── Build fast lookup maps ────────────────────────────────────────
function buildLookup(groups) {
    const map = new Map();
    for (const group of groups) {
        const entry = group.icon
            ? { icon: group.icon }
            : { materialIcon: group.materialIcon };
        for (const value of group.values) {
            map.set(value, entry);
        }
    }
    return map;
}

const genreLookup = buildLookup(GENRE_GROUPS);
const moodLookup = buildLookup(MOOD_GROUPS);
const instrumentLookup = buildLookup(INSTRUMENT_GROUPS);

/**
 * Return the icon for a tag value based on its type.
 *
 * @param {'genre'|'mood'|'instrument'} type - The tag type.
 * @param {string} value - The tag value (e.g. "Synth-pop", "Melancholic", "Piano").
 * @returns {{ icon?: import('lucide-react').LucideIcon, materialIcon?: string } | null}
 *   An object with either `icon` (Lucide component) or `materialIcon` (ligature string),
 *   or `null` when no mapping exists.
 */
export function getTagIcon(type, value) {
    switch (type) {
        case 'genre':
            return genreLookup.get(value) ?? null;
        case 'mood':
            return moodLookup.get(value) ?? null;
        case 'instrument':
            return instrumentLookup.get(value) ?? null;
        default:
            return null;
    }
}
