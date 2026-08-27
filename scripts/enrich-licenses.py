#!/usr/bin/env python3
"""
BOM License Enrichment (v3.0)
=============================
Reads a CycloneDX bom.json, fills in licenses that Trivy could not resolve,
and writes the patched BOM back in place.

Why this exists
---------------
Trivy's `fs` scan resolves licences from *manifests*, not from installed
packages. That leaves whole ecosystems blank in the SBOM:

  * npm   - resolved from package.json; blank when a package omits "license"
            even though it ships a LICENSE file (e.g. polyline@0.2.0).
  * pypi  - blank unless a site-packages dir is present; a `fs` scan of a
            repo never has one, so every Python package is licence-less.
  * gem   - Gemfile.lock carries no licence data at all.

Each of those shows up on the org licence dashboard as a HIGH
"No License Metadata" finding, even when the real licence is permissive.
This script resolves them from the upstream registries.

Usage:
    python3 enrich-licenses.py [--bom bom.json] [--dry-run] [--analyze]
"""

from __future__ import annotations

import json
import sys
import argparse
import urllib.request
import urllib.error
import time
from typing import Optional, Dict, List, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# 1. Curated fallback map for packages whose registries don't expose a SPDX id.
#    Format: { "pkg-type:name@version": "SPDX-ID" }
#            Use "@*" as version wildcard.
#
#    Only add an entry here after reading the package's actual LICENSE text.
#    Never guess: a wrong SPDX id here is worse than a blank, because it
#    silently clears a dashboard finding that a human should have seen.
# ──────────────────────────────────────────────────────────────────────────────
KNOWN_LICENSES: Dict[str, str] = {
    # NuGet - Microsoft packages typically MIT
    "nuget:Microsoft.Windows.CppWinRT@*": "MIT",

    # npm (packages that return non-SPDX strings from the registry)
    "npm:qrcode-terminal@0.11.0": "Apache-2.0",
    "npm:requireg@0.2.2": "MIT",

    # npm: ships a BSD-3-Clause LICENSE file (Development Seed) but omits the
    # "license" field in package.json, so both npm and Trivy report nothing.
    # Verified against node_modules/polyline/LICENSE. Package is abandoned
    # upstream (0.2.0 is latest), so the version pin is safe.
    "npm:polyline@0.2.0": "BSD-3-Clause",

    # npm: ships the full MIT licence text under "# License" in readme.md but
    # declares no "license" field in package.json, so npm, Trivy and the
    # registry API all report nothing. Verified against the 0.1.3 tarball
    # (readme.md contains the complete MIT text). Reached via bunyan-wrapper.
    "npm:bunyan-prettystream@0.1.3": "MIT",

    # gem: Gemfile.lock carries no licence data. Verified via
    # https://rubygems.org/api/v2/rubygems/fast-polylines/versions/2.2.2.json
    "gem:fast-polylines@2.2.2": "MIT",
}

# ──────────────────────────────────────────────────────────────────────────────
# 2. Component names that should be REMOVED from the BOM entirely.
#    These are build-system config files, NOT real library components.
# ──────────────────────────────────────────────────────────────────────────────
REMOVE_PATTERNS = [
    "packages.config",  # Windows/NuGet legacy config files
]

# ──────────────────────────────────────────────────────────────────────────────
# 3. Packages that genuinely have no OSS licence and must NOT be auto-filled.
#    Listing them here keeps them visibly unresolved (so the dashboard finding
#    stays) while recording *why*, so nobody re-triages them from scratch.
# ──────────────────────────────────────────────────────────────────────────────
#    Matched as a PREFIX, so one entry covers a package and all of its
#    per-platform binary siblings (…-darwin-arm64, …-linux-x64, …).
NO_OSS_LICENSE: Dict[str, str] = {
    "npm:@anthropic-ai/claude-agent-sdk":
        "Proprietary - Anthropic Commercial Terms of Service "
        "('SEE LICENSE IN README.md'). Internal build tooling, not redistributed.",
}

