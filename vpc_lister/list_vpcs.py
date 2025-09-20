#!/usr/bin/env python3
"""List VPCs across AWS profiles and regions"""


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
    """List VPCs in given profiles and regions"""
    vpcs_found = {}

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

        for region in ("us-east-1", "us-east-2", "us-west-2", "ca-central-1"):
            vpc_client = session.client('ec2', region_name=region)

            try:
                acct_num = sts_client.get_caller_identity().get('Account')
            except Exception as e:
                logging.error(f"Failed to get account ID for profile {profile}: {e}")
                continue

            try:
                response = vpc_client.describe_vpcs()
            except Exception as e:
                logging.error(f"Failed to describe VPCs in region {region} for profile {profile}: {e}")
            else:
                for vpc in response['Vpcs']:
                    vpcs_found[vpc['VpcId']] = {
                        "account_id": acct_num,
                        "region": region,
                        "cidr": vpc['CidrBlock'],
                        "cidr6": "",
                        "cidrassociations": {}
                    }
                    if 'Ipv6CidrBlockAssociationSet' in vpc.keys():
                        # vpcs_found[vpc['VpcId']] |= {"cidr6": vpc['Ipv6CidrBlockAssociationSet'][0]['Ipv6CidrBlock']}
                        ipv6_set = vpc.get('Ipv6CidrBlockAssociationSet')
                        if ipv6_set and len(ipv6_set) > 0:
                            vpcs_found[vpc['VpcId']]["cidr6"] = ipv6_set[0].get('Ipv6CidrBlock')

                    tempcidr = {}
                    for foo in vpc['CidrBlockAssociationSet']:
                        tempcidr |= {foo['AssociationId']: foo['CidrBlock']}
                        vpcs_found[vpc['VpcId']]['cidrassociations'] |= tempcidr

    if not vpcs_found:
        logging.warning("No VPCs found across selected profiles.")
        return

    if dry_run:
        if outputformat == "JSON":
            print()
            print(json.dumps(vpcs_found, indent=4))
        else:
            print()
            term_width = shutil.get_terminal_size(fallback=(80, 24)).columns
            headers, data = format_table_data(vpcs_found, term_width, wrap=True)
            print(tabulate(data, headers=headers, tablefmt=tformat))
            return

    try:
        with Path(outfile).open('w') as f:
            if outputformat == "CSV":
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                writer.writerow(["VpcId", "AccountId", "Region", "CIDR", "CIDR6"])
                for vpc in sorted(vpcs_found):
                    writer.writerow([
                        vpc,
                        vpcs_found[vpc]["account_id"],
                        vpcs_found[vpc]["region"],
                        vpcs_found[vpc]["cidr"],
                        vpcs_found[vpc]["cidr6"]
                    ])
            else:
                f.write(json.dumps(vpcs_found, indent=4))
    except Exception:
        logging.error(f"Failed to write {outfile}")
    else:
        logging.info(f"Wrote {len(vpcs_found)} VPCs to {outfile}")


def parse_args():
    parser = argparse.ArgumentParser(description="List VPCs across AWS profiles.")
    parser.add_argument(
        "--profile",
        action="append",
        help="Profile name for listing VPCs.  Can use multiple times."
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
        version='vpc-lister-2025-09-09-0')
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


def format_table_data(vpcs_found, max_width, wrap=False):
    headers = ["VPC ID", "Account ID", "Region", "CIDR"]
    data = []

    # Rough estimate of max width per column
    max_bucket = int(max_width * 0.5)
    max_account = int(max_width * 0.3)
    max_region = int(max_width * 0.2)
    max_cidr = int(max_width * 0.2)

    for name, info in sorted(vpcs_found.items()):
        bn = name
        acct = info["account_id"]
        region = info["region"]
        cidr = info["cidr"]

        if not wrap:
            # Truncate values that are too long
            if len(bn) > max_bucket:
                bn = bn[:max_bucket - 3] + "..."
            if len(acct) > max_account:
                acct = acct[:max_account - 3] + "..."
            if len(region) > max_region:
                region = region[:max_region - 3] + "..."
            if len(cidr) > max_cidr:
                cidr = cidr[:max_cidr - 3] + "..."
        else:
            # Wrap long fields
            bn = "\n".join(textwrap.wrap(bn, width=max_bucket))
            acct = "\n".join(textwrap.wrap(acct, width=max_account))
            region = "\n".join(textwrap.wrap(region, width=max_region))
            cidr = "\n".join(textwrap.wrap(cidr, width=max_cidr))

        data.append([bn, acct, region, cidr])

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
    outfile = args.output or f"vpc_list_{datetime.now().strftime('%Y%m%d-%H%M%S')}.{default_ext}"
    outfile = validate_output_path(outfile)

    main(profiles, outfile, args.outputformat, args.dry_run, args.tableformat)
