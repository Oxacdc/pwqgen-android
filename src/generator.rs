//! Port of passwdqc_random() from passwdqc (https://github.com/openwall/passwdqc),
//! written by Solar Designer, which powers the pwqgen program by Dmitry V. Levin
//! and Solar Designer.  The word list is derived from Dianelos Georgoudis'
//! public-domain MakePass list.  See NOTICE.
//!
//! With the English list, the algorithm, word list and bit layout are
//! identical to the C version, so the same 24 random bytes give the same
//! passphrase.  The other lists follow the same rules
//! (4096 distinct words of 3 to 6 ASCII letters), so every language gives
//! exactly the same entropy.

use zeroize::Zeroize;

/// Word list language.  Each list holds exactly 4096 words, one per line.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Language {
    /// First 4096 words of passwdqc's wordset_4k.c (public domain).
    English,
    /// Built by tools/wordlists from CC0 / public-domain corpora.
    French,
    Spanish,
    German,
    /// Transliterated to ASCII (жизнь -> zhizn).
    Russian,
    /// Built by tools/wordlists from William Whitaker's WORDS dictionary.
    Latin,
}

impl Language {
    pub const ALL: [Language; 6] = [
        Language::English,
        Language::French,
        Language::Spanish,
        Language::German,
        Language::Russian,
        Language::Latin,
    ];

    /// Short code, also used to save the user's choice.
    pub fn code(self) -> &'static str {
        match self {
            Language::English => "en",
            Language::French => "fr",
            Language::Spanish => "es",
            Language::German => "de",
            Language::Russian => "ru",
            Language::Latin => "la",
        }
    }

    pub fn from_code(code: &str) -> Option<Language> {
        Language::ALL.into_iter().find(|l| l.code() == code)
    }

    fn word_list(self) -> &'static str {
        match self {
            Language::English => include_str!("words/en.txt"),
            Language::French => include_str!("words/fr.txt"),
            Language::Spanish => include_str!("words/es.txt"),
            Language::German => include_str!("words/de.txt"),
            Language::Russian => include_str!("words/ru.txt"),
            Language::Latin => include_str!("words/la.txt"),
        }
    }
}

/// Words in a list.
pub const WORD_COUNT: usize = 4096;

/// Characters used between words; each encodes 4 bits (see passwdqc_random.c).
const SEPARATORS: &[u8; 16] = b"-_!$&*+=23456789";

const SEPARATOR_BITS: i32 = 4;
/// 12 bits for the word index plus 1 bit for toggling the case of its first letter.
const WORD_BITS: i32 = 13;
const SWORD_BITS: i32 = SEPARATOR_BITS + WORD_BITS;
const WORDS_MAX: usize = 8;
const WORD_LENGTH_MAX: i32 = 6;
/// Size of the C version's output buffer, including NUL termination.
const OUTPUT_SIZE: usize = 0x100;

pub const BITS_MIN: i32 = 2 * (WORD_BITS - 1);
pub const BITS_MAX: i32 = WORDS_MAX as i32 * SWORD_BITS;
/// pwqgen's default (random=47).
pub const BITS_DEFAULT: i32 = 47;

/// Number of random bytes consumed per passphrase.
pub const RANDOM_BYTES: usize = WORDS_MAX * 3;

fn words(lang: Language) -> impl Iterator<Item = &'static str> {
    lang.word_list().lines()
}

fn word(lang: Language, index: usize) -> &'static [u8] {
    words(lang).nth(index).expect("word list has 4096 entries").as_bytes()
}

/// Deterministic core of passwdqc_random(): builds the passphrase from the
/// given random bytes.  `max` is passwdqc's max= parameter (pwqgen's default
/// is 40, which caps `bits` at 85).
pub fn generate_from(
    lang: Language,
    mut bits: i32,
    max: i32,
    rnd: &[u8; RANDOM_BYTES],
) -> Option<String> {
    if !(BITS_MIN..=BITS_MAX).contains(&bits) {
        return None;
    }

    let mut word_count = 1 + (bits + (SWORD_BITS - 1 - WORD_BITS)) / SWORD_BITS;
    let mut trailing_separator = SWORD_BITS * (word_count - 1) >= bits;
    word_count -= trailing_separator as i32;
    let use_separators = (bits + (WORD_BITS - 1)) / WORD_BITS != word_count;
    trailing_separator &= use_separators;
    let separator_count = word_count - !trailing_separator as i32;
    let toggle_case = bits
        > (WORD_BITS - 1) * word_count
            + if use_separators { SEPARATOR_BITS * separator_count } else { 0 };

    let max_length = word_count * (WORD_LENGTH_MAX + 1) - !trailing_separator as i32;
    if max_length >= OUTPUT_SIZE as i32 || max_length > max {
        return None;
    }

    let mut output: Vec<u8> = Vec::with_capacity(OUTPUT_SIZE);
    for chunk in rnd.chunks_exact(3) {
        // Bits 0-11: word index, bit 13: case toggle, bits 16-19: separator.
        let index = ((chunk[1] as usize & 0x0f) << 8) | chunk[0] as usize;
        let w = word(lang, index);
        if output.len() + w.len() >= OUTPUT_SIZE {
            break;
        }
        let start = output.len();
        output.extend_from_slice(w);
        if toggle_case {
            output[start] ^= chunk[1] & 0x20;
            bits -= 1;
        }
        bits -= WORD_BITS - 1;
        if bits <= 0 {
            break;
        }

        if use_separators {
            output.push(SEPARATORS[(chunk[2] & 0x0f) as usize]);
            bits -= SEPARATOR_BITS;
        } else {
            output.push(SEPARATORS[0]);
        }
        if bits <= 0 {
            break;
        }
    }

    let result = (bits <= 0 && output.len() < OUTPUT_SIZE)
        .then(|| String::from_utf8(output.clone()).expect("ASCII only"));
    output.zeroize();
    result
}