# ──────────────────────────────────────────────────────────────────────────────
# 3b. Reviewed and ACCEPTED licence exceptions.
#
#     These are licences that are correctly detected and genuinely non-permissive,
#     but that have been reviewed and accepted for a specific, bounded use. Each
#     entry stamps the component with `mapup:license:*` properties so the SBOM
#     itself records the decision and its reasoning — the finding stops being an
#     open question and becomes an auditable, versioned exception that travels
#     with the BOM into Dependency-Track.
#
#     Matched as a PREFIX, so one entry covers a package and all of its
#     per-platform binary siblings.
#
#     An exception is NOT a licence override. The real licence stays on the
#     component; these properties sit alongside it. If the `condition` below
#     ever stops holding, the exception must be revisited — that is why the
#     condition is written down rather than assumed.
# ──────────────────────────────────────────────────────────────────────────────
ACCEPTED_EXCEPTIONS: Dict[str, Dict[str, str]] = {
    "npm:lightningcss": {
        "license": "MPL-2.0",
        "scope": "build-time only (bundler)",
        "reason": (
            "Reached via @expo/metro-config as the CSS transformer inside the "
            "Metro bundler. Runs on the build machine; never linked into or "
            "shipped inside the app binary. MPL-2.0 is FILE-level copyleft: "
            "obligations attach only to modified MPL files, and it is consumed "
            "unmodified. It is a hard (non-optional) dependency of "
            "@expo/metro-config, so it cannot be removed without forking Expo."
        ),
        "condition": (
            "Holds while we do not modify lightningcss sources and do not "
            "redistribute it under our own name."
        ),
        "reviewed": "2026-08-27",
    },
    "npm:@sentry/cli": {
        "license": "FSL-1.1-MIT",
        "scope": "build-time only (source-map upload)",
        "reason": (
            "Reached via @sentry/react-native. Runs in CI to upload our own "
            "source maps and debug symbols to Sentry; not shipped in the app. "
            "FSL-1.1 grants use for any Permitted Purpose, and its own text "
            "enumerates 'your internal use and access' as a Permitted Purpose. "
            "The only carve-out is Competing Use — making the Software "
            "available to others in a product that substitutes for it or "
            "offers substantially similar functionality. We do not redistribute "
            "sentry-cli and do not offer an error-monitoring product, so no "
            "obligation is triggered. Each release additionally converts to MIT "
            "on the second anniversary of its publication."
        ),
        "condition": (
            "Holds while we do not ship sentry-cli to third parties and do not "
            "offer a competing error-monitoring product."
        ),
        "reviewed": "2026-08-27",
    },
    "npm:@anthropic-ai/claude-agent-sdk": {
        "license": "LicenseRef-Anthropic-Commercial-ToS",
        "scope": "internal tooling only (not redistributed)",
        "reason": (
            "Declares 'SEE LICENSE IN README.md' — Anthropic's commercial Terms "
            "of Service, not an OSS licence, which is why every scanner reports "
            "it as missing licence metadata. Used only by "
            "automate_dependabot_alerts/standalone/scripts, an internal "
            "automation script that is never packaged, published, or shipped to "
            "customers. Licensed to us as an Anthropic customer under those "
            "terms. Recorded as a LicenseRef rather than left blank so the SBOM "
            "states what it actually is instead of reading as 'unknown'."
        ),
        "condition": (
            "Holds while this stays in internal tooling. If it is ever embedded "
            "in a customer-facing product or redistributed, this exception is "
            "void and the terms must be re-reviewed."
        ),
        "reviewed": "2026-08-27",
    },
}


