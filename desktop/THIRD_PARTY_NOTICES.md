# Third-party notices · V5.5 native prototype

Neural Office now has a compiled Windows native prototype with a React frontend and a Tauri/Rust host. A frontend-only React notice does not describe this artifact. Native artifacts must be accompanied by the generated `native-notices` directory described below; this document does not replace those original license texts.

## What the notice collection covers

The current locked Windows dependency graph contains 241 third-party Cargo packages, including dependencies used only during compilation. The installed frontend runtime comprises React 19.3.1, React DOM 19.3.1, Scheduler 0.28.0 and `@tauri-apps/api` 2.12.5. The collector records each installed version and its own declared license; Neural Office's MIT license does not relicense these components.

The native list is a build-dependency superset, not an assertion that all 241 packages are embedded in the executable and not an exhaustive binary SBOM. Development npm tools, system WebView2, external Python/Ollama installations and model files are not included in this collection. Any future redistributed runtime or model needs its own inventory and applicable notices.

## Generate the artifact notices

From the repository root, after frontend installation and Cargo dependency download/build:

```text
python -B tools/collect_native_notices.py --output native-notices
```

The output directory must be new. The collector invokes locked Cargo metadata filtered to `x86_64-pc-windows-msvc` with `custom-protocol`, validates crate-archive SHA-256 against `Cargo.lock`, compares included notices with those archives, and copies license bytes without editing them. The four runtime npm packages are checked against the installed package versions and lockfile; the manifest records their pinned tarball integrity and each copied notice's SHA-256.

The output contains the original Neural Office `LICENSE`, per-component notices, `components.json` and a generated `README.md`. Attach that complete directory to the native artifact. It contains no application source, local absolute paths, raw Cargo metadata, user data or model weights.

Five published crates omit a full license file. Their exact, hash-checked [reviewed overrides](licenses/README.md) retain upstream copyright and attribution. A missing license or changed override stops collection rather than silently omitting the notice.

## MPL source availability

The graph includes unmodified `cssparser 0.37.0`, `cssparser-macros 0.7.1`, `dtoa-short 0.3.5`, `option-ext 0.2.0` and `selectors 0.38.0`, declared under MPL-2.0. The generated README supplies the exact versioned crate download links, and `components.json` records their source-archive SHA-256 values. Their source files remain under MPL-2.0; recipients can obtain the original Source Code Form and notices from those archives. [MPL-2.0](https://www.mozilla.org/en-US/MPL/2.0/) governs those components independently of the project's MIT license.

The collection preserves public names and email addresses occurring in original copyright notices. They are third-party attribution, not Neural Office user data, and must not be redacted by a publication cleanup.
