# EC2 Instance Lister

A command-line tool to list EC2 instances across multiple AWS profiles and regions.


## Features:

* Supports multiple AWS profiles
* Customizable AWS region list
* Output formats: CSV or JSON
* Dry-run mode with terminal table output
* Handles missing/malformed data gracefully
* Validates user paths and input


## Requirements:

* Python 3.7+
* AWS CLI profiles configured (~/.aws/config)
* Python packages:
  * boto3
  * tabulate

To install required packages:
pip install boto3 tabulate


## Usage:

Run the script:
./ec2_instance_lister.py [OPTIONS]


## Options:

--profile        AWS profile name (can be used multiple times)
--regions        List of AWS regions (default: us-east-1 us-east-2 us-west-2)
--output         Output file name (optional)
--outputformat   Output format: JSON or CSV (default: CSV)
--dry-run        Display results in terminal instead of writing to file
--tableformat    Table format for dry-run: plain, pipe, github, grid, fancy\_grid
--log-level      Logging level: DEBUG, INFO, WARNING, etc. (default: INFO)
--version        Show version and exit


## Examples:

List instances with default settings:
./ec2_instance_lister.py

Limit to specific profiles:
./ec2_instance_lister.py --profile dev --profile prod

Use custom regions:
./ec2_instance_lister.py --regions us-west-1 ca-central-1

Dry run with grid table output:
./ec2_instance_lister.py --dry-run --tableformat grid

Export to JSON:
./ec2_instance_lister.py --output instances.json --outputformat json


## Output Fields (CSV):

* Instance ID
* Name
* Account
* Instance Type
* Instance State
* Availability Zone
* Private IP
* Public IP
* VPC
* Subnet
* ENIs (as JSON)


## Notes:

* Valid regions are defined in the VALID_REGIONS constant.


## License:

GNU GPLv3