SPDX_ALIASES: Dict[str, str] = {
    "Apache 2.0": "Apache-2.0",
    "Apache-2": "Apache-2.0",
    "Apache2": "Apache-2.0",
    "Apache License 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "MIT License": "MIT",
    "BSD": "BSD-2-Clause",
    "ISC License": "ISC",
    "GPL-2.0": "GPL-2.0-only",
    "GPL-3.0": "GPL-3.0-only",
    "LGPL-2.1": "LGPL-2.1-only",
    # npm reports geojson-validation as the non-SPDX string "LGPL-3".
    "LGPL-3": "LGPL-3.0-only",
    "LGPL-3.0": "LGPL-3.0-only",
    "MPL 2.0": "MPL-2.0",
    "CC0": "CC0-1.0",
    "UNLICENSED": None,  # Private packages, flag for review
}

# PyPI trove classifier -> SPDX. PyPI's free-text `license` field is
# unreliable (sometimes full licence text), so classifiers are preferred.
PYPI_CLASSIFIERS: Dict[str, str] = {
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
    "License :: OSI Approved :: GNU General Public License v2 (GPLv2)": "GPL-2.0-only",
    "License :: OSI Approved :: GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
    "License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.1-or-later",
    "License :: OSI Approved :: The Unlicense (Unlicense)": "Unlicense",
    "License :: Public Domain": "CC0-1.0",
}


# ──────────────────────────────────────────────────────────────────────────────
# 4. Helpers
# ──────────────────────────────────────────────────────────────────────────────

def should_remove(component: dict) -> bool:
    """Check if component is a config file pseudo-component."""
    name = component.get("name", "")
    return any(pat in name for pat in REMOVE_PATTERNS)


def make_license_entry(spdx_id: str) -> List[dict]:
    """Create a proper CycloneDX license entry."""
    return [{"license": {"id": spdx_id}}]


def normalize_spdx(raw: str) -> Optional[str]:
    """Normalize license strings to SPDX identifiers."""
    if not raw:
        return None
    raw = raw.strip()
    if raw in SPDX_ALIASES:
        return SPDX_ALIASES[raw]
    # Reject free-text blobs: PyPI sometimes puts the whole licence in here.
    if len(raw) > 40 or "\n" in raw:
        return None
    return raw if raw else None


def get_pkg_type(component: dict) -> str:
    """Determine package type from component properties or purl."""
    purl = component.get("purl", "")
    for prefix, kind in (
        ("pkg:npm", "npm"),
        ("pkg:nuget", "nuget"),
        ("pkg:pypi", "pypi"),
        ("pkg:gem", "gem"),
        ("pkg:golang", "golang"),
    ):
        if purl.startswith(prefix):
            return kind
    for prop in component.get("properties", []):
        key = prop.get("name", "").lower()
        if "pkgtype" in key:
            return prop.get("value", "unknown").lower()
    return "unknown"


def full_name(component: dict) -> str:
    """
    Reassemble the registry name from a CycloneDX component.

    CycloneDX stores a scoped npm package as group="@anthropic-ai",
    name="claude-agent-sdk" — never as one string. Looking a component up by
    `.name` alone therefore queries the wrong package (or nothing), which is
    how the @anthropic-ai/* entries kept coming back unresolved.
    """
    group = (component.get("group") or "").strip()
    name = (component.get("name") or "").strip()
    if not group:
        return name
    pkg_type = get_pkg_type(component)
    if pkg_type == "npm":
        return f"{group}/{name}"
    if pkg_type in ("maven", "pom"):
        return f"{group}:{name}"
    return name


def lookup_known(pkg_type: str, name: str, version: str) -> Optional[str]:
    """Check curated fallback map for known licenses."""
    exact = f"{pkg_type}:{name}@{version}"
    wildcard = f"{pkg_type}:{name}@*"
    return KNOWN_LICENSES.get(exact) or KNOWN_LICENSES.get(wildcard)


def is_accepted(component: dict) -> bool:
    """True if pass 1 already stamped this component as a reviewed exception."""
    return any(
        p.get("name") == "mapup:license:review" and p.get("value") == "accepted"
        for p in component.get("properties", [])
    )


