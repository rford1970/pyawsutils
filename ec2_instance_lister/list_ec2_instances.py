#!/usr/bin/env python3
"""List EC2 instances in us-east-1, us-east-2, and us-west-2"""


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


VALID_REGIONS = {"us-east-1", "us-east-2", "us-west-1", "us-west-2",
                 "ca-central-1", "eu-west-1", "eu-west-2", "eu-central-1"}


def main(profiles, outfile, outputformat, dry_run, tformat, regions):
    """List instances in profiles"""
    instances_found = {}

    logging.info(f"Checking regions {regions}")

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

        for region in regions:
            try:
                ec2_client = session.client('ec2', region_name=region)
            except Exception as e:
                logging.error(f"Cannot query EC2 instances in {region}: {e}")
                continue

            try:
                acct_num = sts_client.get_caller_identity().get('Account')
            except Exception as e:
                logging.error(f"Failed to get account ID for profile {profile}: {e}")
                continue

            try:
                paginator = ec2_client.get_paginator("describe_instances")
            except Exception as e:
                logging.exception(e)
            else:
                for page in paginator.paginate():
                    for reservation in page["Reservations"]:
                        for inst in reservation['Instances']:
                            instance_name = 'N/A'
                            if 'Tags' in inst:
                                for tag in inst['Tags']:
                                    if tag['Key'] == 'Name':
                                        instance_name = tag['Value']
                                        break

                            enis = {}
                            for eni in inst['NetworkInterfaces']:
                                enis[eni['NetworkInterfaceId']] = {
                                    'PrivateIpAddress': eni['PrivateIpAddress'],
                                    'Ipv6Addresses': eni['Ipv6Addresses'],
                                    'VpcId': eni['VpcId'],
                                    'SubnetId': eni['SubnetId']
                                }

                            key = f"{inst['InstanceId']}_{acct_num}_{region}"
                            instances_found[key] = {
                                'instance_id': inst['InstanceId'],
                                'instance_name': instance_name,
                                'account': acct_num,
                                'type': inst['InstanceType'],
                                'state': inst['State']['Name'],
                                'az': inst.get('Placement', {}).get('AvailabilityZone', 'N/A'),
                                'privateipv4': inst.get('PrivateIpAddress', 'N/A'),
                                'publicipv4': inst.get('PublicIpAddress'),
                                'vpc': inst.get('VpcId', 'N/A'),
                                'subnet': inst.get('SubnetId', 'N/A'),
                                'enis': enis
                            }

    if not instances_found:
        logging.warning("No instances found across selected profiles.")
        return

    if dry_run:
        if outputformat == "JSON":
            print()
            print(json.dumps(instances_found, indent=4))
        else:
            print()
            term_width = shutil.get_terminal_size(fallback=(80, 24)).columns
            headers, data = format_table_data(instances_found, term_width, wrap=True)
            print(tabulate(data, headers=headers, tablefmt=tformat))
            return

    try:
        with Path(outfile).open('w', encoding='utf-8') as f:
            if outputformat == "CSV":
                writer = csv.writer(f)
                writer.writerow(["InstanceID", "Name", "Account", "Type", "State", "AZ", "PrivateIP", "PublicIP", "VPC", "Subnet", "ENIs"])
                for instance in sorted(instances_found.values(), key=lambda x: (x["account"], x["az"], x["instance_id"])):
                    writer.writerow([
                        instance["instance_id"],
                        instance["instance_name"],
                        instance["account"],
                        instance["type"],
                        instance["state"],
                        instance["az"],
                        instance["privateipv4"],
                        instance["publicipv4"],
                        instance["vpc"],
                        instance["subnet"],
                        json.dumps(instance["enis"], separators=(",", ":"), default=str)
                    ])
            else:
                f.write(json.dumps(instances_found, indent=4))
    except Exception:
        logging.error(f"Failed to write {outfile}")
    else:
        logging.info(f"Wrote {len(instances_found)} instances to {outfile}")


def parse_args():
    parser = argparse.ArgumentParser(description="List EC2 instances across AWS profiles.")
    parser.add_argument(
        "--profile",
        action="append",
        help="Profile name for listing EC2 instances.  Can use multiple times."
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
        help="File output JSON or CSV (default: CSV). NOTE: dry-run uses tableformat)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version='ec2-instance-lister-2025-09-20-0')
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show output without writing to a file")
    parser.add_argument(
        "--tableformat",
        default="github",
        choices=["plain", "pipe", "github", "grid", "fancy_grid"],
        help="Choose dry run output format (default: plain)")
    parser.add_argument(
        "--regions",
        nargs="+",
        default=["us-east-1", "us-east-2", "us-west-2"],
        help="AWS regions to query (default: us-east-1 us-east-2 us-west-2)"
    )

    return parser.parse_args()


def format_table_data(instances_found, max_width, wrap=False):
    headers = ["Name", "Instance ID", "Account", "AZ"]
    data = []

    # Rough estimate of max width per column
    max_name = int(max_width * 0.5)
    max_ident = int(max_width * 0.5)
    max_account = int(max_width * 0.3)
    max_region = int(max_width * 0.2)

    for _, info in sorted(instances_found.items()):
        name = info["instance_name"]
        ident = info["instance_id"]
        acct = info["account"]
        az = info["az"]

        if not wrap:
            # Truncate values that are too long
            if len(name) > max_name:
                name = name[:max_name - 3] + "..."
            if len(ident) > max_ident:
                ident = ident[:max_ident - 3] + "..."
            if len(acct) > max_account:
                acct = acct[:max_account - 3] + "..."
            if len(az) > max_region:
                az = az[:max_region - 3] + "..."
        else:
            # Wrap long fields
            name = "\n".join(textwrap.wrap(name, width=max_name))
            ident = "\n".join(textwrap.wrap(ident, width=max_ident))
            acct = "\n".join(textwrap.wrap(acct, width=max_account))
            az = "\n".join(textwrap.wrap(az, width=max_region))

        data.append([name, ident, acct, az])

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

    invalid_regions = [r for r in args.regions if r not in VALID_REGIONS]
    if invalid_regions:
        logging.error(f"Invalid region(s) specified: {', '.join(invalid_regions)}")
        sys.exit(1)

    profiles = args.profile or []
    default_ext = "json" if args.outputformat == "JSON" else "csv"
    outfile = args.output or f"ec2_instances_{datetime.now().strftime('%Y%m%d-%H%M%S')}.{default_ext}"
    outfile = validate_output_path(outfile)

    main(profiles, outfile, args.outputformat, args.dry_run, args.tableformat, args.regions)
