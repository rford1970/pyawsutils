#!/usr/local/bin/python3
"""S3 object deletion by prefix"""

# WARNING: This script deletes all S3 object versions and delete markers
# for the specified buckets and prefixes. It does NOT bypass S3 Object Lock.
#
# Use DRY_RUN=True to simulate deletions safely.
#
# If this script scares you, that's good - it should.


import boto3
# import colorama
from colorama import Fore, Style
import logging


DRY_RUN = True
S3_BUCKETS = [('bucketname', 'prefix_or_blank')]

logging.basicConfig(level=logging.INFO)


def main():
    """Find objects and delete them - does not override object lock"""

    deleted = {'objects': 0, 'markers': 0}

    session = boto3.Session(profile_name='pigs')
    client = session.client('s3')

    for bucket, prefix in S3_BUCKETS:
        paginator = client.get_paginator('list_object_versions')

        operation_parameters = {'Bucket': bucket, 'Prefix': prefix}

        try:
            page_iterator = paginator.paginate(**operation_parameters)
        except Exception as e:
            logging.error(f"Well, that failed: {e}")
        else:
            try:
                for page in page_iterator:
                    for k in page.get('Versions', []):
                        if DRY_RUN:
                            logging.info(f"DRY_RUN: Would have deleted {bucket}: {k['Key']}: {k['VersionId']}")
                        else:
                            try:
                                client.delete_object(Bucket=bucket, Key=k['Key'], VersionId=k['VersionId'])
                            except Exception as e:
                                logging.error(f"Well, tried to delete {bucket}: {k['Key']}: {k['VersionId']}: {e}")
                            else:
                                deleted['objects'] += 1
                                logging.info(f"Deleted {bucket}: {k['Key']}: {k['VersionId']}")

                    for marker in page.get('DeleteMarkers', []):
                        key = marker.get('Key')
                        version_id = marker.get('VersionId')

                        if DRY_RUN:
                            logging.info(f"DRY_RUN: Would have removed delete marker {bucket}: {key}: {version_id}")
                        else:
                            try:
                                client.delete_object(Bucket=bucket, Key=key, VersionId=version_id)
                            except Exception as e:
                                logging.error(f"Error deleting delete marker {bucket}: {key}: {version_id}: {e}")
                            else:
                                deleted['markers'] += 1
                                logging.info(f"Removed marker {bucket}: {key}: {version_id}")

                    if not page.get('Versions') and not page.get('DeleteMarkers'):
                        logging.info(f"No deletable objects found in {bucket}/{prefix}")

            except Exception as e:
                logging.error(f"Well, that's busted: {e}")

    logging.info(f"\n\nDeleted {deleted['objects']} objects and removed {deleted['markers']} delete markers.\n")


def confirm_destruction_via_valkyrie():  # formerly known as ragnar_lothbrok
    if DRY_RUN:
        return True

    print("\nSend all the objects in the following buckets/prefixes to cloud Valhalla?\n")

    for bucket, prefix in S3_BUCKETS:
        print(f"    {bucket}/{prefix or ''}")

    print()

    print("\nThis is an immediate and ", end='')
    print(Style.BRIGHT + Fore.RED + "IRREVERSIBLE " + Style.RESET_ALL, end='')
    print("deletion of ALL VERSIONS!\n")

    user_input = input("Enter 'yes' to give objects a Viking funeral: ")

    if user_input == 'yes':
        print("\nOperation confirmed by user.\n")
        return True
    else:
        print("\nCancelled by user.\n")
        return False


if __name__ == "__main__":
    verified = confirm_destruction_via_valkyrie()

    if verified:
        main()
