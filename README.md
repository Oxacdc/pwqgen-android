# pwqgen for Android

Generates random passphrases that are easy to remember, such as
`track2Clerk&iran`, with the same algorithm and word list as `pwqgen` from
Openwall's [passwdqc](https://www.openwall.com/passwdqc/).

- 24 to 136 bits of entropy (47 by default, like `pwqgen`).
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
[tests/gen_vectors.c](tests/gen_vectors.c); the Rust generator must match it
for every vector.

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

## License

[0BSD](LICENSE). passwdqc's own license and full attribution are in
[NOTICE](NOTICE).
