# GAEA Automation Script

This Python script automates the GAEA build process. It allows you to configure and run GAEA terrain builds multiple times with variable updates per run. The script can also increment output file paths and handle variable assignments.

### Dependencies

None

### Command Line Arguments

- `terrain_filepath`: The path to the .terrain file (default: `.`).
- `output_filepath`: The path to the output file(s) (default: `.`).
- `num_runs`: The number of build runs to perform. Vars will be reevaluated per run.
- `-increment_filepath`: Flag to increment file path names. (`./001/out`, `./002/out`, etc.)
- `-var`: Variable assignments in the form `var_name=value` or `var_name=lambda: expression`.

### Example Usage

```sh
python automate.py path/to/source.terrain path/to/output 2 -var 834_Seed=10 -var 812_Seed=lambda: random.randint(1, 9999)
```

### Notes/TODO

Currently, build resolution settings must be set in GAEA for the source terrain file.