/// Generates a passphrase with `bits` bits of entropy from the OS CSPRNG.
pub fn generate(lang: Language, bits: i32) -> Option<String> {
    let mut rnd = [0u8; RANDOM_BYTES];
    getrandom::fill(&mut rnd).ok()?;
    let result = generate_from(lang, bits, OUTPUT_SIZE as i32, &rnd);
    rnd.zeroize();
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Every list must give the same 12 bits per word as passwdqc's:
    /// 4096 entries, 3-6 ASCII letters, unique even when the case of the
    /// first letter is toggled.
    #[test]
    fn word_lists_match_passwdqc_assumptions() {
        for lang in Language::ALL {
            let list: Vec<&str> = words(lang).collect();
            assert_eq!(list.len(), WORD_COUNT, "{lang:?}");
            for w in &list {
                assert!(
                    (3..=WORD_LENGTH_MAX as usize).contains(&w.len())
                        && w.bytes().all(|b| b.is_ascii_alphabetic()),
                    "{lang:?}: {w:?}"
                );
            }
            let mut lower: Vec<String> = list.iter().map(|w| w.to_ascii_lowercase()).collect();
            lower.sort();
            lower.dedup();
            assert_eq!(lower.len(), WORD_COUNT, "{lang:?} has duplicates");
        }
    }

    #[test]
    fn language_codes_round_trip() {
        for lang in Language::ALL {
            assert_eq!(Language::from_code(lang.code()), Some(lang));
        }
        assert_eq!(Language::from_code("xx"), None);
    }

    #[test]
    fn every_language_reaches_the_maximum() {
        let rnd = [0xffu8; RANDOM_BYTES];
        for lang in Language::ALL {
            assert!(generate_from(lang, BITS_MAX, 256, &rnd).is_some(), "{lang:?}");
        }
    }

    #[test]
    fn rejects_out_of_range_bits() {
        let rnd = [0u8; RANDOM_BYTES];
        assert_eq!(generate_from(Language::English, BITS_MIN - 1, 256, &rnd), None);
        assert_eq!(generate_from(Language::English, BITS_MAX + 1, 256, &rnd), None);
        assert!(generate_from(Language::English, BITS_MIN, 256, &rnd).is_some());
        assert!(generate_from(Language::English, BITS_MAX, 256, &rnd).is_some());
    }

    #[test]
    fn respects_pwqgen_default_max_length() {
        let rnd = [0u8; RANDOM_BYTES];
        assert!(generate_from(Language::English, 85, 40, &rnd).is_some());
        assert_eq!(generate_from(Language::English, 86, 40, &rnd), None);
    }

    /// Compares against vectors produced by the original C code
    /// (tests/gen_vectors.c): "bits hex-random passphrase-or-NULL" per line.
    #[test]
    fn matches_c_reference() {
        let vectors = include_str!("../tests/vectors.txt");
        let mut count = 0;
        for line in vectors.lines() {
            let mut parts = line.splitn(3, ' ');
            let bits: i32 = parts.next().unwrap().parse().unwrap();
            let hex = parts.next().unwrap();
            let expected = parts.next().unwrap();
            let mut rnd = [0u8; RANDOM_BYTES];
            for (i, byte) in rnd.iter_mut().enumerate() {
                *byte = u8::from_str_radix(&hex[2 * i..2 * i + 2], 16).unwrap();
            }
            let got = generate_from(Language::English, bits, OUTPUT_SIZE as i32, &rnd);
            let expected = (expected != "NULL").then(|| expected.to_string());
            assert_eq!(got, expected, "bits={bits} rnd={hex}");
            count += 1;
        }
        assert!(count > 1000);
    }

    #[test]
    fn generate_uses_os_randomness() {
        for lang in Language::ALL {
            let a = generate(lang, BITS_DEFAULT).unwrap();
            let b = generate(lang, BITS_DEFAULT).unwrap();
            assert_ne!(a, b);
        }
    }
}