def _is_placeholder_licence(value: str) -> bool:
    """
    True for strings that occupy the licence field without naming a licence.

    npm lets a package write "SEE LICENSE IN <file>" instead of an SPDX id, and
    Trivy passes that straight through as a license *name*. It looks resolved to
    any `licenses` length check but tells you nothing, so it must be treated as
    unresolved when deciding whether an exception may apply.
    """
    v = (value or "").strip().upper().replace("_", "-").replace(" ", "-")
    return v.startswith("SEE-LICENSE-IN") or v in ("UNLICENSED", "UNKNOWN", "NONE")


def licence_matches(component: dict, expected: str) -> bool:
    """
    True when an exception written for `expected` may be applied to `component`.

    An exception applies ONLY when the component either has no resolved licence,
    or has exactly the licence the exception is written for. Without that guard a
    prefix like "npm:@sentry/cli" would stamp an FSL-1.1-MIT exception onto
    @sentry/cli 2.55.0, which is still BSD-3-Clause — labelling a permissive
    package with a restrictive licence it does not have.
    """
    ids = []
    for lic in component.get("licenses", []) or []:
        obj = lic.get("license", {}) or {}
        val = obj.get("id") or obj.get("name") or lic.get("expression")
        if val and not _is_placeholder_licence(val):
            ids.append(val)
    if not ids:
        return True  # nothing usable resolved: the exception supplies the licence
    return any(i == expected for i in ids)


def lookup_exception(pkg_type: str, name: str) -> Optional[Dict[str, str]]:
    """Return the accepted-exception record for a package, if one applies."""
    key = f"{pkg_type}:{name}"
    for prefix, rec in ACCEPTED_EXCEPTIONS.items():
        if key == prefix or key.startswith(prefix):
            return rec
    return None


def set_property(component: dict, name: str, value: str) -> None:
    """Set a CycloneDX component property, replacing any existing same-named one."""
    props = [p for p in component.get("properties", []) if p.get("name") != name]
    props.append({"name": name, "value": value})
    component["properties"] = props


def apply_exception(component: dict, rec: Dict[str, str]) -> None:
    """
    Stamp an accepted-exception record onto a component.

    The declared licence is set only when the component has none (the
    @anthropic-ai case, where the real licence is not an SPDX id and the BOM
    would otherwise say nothing at all). Where the scanner already resolved a
    real licence — MPL-2.0, FSL-1.1-MIT — it is left exactly as found: the
    exception explains the licence, it does not rewrite it.
    """
    if not has_valid_license(component):
        component["licenses"] = [{"license": {"name": rec["license"]}}]
    set_property(component, "mapup:license:review", "accepted")
    set_property(component, "mapup:license:declared", rec["license"])
    set_property(component, "mapup:license:scope", rec["scope"])
    set_property(component, "mapup:license:reason", " ".join(rec["reason"].split()))
    set_property(component, "mapup:license:condition", " ".join(rec["condition"].split()))
    set_property(component, "mapup:license:reviewed", rec["reviewed"])


def lookup_no_oss(pkg_type: str, name: str) -> Optional[str]:
    """Return a reason string if this package is known to have no OSS licence."""
    key = f"{pkg_type}:{name}"
    for prefix, reason in NO_OSS_LICENSE.items():
        if key == prefix or key.startswith(prefix):
            return reason
    return None


def has_valid_license(component: dict) -> bool:
    """Check if component has a valid, non-null license."""
    licenses = component.get("licenses", [])
    if not licenses:
        return False
    for lic in licenses:
        license_obj = lic.get("license", {})
        if license_obj and license_obj.get("id"):
            return True
        if lic.get("expression"):
            return True
    return False


def get_license_display(component: dict) -> str:
    """Get a display string for component's license."""
    licenses = component.get("licenses", [])
    if not licenses:
        return "NONE"
    parts = []
    for lic in licenses:
        license_obj = lic.get("license", {})
        if license_obj.get("id"):
            parts.append(license_obj["id"])
        elif lic.get("expression"):
            parts.append(f"({lic['expression']})")
    return ", ".join(parts) if parts else "MALFORMED"


# ──────────────────────────────────────────────────────────────────────────────
# 5. Registry fetchers
# ──────────────────────────────────────────────────────────────────────────────

def fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    """Fetch JSON from URL with timeout and error handling."""
    try:
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "bom-enricher/3.0"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"HTTP {e.code}", end=" ")
        return None
    except Exception as e:
        print(f"Error: {type(e).__name__}", end=" ")
        return None


def fetch_npm_license(name: str, version: str) -> Optional[str]:
    """Fetch license from npm registry."""
    encoded = name.replace("/", "%2F")
    data = fetch_json(f"https://registry.npmjs.org/{encoded}/{version}")
    if not data:
        return None
    lic = data.get("license")
    if isinstance(lic, str):
        return normalize_spdx(lic)
    if isinstance(lic, dict):
        return normalize_spdx(lic.get("type", ""))
    licenses = data.get("licenses")
    if isinstance(licenses, list) and licenses:
        first = licenses[0]
        if isinstance(first, dict):
            return normalize_spdx(first.get("type", ""))
        if isinstance(first, str):
            return normalize_spdx(first)
    if isinstance(licenses, str):
        return normalize_spdx(licenses)
    return None


def fetch_pypi_license(name: str, version: str) -> Optional[str]:
    """
    Fetch license from PyPI.

    Preference order:
      1. info.license_expression - PEP 639, already SPDX.
      2. trove classifiers       - controlled vocabulary, mapped above.
      3. info.license            - free text; only trusted if it is short
                                   enough to be an identifier, not licence text.
    """
    data = fetch_json(f"https://pypi.org/pypi/{name}/{version}/json")
    if not data:
        data = fetch_json(f"https://pypi.org/pypi/{name}/json")
    if not data:
        return None
    info = data.get("info", {})

    expr = info.get("license_expression")
    if expr:
        return normalize_spdx(expr)

    for cls in info.get("classifiers", []) or []:
        if cls in PYPI_CLASSIFIERS:
            return PYPI_CLASSIFIERS[cls]

    return normalize_spdx(info.get("license") or "")


def fetch_gem_license(name: str, version: str) -> Optional[str]:
    """Fetch license from RubyGems (version-specific, falling back to latest)."""
    data = fetch_json(f"https://rubygems.org/api/v2/rubygems/{name}/versions/{version}.json")
    if not data:
        data = fetch_json(f"https://rubygems.org/api/v1/gems/{name}.json")
    if not data:
        return None
    licenses = data.get("licenses")
    if isinstance(licenses, list) and licenses:
        return normalize_spdx(licenses[0])
    if isinstance(licenses, str):
        return normalize_spdx(licenses)
    return None
