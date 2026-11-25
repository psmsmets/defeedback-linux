"""Identify the integration independently of REAPER, Wine, and the plugin."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_version(root=ROOT):
    try:
        return (root / 'VERSION').read_text().strip() or 'unknown'
    except OSError:
        return 'unknown'


def describe_version(root=ROOT):
    text = 'defeedback-linux ' + read_version(root)
    try:
        metadata = json.loads((root / 'installation.json').read_text())
        revision = metadata.get('revision') if isinstance(metadata, dict) else None
    except (OSError, ValueError):
        revision = None
    if isinstance(revision, str) and revision:
        text += ' (revision ' + revision[:12] + ')'
    return text
