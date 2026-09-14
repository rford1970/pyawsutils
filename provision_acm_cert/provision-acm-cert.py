#!/usr/bin/python3

"""Create or delete an ACM certificate and its Route53 validation record."""

import argparse
import logging
import sys
import time

import boto3


def find_hosted_zone(route53_client, domain_name):
    """Find the most-specific public Route53 hosted zone for a domain."""
    domain_name = domain_name.rstrip(".").lower()
    matches = []

    paginator = route53_client.get_paginator("list_hosted_zones")

    for page in paginator.paginate():
        for zone in page.get("HostedZones", []):
            if zone.get("Config", {}).get("PrivateZone", False):
                continue

            zone_name = zone["Name"].rstrip(".").lower()

            if (
                domain_name == zone_name
                or domain_name.endswith("." + zone_name)
            ):
                matches.append(zone)

    if not matches:
        raise RuntimeError(
            f"No public Route53 hosted zone found for {domain_name}"
        )

    return max(
        matches,
        key=lambda zone: len(zone["Name"].rstrip("."))
    )


def get_validation_records(acm_client, certificate_arn):
    """Return DNS validation records associated with a certificate."""
    response = acm_client.describe_certificate(
        CertificateArn=certificate_arn
    )

    certificate = response["Certificate"]
    records = []

    for validation in certificate.get(
        "DomainValidationOptions", []
    ):
        record = validation.get("ResourceRecord")

        if record:
            records.append(record)

    return records


