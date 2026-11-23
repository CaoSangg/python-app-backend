"""Render the three Phase 2 rollout stages from reviewed, non-secret inputs."""

import argparse
import re
from pathlib import Path
from string import Template


DNS_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
DNS_NAME = rf"{DNS_LABEL}(?:\.{DNS_LABEL})*"
LABEL_PART = r"[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,61}[A-Za-z0-9])?"
REPO_PART = r"[a-z0-9]+(?:[._-][a-z0-9]+)*"
IMAGE = rf"{DNS_LABEL}(?:\.{DNS_LABEL})+(?::(?P<port>[1-9][0-9]{{0,4}}))?/{REPO_PART}(?:/{REPO_PART})+@sha256:[0-9a-f]{{64}}"
TEMPLATES = Path(__file__).with_name("templates")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory for the three rendered YAML files")
    parser.add_argument("--namespace", default="song-management")
    parser.add_argument("--release-id", required=True, help="Unique DNS label for this migration attempt (max 50 characters)")
    parser.add_argument("--image", required=True, help="Harbor FQDN[:port]/project/repository@sha256:digest (port 1–65535)")
    parser.add_argument("--worker-label", required=True, help="Verified Worker node label in key=value form with a non-empty value")
    parser.add_argument("--ingress-class", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--tls-secret", required=True)
    args = parser.parse_args()

    checks = (
        ("namespace", args.namespace, DNS_LABEL, 63),
        ("release-id", args.release_id, DNS_LABEL, 50),
        ("ingress-class", args.ingress_class, DNS_NAME, 253),
        ("host", args.host, rf"{DNS_LABEL}(?:\.{DNS_LABEL})+", 253),
        ("tls-secret", args.tls_secret, DNS_NAME, 253),
    )
    for flag, value, pattern, limit in checks:
        if len(value) > limit or not re.fullmatch(pattern, value):
            parser.error(f"invalid --{flag}")

    image_match = re.fullmatch(IMAGE, args.image)
    if len(args.image) > 512 or image_match is None:
        parser.error("invalid --image")
    port = image_match["port"]
    if port is not None and not 1 <= int(port) <= 65535:
        parser.error("registry port in --image must be between 1 and 65535")

    key, separator, value = args.worker_label.partition("=")
    if (
        not separator
        or not re.fullmatch(rf"(?:{DNS_NAME}/)?{LABEL_PART}", key)
        or ("/" in key and len(key.split("/")[0]) > 253)
        or not re.fullmatch(LABEL_PART, value)
    ):
        parser.error("--worker-label must be a Kubernetes label in key=value form with a non-empty value")

    values = {
        "namespace": args.namespace,
        "job": f"song-migrate-{args.release_id}",
        "image": args.image,
        "worker_key": key,
        "worker_value": value,
        "ingress_class": args.ingress_class,
        "host": args.host,
        "tls_secret": args.tls_secret,
    }
    files = {
        template.stem: Template(template.read_text(encoding="utf-8")).substitute(values)
        for template in sorted(TEMPLATES.glob("*.yaml.tmpl"))
    }
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        parser.error(f"cannot create output directory ({exc.strerror})")
    for filename, content in files.items():
        (args.output / filename).write_text(content, encoding="utf-8")
    print(f"Rendered {len(files)} stages. Migration Job: {values['job']}")


if __name__ == "__main__":
    main()
