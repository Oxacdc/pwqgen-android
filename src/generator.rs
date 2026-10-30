//! Port of passwdqc_random() from passwdqc (https://github.com/openwall/passwdqc),
//! written by Solar Designer, which powers the pwqgen program by Dmitry V. Levin
//! and Solar Designer.  The word list is derived from Dianelos Georgoudis'
//! public-domain MakePass list.  See NOTICE.
//!
//! The algorithm, word list and bit layout are identical to the C version, so
//! the same 24 random bytes give the same passphrase.

use zeroize::Zeroize;

/// First 4096 words of passwdqc's wordset_4k.c (public domain), one per line.
const WORDSET_4K: &str = include_str!("wordset_4k.txt");

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

fn words() -> impl Iterator<Item = &'static str> {
    WORDSET_4K.lines()
}

fn word(index: usize) -> &'static [u8] {
    words().nth(index).expect("word list has 4096 entries").as_bytes()
}

/// Deterministic core of passwdqc_random(): builds the passphrase from the
/// given random bytes.  `max` is passwdqc's max= parameter (pwqgen's default
/// is 40, which caps `bits` at 85).
pub fn generate_from(mut bits: i32, max: i32, rnd: &[u8; RANDOM_BYTES]) -> Option<String> {
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
        let w = word(index);
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
pub fn generate(bits: i32) -> Option<String> {
    let mut rnd = [0u8; RANDOM_BYTES];
    getrandom::fill(&mut rnd).ok()?;
    let result = generate_from(bits, OUTPUT_SIZE as i32, &rnd);
    rnd.zeroize();
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn word_list_matches_passwdqc_assumptions() {
        let list: Vec<&str> = words().collect();
        assert_eq!(list.len(), 4096);
        assert!(list
            .iter()
            .all(|w| (3..=6).contains(&w.len()) && w.bytes().all(|b| b.is_ascii_alphabetic())));
        let mut lower: Vec<String> = list.iter().map(|w| w.to_ascii_lowercase()).collect();
        lower.sort();
        lower.dedup();
        assert_eq!(lower.len(), 4096);
    }

    #[test]
    fn rejects_out_of_range_bits() {
        let rnd = [0u8; RANDOM_BYTES];
        assert_eq!(generate_from(BITS_MIN - 1, 256, &rnd), None);
        assert_eq!(generate_from(BITS_MAX + 1, 256, &rnd), None);
        assert!(generate_from(BITS_MIN, 256, &rnd).is_some());
        assert!(generate_from(BITS_MAX, 256, &rnd).is_some());
    }

    #[test]
    fn respects_pwqgen_default_max_length() {
        let rnd = [0u8; RANDOM_BYTES];
        assert!(generate_from(85, 40, &rnd).is_some());
        assert_eq!(generate_from(86, 40, &rnd), None);
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
            let got = generate_from(bits, OUTPUT_SIZE as i32, &rnd);
            let expected = (expected != "NULL").then(|| expected.to_string());
            assert_eq!(got, expected, "bits={bits} rnd={hex}");
            count += 1;
        }
        assert!(count > 1000);
    }

    #[test]
    fn generate_uses_os_randomness() {
        let a = generate(BITS_DEFAULT).unwrap();
        let b = generate(BITS_DEFAULT).unwrap();
        assert_ne!(a, b);
    }
}
