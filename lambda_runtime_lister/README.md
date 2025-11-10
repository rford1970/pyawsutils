LAMBDA RUNTIME LISTER
=====================

Description:
------------
This script lists all Lambda functions across one or more AWS profiles and the configured runtime.

It supports:
  - Multiple profiles and region lookups
  - Logging verbosity control

This script performs **read-only** operations. It does NOT modify or delete any resources.


Use:
------
Run the script with the desired options.

Examples:
---------
1. List functions using all available profiles:
   $ ./lambda_runtime_lister.py

2. List functions for specific profiles and output to a CSV file:
   $ ./lambda_runtime_lister.py --profile dev --profile prod --output my_buckets.csv

3. Display output in the terminal:
   $ ./lambda_runtime_lister.py --profile dev --profile prod


Command-Line Options:
---------------------
  --profile        AWS profile name to use. Can be used multiple times.
  --log-level      Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL).  Default: INFO
  --output         Output file name.
  --version        Display script version.


Dependencies:
-------------
  - boto3
  - (Python 3.8+ recommended)


Notes:
------
- You must have AWS credentials configured for the specified profiles (via `~/.aws/credentials`).


License:
--------
GNU GPL 3.0

