S3 BUCKET LISTER
================

Description:
------------
This script lists all S3 buckets across one or more AWS profiles, including the bucket name, associated AWS account ID, and region (determined from bucket location).

It supports:
  - Output as CSV or JSON
  - Dry-run display in the terminal with customizable table formats
  - Optional output file path
  - Multiple profiles and region lookups
  - Logging verbosity control

This script performs **read-only** operations. It does NOT modify or delete any resources.


Usage:
------
Run the script with the desired options.

Examples:
---------
1. List buckets using all available profiles:
   $ ./s3_bucket_lister.py

2. List buckets for specific profiles and output to a CSV file:
   $ ./s3_bucket_lister.py --profile dev --profile prod --output my_buckets.csv

3. Display output in the terminal using dry-run mode (GitHub-style table):
   $ ./s3_bucket_lister.py --dry-run --tableformat github

4. Output as JSON and write to a file:
   $ ./s3_bucket_lister.py --outputformat json --output output.json


Command-Line Options:
---------------------
  --profile        AWS profile name to use. Can be used multiple times.
  --log-level      Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: INFO
  --output         Output file name. Defaults to timestamped CSV/JSON.
  --outputformat   Choose between CSV or JSON. Default: CSV
  --dry-run        Print results in terminal instead of writing to file
  --tableformat    Format for dry-run table output (plain, pipe, github, grid, fancy_grid)
  --version        Display script version


Dependencies:
-------------
  - boto3
  - tabulate
  - (Python 3.8+ recommended)

Installation:
-------------
Install dependencies using pip:
  $ pip install boto3 tabulate


Notes:
------
- You must have AWS credentials configured for the specified profiles (via `~/.aws/credentials`).
- The script determines the bucket's region using `get_bucket_location`.
- Buckets in `us-east-1` may report a null LocationConstraint, which is normalized internally.

License:
--------
GNU GPL 3.0

