#!/usr/bin/env python3
"""Disable SSM sharing documents publicly in select regions"""


import argparse
import boto3
import logging
import sys


VALID_REGIONS = {"us-east-1", "us-east-2", "us-west-1", "us-west-2",
                 "ca-central-1", "eu-west-1", "eu-west-2", "eu-central-1"}


def main(profiles, regions):
    """Disable public sharing of SSM documents"""

    logging.info(f"Setting regions {regions}")

    if not profiles:
        profiles = boto3.session.Session().available_profiles

    for profile in profiles:
        logging.info(f"Processing profile {profile}")
        try:
            session = boto3.Session(profile_name=profile)
        except Exception as e:
            logging.error(f"Failed to create session for profile {profile}: {e}")
            continue

        for region in regions:
            try:
                ssm_client = session.client('ssm', region_name=region)
            except Exception as e:
                logging.error(f"Cannot set session in {region}: {e}")
                continue

            try:
                ssm_client.update_service_setting(
                    SettingId='/ssm/documents/console/public-sharing-permission',
                    SettingValue='Disable'
                )
            except Exception as e:
                logging.error(f"Cannot set permission in {region}: {e}")
                continue
            else:
                logging.info(f"Set permission to disabled in {region}")


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
        "--version",
        action="version",
        version='ssm-disable-pubdoc-2025-11-17-0')
    parser.add_argument(
        "--regions",
        nargs="+",
        default=["us-east-1", "us-east-2", "us-west-2"],
        help="AWS regions to query (default: us-east-1 us-east-2 us-west-2)"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    invalid_regions = [r for r in args.regions if r not in VALID_REGIONS]
    if invalid_regions:
        logging.error(f"Invalid region(s) specified: {', '.join(invalid_regions)}")
        sys.exit(1)

    profiles = args.profile or []

    main(profiles, args.regions)
