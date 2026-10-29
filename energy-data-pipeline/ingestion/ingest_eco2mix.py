"""Ingestion des données éCO2mix nationales (RTE) vers AWS S3.

Le fichier est stocké tel quel (couche "raw") et rangé par date d'ingestion :
    s3://<bucket>/raw/eco2mix/ingestion_date=AAAA-MM-JJ/eco2mix_national_tr_<horodatage>.csv

Exemples :
    # Test sans AWS : écrit le fichier dans ./data_local
    python ingestion/ingest_eco2mix.py --local-dir data_local

    # Envoi vers S3 (le bucket vient de --bucket ou de la variable S3_BUCKET)
    python ingestion/ingest_eco2mix.py --bucket mon-bucket
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# Export CSV du jeu de données "Données éCO2mix nationales temps réel" sur data.gouv.fr
# (producteur : RTE / ODRÉ, Licence Ouverte 2.0, mise à jour tous les quarts d'heure).
DEFAULT_SOURCE_URL = (
    "https://www.data.gouv.fr/api/1/datasets/r/7d2651ba-faaf-4ca6-a6f4-ac47e5ef9d33"
)
DEFAULT_PREFIX = "raw/eco2mix"

log = logging.getLogger("ingest_eco2mix")


def download(url: str, timeout: int = 120) -> bytes:
    """Télécharge le fichier source (data.gouv.fr redirige vers le producteur)."""
    log.info("Téléchargement depuis %s", url)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def validate(content: bytes) -> int:
    """Vérifie que le contenu ressemble à un CSV non vide et renvoie le nombre de lignes de données."""
    if not content.strip():
        raise ValueError("Le fichier téléchargé est vide.")
    text = content.decode("utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    header = lines[0]
    if ";" not in header and "," not in header:
        raise ValueError(f"En-tête inattendu, ce n'est pas un CSV : {header[:120]!r}")
    data_rows = len(lines) - 1
    if data_rows <= 0:
        raise ValueError("Le fichier ne contient que l'en-tête.")
    return data_rows


def build_key(prefix: str, now: datetime) -> str:
    """Construit le chemin partitionné par date d'ingestion."""
    return (
        f"{prefix.strip('/')}/ingestion_date={now:%Y-%m-%d}/"
        f"eco2mix_national_tr_{now:%Y%m%dT%H%M%SZ}.csv"
    )


def upload_to_s3(content: bytes, bucket: str, key: str) -> None:
    import boto3  # importé ici pour pouvoir tester en local sans boto3

    boto3.client("s3").put_object(
        Bucket=bucket, Key=key, Body=content, ContentType="text/csv"
    )
    log.info("Envoyé vers s3://%s/%s", bucket, key)


def save_locally(content: bytes, root: str, key: str) -> Path:
    path = Path(root) / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    log.info("Écrit en local : %s", path)
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument(
        "--from-file", help="Lire un fichier local au lieu de télécharger (utile pour les tests)."
    )
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET"))
    parser.add_argument("--prefix", default=os.getenv("S3_PREFIX", DEFAULT_PREFIX))
    parser.add_argument(
        "--local-dir", help="Écrire dans ce dossier au lieu d'envoyer vers S3."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    if not args.local_dir and not args.bucket:
        log.error("Indique --bucket (ou S3_BUCKET dans .env), ou --local-dir pour un test local.")
        return 2

    content = Path(args.from_file).read_bytes() if args.from_file else download(args.source_url)
    rows = validate(content)
    checksum = hashlib.sha256(content).hexdigest()[:12]
    log.info("%d lignes de données, %.1f Ko, sha256=%s", rows, len(content) / 1024, checksum)

    key = build_key(args.prefix, datetime.now(timezone.utc))
    if args.local_dir:
        save_locally(content, args.local_dir, key)
    else:
        upload_to_s3(content, args.bucket, key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
