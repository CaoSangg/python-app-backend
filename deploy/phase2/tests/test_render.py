import subprocess
import sys
from pathlib import Path

import pytest


RENDERER = Path(__file__).resolve().parents[1] / "render.py"
REGISTRY = "harbor.example.invalid"
DIGEST = "sha256:" + "a" * 64
IMAGE = f"{REGISTRY}/lab/song-management@{DIGEST}"
STAGES = {"00-namespace.yaml", "10-migration.yaml", "20-workload.yaml"}


def render(tmp_path, **overrides):
    output = tmp_path / "rendered"
    options = {
        "output": str(output),
        "image": IMAGE,
        "worker-label": "node-role.kubernetes.io/worker=worker",
        "release-id": "test-r1",
        "ingress-class": "traefik",
        "host": "songs.example.invalid",
        "tls-secret": "songs-tls",
        **overrides,
    }
    command = [sys.executable, str(RENDERER)]
    for flag, value in options.items():
        command.extend([f"--{flag}", value])
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
    return result, output


@pytest.mark.parametrize("port", [None, 1, 8443, 65535])
def test_accepts_harbor_fqdn_with_optional_port(tmp_path, port):
    registry = REGISTRY if port is None else f"{REGISTRY}:{port}"
    image = f"{registry}/lab/song-management@{DIGEST}"
    result, output = render(tmp_path, image=image)

    assert result.returncode == 0, result.stderr
    assert {path.name for path in output.iterdir()} == STAGES
    for filename in ("10-migration.yaml", "20-workload.yaml"):
        assert f'image: "{image}"' in (output / filename).read_text(encoding="utf-8")


@pytest.mark.parametrize("port", ["0", "65536", "99999", "100000", "nope", ""])
def test_rejects_invalid_registry_ports(tmp_path, port):
    image = f"{REGISTRY}:{port}/lab/song-management@{DIGEST}"
    result, output = render(tmp_path, image=image)

    assert result.returncode == 2
    assert "--image" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("suffix", [
    ":latest",
    "@sha256:" + "a" * 63,
    "@sha256:" + "a" * 65,
    "@sha256:" + "z" * 64,
    "@sha512:" + "a" * 64,
])
def test_rejects_missing_or_invalid_sha256_digest(tmp_path, suffix):
    result, output = render(tmp_path, image=f"{REGISTRY}/lab/song-management{suffix}")

    assert result.returncode == 2
    assert "--image" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("label", ["worker=lab-1", "node-role.kubernetes.io/worker=worker", "lab.example.invalid/Node_Role=worker.v1"])
def test_accepts_worker_labels_with_values(tmp_path, label):
    result, output = render(tmp_path, **{"worker-label": label})

    assert result.returncode == 0, result.stderr
    key, value = label.split("=", 1)
    for filename in ("10-migration.yaml", "20-workload.yaml"):
        assert f'"{key}": "{value}"' in (output / filename).read_text(encoding="utf-8")


@pytest.mark.parametrize("label", [
    "node-role.kubernetes.io/worker=",
    "worker",
    "=worker",
    "Bad.example/worker=worker",
    "worker=-lab",
    "worker=lab=extra",
    "worker=" + "a" * 64,
])
def test_rejects_invalid_worker_labels(tmp_path, label):
    result, output = render(tmp_path, **{"worker-label": label})

    assert result.returncode == 2
    assert "--worker-label" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("release_id", ["r", "a" * 50])
def test_accepts_release_id_at_length_limits(tmp_path, release_id):
    result, output = render(tmp_path, **{"release-id": release_id})

    assert result.returncode == 0, result.stderr
    assert f'name: "song-migrate-{release_id}"' in (output / "10-migration.yaml").read_text(encoding="utf-8")


@pytest.mark.parametrize("release_id", ["", "a" * 51, "R1", "release_1", "r1-"])
def test_rejects_invalid_release_ids(tmp_path, release_id):
    result, output = render(tmp_path, **{"release-id": release_id})

    assert result.returncode == 2
    assert "--release-id" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("host", ["songs.example.invalid", "songs-v2.lab.example.invalid"])
def test_accepts_ingress_fqdn(tmp_path, host):
    result, output = render(tmp_path, host=host)

    assert result.returncode == 0, result.stderr
    workload = (output / "20-workload.yaml").read_text(encoding="utf-8")
    assert f'hosts: ["{host}"]' in workload
    assert f'host: "{host}"' in workload


@pytest.mark.parametrize("host", ["songs", "songs.example.invalid:443", "https://songs.example.invalid", "songs_v2.example.invalid", "songs.example.invalid/"])
def test_rejects_invalid_ingress_hostnames(tmp_path, host):
    result, output = render(tmp_path, host=host)

    assert result.returncode == 2
    assert "--host" in result.stderr
    assert not output.exists()