def wait_for_validation_records(
    acm_client,
    certificate_arn,
    timeout=90,
    poll_interval=2,
):
    """Wait up to timeout seconds for ACM DNS validation records."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        records = get_validation_records(
            acm_client,
            certificate_arn,
        )

        if records:
            return records

        time.sleep(poll_interval)

    raise RuntimeError(
        f"Timed out after {timeout} seconds waiting for "
        "ACM DNS validation records"
    )


def wait_for_issued_status(
    acm_client,
    certificate_arn,
    timeout=180,
    poll_interval=5,
):
    """Wait up to timeout seconds for the certificate to become ISSUED."""
    deadline = time.monotonic() + timeout
    status = "UNKNOWN"

    while time.monotonic() < deadline:
        response = acm_client.describe_certificate(
            CertificateArn=certificate_arn
        )

        status = response["Certificate"].get(
            "Status",
            "UNKNOWN",
        )

        if status == "ISSUED":
            return status

        if status in (
            "FAILED",
            "EXPIRED",
            "REVOKED",
            "VALIDATION_TIMED_OUT",
        ):
            return status

        time.sleep(poll_interval)

    return status


def find_certificate(acm_client, certname):
    """Find an ACM certificate whose primary domain matches certname."""
    paginator = acm_client.get_paginator("list_certificates")
    matches = []

    for page in paginator.paginate():
        for certificate in page.get("CertificateSummaryList", []):
            if certificate.get("DomainName") == certname:
                matches.append(certificate)

    if not matches:
        raise RuntimeError(
            f"No ACM certificate found for {certname}"
        )

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple ACM certificates found for {certname}; "
            "refusing to guess which one to delete"
        )

    return matches[0]["CertificateArn"]


def get_route53_record(route53_client, hosted_zone_id, record):
    """Get the current Route53 record set matching ACM validation."""
    response = route53_client.list_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        StartRecordName=record["Name"],
        StartRecordType=record["Type"],
        MaxItems="1",
    )

    records = response.get("ResourceRecordSets", [])

    if not records:
        return None

    current = records[0]

    if (
        current["Name"].rstrip(".").lower()
        != record["Name"].rstrip(".").lower()
        or current["Type"] != record["Type"]
    ):
        return None

    return current


def create_certificate(
    acm_client,
    route53_client,
    certname,
    exportable,
):
    """Create ACM certificate and Route53 validation records."""

    request = {
        "DomainName": certname,
        "ValidationMethod": "DNS",
        "Tags": [
            {
                "Key": "Name",
                "Value": certname,
            }
        ],
    }

    if exportable:
        request["Options"] = {
            "Export": "ENABLED"
        }

    response = acm_client.request_certificate(**request)
    certificate_arn = response["CertificateArn"]

    logging.info(
        "Certificate requested: %s",
        certificate_arn,
    )

    logging.info(
        "Waiting up to 90 seconds for ACM validation records"
    )

    validation_records = wait_for_validation_records(
        acm_client,
        certificate_arn,
        timeout=90,
    )

    for record in validation_records:
        hosted_zone = find_hosted_zone(
            route53_client,
            record["Name"],
        )

        logging.info(
            "Creating validation record %s in hosted zone %s",
            record["Name"],
            hosted_zone["Name"],
        )

        route53_client.change_resource_record_sets(
            HostedZoneId=hosted_zone["Id"],
            ChangeBatch={
                "Comment": f"ACM validation for {certname}",
                "Changes": [
                    {
                        "Action": "UPSERT",
                        "ResourceRecordSet": {
                            "Name": record["Name"],
                            "Type": record["Type"],
                            "TTL": 300,
                            "ResourceRecords": [
                                {
                                    "Value": record["Value"]
                                }
                            ],
                        },
                    }
                ],
            },
        )

    logging.info(
        "Waiting up to 180 seconds for certificate issuance"
    )

    status = wait_for_issued_status(
        acm_client,
        certificate_arn,
        timeout=180,
    )

    if status == "ISSUED":
        logging.info(
            "Certificate status: ISSUED"
        )
    else:
        logging.warning(
            "Certificate was not issued within the wait period; "
            "current status: %s",
            status,
        )

    # stdout intentionally contains only the ARN.
    print(certificate_arn)


def delete_certificate(
    acm_client,
    route53_client,
    certname,
):
    """Delete ACM certificate and its Route53 validation records."""

    certificate_arn = find_certificate(
        acm_client,
        certname,
    )

    logging.info(
        "Found certificate %s",
        certificate_arn,
    )

    validation_records = get_validation_records(
        acm_client,
        certificate_arn,
    )

    for record in validation_records:
        hosted_zone = find_hosted_zone(
            route53_client,
            record["Name"],
        )

        current_record = get_route53_record(
            route53_client,
            hosted_zone["Id"],
            record,
        )

        if not current_record:
            logging.warning(
                "Route53 validation record %s was not found",
                record["Name"],
            )
            continue

        logging.info(
            "Deleting Route53 validation record %s",
            current_record["Name"],
        )

        route53_client.change_resource_record_sets(
            HostedZoneId=hosted_zone["Id"],
            ChangeBatch={
                "Comment": f"Remove ACM validation for {certname}",
                "Changes": [
                    {
                        "Action": "DELETE",
                        "ResourceRecordSet": current_record,
                    }
                ],
            },
        )

    logging.info(
        "Deleting ACM certificate %s",
        certificate_arn,
    )

    acm_client.delete_certificate(
        CertificateArn=certificate_arn
    )

    print(certificate_arn)


def main(profile, region, certname, operation, exportable):
    """Create or delete an ACM certificate."""

    logging.info(
        "Using ACM profile %s in region %s",
        profile,
        region,
    )

    session = boto3.Session(profile_name=profile)

    acm_client = session.client(
        "acm",
        region_name=region,
    )

    # Route53 deliberately uses the default AWS credential chain.
    route53_client = boto3.client("route53")

    if operation == "create":
        create_certificate(
            acm_client,
            route53_client,
            certname,
            exportable,
        )

    elif operation == "delete":
        delete_certificate(
            acm_client,
            route53_client,
            certname,
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Create or delete an ACM certificate and its "
            "Route53 DNS validation record."
        )
    )

    operation = parser.add_mutually_exclusive_group(
        required=True
    )

    operation.add_argument(
        "--create",
        action="store_true",
        help="Create the certificate and validation record.",
    )

    operation.add_argument(
        "--delete",
        action="store_true",
        help="Delete the certificate and validation record.",
    )

    parser.add_argument(
        "-p",
        "--profile",
        required=True,
        help="AWS profile used for ACM.",
    )

    parser.add_argument(
        "-r",
        "--region",
        default="us-east-1",
        help="AWS region for ACM (default: us-east-1).",
    )

    parser.add_argument(
        "-c",
        "--certname",
        required=True,
        help="Certificate FQDN, e.g. www.example.com.",
    )

    parser.add_argument(
        "--exportable",
        action="store_true",
        help="Create the ACM certificate as exportable.",
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=[
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        ],
        help="Set logging level (default: INFO).",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="acm-cert-create-2026-09-14-0",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(levelname)s: %(message)s",
    )

    operation = "create" if args.create else "delete"

    if operation == "delete" and args.exportable:
        logging.error(
            "--exportable is only valid with --create"
        )
        sys.exit(2)

    try:
        main(
            profile=args.profile,
            region=args.region,
            certname=args.certname,
            operation=operation,
            exportable=args.exportable,
        )
    except Exception as exc:
        logging.error("%s", exc)
        sys.exit(1)
