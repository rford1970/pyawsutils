#!/usr/bin/env python3
"""List S3 buckets in profiles"""


import argparse
import boto3
import csv
import logging
import os
from pathlib import Path
import sys


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


def parse_args():
    parser = argparse.ArgumentParser(description="List Lambda function runtimes across AWS profiles.")
    parser.add_argument(
        "--profile",
        action="append",
        help="Profile name for listing Lambda runtimes.  Can use multiple times."
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)"
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output file name (optional)."
    )
    parser.add_argument(
        "--version",
        action="version",
        version='lambda-runtime-lister-2025-11-10-0')

    return parser.parse_args()


def main(profiles, outfile):
    functions = []

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

        try:
            acct_num = sts_client.get_caller_identity().get('Account')
        except Exception as e:
            logging.error(f"Failed to get account ID for profile {profile}: {e}")
            continue

        for region in ("us-east-1", "us-east-2", "us-west-2"):
            lambda_client = session.client('lambda', region_name=region)

            paginator = lambda_client.get_paginator('list_functions')

            for page in paginator.paginate():
                for function in page['Functions']:
                    try:
                        functions.append([acct_num, function['FunctionName'], function['Runtime'], region])
                    except Exception:
                        pass

    if outfile == '':
        print(f"{'Account':<13} {'Function Name':<42} {'Runtime':<15}")
        print("-" * 70)

        for f in functions:
            print(f"{f[0]:<13} {f[1]:<42} {f[2]:<15}")
    else:
        try:
            with Path(outfile).open('w') as f:
                writer = csv.writer(f)
                writer.writerow(["Account", "Function Name", "Runtime", "Region"])
                writer.writerows(functions)
        except Exception:
            logging.error(f"Failed to write {outfile}")
        else:
            logging.info(f"Wrote {len(functions)} functions to {outfile}")


if __name__ == "__main__":
    args = parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    profiles = args.profile or []
    if args.output != '':
        outfile = validate_output_path(args.output)
    else:
        outfile = ""

    main(profiles, outfile)
