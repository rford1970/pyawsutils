#!/usr/bin/env python3
"""List S3 buckets in profiles"""


import argparse
import boto3
import csv
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import sys
from tabulate import tabulate
import textwrap


def main(profiles, outfile, outputformat, dry_run, tformat):
    """List buckets in profiles"""
    buckets_found = {}

    if not profiles:
        profiles = boto3.session.Session().available_profiles

    for profile in profiles:
        logging.info(f"Processing profile {profile}")
        try:
            session = boto3.Session(profile_name=profile)
        except Exception:
            logging.error(f"Failed to create session for profile {profile}")
            continue
        sts_client = session.client('sts')
        s3_client = session.client('s3')

        try:
            acct_num = sts_client.get_caller_identity().get('Account')
        except Exception as e:
            logging.error(f"Failed to get account ID for profile {profile}: {e}")
            continue

        try:
            response = s3_client.list_buckets()
        except Exception as e:
            logging.error(e)
        else:
            for bucket in response['Buckets']:
                try:
                    loc_response = s3_client.get_bucket_location(Bucket=bucket['Name'])
                    location = loc_response.get('LocationConstraint')
                except Exception:
                    location = ""
                else:
                    if not location:
                        location = 'us-east-1'
                buckets_found[bucket['Name']] = {
                    "account_id": acct_num,
                    "region": location
                }

    if not buckets_found:
        logging.warning("No buckets found across selected profiles.")
        return

    if dry_run:
        if outputformat == "JSON":
            print()
            print(json.dumps(buckets_found, indent=4))
        else:
            print()
            term_width = shutil.get_terminal_size(fallback=(80, 24)).columns
            headers, data = format_table_data(buckets_found, term_width, wrap=True)
            print(tabulate(data, headers=headers, tablefmt=tformat))
            return

    try:
        with Path(outfile).open('w') as f:
            if outputformat == "CSV":
                writer = csv.writer(f)
                writer.writerow(["BucketName", "AccountId", "Region"])
                for bucket in sorted(buckets_found):
                    writer.writerow([
                        bucket,
                        buckets_found[bucket]["account_id"],
                        buckets_found[bucket]["region"]
                    ])
            else:
                f.write(json.dumps(buckets_found, indent=4))
    except Exception:
        logging.error(f"Failed to write {outfile}")
    else:
        logging.info(f"Wrote {len(buckets_found)} buckets to {outfile}")


def parse_args():
    parser = argparse.ArgumentParser(description="List S3 buckets across AWS profiles.")
    parser.add_argument(
        "--profile",
        action="append",
        help="Profile name for listing S3 buckets.  Can use multiple times."
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
        version='s3-bucket-lister-2025-09-06-0')
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show output without writing to a file")
    parser.add_argument(
        "--tableformat",
        default="plain",
        choices=["plain", "pipe", "github", "grid", "fancy_grid"],
        help="Choose dry run output format (default: plain)")

    return parser.parse_args()


def format_table_data(buckets_found, max_width, wrap=False):
    headers = ["Bucket Name", "Account ID", "Region"]
    data = []

    # Rough estimate of max width per column
    max_bucket = int(max_width * 0.5)
    max_account = int(max_width * 0.3)
    max_region = int(max_width * 0.2)

    for name, info in sorted(buckets_found.items()):
        bn = name
        acct = info["account_id"]
        region = info["region"]

        if not wrap:
            # Truncate values that are too long
            if len(bn) > max_bucket:
                bn = bn[:max_bucket - 3] + "..."
            if len(acct) > max_account:
                acct = acct[:max_account - 3] + "..."
            if len(region) > max_region:
                region = region[:max_region - 3] + "..."
        else:
            # Wrap long fields
            bn = "\n".join(textwrap.wrap(bn, width=max_bucket))
            acct = "\n".join(textwrap.wrap(acct, width=max_account))
            region = "\n".join(textwrap.wrap(region, width=max_region))

        data.append([bn, acct, region])

    return headers, data


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
    outfile = args.output or f"bucket_list_{datetime.now().strftime('%Y%m%d-%H%M%S')}.{default_ext}"
    outfile = validate_output_path(outfile)

    main(profiles, outfile, args.outputformat, args.dry_run, args.tableformat)
