#!/usr/bin/env python3
"""List ACM certificates across AWS profiles and regions"""


import argparse
import boto3
import csv
from datetime import date, datetime
import json
import logging
import os
from pathlib import Path
import sys


def main(profiles, outfile, outputformat, dry_run):
    """List certs in given profiles and regions"""
    certs_found = {}

    if not profiles:
        profiles = boto3.session.Session().available_profiles

    for profile in profiles:
        logging.info(f"Processing profile {profile}")
        try:
            session = boto3.Session(profile_name=profile)
        except Exception as e:
            logging.error(f"Failed to create session for profile {profile}: {e}")
            continue
        sts_client = session.client('sts')

        try:
            acct_num = sts_client.get_caller_identity().get('Account')
        except Exception as e:
            logging.error(f"Failed to get account ID for profile {profile}: {e}")
            continue

        for region in ("us-east-1", "us-east-2", "us-west-2", "ca-central-1"):
            acm_client = session.client('acm', region_name=region)

            try:
                paginator = acm_client.get_paginator("list_certificates")
            except Exception as e:
                logging.error(f"Failed to get cert list for profile {profile} in {region}: {e}")
                continue
            else:
                try:
                    for page in paginator.paginate():
                        for cert in page.get("CertificateSummaryList", []):
                            try:
                                details = acm_client.describe_certificate(CertificateArn=cert["CertificateArn"])["Certificate"]
                            except Exception as e:
                                logging.error(f"Failed to describe certificate {cert['CertificateArn']} for profile {profile} in {region}: {e}" )
                                continue
                            certs_found[cert['CertificateArn']] = {'account_no': acct_num, 'region': region, 'cert': details}
                except Exception as e:
                    logging.error(f"Failed to paginate cert list for profile {profile} in {region}: {e}")

    if not certs_found:
        logging.warning("No certs found across selected profiles.")
        return

    if dry_run:
        print()
        print(json.dumps(certs_found, indent=4, default=json_serializer))
        return

    try:
        with Path(outfile).open('w', encoding='utf-8', newline='') as f:
            if outputformat == "CSV":
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                writer.writerow(["AccountId", "Region", "Certificate ARN", "Domain Name", "SANs", "Not After"])
                for cert in sorted(certs_found):
                    not_after = certs_found[cert]["cert"].get("NotAfter")
                    writer.writerow([
                        certs_found[cert]["account_no"],
                        certs_found[cert]["region"],
                        certs_found[cert]["cert"].get("CertificateArn", ""),
                        certs_found[cert]["cert"].get("DomainName", ""),
                        ";".join(certs_found[cert]["cert"].get("SubjectAlternativeNames", [])),
                        not_after.isoformat() if not_after else "",
                    ])
            else:
                f.write(json.dumps(certs_found, indent=4, default=json_serializer))
    except Exception as e:
        logging.error(f"Failed to write {outfile}: {e}")
    else:
        logging.info(f"Wrote {len(certs_found)} certs to {outfile}")


def parse_args():
    parser = argparse.ArgumentParser(description="List ACM certs across AWS profiles.")
    parser.add_argument(
        "--profile",
        action="append",
        help="Profile name for listing ACM certs.  Can use multiple times."
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)"
    )
    parser.add_argument(
        "--output",
        help="Output file name (optional). Defaults to timestamped file based on format."
    )
    parser.add_argument(
        "--outputformat",
        type=lambda s: s.upper(),
        default="CSV",
        choices=["JSON", "CSV"],
        help="File output JSON or CSV (default: CSV)."
    )
    parser.add_argument(
        "--version",
        action="version",
        version='acm-lister-2026-03-09-0')
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show output without writing to a file")

    return parser.parse_args()


def json_serializer(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def validate_output_path(path_str):
    """Validate the user-provided output path"""
    path = Path(path_str).expanduser()

    # Check if it's a directory
    if path.exists() and path.is_dir():
        logging.error(f"Output path '{path}' is a directory, not a file.")
        sys.exit(1)

    # Check if parent directory exists and is writable
    parent = path.parent
    if not parent.exists():
        logging.error(f"Directory '{parent}' does not exist.")
        sys.exit(1)
    if not os.access(parent, os.W_OK):
        logging.error(f"Directory '{parent}' is not writable.")
        sys.exit(1)

    return path


if __name__ == "__main__":
    args = parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    profiles = args.profile or []
    default_ext = "json" if args.outputformat == "JSON" else "csv"
    outfile = args.output or f"acm_cert_list_{datetime.now().strftime('%Y%m%d-%H%M%S')}.{default_ext}"
    outfile = validate_output_path(outfile)

    main(profiles, outfile, args.outputformat, args.dry_run)