def fetch_nuget_license(name: str, version: str) -> Optional[str]:
    """Fetch license from NuGet registry."""
    id_lower = name.lower()
    ver_lower = version.lower()

    # Try the registration API (catalog entry)
    index = fetch_json(f"https://api.nuget.org/v3/registration5-gz-semver2/{id_lower}/index.json")
    if not index:
        index = fetch_json(f"https://api.nuget.org/v3/registration5/{id_lower}/index.json")

    if index:
        for page in index.get("items", []):
            items = page.get("items", [])
            if not items:
                page_data = fetch_json(page.get("@id", ""))
                if page_data:
                    items = page_data.get("items", [])
            for entry in items:
                cat = entry.get("catalogEntry", {})
                if cat.get("version", "").lower() == ver_lower:
                    expr = cat.get("licenseExpression", "")
                    if expr:
                        return normalize_spdx(expr)
                    url = cat.get("licenseUrl", "").lower()
                    if "mit" in url:
                        return "MIT"
                    if "apache" in url:
                        return "Apache-2.0"
                    if "bsd" in url:
                        return "BSD-3-Clause"

    # Fallback: download .nuspec and parse manually
    nuspec_url = (
        f"https://api.nuget.org/v3-flatcontainer/"
        f"{id_lower}/{ver_lower}/{id_lower}.nuspec"
    )
    try:
        req = urllib.request.Request(nuspec_url, headers={"User-Agent": "bom-enricher/2.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            nuspec = resp.read().decode(errors="replace")

        # Check for license expression first
        if "<license" in nuspec and 'type="expression"' in nuspec:
            start = nuspec.index(">", nuspec.index("<license")) + 1
            end = nuspec.index("</license>", start)
            return normalize_spdx(nuspec[start:end].strip())

        # Fall back to licenseUrl heuristics
        if "<licenseUrl>" in nuspec:
            start = nuspec.index("<licenseUrl>") + len("<licenseUrl>")
            end = nuspec.index("</licenseUrl>", start)
            url_text = nuspec[start:end].lower()
            if "mit" in url_text:
                return "MIT"
            if "apache" in url_text:
                return "Apache-2.0"
            if "bsd" in url_text:
                return "BSD-3-Clause"
    except Exception:
        pass

    return None


# ──────────────────────────────────────────────────────────────────────────────
# 6. Per-component enrichment
# ──────────────────────────────────────────────────────────────────────────────

FETCHERS = {
    "npm": fetch_npm_license,
    "nuget": fetch_nuget_license,
    "pypi": fetch_pypi_license,
    "gem": fetch_gem_license,
}


def enrich_component(component: dict, dry_run: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Enrich a component with license info if missing.
    Returns: (was_enriched, spdx_id_or_none)
    """
    if has_valid_license(component):
        return (False, None)

    pkg_type = get_pkg_type(component)
    name = full_name(component)
    version = component.get("version") or ""

    # Versionless entries are manifest/module-root pseudo-components, not
    # real dependencies. The workflow's jq pass should already have dropped
    # them; skip rather than trying to resolve a licence for a file path.
    if not version:
        return (False, None)

    # Known-proprietary: leave unresolved on purpose, but say why.
    reason = lookup_no_oss(pkg_type, name)
    if reason:
        print(f"  [policy] ⏭  {name}@{version} — no OSS licence by design: {reason}")
        return (False, None)

    # Curated map first (no network)
    spdx = lookup_known(pkg_type, name, version)
    if spdx:
        if not dry_run:
            component["licenses"] = make_license_entry(spdx)
        print(f"  [known] ✅ {name}@{version} → {spdx}")
        return (True, spdx)

    fetcher = FETCHERS.get(pkg_type)
    if fetcher:
        print(f"  [{pkg_type}] Fetching {name}@{version} ... ", end="", flush=True)
        spdx = fetcher(name, version)
        print(spdx or "NOT FOUND")
        time.sleep(0.15)  # Rate limiting

    if spdx:
        if not dry_run:
            component["licenses"] = make_license_entry(spdx)
        return (True, spdx)

    print(f"  ⚠️  {name}@{version} [{pkg_type}] — license unknown")
    return (False, None)


# ──────────────────────────────────────────────────────────────────────────────
# 7. Main
# ──────────────────────────────────────────────────────────────────────────────

def enrich_bom(bom_path: str, dry_run: bool = False) -> None:
    print(f"\n📄 Loading BOM: {bom_path}")
    with open(bom_path) as f:
        bom = json.load(f)

    components = bom.get("components", []) or []
    total_before = len(components)

    filtered = [c for c in components if not should_remove(c)]
    removed = total_before - len(filtered)
    if removed:
        print(f"\n🗑️  Removed {removed} config-file pseudo-component(s)")

    # Pass 1: stamp reviewed-and-accepted exceptions. This runs over ALL
    # components, not just licence-less ones — MPL-2.0 and FSL-1.1-MIT are
    # resolved perfectly well by the scanner; what they lack is the record of
    # the review decision, which is exactly what this adds.
    accepted = []
    for c in filtered:
        rec = lookup_exception(get_pkg_type(c), full_name(c))
        if rec and licence_matches(c, rec["license"]):
            if not dry_run:
                apply_exception(c, rec)
            accepted.append((full_name(c), c.get("version", ""), rec))

    if accepted:
        print(f"\n🔖 Accepted licence exceptions ({len(accepted)} component(s)):")
        seen_rec = []
        for name, version, rec in accepted:
            print(f"   - {name}@{version} — {rec['license']} [{rec['scope']}]")
            if rec not in seen_rec:
                seen_rec.append(rec)
        for rec in seen_rec:
            print(f"\n   {rec['license']} — reviewed {rec['reviewed']}")
            print(f"     why      : {' '.join(rec['reason'].split())}")
            print(f"     holds if : {' '.join(rec['condition'].split())}")

    missing = [
        c for c in filtered
        if not has_valid_license(c) and c.get("version") and not is_accepted(c)
    ]
    valid_before = len([
        c for c in filtered if has_valid_license(c) or is_accepted(c)
    ])

    print(f"\n📊 Initial state:")
    print(f"   Total components  : {len(filtered)}")
    print(f"   With valid license: {valid_before}")
    print(f"   Missing license   : {len(missing)}")

    resolved_count = 0
    unresolved = []

    if missing:
        print(f"\n🔧 Enriching {len(missing)} components...\n")
        for c in missing:
            enriched, spdx = enrich_component(c, dry_run)
            if enriched:
                resolved_count += 1
            else:
                unresolved.append(c)

    still_missing = len(unresolved)
    valid_after = valid_before + resolved_count

    print(f"\n{'─' * 50}")
    print(f"📊 Final Summary:")
    print(f"   Total components  : {len(filtered)}")
    print(f"   With valid license: {valid_after}")
    print(f"   Resolved this run : {resolved_count}")
    print(f"   Still missing     : {still_missing}")

    if unresolved:
        print(f"\n   ⚠️  Packages needing manual review:")
        for c in unresolved:
            pkg_type = get_pkg_type(c)
            name = full_name(c)
            version = c.get("version", "")
            current = get_license_display(c)
            print(f"      - [{pkg_type}] {name}@{version} (current: {current})")
        print(f"\n   💡 Read the package's LICENSE file, then add it to")
        print(f"      KNOWN_LICENSES (or NO_OSS_LICENSE) in this script.")

    if not dry_run:
        bom["components"] = filtered
        with open(bom_path, "w") as f:
            json.dump(bom, f, indent=2)
        print(f"\n✅ Patched BOM written to: {bom_path}")
    else:
        print(f"\n🔍 [DRY-RUN] No files were modified.")


def analyze_only(bom_path: str) -> None:
    """Report licence distribution without making changes."""
    print(f"\n📄 Analyzing BOM: {bom_path}")
    with open(bom_path) as f:
        bom = json.load(f)
    components = bom.get("components", []) or []

    license_counts: Dict[str, int] = {}
    missing = []
    for c in components:
        if not has_valid_license(c):
            missing.append(c)
            continue
        for lic in c.get("licenses", []):
            lid = lic.get("license", {}).get("id") or lic.get("expression", "Unknown")
            license_counts[lid] = license_counts.get(lid, 0) + 1

    print(f"\n   Total components : {len(components)}")
    print(f"   Missing licence  : {len(missing)}")
    print("\n   License distribution:")
    for lic, count in sorted(license_counts.items(), key=lambda x: -x[1]):
        print(f"     {count:5d}  {lic}")
    if missing:
        print("\n   Missing licence:")
        for c in missing:
            print(f"     - [{get_pkg_type(c)}] {full_name(c)}@{c.get('version','')}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Enrich a CycloneDX BOM with missing licences.")
    ap.add_argument("--bom", default="bom.json", help="Path to bom.json (default: bom.json)")
    ap.add_argument("--dry-run", action="store_true", help="Report what would change, write nothing")
    ap.add_argument("--analyze", action="store_true", help="Only report current licence state")
    args = ap.parse_args()

    try:
        if args.analyze:
            analyze_only(args.bom)
        else:
            enrich_bom(args.bom, dry_run=args.dry_run)
    except FileNotFoundError:
        print(f"❌ BOM not found: {args.bom}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ BOM is not valid JSON: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
