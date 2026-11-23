"""Verify the Song Management HTTP contract without changing cluster resources."""

import argparse
import json
import re
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


ARTIST = "Phase 2 smoke"
SENTINEL = r"phase2-smoke-[0-9a-f]{32}"


class SmokeFailure(RuntimeError):
    pass


class RefuseRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(opener, base_url, method, path, status, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(base_url + path, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        response = opener.open(req, timeout=15)
    except HTTPError as exc:
        response = exc
    except URLError as exc:
        raise SmokeFailure(f"{method} {path} could not connect or verify TLS") from exc
    with response:
        if response.status != status:
            raise SmokeFailure(f"{method} {path}: expected {status}, received {response.status}")
        data = response.read()
    return json.loads(data) if data else None


def verify(condition, message):
    if not condition:
        raise SmokeFailure(message)


def create_sentinel(send):
    payload = {"name": f"phase2-smoke-{uuid4().hex}", "artist": ARTIST, "year": 2021}
    song = send("POST", "/songs", 201, payload)
    verify(type(song["id"]) is int and song["id"] > 0 and song == {"id": song["id"], **payload}, "POST returned an unexpected song")
    return song


def crud(send):
    song = create_sentinel(send)
    path = f"/songs/{song['id']}"
    print(f"Smoke sentinel created: ID {song['id']}, marker {song['name']}")
    verify(song in send("GET", "/songs", 200), "List did not contain the smoke record")
    verify(send("GET", path, 200) == song, "GET by ID did not return the smoke record")
    updated = {**song, "name": song["name"] + "-updated", "year": None}
    payload = {key: updated[key] for key in ("name", "artist", "year")}
    verify(send("PUT", path, 200, payload) == updated, "PUT did not return the updated smoke record")
    verify(send("GET", path, 200) == updated, "The updated record did not persist")
    verify(send("DELETE", path, 204) is None, "DELETE returned a body")
    verify(send("GET", path, 404) == {"detail": "Song not found"}, "Deleted record returned an unexpected response")
    print(f"CRUD PASS: POST 201, GET list/item 200, PUT 200, DELETE 204, then GET 404 (sentinel ID {song['id']})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("health", "crud", "seed", "check"))
    parser.add_argument("--url", required=True, help="Approved HTTPS Ingress or HTTP loopback for local tests")
    parser.add_argument("--ca-bundle", help="Append a verified client CA bundle to system trust")
    parser.add_argument("--record", type=Path, help="Read the JSON produced by seed")
    parser.add_argument("--allow-test-writes", action="store_true", help="Required for CRUD, seed or deleting the saved sentinel")
    parser.add_argument("--cleanup", action="store_true", help="Delete the saved sentinel after a successful check")
    args = parser.parse_args()
    url = urlsplit(args.url)
    loopback = url.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        not url.hostname or url.username is not None or url.password is not None
        or url.path not in {"", "/"} or url.query or url.fragment
        or (url.scheme != "https" and not (url.scheme == "http" and loopback))
    ):
        parser.error("provide an HTTPS origin, or HTTP loopback for an isolated local test")
    if args.cleanup and args.mode != "check":
        parser.error("--cleanup is only supported with check")
    if (args.mode in {"crud", "seed"} or args.cleanup) and not args.allow_test_writes:
        parser.error("test writes require --allow-test-writes and approval for the target")
    if args.mode == "check" and args.record is None:
        parser.error("check requires --record")

    base_url = args.url.rstrip("/")
    try:
        context = ssl.create_default_context()
        if args.ca_bundle:
            context.load_verify_locations(cafile=args.ca_bundle)
        opener = build_opener(HTTPSHandler(context=context), RefuseRedirect())

        def send(method, path, status, payload=None):
            return request(opener, base_url, method, path, status, payload)

        if args.mode == "health":
            for probe in ("live", "ready"):
                verify(send("GET", f"/health/{probe}", 200) == {"status": "ok"}, f"Unexpected {probe} response")
            print("Health PASS: /health/live 200, /health/ready 200")
        elif args.mode == "crud":
            crud(send)
        elif args.mode == "seed":
            print(json.dumps({"origin": base_url, "song": create_sentinel(send)}))
        else:
            record = json.loads(args.record.read_text(encoding="utf-8-sig"))
            song = record["song"]
            verify(
                record["origin"] == base_url and type(song["id"]) is int and song["id"] > 0
                and song["artist"] == ARTIST and re.fullmatch(SENTINEL, song["name"]) and song["year"] == 2021,
                "Record must be a seed from the same origin with a valid smoke marker",
            )
            path = f"/songs/{song['id']}"
            verify(send("GET", path, 200) == song, "Saved record did not persist")
            print(f"Persistence record PASS: sentinel ID {song['id']} is unchanged")
            if args.cleanup:
                send("DELETE", path, 204)
                verify(send("GET", path, 404) == {"detail": "Song not found"}, "Sentinel cleanup was not confirmed")
                print("Sentinel cleanup PASS: DELETE 204 and GET 404")
    except SmokeFailure as exc:
        parser.exit(1, f"Smoke failed: {exc}\n")
    except (OSError, ValueError, TypeError, KeyError):
        parser.exit(1, "Smoke failed: invalid response, record file, connection or CA bundle\n")


if __name__ == "__main__":
    main()
