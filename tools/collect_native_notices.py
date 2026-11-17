"""Collect pinned native-build and frontend-runtime notices without copying code.

Python 3.11+. Run after npm ci and cargo fetch/build. Output must not exist.
Cargo metadata is private input: absolute paths are never serialized to output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tomllib


TARGET = 'x86_64-pc-windows-msvc'
REGISTRY = 'registry+https://github.com/rust-lang/crates.io-index'
NOTICE_NAME = re.compile(r'^(LICENSE|LICENCE|COPYING|NOTICE|COPYRIGHT)(?:$|[-_.])', re.I)
SAFE_PART = re.compile(r'^[A-Za-z0-9_.+-]+$')
RUNTIME_NPM = ('@tauri-apps/api', 'react', 'react-dom', 'scheduler')


class CollectionError(ValueError):
    """A required license/provenance input is absent or inconsistent."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(condition: bool, message: str):
    if not condition:
        raise CollectionError(message)


def safe_part(value: str) -> str:
    require(bool(SAFE_PART.fullmatch(value)), 'Unsafe package name/version or notice filename')
    return value


def contained(root: Path, path: Path) -> Path:
    resolved = path.resolve(strict=True)
    require(resolved.is_relative_to(root.resolve()), 'Notice escaped its package directory')
    return resolved


def notice_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    require(0 < len(data) <= 1024 * 1024 and b'\x00' not in data, 'Invalid or oversized notice')
    data.decode('utf-8-sig')
    return data


def package_notices(root: Path, license_file: str | None = None):
    paths = {p for p in root.iterdir() if p.is_file() and NOTICE_NAME.match(p.name)}
    if license_file:
        paths.add(contained(root, root / license_file))
    return [(p.relative_to(root).as_posix(), notice_bytes(contained(root, p)))
            for p in sorted(paths, key=lambda item: item.as_posix())]


def override_notice(package: dict, root: Path, overrides: dict, license_root: Path):
    key = f"{package['name']}@{package['version']}"
    require(key in overrides, f'Missing license and exact override: {key}')
    override = overrides[key]
    require(override['license'] == package['license'], f'Override license changed: {key}')
    data = notice_bytes(contained(license_root, license_root / override['file']))
    require(sha256(data) == override['sha256'], f'Override hash mismatch: {key}')
    vcs = read_json(root / '.cargo_vcs_info.json')
    require(vcs['git']['sha1'] == override['upstream_commit'], f'Override source commit changed: {key}')
    require(override['origin_url'].startswith('https://'), f'Invalid override origin: {key}')
    return override, data


def archive_notice(archive: tarfile.TarFile, prefix: str, filename: str) -> bytes:
    member = archive.getmember(f'{prefix}/{filename}')
    require(member.isfile() and member.size <= 1024 * 1024, 'Invalid notice in crate archive')
    stream = archive.extractfile(member)
    require(stream is not None, 'Missing notice in crate archive')
    return stream.read()


def add_notices(component: dict, notices, outputs: dict[str, bytes], prefix: str):
    component['notices'] = []
    for index, (name, data, origin) in enumerate(notices, 1):
        leaf = safe_part(Path(name).name)
        path = f'{prefix}/{index:02d}-{leaf}'
        require(path not in outputs, 'Duplicate notice output')
        outputs[path] = data
        component['notices'].append({'path': path, 'sha256': sha256(data),
                                      'source_file': name, 'origin': origin})


