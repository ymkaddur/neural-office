# Reviewed native-license overrides

These five files fill omissions in the published crates used by the V5.5 Windows native prototype. They are original upstream license texts, not Neural Office licenses. Copyright notices and public attribution addresses are preserved verbatim.

`overrides.json` binds each exact package version to its declared license, SHA-256 of the preserved bytes, upstream commit and download origin. The commit was checked against `.cargo_vcs_info.json` inside that version's published crate. For `selectors`, the full MPL-2.0 text comes from the license steward, Mozilla; it is not represented as a license file present in the Stylo repository.

| Crate | License text origin | Commit recorded in crate |
|---|---|---|
| alloc-stdlib 0.3.0 | [Repository-root LICENSE](https://github.com/dropbox/rust-alloc-no-stdlib/blob/0a81fd6928ea3b33c8cd484aa4575d50ffb98012/LICENSE) | `0a81fd6928ea3b33c8cd484aa4575d50ffb98012` |
| selectors 0.38.0 | [Mozilla MPL-2.0 text](https://www.mozilla.org/media/MPL/2.0/index.815ca599c9df.txt) | `572ecba2d1600e7c3d490586692a209faf703baa` |
| webview2-com 0.39.1 | [Repository-root LICENSE](https://github.com/wravery/webview2-rs/blob/edc2caf886175ccaebe86078c9cfe1ae2a187328/LICENSE) | `edc2caf886175ccaebe86078c9cfe1ae2a187328` |
| webview2-com-sys 0.39.1 | [Repository-root LICENSE](https://github.com/wravery/webview2-rs/blob/edc2caf886175ccaebe86078c9cfe1ae2a187328/LICENSE) | `edc2caf886175ccaebe86078c9cfe1ae2a187328` |
| webview2-com-macros 0.8.1 | [Repository-root LICENSE](https://github.com/wravery/webview2-rs/blob/dffa41a8a46d3f5565eefbff2de57d38d399f158/LICENSE) | `dffa41a8a46d3f5565eefbff2de57d38d399f158` |

The three WebView2 license files have identical SHA-256 values. They remain associated with their separate package versions. The collector fails on a missing override, altered bytes, different declared license or changed source commit.

Run from the repository root after `npm ci` in `desktop` and Cargo dependency download/build:

```text
python -B tools/collect_native_notices.py --output native-notices
```

The new output directory contains the original repository `LICENSE`, third-party license/notice files, `components.json` and a generated `README.md` with exact source-archive links for all MPL dependencies. It must accompany the native artifact. Do not publish the raw Cargo metadata input: it contains local filesystem paths. An optional `--metadata` argument permits an already generated metadata file to be used locally; production CI generates its own metadata with the locked Windows target and `custom-protocol` feature.

This is a Cargo build-dependency superset and frontend-runtime notice collection, not an exhaustive binary SBOM or proof that every resolved package survives linking. Source archives are linked, not copied into the notices directory. System runtimes, model weights and external Python/Ollama installations are outside its scope.
