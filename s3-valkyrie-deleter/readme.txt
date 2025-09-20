===================
S3 Valkyrie Deleter
===================

This script is a dangerous tool for deleting **all versions and delete markers** of objects in S3 buckets by prefix.

---

## !!! WARNING: This is a destructive script. Use with caution.

It does **not** bypass S3 Object Lock.

Use `DRY_RUN = True` to preview actions safely.


## Features

* Deletes **all versions** of objects in specified buckets and prefixes.
* Deletes **delete markers**.
* Uses AWS CLI profile for credentials.
* Supports **dry-run mode**.
* Confirmation prompt before actual deletion.


## Installation

  Install required packages:

   pip install -r requirements.txt


## Configuration

Edit `s3_valkyrie.py` and set:

* DRY_RUN = True (set to False only when sure)
* S3_BUCKETS = [('bucket-name', 'prefix'), ...]
* AWS profile is specified in the script (e.g. 'pigs')


## Usage

Run the script:

```
python3 s3_valkyrie.py
```

If `DRY_RUN` is `False`, you will be prompted:

```
Enter 'yes' to give objects a Viking funeral:
```

Only if you type `yes` will the deletion proceed.


## Sample Output

```
DRY_RUN: Would have deleted my-bucket: logs/log1.txt: version-id
DRY_RUN: Would have removed delete marker my-bucket: logs/log2.txt: version-id
```


## Safety Recommendations

* ALWAYS test with `DRY_RUN = True`


## License

GNU GPL 3.0


## Disclaimer

Use at your own risk. The author assumes no responsibility for data loss.