def collect(repo: Path, metadata: dict, license_root: Path | None = None):
    repo = repo.resolve()
    license_root = license_root or repo / 'desktop/licenses'
    overrides = read_json(license_root / 'overrides.json')['overrides']
    lock = tomllib.loads((repo / 'desktop/src-tauri/Cargo.lock').read_text(encoding='utf-8'))
    locked = {(p['name'], p['version'], p.get('source')): p for p in lock['package']}
    outputs: dict[str, bytes] = {'LICENSE': notice_bytes(repo / 'LICENSE')}
    components = []
    own = [p for p in metadata['packages'] if p.get('source') is None]
    require(len(own) == 1 and own[0]['name'] == 'neural-office-desktop', 'Unexpected local Cargo package')
    for package in sorted(metadata['packages'], key=lambda p: (p['name'], p['version'])):
        if not package.get('source'):
            continue
        name, version = safe_part(package['name']), safe_part(package['version'])
        key = f'{name}@{version}'
        require(package['source'] == REGISTRY, f'Unreviewed Cargo source: {key}')
        entry = locked.get((name, version, REGISTRY))
        require(bool(entry and entry.get('checksum')), f'Package not pinned in Cargo.lock: {key}')
        root = Path(package['manifest_path']).parent.resolve()
        # Cargo registry caches need not have cargo-vendor's .cargo-checksum.json.
        # Verify the original downloaded archive, then compare notice bytes directly.
        archive_path = root.parents[2] / 'cache' / root.parent.name / f'{name}-{version}.crate'
        require(archive_path.is_file(), f'Crate archive absent; run cargo fetch: {key}')
        with archive_path.open('rb') as source:
            require(hashlib.file_digest(source, 'sha256').hexdigest() == entry['checksum'],
                    f'Crate archive checksum mismatch: {key}')
        require(bool(package.get('license')), f'No declared license: {key}')
        component = {'ecosystem': 'cargo', 'name': name, 'version': version,
                     'scope': 'windows-cargo-build-superset', 'declared_license': package['license'],
                     'source_archive': f'https://static.crates.io/crates/{name}/{name}-{version}.crate',
                     'source_archive_sha256': entry['checksum'], 'source_hash_basis': 'Cargo.lock'}
        found = package_notices(root, package.get('license_file'))
        notices = []
        with tarfile.open(archive_path, 'r:gz') as archive:
            for filename, data in found:
                require(archive_notice(archive, f'{name}-{version}', filename) == data,
                        f'Registry notice differs from verified archive: {key}/{filename}')
                notices.append((filename, data, 'published-crate'))
            if not any(NOTICE_NAME.match(n).group(1).upper() in ('LICENSE', 'LICENCE', 'COPYING')
                       for n, _ in found if NOTICE_NAME.match(n)) and not package.get('license_file'):
                override, data = override_notice(package, root, overrides, license_root)
                vcs = json.loads(archive_notice(archive, f'{name}-{version}', '.cargo_vcs_info.json'))
                require(vcs['git']['sha1'] == override['upstream_commit'], f'Archive commit differs: {key}')
                notices.append((override['file'], data, override['origin_url']))
                component['license_override'] = {'upstream_commit': override['upstream_commit'],
                                                   'reason': override['reason']}
        require(bool(notices), f'No notices: {key}')
        add_notices(component, notices, outputs, f'cargo/{name}-{version}')
        components.append(component)

    desktop = repo / 'desktop'
    npm_lock = read_json(desktop / 'package-lock.json')['packages']
    declared = read_json(desktop / 'package.json')['dependencies']
    require(set(declared) == set(RUNTIME_NPM) - {'scheduler'}, 'Runtime npm roots changed; review inventory')
    for name in RUNTIME_NPM:
        root = desktop / 'node_modules' / name
        package = read_json(root / 'package.json')
        version = safe_part(package['version'])
        require(package['name'] == name, 'Installed npm package identity mismatch')
        locked_npm = npm_lock.get(f'node_modules/{name}', {})
        require(locked_npm.get('version') == version, f'Installed npm version differs from lock: {name}')
        require(bool(package.get('license')), f'No npm license: {name}')
        require(set(package.get('dependencies', {})).issubset(RUNTIME_NPM), f'Unreviewed runtime dependency: {name}')
        archive = locked_npm.get('resolved', '')
        require(archive.startswith('https://registry.npmjs.org/') and bool(locked_npm.get('integrity')),
                f'Npm archive not pinned: {name}')
        component = {'ecosystem': 'npm', 'name': name, 'version': version, 'scope': 'frontend-runtime',
                     'declared_license': package['license'], 'source_archive': archive,
                     'source_archive_integrity': locked_npm['integrity'], 'source_hash_basis': 'package-lock.json'}
        found = package_notices(root)
        require(bool(found), f'Missing npm license: {name}')
        add_notices(component, [(n, d, 'installed-npm-package') for n, d in found], outputs,
                    f"npm/{name.replace('@', '').replace('/', '__')}-{version}")
        components.append(component)

    manifest = {'schema_version': 1, 'target': TARGET,
                'scope': 'Cargo Windows build dependency superset plus installed frontend runtime packages; not an exhaustive binary SBOM',
                'own_license': {'path': 'LICENSE', 'sha256': sha256(outputs['LICENSE']), 'source_file': 'repository/LICENSE'},
                'input_hashes': {'Cargo.lock': sha256((repo / 'desktop/src-tauri/Cargo.lock').read_bytes()),
                                 'package-lock.json': sha256((desktop / 'package-lock.json').read_bytes())},
                'components': components}
    outputs['components.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    mpl = [c for c in components if 'MPL-2.0' in c['declared_license']]
    lines = ['# Neural Office V5.5 — native prototype notices', '',
             f"This collection contains {sum(c['ecosystem'] == 'cargo' for c in components)} Cargo packages "
             f"in the {TARGET} dependency/build superset and {sum(c['ecosystem'] == 'npm' for c in components)} installed frontend runtime packages.", '',
             'The Rust list includes build tools and dependencies that may not survive linking. It is not an exhaustive binary SBOM or a claim that every listed package is embedded.', '',
             'LICENSE is the original Neural Office license. Each third-party notice is copied byte for byte, including copyright names and public attribution addresses. Their own terms remain applicable. components.json records versions, declared license expressions, notice SHA-256 hashes and pinned source archives.', '',
             'This directory contains licenses and metadata only: no application sources, models, credentials, raw Cargo metadata, local paths, Python installation, Ollama runtime, or WebView2 installation. Development npm packages are outside this collection; installed system runtimes and other redistributed binaries need their own inventory.', '',
             '## Source form for MPL-2.0 components', '',
             'These dependencies are used without source modifications by this project. Obtain the exact Source Code Form, including its original notices, using the versioned crate archives below. Their SHA-256 values are pinned in components.json and Cargo.lock. MPL-2.0 remains applicable to those source files; the Neural Office MIT license does not replace it.', '']
    lines.extend(f"- [{c['name']} {c['version']}]({c['source_archive']}) — SHA-256 `{c['source_archive_sha256']}`" for c in mpl)
    lines += ['', '## Regeneration', '',
              'After npm ci and Cargo dependency download, run from the repository root:', '',
              '```text', 'python -B tools/collect_native_notices.py --output native-notices', '```', '',
              'The output directory must not already exist. Missing licenses, changed override hashes, unpinned packages or changed override source commits stop generation. The collector invokes locked Cargo metadata with Windows filtering and custom-protocol enabled; it never runs the application or a model.', '']
    outputs['README.md'] = '\n'.join(lines).encode('utf-8')
    return outputs, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--metadata', type=Path, help='Previously generated private Cargo metadata (not copied)')
    parser.add_argument('--cargo', default='cargo')
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), 'Output directory already exists; choose a new directory')
        if args.metadata:
            metadata = read_json(args.metadata)
        else:
            result = subprocess.run([args.cargo, 'metadata', '--locked', '--format-version', '1',
                                     '--filter-platform', TARGET, '--features', 'custom-protocol'],
                                    cwd=args.repo / 'desktop/src-tauri', check=True, capture_output=True)
            metadata = json.loads(result.stdout)
        outputs, manifest = collect(args.repo, metadata)
        args.output.mkdir(parents=True, exist_ok=False)
        for relative, data in outputs.items():
            destination = args.output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        print(f"Collected {len(manifest['components'])} third-party components; {len(outputs)} files. No source code copied.")
    except (CollectionError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Do not serialize local paths or private Cargo stderr into a distributable report.
        detail = str(error) if isinstance(error, CollectionError) else type(error).__name__
        print(f'Notice collection failed: {detail}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
