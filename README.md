# pwqgen for Android

Generates random passphrases that are easy to remember, such as
`track2Clerk&iran`, with the same algorithm and word list as `pwqgen` from
Openwall's [passwdqc](https://www.openwall.com/passwdqc/).

- 24 to 136 bits of entropy (47 by default, like `pwqgen`).
- Word lists in English (passwdqc's own), French, Spanish, German, Russian
  (transliterated: zhizn, doroga) and Latin. The extra lists follow
  passwdqc's rules (4096 words of 3 to 6 ASCII letters),
  so the entropy is the same in every language. They are built from CC0 and
  public-domain sources; see [tools/wordlists](tools/wordlists/README.md).
- No permissions; randomness from the OS CSPRNG.
- `FLAG_SECURE` blocks screenshots and the recent apps preview.
- Copied passphrases are flagged as sensitive (hidden in Android 13+ clipboard preview).
- 100% Rust: NativeActivity + egui, clipboard through JNI. No Gradle.

## Building

Requirements: Rust with the `aarch64-linux-android`, `armv7-linux-androideabi`
and `x86_64-linux-android` targets, an Android SDK (build-tools and a
platform), NDK r29, `zip`, and a JDK (for `apksigner`/`keytool`).

```sh
ANDROID_HOME=/path/to/sdk ./tools/build-apk.sh
```

This writes a signed `build/pwqgen.apk`. On first run it creates a signing key
in `~/.android-keys` (override with `PWQGEN_KEYS`). Other options are listed at
the top of [tools/build-apk.sh](tools/build-apk.sh): `UNSIGNED=1` for an
unsigned APK, `ABIS` to choose architectures, `SCREENSHOTS=1` for a build that
allows screenshots.

## Tests

```sh
cargo test
```

`tests/vectors.txt` was produced by compiling passwdqc's own C code with
[tests/gen_vectors.c](tests/gen_vectors.c); with the English list, the Rust
generator must match it for every vector. The tests also check that every
word list has 4096 unique words of 3 to 6 ASCII letters.

## Releasing

Bump `android:versionCode` and `android:versionName` in
`android/AndroidManifest.xml` and `version` in `Cargo.toml` (the build checks
they match), add `fastlane/metadata/android/*/changelogs/<versionCode>.txt`,
then tag `v<versionName>`.

`fdroid/io.github.oxacdc.pwqgen.yml` is the build recipe for
[fdroiddata](https://gitlab.com/fdroid/fdroiddata).

## Credits

This app is a port; the passphrase design is entirely the work of the
passwdqc authors:

- **Solar Designer** ([Openwall](https://www.openwall.com/)): author of
  passwdqc and of `passwdqc_random()`, the generator ported here, and curator
  of its word list.
- **Dmitry V. Levin**: author of the `pwqgen` command-line program, later
  updated by Solar Designer.
- **Dianelos Georgoudis**: author of the public-domain MakePass word list
  that passwdqc's list comes from.

The French, Spanish, German and Russian lists were selected with word counts
from [Mozilla Common Voice](https://commonvoice.mozilla.org/) sentences (CC0),
[Project Gutenberg](https://www.gutenberg.org/) books and Russian prose from
[Wikisource](https://ru.wikisource.org/) (public domain); the Latin list from **William Whitaker**'s
[WORDS](https://github.com/mk270/whitakers-words) dictionary.

## License

[0BSD](LICENSE). passwdqc's own license and full attribution are in
[NOTICE](NOTICE).
